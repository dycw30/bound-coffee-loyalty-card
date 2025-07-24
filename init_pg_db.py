# init_pg_db.py
import os
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.getenv("DATABASE_URL")

conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL
);
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    unique_id TEXT NOT NULL,
    total_orders INTEGER DEFAULT 0,
    tokens_earned INTEGER DEFAULT 0,
    tokens_redeemed INTEGER DEFAULT 0
);
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS drinks (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL
);
""")

conn.commit()
cur.close()
conn.close()

print("✅ PostgreSQL database initialized.")
