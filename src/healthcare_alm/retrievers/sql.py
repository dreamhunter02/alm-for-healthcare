# SPDX-FileCopyrightText: Copyright (c) 2023-2026 NVIDIA CORPORATION & AFFILIATES.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


class ReadOnlySQLRetriever:
    def __init__(self, db_path: Path | str, max_rows: int = 5000) -> None:
        self.db_path = Path(db_path).resolve()
        self.max_rows = max_rows

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        normalized = sql.lstrip().upper()
        if not (normalized.startswith("SELECT") or normalized.startswith("WITH")):
            raise ValueError("Only SELECT queries are allowed")
        uri = f"file:{self.db_path}?mode=ro"
        with sqlite3.connect(uri, uri=True) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql, params)
            rows = cursor.fetchmany(self.max_rows + 1)
        if len(rows) > self.max_rows:
            raise ValueError(f"Query exceeded row limit of {self.max_rows}")
        return [dict(row) for row in rows]
