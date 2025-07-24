import psycopg2
from dotenv import load_dotenv
import os

# ✅ Load .env from the current folder
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=env_path)

# ✅ Print check to confirm .env loaded correctly
print("Connecting to:", os.getenv("DB_HOST"))

# ✅ Connect to the PostgreSQL database
conn = psycopg2.connect(
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT")
)

# ✅ Initialize schema
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
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
