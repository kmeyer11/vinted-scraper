"""Thin client around vinted_scraper's VintedWrapper for searching, plus a
best-effort favourite() call (favouriting is not exposed by vinted_scraper
itself and relies on an undocumented Vinted endpoint)."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx
from vinted_scraper import VintedWrapper

log = logging.getLogger(__name__)

FAVOURITE_ENDPOINT = "/api/v2/items/{item_id}/favourite"


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
    """Wraps VintedWrapper for search, and adds a best-effort favourite() call."""

    def __init__(self, domain: str, auth_cookie: Optional[str] = None):
        self.domain = domain.rstrip("/")
        self.auth_cookie = auth_cookie
        self._wrapper = VintedWrapper(self.domain)

    def search(self, params: Dict[str, Any]) -> List[VintedItem]:
        data = self._wrapper.search(params)
        return [VintedItem.from_json(raw) for raw in data.get("items", [])]

    def favourite(self, item_id: str) -> bool:
        """Best-effort: add an item to favourites using the user's own logged-in
        cookie (see .env.example). Vinted has no documented public API for this,
        so this can break if they change something. Never raises - callers
        should treat favouriting as optional and keep going on failure.
        """
        if not self.auth_cookie:
            log.warning("No VINTED_COOKIE configured, skipping favourite for item %s", item_id)
            return False

        url = f"{self.domain}{FAVOURITE_ENDPOINT.format(item_id=item_id)}"
        headers = {
            "Cookie": self.auth_cookie,
            "User-Agent": self._wrapper.user_agent,
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest",
        }
        try:
            resp = httpx.post(url, headers=headers, timeout=15)
        except httpx.HTTPError as exc:
            log.error("Favourite request failed for item %s: %s", item_id, exc)
            return False

        if resp.status_code in (200, 201):
            return True

        log.error(
            "Could not favourite item %s (HTTP %s): %s",
            item_id,
            resp.status_code,
            resp.text[:300],
        )
        return False
