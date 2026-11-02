"""
HW5 - Wildcat Capital star schema checks (Parts A and B).

Proves in code that:
  1. Each table has the row count given in the handout
  2. Every primary key is unique and never blank
  3. Every foreign key matches a row in the table it points to (no orphans),
     and the only blank foreign key is fact_transactions[security_id] on cash rows
  4. Fact date columns match dim_date[date] (not dim_date[date_id])
  5. Each fact table's grain is unique

Run from the hw05 folder:
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

failures = []


def check(passed, message):
    """Print PASS/FAIL for one check and remember failures."""
    print(f"  [{'PASS' if passed else 'FAIL'}] {message}")
    if not passed:
        failures.append(message)


def load_tables():
    tables = {}
    for name in EXPECTED_ROWS:
        # Read dates as text so they compare exactly with dim_date[date];
        # keep zip codes as text so leading zeros are not lost
        tables[name] = pd.read_csv(
            DATA_DIR / f"{name}.csv",
            dtype={"zip_code": str, "date": str, "fee_date": str,
                   "snapshot_date": str, "txn_date": str},
        )
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

    print("\n5. Fact dates join to dim_date[date], not dim_date[date_id]")
    check(t["dim_date"]["date"].is_unique, "dim_date[date] is unique (valid one side)")
    for fact, col in [("fact_fees", "fee_date"),
                      ("fact_portfolio_snapshot", "snapshot_date"),
                      ("fact_transactions", "txn_date")]:
        as_id = pd.to_numeric(t[fact][col], errors="coerce").notna().any()
        check(not as_id, f"{fact}[{col}] holds calendar dates, not date_id integers")

    print("\n6. Fact grain is unique (Part B)")
    for fact, cols in GRAINS.items():
        dupes = t[fact].duplicated(subset=cols).sum()
        check(dupes == 0, f"{fact}: one row per {' + '.join(cols)} ({dupes} duplicates)")

    print("\n" + "=" * 60)
    if failures:
        print(f"{len(failures)} check(s) FAILED")
        sys.exit(1)
    print("All checks passed")


if __name__ == "__main__":
    main()
