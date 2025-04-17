"""Distributed Task Orchestration Demo"""
import argparse
from task_orch.session_coordinator import SessionCoordinator


parser = argparse.ArgumentParser(description="Distributed Task Orchestration Demo")
parser.add_argument("--session-id", type=str, required=True)
parser.add_argument("--tasks", nargs="+", required=True)
args = parser.parse_args()

coordinator = SessionCoordinator()
coordinator.run_session(args.session_id, args.tasks)
