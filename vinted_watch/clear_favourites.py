"""List and optionally clear items in your Vinted favourites.

Uses the same toggle endpoint as `cli.py --favorite`: calling it on an item
that's already favourited un-favourites it. Preview-only by default -
nothing is removed unless you pass --yes.

By default, only favourites that are also present in the local "seen
items" database (vinted_watch.db - i.e. books this tool itself found and
favourited via a search watch) are eligible for removal. Anything else
you've favourited yourself in the app (clothes, manual favourites, ...)
is left untouched. Pass --all-favourites to lift that restriction.

Usage:
    python -m vinted_watch.clear_favourites                       # just list what's eligible
    python -m vinted_watch.clear_favourites --yes                 # remove all known books
    python -m vinted_watch.clear_favourites --yes --contains "foo"  # remove only title matches
    python -m vinted_watch.clear_favourites --yes --all-favourites  # remove ALL favourites, not just known books
"""
from __future__ import annotations

import argparse
import logging
import os
import time

from .cli import _load_env_file
from .client import VintedClient
from .storage import SeenStore

log = logging.getLogger("vinted_watch.clear_favourites")


def main() -> None:
    parser = argparse.ArgumentParser(description="List and optionally clear your Vinted favourites.")
    parser.add_argument("--domain", default="https://www.vinted.dk")
    parser.add_argument(
        "--db",
        default="vinted_watch.db",
        help="Path to the SQLite 'seen items' database used to identify which "
        "favourites are books this tool found (default: vinted_watch.db).",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Actually remove favourites. Without this flag, only lists them (dry run).",
    )
    parser.add_argument(
        "--contains",
        default=None,
        help="Only affect favourites whose title contains this text (case-insensitive).",
    )
    parser.add_argument(
        "--all-favourites",
        action="store_true",
        help="Consider ALL current Vinted favourites eligible, not just ones "
        "this tool found and favourited itself (see --db). Use with care - "
        "this can also remove things like clothes you favourited manually.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging.")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    _load_env_file()
    auth_cookie = os.environ.get("VINTED_COOKIE")
    csrf_token = os.environ.get("VINTED_CSRF_TOKEN")
    if not auth_cookie or not csrf_token:
        log.error("VINTED_COOKIE and VINTED_CSRF_TOKEN must be set in .env (see .env.example).")
        raise SystemExit(1)

    client = VintedClient(domain=args.domain, auth_cookie=auth_cookie, csrf_token=csrf_token)

    log.info("Fetching your current favourites...")
    favourites = client.list_favourites()

    if not args.all_favourites:
        with SeenStore(args.db) as store:
            favourites = [item for item in favourites if not store.is_new(item.id)]

    if args.contains:
        needle = args.contains.lower()
        favourites = [item for item in favourites if needle in item.title.lower()]

    scope = "ALL favourites" if args.all_favourites else "known books"
    suffix = " matching filter" if args.contains else ""
    print(f"Found {len(favourites)} eligible favourite(s) ({scope}){suffix}.")
    for item in favourites:
        print(f"  {item.title} - {item.url}")

    if not args.yes:
        print("\nDry run - nothing removed. Re-run with --yes to actually remove these.")
        return

    removed = 0
    for item in favourites:
        ok = client.unfavourite(item.id)
        print(f"{'Removed' if ok else 'FAILED'}: {item.title}")
        if ok:
            removed += 1
        time.sleep(1.0)  # be polite / avoid rate limiting

    print(f"\nDone. Removed {removed}/{len(favourites)}.")


if __name__ == "__main__":
    main()
