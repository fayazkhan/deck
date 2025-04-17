import unittest
import unittest.mock
import threading

from task_orch.session_coordinator import SessionCoordinator, StateStore, SessionState, TaskWorker, TaskState


class TestSessionCoordinator(unittest.TestCase):
    def setUp(self):
        self.state_store = StateStore()

    def test_successful_run(self):
        session_id = "test1"
        tasks = ["download_statements", "download_metadata", "update_profile"]
        coordinator = SessionCoordinator(state_store=self.state_store, task_template=unittest.mock.Mock())
        final_state, task_states = coordinator.run_session(session_id, tasks)
        self.assertEqual(final_state, SessionState.COMPLETED)
        self.assertEqual(set(task_states.keys()), set(tasks + ["AUTHENTICATE", "DISCONNECT"]))

    def test_task_failure(self):
        session_id = "test2"
        tasks = ["download_statements", "download_metadata", "update_profile"]
        coordinator = SessionCoordinator(
            state_store=self.state_store, task_template=unittest.mock.Mock(side_effect=Exception("Task failed")))
        final_state, task_states = coordinator.run_session(session_id, tasks)
        self.assertEqual(final_state, SessionState.FAILED)

    def test_authenticate_failure(self):
        session_id = "test3"
        tasks = ["download_statements"]
        def task_template(session_id, task_name):
            if task_name == "AUTHENTICATE":
                raise Exception("Auth failed")
        coordinator = SessionCoordinator(
            state_store=self.state_store, task_template=task_template)
        final_state, task_states = coordinator.run_session(session_id, tasks)
        self.assertEqual(final_state, SessionState.FAILED)
        self.assertEqual(task_states["AUTHENTICATE"], TaskState.FAILED)
        self.assertEqual(task_states["download_statements"], TaskState.SKIPPED)
        # Ensure that DISCONNECT is still completed.
        self.assertEqual(task_states["DISCONNECT"], TaskState.SUCCESS)


class TestTaskWorker(unittest.TestCase):
    def setUp(self):
        self.barrier = threading.Barrier(1)
        self.state_store = StateStore()
        self.state_store.create_session("test_session", ["test_worker"])

    def test_timeout_handling(self):
        self.barrier.abort()
        task_worker = TaskWorker(
            name="test_worker", start_barrier=self.barrier, state_store=self.state_store, session_id="test_session")
        task_worker.run()
        self.assertEqual(self.state_store.get_task_state("test_session", "test_worker"), TaskState.TIMEOUT)

    def test_task_failure_handling(self):
        task_worker = TaskWorker(
            name="test_worker", start_barrier=self.barrier, state_store=self.state_store, session_id="test_session",
            task=unittest.mock.Mock(side_effect=Exception("Task failed")))
        task_worker.run()
        self.assertEqual(self.state_store.get_task_state("test_session", "test_worker"), TaskState.FAILED)
