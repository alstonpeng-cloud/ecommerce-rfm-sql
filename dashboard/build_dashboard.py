"""Build dashboard data from the RFM pipeline output.

Reads output/*.csv and writes dashboard/data.js so the dashboard works
offline via file:// (no fetch, no server, no third-party Python packages).

Usage:  python dashboard/build_dashboard.py   (run from project root or anywhere)
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
DASH = ROOT / "dashboard"


def read_rows(name: str) -> list[dict]:
    with (OUT / name).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def num(row: dict, key: str, cast=float):
    return cast(row[key])


def main() -> None:
    summary = read_rows("t_segment_summary.csv")
    roi = read_rows("t_roi_sensitivity.csv")
    users = read_rows("v_user_segments.csv")

    segments = [
        {
            "name": r["segment"],
            "users": num(r, "user_count", int),
            "pctUsers": num(r, "pct_users"),
            "avgRecency": num(r, "avg_recency_days"),
            "avgFrequency": num(r, "avg_frequency"),
            "avgMonetary": num(r, "avg_monetary"),
            "totalMonetary": num(r, "total_monetary"),
            "pctRevenue": num(r, "pct_revenue"),
        }
        for r in summary
    ]
    segments.sort(key=lambda x: x["totalMonetary"], reverse=True)

    # Normalise R/F/M averages to 0-100 for the radar chart.
    for key, field in [("r", "avgRecency"), ("f", "avgFrequency"), ("m", "avgMonetary")]:
        lo = min(s[field] for s in segments)
        hi = max(s[field] for s in segments)
        for s in segments:
            s[f"radar_{key}"] = round(
                100 if hi == lo else (s[field] - lo) / (hi - lo) * 100, 1
            )
    # Recency: lower is better, so invert the radar axis.
    for s in segments:
        s["radar_r"] = round(100 - s["radar_r"], 1)

    roi_rows = [
        {
            "liftTrad": num(r, "lift_trad"),
            "liftTarget": num(r, "lift_target"),
            "tradRoi": num(r, "trad_roi_pct"),
            "targetRoi": num(r, "target_roi_pct"),
        }
        for r in roi
    ]

    scatter = [
        {
            "segment": r["segment"],
            "recency": num(r, "recency_days", int),
            "frequency": num(r, "frequency", int),
            "monetary": num(r, "monetary"),
        }
        for r in users
    ]

    total_users = sum(s["users"] for s in segments)
    total_revenue = sum(s["totalMonetary"] for s in segments)
    payload = {
        "snapshot": "2025-06-30",
        "totalUsers": total_users,
        "totalRevenue": round(total_revenue, 2),
        "segments": segments,
        "roi": roi_rows,
        "scatter": scatter,
    }

    DASH.mkdir(exist_ok=True)
    target = DASH / "data.js"
    target.write_text(
        "window.RFM_DATA = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )
    print(f"wrote {target.relative_to(ROOT)}: {len(segments)} segments, "
          f"{len(roi_rows)} scenarios, {len(scatter)} users")


if __name__ == "__main__":
    main()
