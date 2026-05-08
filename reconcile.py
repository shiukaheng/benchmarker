"""Reconcile CLI - manages job state and launches workflows."""
import argparse
from sqlmodel import create_engine

from lib import run_reconciliation


def main():
    parser = argparse.ArgumentParser(description="Reconcile job states with K8s workflows")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be done without making changes")
    args = parser.parse_args()

    engine = create_engine("sqlite:///benchmark.db")
    run_reconciliation(engine, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
