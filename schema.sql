-- schema.sql
DROP TABLE IF EXISTS clients;

CREATE TABLE clients (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  company TEXT NOT NULL,
  name TEXT NOT NULL,
  phone TEXT NOT NULL UNIQUE,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 最初の1社（モック）
INSERT INTO clients (company, name, phone, is_active)
VALUES ('滝本建設', '吉田様', '09097796101', 1);