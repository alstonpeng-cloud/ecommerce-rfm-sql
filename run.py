"""One-command reproducible pipeline: CSV -> SQLite -> analytics tables.

Zero third-party dependencies (Python 3.9+ standard library only).
Usage:  python run.py
Outputs: rfm.sqlite and output/*.csv
"""
import csv
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SQL_DIR = ROOT / "sql"
OUT = ROOT / "output"
DB = ROOT / "rfm.sqlite"
AS_OF = "2025-06-30"
TABLES = ["users", "orders", "order_items"]
INT_COLS = {"age", "income", "quantity", "newsletter_subscribed"}
REAL_COLS = {"unit_price"}


def load_csv(conn: sqlite3.Connection, name: str, path: Path) -> int:
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        cols = []
        for c in header:
            kind = "INTEGER" if c in INT_COLS else "REAL" if c in REAL_COLS else "TEXT"
            cols.append(f'"{c}" {kind}')
        conn.execute(f"DROP TABLE IF EXISTS {name}")
        conn.execute(f'CREATE TABLE {name} ({", ".join(cols)})')
        placeholders = ",".join("?" for _ in header)
        cur = conn.executemany(f"INSERT INTO {name} VALUES ({placeholders})", reader)
        return cur.rowcount


def export_csv(conn: sqlite3.Connection, table: str, path: Path) -> None:
    cur = conn.execute(f"SELECT * FROM {table}")
    names = [d[0] for d in cur.description]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(names)
        writer.writerows(cur.fetchall())


def show(conn: sqlite3.Connection, table: str) -> None:
    cur = conn.execute(f"SELECT * FROM {table}")
    names = [d[0] for d in cur.description]
    rows = cur.fetchall()
    widths = [max(len(str(n)), max((len(str(r[i])) for r in rows), default=0))
              for i, n in enumerate(names)]
    print(" | ".join(str(n).ljust(widths[i]) for i, n in enumerate(names)))
    print("-+-".join("-" * w for w in widths))
    for r in rows:
        print(" | ".join(str(v).ljust(widths[i]) for i, v in enumerate(r)))


def main() -> None:
    if not (DATA / "users.csv").exists():
        print("Generating synthetic data ...")
        subprocess.run([sys.executable, str(DATA / "generate_data.py")], check=True)

    if DB.exists():
        DB.unlink()
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA journal_mode = OFF;")

    for name in TABLES:
        n = load_csv(conn, name, DATA / f"{name}.csv")
        print(f"loaded {name:12s} {n:6,d} rows")

    for filename in ["01_rfm_segmentation.sql", "02_campaign_roi.sql"]:
        script = (SQL_DIR / filename).read_text(encoding="utf-8")
        conn.executescript(script.replace("{{AS_OF}}", AS_OF))
        print(f"executed {filename}")

    OUT.mkdir(exist_ok=True)
    for table in ["v_rfm_raw", "v_user_segments", "t_segment_summary", "t_roi_sensitivity"]:
        export_csv(conn, table, OUT / f"{table}.csv")

    print("\n=== Segment summary ===")
    show(conn, "t_segment_summary")
    print("\n=== ROI sensitivity ===")
    show(conn, "t_roi_sensitivity")

    conn.close()
    print(f"\nDone. Database: {DB.name}; CSV exports: {OUT.name}/")


if __name__ == "__main__":
    main()
