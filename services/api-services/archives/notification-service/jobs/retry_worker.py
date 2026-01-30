"""Background retry worker scaffold.

This is a placeholder. In production this would be a separate worker process consuming Redis streams or a broker.
"""
from time import sleep
from app.utils.queue import default_queue


def run_once():
    item = default_queue.pop()
    if not item:
        return False
    # placeholder: try to re-send (left as TODO)
    print("Retry worker would process:", item)
    return True


def run_loop(poll_interval: float = 5.0):
    while True:
        processed = run_once()
        if not processed:
            sleep(poll_interval)
