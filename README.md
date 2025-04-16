# Distributed Task Orchestration

Installation:

    poetry install --with test


Running a session:

    python -m task_orch --session-id mysession --tasks download_statements download_metadata update_profile


Running tests:

    pytest
