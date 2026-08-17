"""Heuristic filter: keep only listing titles that read as Danish/English.

Vinted's free-text search matches across all languages/locales, so a
search for e.g. "1984 George Orwell" also returns every Polish, Czech and
Ukrainian re-listing of the same book. This is a cheap character-based
filter (no external language-detection dependency) that rejects the
scripts/diacritics that dominated that noise in practice, without trying
to be a general-purpose language classifier.
"""
from __future__ import annotations

import re

# Cyrillic (Russian/Ukrainian/Bulgarian/...) - never Danish or English.
_CYRILLIC = re.compile(r"[Ѐ-ӿ]")

# Diacritics that are distinctly Polish or Czech/Slovak - not used in
# Danish or English. These accounted for most of the non-Danish/English
# noise seen in practice (translated classics re-listed in Polish etc).
_OTHER_LATIN_DIACRITICS = re.compile(
    r"[ąćęłńóśźżĄĆĘŁŃÓŚŹŻčďěľňřšťůžČĎĚĽŇŘŠŤŮŽ]"
)


def looks_danish_or_english(title: str) -> bool:
    if _CYRILLIC.search(title):
        return False
    if _OTHER_LATIN_DIACRITICS.search(title):
        return False
    return True
