"""Cross-check SQL results against an independent Python calculation.

Zero third-party dependencies. Run after `python run.py`:
    python tests/test_pipeline.py
"""
import csv
import sqlite3
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "rfm.sqlite"
DATA = ROOT / "data"
AS_OF = date(2025, 6, 30)


def read_csv(name: str) -> list[dict]:
    with (DATA / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def scalar(conn: sqlite3.Connection, sql: str):
    return conn.execute(sql).fetchone()[0]


def check_duplicates_removed(conn: sqlite3.Connection) -> None:
    raw = scalar(conn, "SELECT COUNT(*) FROM orders")
    clean = scalar(conn, "SELECT COUNT(*) FROM v_clean_orders")
    dup = scalar(conn,
        "SELECT COUNT(*) FROM (SELECT order_id FROM orders GROUP BY order_id HAVING COUNT(*) > 1)")
    assert dup > 0, "fixture should contain duplicated order rows"
    assert clean < raw, "duplicate log lines were not removed"
    print(f"[PASS] de-duplication: {raw:,} raw order rows -> {clean:,} clean orders")


def check_rfm_matches_python(conn: sqlite3.Connection) -> None:
    orders = read_csv("orders.csv")
    items = read_csv("order_items.csv")

    valid = {}
    for o in orders:
        if o["status"] == "completed" and o["order_id"] not in valid:
            valid[o["order_id"]] = o

    amount = defaultdict(float)
    for it in items:
        if it["order_id"] in valid:
            amount[it["order_id"]] += int(it["quantity"]) * float(it["unit_price"])
    amount = {oid: round(v, 2) for oid, v in amount.items()}

    stats: dict[str, list] = {}
    for oid, o in valid.items():
        uid = o["user_id"]
        days = (AS_OF - date.fromisoformat(o["order_date"])).days
        if uid not in stats:
            stats[uid] = [days, set(), 0.0]
        s = stats[uid]
        s[0] = min(s[0], days)
        s[1].add(oid)
        s[2] += amount[oid]
    expected = {uid: (s[0], len(s[1]), round(s[2], 2)) for uid, s in stats.items()}

    actual = {
        r[0]: (r[1], r[2], round(r[3], 2))
        for r in conn.execute(
            "SELECT user_id, recency_days, frequency, monetary FROM v_rfm_raw")
    }
    assert expected.keys() == actual.keys(), "user sets differ"
    for uid, e in expected.items():
        a = actual[uid]
        assert e[0] == a[0] and e[1] == a[1] and abs(e[2] - a[2]) < 0.02, (uid, e, a)
    print(f"[PASS] RFM matches independent Python calc for {len(actual):,} users")


def check_scores_and_segments(conn: sqlite3.Connection) -> None:
    rows = list(conn.execute(
        "SELECT user_id, r_score, f_score, m_score, segment FROM v_user_segments"))
    for r in rows:
        assert all(1 <= v <= 5 for v in r[1:4]), f"score out of range: {r}"
    ids = [r[0] for r in rows]
    assert len(set(ids)) == len(ids), "duplicate users in segmentation"
    segments = {r[4] for r in rows}
    assert len(segments) == 8, f"expected 8 segments, got {len(segments)}"
    print(f"[PASS] scores 1-5, {len(segments)} segments, {len(rows):,} users uniquely labelled")


def check_roi_grid(conn: sqlite3.Connection) -> None:
    rows = list(conn.execute(
        "SELECT lift_trad, trad_roi_pct, target_roi_pct FROM t_roi_sensitivity"))
    assert len(rows) == 4, "expected 4 lift scenarios"
    for r in rows:
        assert r[2] > r[1], f"precision should beat traditional in scenario {r}"
    print(f"[PASS] ROI grid: precision beats traditional in all {len(rows)} scenarios")


def main() -> None:
    if not DB.exists():
        raise SystemExit("Run `python run.py` first.")
    conn = sqlite3.connect(DB)
    try:
        check_duplicates_removed(conn)
        check_rfm_matches_python(conn)
        check_scores_and_segments(conn)
        check_roi_grid(conn)
    finally:
        conn.close()
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
