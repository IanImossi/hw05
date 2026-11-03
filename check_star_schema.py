"""
HW5 - Wildcat Capital star schema checks (Parts A and B).

Proves in code that:
  1. Each table has the row count given in the handout
  2. Every primary key is unique and never blank
  3. Every foreign key matches a row in the table it points to (no orphans),
     and the only blank foreign key is fact_transactions[security_id] on cash rows
  4. Fact date columns match dim_date[date] (not dim_date[date_id])
  5. dim_date is one continuous run of days covering every fact date
  6. Each fact table's grain is unique
  7. The Part E design claims hold: fact advisor_id matches dim_client,
     post-departure transactions exist, and snapshots and securities use
     different benchmark sets

Run from the hw05 folder:
    pip install -r requirements.txt
    python check_star_schema.py
Exits with code 1 if any check fails.
"""

from pathlib import Path
import sys

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "Wildcat Capital Clean"

# Expected row counts from the HW5 handout
EXPECTED_ROWS = {
    "dim_advisor": 25,
    "dim_benchmark": 8,
    "dim_client": 2500,
    "dim_date": 1827,
    "dim_security": 500,
    "fact_fees": 122197,
    "fact_portfolio_snapshot": 129547,
    "fact_transactions": 298572,
}

# Part A: primary key of each table
PRIMARY_KEYS = {
    "dim_advisor": "advisor_id",
    "dim_benchmark": "benchmark_id",
    "dim_client": "client_id",
    "dim_date": "date_id",
    "dim_security": "security_id",
    "fact_fees": "fee_id",
    "fact_portfolio_snapshot": "snapshot_id",
    "fact_transactions": "txn_id",
}

