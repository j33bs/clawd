from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import lancedb
import pyarrow as pa

MODERNBERT_TABLE = "rag_modernbert"
MINILM_TABLE = "rag_minilm"


def make_row_id(doc_id: str, chunk_id: str, model_id: str) -> str:
    payload = f"{doc_id}:{chunk_id}:{model_id}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:32]


def _escape_sql(value: str) -> str:
    return str(value).replace("'", "''")


def _schema(dim: int) -> pa.Schema:
    return pa.schema(
        [
            pa.field("id", pa.string()),
            pa.field("doc_id", pa.string()),
            pa.field("source", pa.string()),
            pa.field("path", pa.string()),
            pa.field("section", pa.string()),
            pa.field("chunk_id", pa.string()),
            pa.field("text", pa.string()),
            pa.field("tokens", pa.int32()),
            pa.field("embedding", pa.list_(pa.float32(), dim)),
            pa.field("model_id", pa.string()),
            pa.field("updated_at", pa.string()),
        ]
    )


class LanceVectorStore:
    def __init__(self, db_dir: str):
        self.db_dir = Path(db_dir)
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.db = lancedb.connect(str(self.db_dir))

    def table_exists(self, name: str) -> bool:
        if hasattr(self.db, "list_tables"):
            response = self.db.list_tables()
            names = getattr(response, "tables", response)
        else:
            names = self.db.table_names()
        normalized = []
        for item in names:
            if isinstance(item, (tuple, list)) and item:
                normalized.append(str(item[0]))
            else:
                normalized.append(str(item))
        return name in set(normalized)

    def ensure_table(self, name: str, dim: int):
        if self.table_exists(name):
            return self.db.open_table(name)
        return self.db.create_table(name, data=[], schema=_schema(dim))

    def upsert(self, name: str, rows: list[dict]):
        if not rows:
            return 0

        dim = len(rows[0].get("embedding", []))
        table = self.ensure_table(name, dim=dim)

        ids = sorted({str(row.get("id", "")).strip() for row in rows if row.get("id")})
        if ids:
            joined = ", ".join(f"'{_escape_sql(i)}'" for i in ids)
            table.delete(f"id IN ({joined})")

        table.add(rows)
        return len(rows)

    def query(
        self,
        name: str,
        vector: list[float],
        k: int,
        where: str | None = None,
    ) -> list[dict]:
        if not self.table_exists(name):
            raise RuntimeError(f"LanceDB table missing: {name}")

        table = self.db.open_table(name)
        search = table.search(vector, vector_column_name="embedding")
        if where:
            search = search.where(where)
        df = search.limit(int(k)).to_pandas()

        rows = df.to_dict(orient="records")
        out: list[dict[str, Any]] = []
        for row in rows:
            distance = row.get("_distance")
            if distance is not None:
                try:
                    distance = float(distance)
                except Exception:
                    distance = None
            score = None
            if distance is not None:
                score = 1.0 / (1.0 + max(distance, 0.0))
            row["distance"] = distance
            row["score"] = score
            out.append(row)
        return out

    def delete_by_doc(self, name: str, doc_id: str):
        if not self.table_exists(name):
            return 0
        table = self.db.open_table(name)
        table.delete(f"doc_id = '{_escape_sql(doc_id)}'")
        return 1

    def stats(self, name: str) -> dict:
        if not self.table_exists(name):
            return {"name": name, "exists": False, "rows": 0, "dim": None}

        table = self.db.open_table(name)
        rows = int(table.count_rows())
        dim = None
        field = table.schema.field("embedding")
        if hasattr(field.type, "list_size"):
            dim = int(field.type.list_size)

        return {"name": name, "exists": True, "rows": rows, "dim": dim}
