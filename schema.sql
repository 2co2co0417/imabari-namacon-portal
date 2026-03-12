DROP TABLE IF EXISTS clients;
DROP TABLE IF EXISTS notices;

CREATE TABLE clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company TEXT NOT NULL,
    name TEXT NOT NULL,
    phone TEXT NOT NULL UNIQUE,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE notices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    notice_date TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);