"""Add result column to existing signal_performance table."""
from agentest.utils.indicators.tracker_db import _conn
conn = _conn()
try:
    conn.execute("ALTER TABLE signal_performance ADD COLUMN result TEXT DEFAULT 'pending'")
    print("Added result column")
except Exception as e:
    print(f"Already exists or error: {e}")
conn.commit()
conn.close()
