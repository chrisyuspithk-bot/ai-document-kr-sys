"""Dialect-safe vector column type.

On PostgreSQL this delegates to pgvector's ``Vector`` type so embeddings can be
used in ``<=>`` similarity queries. On other dialects (SQLite in tests) the
vector is stored as a JSON array so ``create_all`` works without a vector
extension.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import types


class Vector(types.TypeDecorator):
    impl = types.Text
    cache_ok = True

    def __init__(self, dim: int) -> None:
        super().__init__()
        self.dim = dim

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import Vector as PGVector

            return dialect.type_descriptor(PGVector(self.dim))
        return dialect.type_descriptor(types.Text())

    def process_bind_param(self, value: list[float] | None, dialect: Any) -> Any:
        if value is None or dialect.name == "postgresql":
            return value
        return json.dumps(value)

    def process_result_value(self, value: Any, dialect: Any) -> list[float] | None:
        if value is None or dialect.name == "postgresql":
            return value
        return json.loads(value)