# Part A: foreign keys as (table, column, parent table, parent column)
FOREIGN_KEYS = [
    ("dim_client", "advisor_id", "dim_advisor", "advisor_id"),
    ("dim_security", "benchmark_id", "dim_benchmark", "benchmark_id"),
    ("fact_fees", "client_id", "dim_client", "client_id"),
    ("fact_fees", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_fees", "fee_date", "dim_date", "date"),
    ("fact_portfolio_snapshot", "client_id", "dim_client", "client_id"),
    ("fact_portfolio_snapshot", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_portfolio_snapshot", "benchmark_id", "dim_benchmark", "benchmark_id"),
    ("fact_portfolio_snapshot", "snapshot_date", "dim_date", "date"),
    ("fact_transactions", "client_id", "dim_client", "client_id"),
    ("fact_transactions", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_transactions", "security_id", "dim_security", "security_id"),
    ("fact_transactions", "txn_date", "dim_date", "date"),
]

# The only foreign key allowed to be blank, and the rows where it may be blank
NULLABLE_FK = ("fact_transactions", "security_id")
CASH_TXN_TYPES = {"Deposit", "Withdrawal", "Advisory Fee"}

# Part B: columns that must be unique together at each fact table's grain
GRAINS = {
    "fact_fees": ["client_id", "fee_date"],
    "fact_portfolio_snapshot": ["client_id", "snapshot_date"],
    "fact_transactions": ["txn_id"],
}

# Part B: a coarser grain that must NOT be unique, which shows why
# fact_transactions needs txn_id (a client can have several events per day)
NOT_UNIQUE_GRAINS = {
    "fact_transactions": ["client_id", "txn_date"],
}

# dim_date must cover this range with one row per day
DATE_START, DATE_END = "2020-01-01", "2024-12-31"

# Part E (d): benchmark IDs used by each table that points to dim_benchmark
EXPECTED_BENCHMARKS = {
    ("fact_portfolio_snapshot", "benchmark_id"): {1, 3, 8},
    ("dim_security", "benchmark_id"): {1, 2, 3, 4, 5, 7},
}

# Part E (b): transactions flagged as booked after an advisor departure
EXPECTED_POST_DEPARTURE = 2410

# Key columns read as nullable whole numbers, so a blank stays blank and
# 45 is compared with 45 (not 45.0 with 45)
KEY_COLUMNS = {
    "advisor_id", "benchmark_id", "client_id", "date_id", "security_id",
    "fee_id", "snapshot_id", "txn_id",
}
DATE_COLUMNS = ["date", "fee_date", "snapshot_date", "txn_date"]

failures = []


def check(passed, message):
    """Print PASS/FAIL for one check and remember failures."""
    print(f"  [{'PASS' if passed else 'FAIL'}] {message}")
    if not passed:
        failures.append(message)


def load_tables():
    tables = {}
    for name in EXPECTED_ROWS:
        path = DATA_DIR / f"{name}.csv"
        header = pd.read_csv(path, nrows=0).columns
        # Keys as nullable whole numbers; dates as text so they compare
        # exactly with dim_date[date]; zip codes as text to keep leading zeros
        dtypes = {c: "Int64" for c in header if c in KEY_COLUMNS}
        dtypes.update({c: str for c in header if c in DATE_COLUMNS + ["zip_code"]})
        tables[name] = pd.read_csv(path, dtype=dtypes)
    return tables


def main():
    t = load_tables()

    print("\n1. Row counts match the handout")
    for name, expected in EXPECTED_ROWS.items():
        actual = len(t[name])
        check(actual == expected, f"{name}: {actual:,} rows (expected {expected:,})")

    print("\n2. Primary keys are unique and never blank")
    for name, pk in PRIMARY_KEYS.items():
        col = t[name][pk]
        blanks = col.isna().sum()
        dupes = col.duplicated().sum()
        check(blanks == 0 and dupes == 0,
              f"{name}[{pk}]: {blanks} blanks, {dupes} duplicates")

    print("\n3. Foreign keys have no orphans")
    for child, col, parent, pcol in FOREIGN_KEYS:
        values = t[child][col]
        blanks = values.isna().sum()
        orphans = (~values.dropna().isin(t[parent][pcol])).sum()
        check(orphans == 0, f"{child}[{col}] -> {parent}[{pcol}]: {orphans} orphans")
        if (child, col) != NULLABLE_FK:
            check(blanks == 0, f"{child}[{col}]: {blanks} blanks (none allowed)")

    print("\n4. Blank security_id appears only on cash transactions")
    txn = t["fact_transactions"]
    blank = txn["security_id"].isna()
    is_cash = txn["txn_type"].isin(CASH_TXN_TYPES)
    check((blank == is_cash).all(),
          f"{blank.sum():,} blank security_id rows; all are "
          f"{', '.join(sorted(CASH_TXN_TYPES))} and every other row has a security")
    print("     Blank security_id by txn_type:")
    for txn_type, count in txn.loc[blank, "txn_type"].value_counts().items():
        print(f"       {txn_type:<14}{count:>8,}")

    print("\n5. dim_date is continuous and fact dates join to dim_date[date]")
    dim_date = t["dim_date"]
    days = pd.to_datetime(dim_date["date"], format="%Y-%m-%d", errors="coerce")
    check(days.notna().all(), "dim_date[date] values are all valid YYYY-MM-DD dates")
    check(dim_date["date"].is_unique, "dim_date[date] is unique (valid one side)")
    expected_days = pd.date_range(DATE_START, DATE_END, freq="D")
    check(days.sort_values().reset_index(drop=True).equals(pd.Series(expected_days)),
          f"dim_date has exactly one row per day from {DATE_START} to {DATE_END} "
          f"({len(expected_days):,} days)")
    for fact, col in [("fact_fees", "fee_date"),
                      ("fact_portfolio_snapshot", "snapshot_date"),
                      ("fact_transactions", "txn_date")]:
        values = t[fact][col]
        parsed = pd.to_datetime(values, format="%Y-%m-%d", errors="coerce")
        in_date = values.isin(dim_date["date"]).all()
        in_id = values.isin(dim_date["date_id"].astype(str)).any()
        check(parsed.notna().all() and in_date and not in_id,
              f"{fact}[{col}] holds calendar dates that all match dim_date[date] "
              f"and none match a date_id")

    print("\n6. Fact grain is unique (Part B)")
    for fact, cols in GRAINS.items():
        dupes = t[fact].duplicated(subset=cols).sum()
        check(dupes == 0, f"{fact}: one row per {' + '.join(cols)} ({dupes} duplicates)")
    for fact, cols in NOT_UNIQUE_GRAINS.items():
        dupes = t[fact].duplicated(subset=cols).sum()
        check(dupes > 0,
              f"{fact}: {' + '.join(cols)} is NOT unique ({dupes:,} repeated rows), "
              f"so the grain must be the single event (txn_id)")

    print("\n7. Part E design claims")
    client_advisor = t["dim_client"][["client_id", "advisor_id"]]
    for fact in ["fact_fees", "fact_portfolio_snapshot", "fact_transactions"]:
        merged = t[fact][["client_id", "advisor_id"]].merge(
            client_advisor, on="client_id", suffixes=("", "_client"))
        differ = (merged["advisor_id"] != merged["advisor_id_client"]).sum()
        check(differ == 0,
              f"(b) {fact}[advisor_id] equals dim_client[advisor_id] on every row "
              f"({differ} differ)")
    flag = t["fact_transactions"]["is_post_departure_txn"]
    check(set(flag.unique()) <= {0, 1} and flag.sum() == EXPECTED_POST_DEPARTURE,
          f"(b) {flag.sum():,} transactions flagged is_post_departure_txn "
          f"(expected {EXPECTED_POST_DEPARTURE:,})")
    for (table, col), expected in EXPECTED_BENCHMARKS.items():
        used = set(int(v) for v in t[table][col].dropna().unique())
        check(used == expected,
              f"(d) {table}[{col}] uses benchmarks {sorted(used)} "
              f"(expected {sorted(expected)})")

    print("\n" + "=" * 60)
    if failures:
        print(f"{len(failures)} check(s) FAILED")
        sys.exit(1)
    print("All checks passed")


if __name__ == "__main__":
    main()
