from contextlib import contextmanager
import unittest
from pathlib import Path
import tempfile

from artiq import tools


# Helper to create temporary modules
# Very simplified version of CPython's
# Lib/test/test_importlib/util.py:create_modules
@contextmanager
def create_modules(*names):
    mapping = {}
    with tempfile.TemporaryDirectory() as temp_dir:
        mapping[".root"] = Path(temp_dir)

        for name in names:
            file_path = Path(temp_dir) / f"{name}.py"
            with file_path.open("w") as fp:
                print(f"_MODULE_NAME = {name!r}", file=fp)
            mapping[name] = file_path

        yield mapping


MODNAME = "modname"


class TestFileImport(unittest.TestCase):
    def test_import_and_prefix_is_present(self):
        prefix = "prefix_"
        with create_modules(MODNAME) as mods:
            mod = tools.file_import(str(mods[MODNAME]), prefix=prefix)
            self.assertEqual(prefix + MODNAME, mod.__name__)

    def test_can_import_from_same_level(self):
        m1_name, m2_name = "mod1", "mod2"
        with create_modules(m1_name, m2_name) as mods:
            with mods[m2_name].open("a") as fp:
                print(f"from {m1_name} import _MODULE_NAME as _M1_NAME", file=fp)

            mod1 = tools.file_import(str(mods[m1_name]))
            mod2 = tools.file_import(str(mods[m2_name]))

            self.assertEqual(mod2._M1_NAME, mod1._MODULE_NAME)


class TestGetExperiment(unittest.TestCase):
    def test_fail_no_experiments(self):
        with create_modules(MODNAME) as mods:
            mod = tools.file_import(str(mods[MODNAME]))
            with self.assertRaises(ValueError):
                tools.get_experiment(mod)

    def test_fail_hidden_experiment(self):
        with create_modules(MODNAME) as mods:
            with mods[MODNAME].open("a") as fp:
                print(
                    """
from artiq.experiment import *

class _Exp1(EnvExperiment):
    pass
                """,
                    file=fp,
                )

            mod = tools.file_import(str(mods[MODNAME]))
            with self.assertRaises(ValueError):
                tools.get_experiment(mod)

    def test_multiple_experiments(self):
        with create_modules(MODNAME) as mods:
            with mods[MODNAME].open("a") as fp:
                print(
                    """
from artiq.experiment import *

class Exp1(EnvExperiment):
    pass

class Exp2(EnvExperiment):
    pass
                """,
                    file=fp,
                )

            mod = tools.file_import(str(mods[MODNAME]))

            # by class name
            self.assertIs(mod.Exp1, tools.get_experiment(mod, "Exp1"))
            self.assertIs(mod.Exp2, tools.get_experiment(mod, "Exp2"))

            # by elimination should fail
            with self.assertRaises(ValueError):
                tools.get_experiment(mod)

    def test_single_experiment(self):
        with create_modules(MODNAME) as mods:
            with mods[MODNAME].open("a") as fp:
                print(
                    """
from artiq.experiment import *

class Exp1(EnvExperiment):
    pass
                """,
                    file=fp,
                )

            mod = tools.file_import(str(mods[MODNAME]))

            # by class name
            self.assertIs(mod.Exp1, tools.get_experiment(mod, "Exp1"))

            # by elimination
            self.assertIs(mod.Exp1, tools.get_experiment(mod))

    def test_nested_experiment(self):
        with create_modules(MODNAME) as mods:
            with mods[MODNAME].open("a") as fp:
                print(
                    """
from artiq.experiment import *

class Foo:
    class Exp1(EnvExperiment):
        pass
                """,
                    file=fp,
                )

            mod = tools.file_import(str(mods[MODNAME]))

            # by class name
            self.assertIs(mod.Foo.Exp1, tools.get_experiment(mod, "Foo.Exp1"))

            # by elimination should fail
            with self.assertRaises(ValueError):
                tools.get_experiment(mod)
