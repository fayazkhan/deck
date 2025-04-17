"""Dummy tasks for testing the task orchestration system."""
import random
import time


def dummy_task(session_id, task_name):
    print(f"Running task {task_name} for session {session_id}")
    time.sleep(random.uniform(1, 3))  # Simulate work
    # Randomly fail or timeout for demonstration
    if random.random() < 0.3:
        raise Exception("Simulated failure")
    print(f"Task {task_name} completed for session {session_id}")
