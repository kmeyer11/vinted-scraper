"""Load search settings (YAML) plus the titles/authors text lists they apply to."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml


@dataclass
class Watch:
    name: str
    search_text: str
    catalog_ids: Optional[str] = None
    price_from: Optional[float] = None
    price_to: Optional[float] = None
    order: str = "newest_first"
    per_page: int = 48

    def to_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "search_text": self.search_text,
            "order": self.order,
            "per_page": self.per_page,
        }
        if self.catalog_ids:
            params["catalog_ids"] = self.catalog_ids
        if self.price_from is not None:
            params["price_from"] = self.price_from
        if self.price_to is not None:
            params["price_to"] = self.price_to
        return params


@dataclass
class Config:
    domain: str
    watches: List[Watch] = field(default_factory=list)


def _read_lines(path: Path) -> List[str]:
    if not path.exists():
        return []
    lines = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


def load_config(path: Union[str, Path]) -> Config:
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    domain = raw.get("domain", "https://www.vinted.dk")
    catalog_ids = str(raw["catalog_ids"]) if raw.get("catalog_ids") else None
    price_from = raw.get("price_from")
    price_to = raw.get("price_to")
    order = raw.get("order", "newest_first")
    per_page = raw.get("per_page", 48)

    base_dir = path.parent
    titles_file = base_dir / raw.get("titles_file", "titler.txt")
    authors_file = base_dir / raw.get("authors_file", "forfattere.txt")

    watches: List[Watch] = []
    for title in _read_lines(titles_file):
        watches.append(
            Watch(
                name=f"Titel: {title}",
                search_text=title,
                catalog_ids=catalog_ids,
                price_from=price_from,
                price_to=price_to,
                order=order,
                per_page=per_page,
            )
        )
    for author in _read_lines(authors_file):
        watches.append(
            Watch(
                name=f"Forfatter: {author}",
                search_text=author,
                catalog_ids=catalog_ids,
                price_from=price_from,
                price_to=price_to,
                order=order,
                per_page=per_page,
            )
        )

    if not watches:
        raise ValueError(
            f"Ingen titler eller forfattere fundet. Tilføj linjer til "
            f"{titles_file} og/eller {authors_file}."
        )

    return Config(domain=domain, watches=watches)
