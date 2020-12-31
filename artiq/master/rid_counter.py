import logging
import os
import tempfile
import re

logger = logging.getLogger(__name__)


class RIDCounter:
    """Monotonically incrementing counter for RIDs (experiment run ids).

    A cache is used, but if necessary, the last used rid will be determined
    from the given results directory.
    """

    def __init__(self, cache_filename="last_rid.pyon", results_dir="results"):
        self.cache_filename = cache_filename
        self.results_dir = results_dir
        self._next_rid = self._last_rid() + 1
        logger.debug("Next RID is %d", self._next_rid)

    def get(self):
        rid = self._next_rid
        self._next_rid += 1
        self._update_cache(rid)
        return rid

    def _last_rid(self):
        try:
            rid = self._last_rid_from_cache()
        except FileNotFoundError:
            logger.debug("Last RID cache not found, scanning results")
            rid = self._last_rid_from_results()
            self._update_cache(rid)
            return rid
        else:
            logger.debug("Using last RID from cache")
            return rid

    def _update_cache(self, rid):
        contents = str(rid) + "\n"
        directory = os.path.abspath(os.path.dirname(self.cache_filename))
        with tempfile.NamedTemporaryFile("w", dir=directory, delete=False
                                         ) as f:
            f.write(contents)
            tmpname = f.name
        os.replace(tmpname, self.cache_filename)

    def _last_rid_from_cache(self):
        with open(self.cache_filename, "r") as f:
            return int(f.read())

    def _last_rid_from_results(self):
        r = -1
        try:
            day_folders = os.listdir(self.results_dir)
        except:
            return r
        day_folders = filter(
            lambda x: re.fullmatch("\\d\\d\\d\\d-\\d\\d-\\d\\d", x),
            day_folders)
        for df in day_folders:
            day_path = os.path.join(self.results_dir, df)
            try:
                hm_folders = os.listdir(day_path)
            except:
                continue
            hm_folders = filter(lambda x: re.fullmatch("\\d\\d(-\\d\\d)?", x),
                                hm_folders)
            for hmf in hm_folders:
                hm_path = os.path.join(day_path, hmf)
                try:
                    h5files = os.listdir(hm_path)
                except:
                    continue
                for x in h5files:
                    m = re.fullmatch(
                        "(\\d\\d\\d\\d\\d\\d\\d\\d\\d)-.*\\.h5", x)
                    if m is None:
                        continue
                    rid = int(m.group(1))
                    if rid > r:
                        r = rid
        return r
