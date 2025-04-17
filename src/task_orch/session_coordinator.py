"""
Orchestrates and manages tasks within a session.
It includes classes and utilities to define task states, session states, and coordinate 
the execution of tasks using threading. The module is designed to handle task dependencies, 
timeouts, and failures gracefully.

Usage:
    - Define tasks and their dependencies using the `SessionCoordinator` class.
    - Use the `StateStore` to track the progress and state of tasks and sessions.
    - Implement custom task logic by providing a task function to the `TaskWorker`.
Example:
    coordinator = SessionCoordinator()
    session_id = "session_1"
    tasks = ["TASK_1", "TASK_2", "TASK_3"]
    session_state, task_states = coordinator.run_session(session_id, tasks)
"""
import threading
from enum import Enum, auto

from task_orch.dummy_tasks import dummy_task


class SessionCoordinator:
    """Coordinates the execution of tasks within a session."""
    def __init__(
            self, state_store=None, task_template=dummy_task):
        self.task_template = task_template
        self.state_store = state_store or StateStore()

    def run_session(self, session_id, tasks):
        print(f"Session {session_id} starting with tasks: {tasks}")
        self.state_store.create_session(session_id, tasks)
        
        authenticated = threading.Barrier(len(tasks) + 1)
        completed = threading.Barrier(len(tasks) + 1)

        # Start all task workers
        workers = [
            TaskWorker(
                name="AUTHENTICATE", session_id=session_id, state_store=self.state_store, task=self.task_template,
                end_barrier=authenticated  # Signal when authentication is done
            ),
            TaskWorker(
                name="DISCONNECT", session_id=session_id, state_store=self.state_store, task=self.task_template,
                start_barrier=completed,  # This task will wait for all others to finish
                always_run=True  # DISCONNECT should always run even if others fail
            )
        ] + [
            TaskWorker(
                name=task, session_id=session_id, state_store=self.state_store, task=self.task_template,
                start_barrier=authenticated,  # Wait for authentication to complete
                end_barrier=completed  # Signal when task is done
            )
            for task in tasks
        ]
        self.state_store.set_session_state(session_id, SessionState.RUNNING)
        print(f"Session {session_id}: Starting all tasks.")
        for w in workers:
            w.start()
        # Wait for all tasks to complete
        for w in workers:
            w.join(timeout=15)

        # Final session state
        if self.state_store.any_task_failed(session_id):
            self.state_store.set_session_state(session_id, SessionState.FAILED)
            print(f"Session {session_id}: One or more tasks failed or timed out.")
        else:
            self.state_store.set_session_state(session_id, SessionState.COMPLETED)
            print(f"Session {session_id}: Session completed successfully.")

        # Print final states
        print(f"Session {session_id} final state: {self.state_store.get_session_state(session_id)}")
        print(f"Session {session_id} task states: {self.state_store.get_all_task_states(session_id)}")
        return self.state_store.get_session_state(session_id), self.state_store.get_all_task_states(session_id)


class TaskState(Enum):
    """Enum representing the state of a task."""
    PENDING = auto()
    RUNNING = auto()
    SUCCESS = auto()
    FAILED = auto()
    TIMEOUT = auto()
    SKIPPED = auto()


class SessionState(Enum):
    """Enum representing the state of a session."""
    INIT = auto()
    RUNNING = auto()
    FAILED = auto()
    COMPLETED = auto()


class TaskWorker(threading.Thread):
    """Thread worker for executing tasks within a session."""
    def __init__(self, *, name, session_id, start_barrier=None, end_barrier=None, state_store=None, always_run=False, timeout=10, task=dummy_task):
        super().__init__(name=name)
        self.name = name
        self.start_barrier = start_barrier or threading.Barrier(1)
        self.end_barrier = end_barrier or threading.Barrier(1)
        self.state_store = state_store
        self.always_run = always_run
        self.session_id = session_id
        self.timeout = timeout
        self.task = task

    def run(self):
        try:
            self.start_barrier.wait(timeout=self.timeout)
            if not self.always_run and self.state_store.any_task_failed(self.session_id):
                self.state_store.set_task_state(self.session_id, self.name, TaskState.SKIPPED)
                return
            self.state_store.set_task_state(self.session_id, self.name, TaskState.RUNNING)
            self.task(self.session_id, self.name)
            self.state_store.set_task_state(self.session_id, self.name, TaskState.SUCCESS)
        except threading.BrokenBarrierError:
            self.state_store.set_task_state(self.session_id, self.name, TaskState.TIMEOUT)
        except Exception as e:
            print(f"Task {self.name} failed with exception: {e}")
            self.state_store.set_task_state(self.session_id, self.name, TaskState.FAILED)
        finally:
            self.end_barrier.wait(timeout=self.timeout)


class StateStore:
    """Thread-safe store for managing session and task states."""
    def __init__(self):
        self.sessions = {}
        self.lock = threading.Lock()

    def create_session(self, session_id, tasks):
        """Create a new session with the given ID and tasks."""
        with self.lock:
            self.sessions[session_id] = {
                'state': SessionState.INIT,
                'tasks': {t: TaskState.PENDING for t in tasks}
            }

    def set_session_state(self, session_id, state):
        """Set the state of a session."""
        with self.lock:
            self.sessions[session_id]['state'] = state

    def set_task_state(self, session_id, task, state):
        """Set the state of a task within a session."""
        with self.lock:
            self.sessions[session_id]['tasks'][task] = state

    def get_task_state(self, session_id, task):
        """Get the state of a task within a session."""
        with self.lock:
            return self.sessions[session_id]['tasks'][task]

    def get_all_task_states(self, session_id):
        """Get the states of all tasks within a session."""
        with self.lock:
            return dict(self.sessions[session_id]['tasks'])

    def get_session_state(self, session_id):
        """Get the state of a session."""
        with self.lock:
            return self.sessions[session_id]['state']

    def any_task_failed(self, session_id):
        """Check if any task in the session has failed or timed out."""
        with self.lock:
            return any(
                s in (TaskState.FAILED, TaskState.TIMEOUT, TaskState.SKIPPED)
                for s in self.sessions[session_id]['tasks'].values()
            )
