# db.py
import sqlite3
from pathlib import Path
from flask import g

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "app.db"
SCHEMA_PATH = BASE_DIR / "schema.sql"

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db(app):
    # 初回だけ schema.sql から作成
    if not DB_PATH.exists():
        if not SCHEMA_PATH.exists():
            raise FileNotFoundError(f"schema.sql not found: {SCHEMA_PATH}")
        sql = SCHEMA_PATH.read_text(encoding="utf-8")
        db = sqlite3.connect(DB_PATH)
        db.executescript(sql)
        db.commit()
        db.close()