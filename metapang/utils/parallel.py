from concurrent.futures import ProcessPoolExecutor
from multiprocessing import BoundedSemaphore


class BoundedExecutorMixin:
    """Mixin that bounds an executor's queue to queue_size in-flight jobs."""

    def __init__(self, queue_size: int):
        self._semaphore = BoundedSemaphore(queue_size)

    def acquire(self):
        """Acquire a slot from the bounded queue, blocking if full."""
        self._semaphore.acquire()

    def release(self, _):
        """Release a slot back to the bounded queue."""
        self._semaphore.release()

    def submit(self, fn, *args, **kwargs):
        """Submit a job, blocking while the in-flight queue is full."""
        self._semaphore.acquire()
        future = super().submit(fn, *args, **kwargs)  # type: ignore[misc]
        future.add_done_callback(self.release)
        return future


class BoundedProcessPoolExecutor(BoundedExecutorMixin, ProcessPoolExecutor):
    """A ProcessPoolExecutor bounded to queue_size in-flight jobs."""

    def __init__(self, queue_size: int, **kwargs):
        BoundedExecutorMixin.__init__(self, queue_size)
        ProcessPoolExecutor.__init__(self, **kwargs)
