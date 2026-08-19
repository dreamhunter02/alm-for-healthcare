import sqlite3

import pytest

from healthcare_alm.retrievers.sql import ReadOnlySQLRetriever


def test_retriever_reads_rows_and_rejects_mutation(tmp_path):
    db = tmp_path / "test.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE inventory(asset_id TEXT)")
        conn.execute("INSERT INTO inventory VALUES ('PUMP-001')")
    retriever = ReadOnlySQLRetriever(db)
    assert retriever.query("SELECT asset_id FROM inventory") == [{"asset_id": "PUMP-001"}]
    with pytest.raises(ValueError, match="SELECT"):
        retriever.query("DELETE FROM inventory")
