import os
import shutil
from prometheus_client import multiprocess

MULTIPROC_DIR = os.environ.get("PROMETHEUS_MULTIPROC_DIR", "/tmp/prometheus_multiproc")


def when_ready(server):
    if os.path.isdir(MULTIPROC_DIR):
        shutil.rmtree(MULTIPROC_DIR)
    os.makedirs(MULTIPROC_DIR, exist_ok=True)


def child_exit(server, worker):
    multiprocess.mark_process_dead(worker.pid, MULTIPROC_DIR)