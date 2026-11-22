"""Generate reproducible synthetic e-commerce transaction data.

Three normalized tables (users / orders / order_items) so the downstream
project has to demonstrate real SQL: joins, aggregation, de-duplication and
window functions -- not just reading a ready-made wide table.

All records are synthetic with a fixed seed. No real user data is involved.
"""
import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 20261123
N_USERS = 2000
AS_OF = date(2025, 6, 30)

CATEGORIES = {
    "数码配件": (59, 899),
    "家居日用": (25, 320),
    "美妆个护": (39, 459),
    "服饰鞋包": (79, 799),
    "食品生鲜": (15, 189),
    "图书文具": (19, 159),
}
INTERESTS = list(CATEGORIES)
CITIES = ["深圳", "上海", "杭州", "北京", "广州", "成都", "武汉", "长沙"]
CHANNELS = ["app", "web", "mini_program"]
STATUSES = ["completed", "completed", "completed", "completed",
            "completed", "completed", "completed", "completed",
            "cancelled", "refunded"]


def poisson(rng: random.Random, lam: float) -> int:
    """Knuth sampler: stdlib random has no poisson method."""
    limit = math.exp(-lam)
    k, p = 0, 1.0
    while p > limit:
        k += 1
        p *= rng.random()
    return k - 1


def main() -> None:
    rng = random.Random(SEED)
    out = Path(__file__).resolve().parent
    out.mkdir(parents=True, exist_ok=True)

    users = []
    orders = []
    items = []
    order_seq = 0
    item_seq = 0

    for i in range(1, N_USERS + 1):
        uid = f"U{i:05d}"
        signup = date(2024, 1, 1) + timedelta(days=rng.randint(0, 500))
        if signup > AS_OF:
            signup = AS_OF - timedelta(days=15)
        days = (AS_OF - signup).days
        interest = rng.choice(INTERESTS)

        users.append({
            "user_id": uid,
            "signup_date": signup.isoformat(),
            "age": rng.randint(18, 62),
            "income": rng.choice([5000, 8000, 12000, 18000, 25000, 40000]),
            "newsletter_subscribed": rng.choice([0, 1]),
            "interests": interest,
            "preferred_category": interest if rng.random() < 0.7 else rng.choice(INTERESTS),
            "city": rng.choice(CITIES),
        })

        # Two independent drivers: purchase intensity and recency tendency.
        activity = min(max(rng.lognormvariate(-1.1, 0.85), 0.05), 5.0)
        recency_bias = rng.random()
        n_orders = min(poisson(rng, activity * days / 210.0), 30)

        for _ in range(n_orders):
            u = rng.random()
            if recency_bias < 0.30:
                frac = 1 - u ** 2          # recently active
            elif recency_bias > 0.70:
                frac = u ** 2              # dormant / lapsed
            else:
                frac = u
            odate = signup + timedelta(days=int(frac * max(days, 1)))
            if odate > AS_OF:
                odate = AS_OF

            order_seq += 1
            oid = f"O{order_seq:07d}"
            orders.append({
                "order_id": oid,
                "user_id": uid,
                "order_date": odate.isoformat(),
                "status": rng.choice(STATUSES),
                "channel": rng.choice(CHANNELS),
            })

            # Simulate a duplicated log line for a small share of orders.
            if rng.random() < 0.02:
                orders.append(dict(orders[-1]))

            for _ in range(rng.randint(1, 4)):
                item_seq += 1
                cat = users[-1]["preferred_category"] if rng.random() < 0.6 else rng.choice(INTERESTS)
                lo, hi = CATEGORIES[cat]
                price = round(rng.uniform(lo, hi), 2)
                items.append({
                    "order_item_id": f"I{item_seq:08d}",
                    "order_id": oid,
                    "product_id": f"P{rng.randint(1, 300):04d}",
                    "category": cat,
                    "quantity": rng.choices([1, 2, 3], weights=[0.75, 0.2, 0.05])[0],
                    "unit_price": price,
                })

    def dump(name: str, rows: list[dict]) -> None:
        path = out / name
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        print(f"{name}: {len(rows):,} rows")

    dump("users.csv", users)
    dump("orders.csv", orders)
    dump("order_items.csv", items)
    print(f"as_of_date: {AS_OF}")


if __name__ == "__main__":
    main()
