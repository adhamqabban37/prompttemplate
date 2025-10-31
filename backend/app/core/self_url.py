import os
import pathlib


def _in_container() -> bool:
    # Heuristic: /.dockerenv exists or cgroup mentions docker/containerd
    try:
        if pathlib.Path("/.dockerenv").exists():
            return True
    except Exception:
        pass
    try:
        with open("/proc/1/cgroup", "r") as f:
            data = f.read()
            return ("docker" in data) or ("containerd" in data)
    except Exception:
        return False


def get_self_base_url() -> str:
    """
    Return the correct base URL to call THIS backend from the orchestrator.
    - Inside a container: default http://127.0.0.1:8000 (container internal port)
    - Outside a container: default http://localhost:8001 (host-mapped port)

    Override with env vars:
    - INTERNAL_SELF_BASE_URL
    - EXTERNAL_SELF_BASE_URL
    """
    if _in_container():
        return os.getenv("INTERNAL_SELF_BASE_URL", "http://127.0.0.1:8000")
    return os.getenv("EXTERNAL_SELF_BASE_URL", "http://localhost:8001")
