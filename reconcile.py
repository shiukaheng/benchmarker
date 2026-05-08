"""Reconcile job states and execute pending work.

This script shows the two-step pattern:
1. PLAN: Examine current state, decide what actions are needed
2. EXECUTE: Perform the actions (launch workflows, update job status)
"""
import argparse

from kubernetes import client, config
from sqlmodel import create_engine

from lib.reconcile import plan_reconciliation, execute_reconciliation


def main():
    parser = argparse.ArgumentParser(description="Reconcile job states")
    parser.add_argument("--dry-run", action="store_true", help="Plan only, don't execute")
    args = parser.parse_args()

    engine = create_engine("sqlite:///benchmark.db")

    # Step 1: PLAN - Generate list of actions needed
    print("Planning reconciliation...")
    actions = plan_reconciliation(engine)

    if not actions:
        print("No actions needed.")
        return

    print(f"\nPlanned {len(actions)} actions:")
    for i, action in enumerate(actions, 1):
        prefix = "[DRY] " if args.dry_run else ""
        print(f"  {i}. {prefix}{action}")

    if args.dry_run:
        print("\n[DRY RUN] No changes committed")
        return

    # Step 2: EXECUTE - Perform the planned actions
    print("\nExecuting actions...")
    config.load_kube_config()
    api = client.CustomObjectsApi()
    execute_reconciliation(engine, actions, api)
    print("\nReconciliation complete.")


if __name__ == "__main__":
    main()
