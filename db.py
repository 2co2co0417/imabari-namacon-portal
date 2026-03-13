import os
from flask import g
import psycopg
from psycopg.rows import dict_row

def get_database_url():
    db_url = os.getenv("DATABASE_URL", "").strip()
    if not db_url:
        raise RuntimeError("DATABASE_URL が設定されていません。")
    return db_url

def get_db():
    if "db" not in g:
        g.db = psycopg.connect(
            get_database_url(),
            row_factory=dict_row,
            autocommit=False
        )
    return g.db

def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db(app):
    with app.app_context():
        db = get_db()
        with app.open_resource("schema.sql", mode="r", encoding="utf-8") as f:
            sql = f.read()

        statements = [s.strip() for s in sql.split(";") if s.strip()]

        with db.cursor() as cur:
            for statement in statements:
                cur.execute(statement)

        db.commit()