import os
import tempfile


class ResultsLocator:
    """Locates the path to save archived data at."""

    def __init__(self, cache_filename="results_path.pyon"):
        self.cache_filename = cache_filename

    def get(self):
        return self._results_path_from_cache()

    def set(self, results_path):
        self._update_cache(results_path)

    def _update_cache(self, results_path):
        contents = os.path.normpath(results_path)
        directory = os.path.abspath(os.path.dirname(self.cache_filename))
        with tempfile.NamedTemporaryFile("w", dir=directory, delete=False
                                         ) as f:
            f.write(contents)
            tmpname = f.name
        os.replace(tmpname, self.cache_filename)

    def _results_path_from_cache(self):
        with open(self.cache_filename, "r") as f:
            return f.read()
