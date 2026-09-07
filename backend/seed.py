"""Seed the demonstration dataset.

    python seed.py            # reset and reseed
    python seed.py --keep     # seed without clearing existing rows
"""

from __future__ import annotations

import argparse
import sys

from app.db.session import session_scope
from app.seeds.seeder import DemoSeeder


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the Nexgile WealthAgent demonstration dataset.")
    parser.add_argument("--keep", action="store_true", help="Do not clear existing data first.")
    args = parser.parse_args()

    with session_scope() as db:
        summary = DemoSeeder(db).run(reset=not args.keep)

    print("\nNexgile WealthAgent — demonstration dataset created\n")
    width = max(len(name) for name in summary["counts"])
    for name, count in summary["counts"].items():
        print(f"  {name.ljust(width)}  {count:>7,}")
    print(f"\n  {'TOTAL'.ljust(width)}  {summary['total_rows']:>7,} rows\n")

    print("Demo accounts (password: %s)" % summary["password"])
    for account in summary["demo_accounts"]:
        print(f"  {(account['label'] or account['role']).ljust(22)} {account['email']}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
