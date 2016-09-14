import threading
import logging
import inspect


logger = logging.getLogger(__name__)


class FFProxy:
    """Proxies a target object and runs its methods in the background.

    All method calls to this object are forwarded to the target and executed
    in a background thread. Method calls return immediately. Exceptions from
    the target method are turned into warnings. At most one method from the
    target object may be executed in the background; if a new call is
    submitted while the previous one is still executing, a warning is printed
    and the new call is dropped.

    This feature is typically used to wrap slow and non-critical RPCs in
    experiments.
    """
    def __init__(self, target):
        self.target = target

        valid_methods = inspect.getmembers(target, inspect.ismethod)
        self._valid_methods = {m[0] for m in valid_methods}
        self._thread = None

    def ff_join(self):
        """Waits until any background method finishes its execution."""
        if self._thread is not None:
            self._thread.join()

    def __getattr__(self, k):
        if k not in self._valid_methods:
            raise AttributeError
        def run_in_thread(*args, **kwargs):
            if self._thread is not None and self._thread.is_alive():
                logger.warning("skipping fire-and-forget call to %r.%s as "
                               "previous call did not complete",
                               self.target, k)
                return
            def thread_body():
                try:
                    getattr(self.target, k)(*args, **kwargs)
                except:
                    logger.warning("fire-and-forget call to %r.%s raised an "
                                   "exception:", self.target, k, exc_info=True)
            self._thread = threading.Thread(target=thread_body)
            self._thread.start()
        return run_in_thread
