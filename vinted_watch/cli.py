"""CLI entry point: run configured Vinted watches once and report new matches.

Usage:
    python -m vinted_watch.cli --config config.yaml
    python -m vinted_watch.cli --config config.yaml --favorite --csv matches.csv

Run it periodically yourself (cron, launchd, Task Scheduler, ...) to keep
checking for new listings - it only reports items it hasn't seen before.
"""
from __future__ import annotations

import argparse
import csv
import logging
import os
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

from .client import VintedClient, VintedItem
from .config import load_config
from .lang_filter import looks_danish_or_english
from .storage import SeenStore

log = logging.getLogger("vinted_watch")


def _load_env_file(path: str = ".env") -> None:
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _write_csv(csv_path: str, new_matches: List[Tuple[str, VintedItem]]) -> None:
    write_header = not Path(csv_path).exists()
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["watch", "title", "price", "currency", "brand", "status", "url"])
        for watch_name, item in new_matches:
            writer.writerow(
                [watch_name, item.title, item.price_amount, item.price_currency, item.brand, item.status, item.url]
            )


def run_once(config_path: str, db_path: str, favorite: bool, csv_path: Optional[str]) -> int:
    _load_env_file()
    config = load_config(config_path)
    auth_cookie = os.environ.get("VINTED_COOKIE") if favorite else None
    csrf_token = os.environ.get("VINTED_CSRF_TOKEN") if favorite else None

    if favorite and not (auth_cookie and csrf_token):
        log.warning(
            "--favorite is set but VINTED_COOKIE and/or VINTED_CSRF_TOKEN is not "
            "configured (see .env.example); matches will still be found and "
            "logged, but nothing will be favourited."
        )

    client = VintedClient(domain=config.domain, auth_cookie=auth_cookie, csrf_token=csrf_token)
    new_matches: List[Tuple[str, VintedItem]] = []

    with SeenStore(db_path) as store:
        for watch in config.watches:
            log.info("Searching watch '%s'...", watch.name)
            try:
                items = client.search(watch.to_params())
            except Exception as exc:  # noqa: BLE001 - one bad watch shouldn't stop the rest
                log.error("Search failed for watch '%s': %s", watch.name, exc)
                continue

            items = [item for item in items if looks_danish_or_english(item.title)]

            # Vinted's search_text match is loose (fuzzy/partial across
            # title, description, ...), so it returns plenty of items whose
            # title has nothing to do with what we searched for. Require the
            # search text to actually appear in the item's own title.
            needle = watch.search_text.strip().lower()
            items = [item for item in items if needle in item.title.lower()]

            for item in items:
                if not store.is_new(item.id):
                    continue

                store.mark_seen(item.id, watch.name, item.title, item.price_amount, item.url)
                new_matches.append((watch.name, item))

                price = f"{item.price_amount} {item.price_currency}".strip()
                print(f"[{watch.name}] {item.title} - {price} - {item.url}")

                if favorite and auth_cookie and csrf_token:
                    ok = client.favourite(item.id)
                    print(f"    -> favourite {'OK' if ok else 'FAILED'}")

            time.sleep(1.5)  # be polite between watches / avoid hammering the site

    if csv_path and new_matches:
        _write_csv(csv_path, new_matches)

    log.info("Done. %d new match(es) found.", len(new_matches))
    return len(new_matches)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find new book listings on Vinted matching your saved searches."
    )
    parser.add_argument(
        "--config", default="config.yaml", help="Path to watches config (YAML). Default: config.yaml"
    )
    parser.add_argument(
        "--db", default="vinted_watch.db", help="Path to the SQLite 'seen items' database."
    )
    parser.add_argument(
        "--favorite",
        action="store_true",
        help="Best-effort auto-favourite new matches (needs VINTED_COOKIE and VINTED_CSRF_TOKEN in .env).",
    )
    parser.add_argument("--csv", default=None, help="Optional path to append new matches to as CSV.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging.")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if not Path(args.config).exists():
        log.error("Config file not found: %s (copy config.example.yaml to get started)", args.config)
        sys.exit(1)

    run_once(args.config, args.db, args.favorite, args.csv)


if __name__ == "__main__":
    main()
