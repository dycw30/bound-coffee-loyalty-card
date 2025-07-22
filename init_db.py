
import sqlite3
from werkzeug.security import generate_password_hash

conn = sqlite3.connect('loyalty_card.db')
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    role TEXT NOT NULL
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    unique_id TEXT NOT NULL,
    total_orders INTEGER DEFAULT 0,
    tokens_earned INTEGER DEFAULT 0,
    tokens_redeemed INTEGER DEFAULT 0
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS drinks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
)
""")

admin_pass = generate_password_hash('admin123')
c.execute('INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)', ('adminJane', admin_pass, 'admin'))

barista_pass = generate_password_hash('barista123')
c.execute('INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)', ('baristaDavid', barista_pass, 'barista'))

conn.commit()
conn.close()
