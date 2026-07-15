"""One-time setup check: pgvector enabled + Google Sheet reachable. Run: python scripts/check_setup.py"""
import os
import re
import urllib.request

import psycopg
from dotenv import load_dotenv

load_dotenv()

# 1) Enable pgvector and verify
with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=15) as conn:
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    conn.commit()
    row = conn.execute(
        "select extname, extversion from pg_extension where extname = 'vector'"
    ).fetchone()
    print("pgvector enabled:", row)

# 2) Google Sheet must be link-shared for the export URL to work
sheet_id = re.search(r"/d/([\w-]+)", os.environ["GOOGLE_SHEET_URL"]).group(1)
url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
data = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", errors="ignore")
lines = data.splitlines()
print("Sheet rows fetched:", len(lines))
print("Header:", lines[0][:100])
print("Row 1:", lines[1][:100])
