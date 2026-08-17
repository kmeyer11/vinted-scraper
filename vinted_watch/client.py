"""Thin client around vinted_scraper's VintedWrapper for searching, plus
best-effort favourite/unfavourite/list-favourites calls (none of this is
exposed by vinted_scraper itself - it relies on undocumented Vinted
endpoints, reverse-engineered from a real browser session - see
.env.example)."""
from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass
from http.cookies import SimpleCookie
from typing import Any, Dict, List, Optional

import httpx
from vinted_scraper import VintedWrapper

log = logging.getLogger(__name__)

TOGGLE_FAVOURITE_ENDPOINT = "/api/v2/user_favourites/toggle"
FAVOURITES_LIST_ENDPOINT = "/api/v2/users/{user_id}/items/favourites"

# Vinted domain -> Locale header value. Falls back to en-US for unknown domains.
_LOCALE_BY_TLD = {
    "vinted.dk": "da-DK",
    "vinted.com": "en-US",
    "vinted.co.uk": "en-GB",
    "vinted.de": "de-DE",
    "vinted.fr": "fr-FR",
    "vinted.nl": "nl-NL",
    "vinted.se": "sv-SE",
    "vinted.pl": "pl-PL",
}


def _locale_for_domain(domain: str) -> str:
    host = domain.split("://", 1)[-1].removeprefix("www.").rstrip("/")
    return _LOCALE_BY_TLD.get(host, "en-US")


def _cookie_value(cookie_header: str, name: str) -> Optional[str]:
    cookie = SimpleCookie()
    cookie.load(cookie_header)
    morsel = cookie.get(name)
    return morsel.value if morsel else None


_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Safari/605.1.15"
)


def _user_id_from_cookie(cookie_header: str) -> Optional[str]:
    """Read the account id out of the access_token_web JWT (no signature
    verification - we're only reading a claim we already trust, since it's
    our own cookie)."""
    token = _cookie_value(cookie_header, "access_token_web")
    if not token or token.count(".") != 2:
        return None
    payload_b64 = token.split(".")[1]
    payload_b64 += "=" * (-len(payload_b64) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
    except Exception:  # noqa: BLE001 - malformed/unexpected token shape
        return None
    return payload.get("sub")


@dataclass
class VintedItem:
    id: str
    title: str
    price_amount: str
    price_currency: str
    brand: str
    status: str
    url: str
    photo_url: Optional[str]

    @classmethod
    def from_json(cls, raw: Dict[str, Any]) -> "VintedItem":
        price = raw.get("price") or {}
        photo = raw.get("photo") or {}
        return cls(
            id=str(raw["id"]),
            title=(raw.get("title") or "").strip(),
            price_amount=str(price.get("amount", "")),
            price_currency=str(price.get("currency_code", "")),
            brand=raw.get("brand_title", "") or "",
            status=raw.get("status", "") or "",
            url=raw.get("url", "") or "",
            photo_url=photo.get("url"),
        )


class VintedClient:
    """Wraps VintedWrapper for search, and adds best-effort favourite management."""

    def __init__(
        self,
        domain: str,
        auth_cookie: Optional[str] = None,
        csrf_token: Optional[str] = None,
    ):
        self.domain = domain.rstrip("/")
        self.auth_cookie = auth_cookie
        self.csrf_token = csrf_token
        self.anon_id = _cookie_value(auth_cookie, "anon_id") if auth_cookie else None
        self.user_id = _user_id_from_cookie(auth_cookie) if auth_cookie else None
        self._wrapper: Optional[VintedWrapper] = None

    @property
    def _search_wrapper(self) -> VintedWrapper:
        # Lazy: only fetches an anonymous session cookie if search() is
        # actually used, so favourite-only usage doesn't depend on it.
        if self._wrapper is None:
            self._wrapper = VintedWrapper(self.domain)
        return self._wrapper

    def search(self, params: Dict[str, Any]) -> List[VintedItem]:
        data = self._search_wrapper.search(params)
        return [VintedItem.from_json(raw) for raw in data.get("items", [])]

    def _auth_headers(self) -> Dict[str, str]:
        headers = {
            "Cookie": self.auth_cookie,
            "User-Agent": _DEFAULT_USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Origin": self.domain,
            "Referer": f"{self.domain}/",
            "Locale": _locale_for_domain(self.domain),
        }
        if self.csrf_token:
            headers["X-CSRF-Token"] = self.csrf_token
        if self.anon_id:
            headers["X-Anon-Id"] = self.anon_id
        return headers

    def _toggle_favourite(self, item_id: str) -> bool:
        """Best-effort: toggle an item's favourite state using the user's own
        logged-in cookie + CSRF token (see .env.example). Vinted has no
        documented public API for this, so this can break if they change
        something. Never raises - callers should treat this as optional and
        keep going on failure.
        """
        if not self.auth_cookie or not self.csrf_token:
            log.warning(
                "VINTED_COOKIE and/or VINTED_CSRF_TOKEN not configured, "
                "skipping favourite toggle for item %s",
                item_id,
            )
            return False

        url = f"{self.domain}{TOGGLE_FAVOURITE_ENDPOINT}"
        headers = {**self._auth_headers(), "Content-Type": "application/json"}

        try:
            resp = httpx.post(
                url,
                headers=headers,
                json={"type": "item", "user_favourites": [int(item_id)]},
                timeout=15,
            )
        except httpx.HTTPError as exc:
            log.error("Favourite toggle failed for item %s: %s", item_id, exc)
            return False

        if resp.status_code in (200, 201):
            return True

        log.error(
            "Could not toggle favourite for item %s (HTTP %s): %s",
            item_id,
            resp.status_code,
            resp.text[:300],
        )
        return False

    def favourite(self, item_id: str) -> bool:
        return self._toggle_favourite(item_id)

    def unfavourite(self, item_id: str) -> bool:
        return self._toggle_favourite(item_id)

    def list_favourites(self) -> List[VintedItem]:
        """Fetch every item currently in the user's Vinted favourites
        (paginated). Requires VINTED_COOKIE with a valid access_token_web."""
        if not self.auth_cookie or not self.user_id:
            raise RuntimeError(
                "VINTED_COOKIE (containing a valid access_token_web) is required "
                "to list favourites."
            )

        endpoint = FAVOURITES_LIST_ENDPOINT.format(user_id=self.user_id)
        url = f"{self.domain}{endpoint}"
        headers = self._auth_headers()

        # De-duplicated by id: pages can shift while paginating (e.g. many
        # items favourited within the same second sort unstably), which can
        # otherwise return the same item on two pages.
        items_by_id: Dict[str, VintedItem] = {}
        page = 1
        while True:
            resp = httpx.get(url, headers=headers, params={"page": page}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            for raw in data.get("items", []):
                item = VintedItem.from_json(raw)
                items_by_id[item.id] = item

            pagination = data.get("pagination") or {}
            total_pages = pagination.get("total_pages", page)
            if page >= total_pages:
                break
            page += 1

        return list(items_by_id.values())
