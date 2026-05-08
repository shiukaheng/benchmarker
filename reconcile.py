"""Reconcile job states with K8s workflows."""
import argparse

from sqlmodel import create_engine

from lib import run_reconciliation


def main():
    parser = argparse.ArgumentParser(description="Reconcile job states")
    parser.add_argument("--dry-run", action="store_true", help="Preview without executing")
    args = parser.parse_args()

    engine = create_engine("sqlite:///benchmark.db")
    run_reconciliation(engine, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
