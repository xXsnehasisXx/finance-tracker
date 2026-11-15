"""Helpers for the LIVE LangSmith tests: trace creation AND retrieval against the real LangSmith API."""
import datetime
import time

from common.observability import langsmith_api_key


class TraceCheck:
    def __init__(self):
        from langsmith import Client

        self.client = Client(api_key=langsmith_api_key())
        self.started = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5)

    def wait_for_run(self, project: str, name: str, timeout: float = 90, is_root: bool = True):
        """Polls LangSmith until a run called `name` created after this check started is retrievable from `project`."""
        deadline, last_error = time.time() + timeout, None
        while time.time() < deadline:
            self.client.flush()
            try:
                runs = list(self.client.list_runs(project_name=project, start_time=self.started, is_root=is_root, limit=50))
            except Exception as exc:  # noqa: BLE001  (project is created lazily by the first run)
                runs, last_error = [], exc
            hit = [r for r in runs if r.name == name]
            if hit:
                return hit[0]
            time.sleep(3)
        raise AssertionError(f"No LangSmith run '{name}' found in project '{project}' within {timeout}s (last error: {last_error})")

    def child_names(self, project: str, trace_id) -> set[str]:
        return {r.name for r in self.client.list_runs(project_name=project, trace_id=trace_id, is_root=False, limit=100)}
