from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel

Subfield = Literal["CO", "EP", "GA", "HE", "IM", "SR"]
Kind = Literal["topical", "identifier", "question", "synonym", "method", "contrarian"]

EVAL_DIR = Path("eval")


class Query(BaseModel):
    id: str
    query: str
    intent: str
    subfield: Subfield
    kind: Kind
    lang: str = "en"
    translation_of: str | None = None  # id of the English query this one translates


def load_queries(path: Path = EVAL_DIR / "queries.yaml") -> list[Query]:
    queries = [Query(**q) for q in yaml.safe_load(path.read_text(encoding="utf-8"))]
    ids = [q.id for q in queries]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate query ids")
    return queries
