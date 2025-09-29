import sqlite3

def init_db(db_path: str = "db/cve.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cve (
            id TEXT PRIMARY KEY,
            description TEXT,
            cvss_v3 REAL,
            published_date TEXT,
            last_modified TEXT,
            vendor TEXT,
            product TEXT,
            epss REAL
        )
    """)

    conn.commit()
    conn.close()
    print(f"Database initialized at {db_path}")

if __name__ == "__main__":
    init_db()
