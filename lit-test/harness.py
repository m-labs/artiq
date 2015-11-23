"""
The purpose of this harness is to emulate the behavior of
the python executable, but add the ARTIQ root to sys.path
beforehand.

This is necessary because eggs override the PYTHONPATH environment
variable, but not current directory; therefore `python -m artiq...`
ran from the ARTIQ root would work, but there is no simple way to
emulate the same behavior when invoked under lit.
"""

import sys, os, argparse, importlib

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('-m', metavar='mod', type=str,
                    help='run library module as a script')
parser.add_argument('args', type=str, nargs='+',
                    help='arguments passed to program in sys.argv[1:]')
args = parser.parse_args(sys.argv[1:])

artiq_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(1, artiq_path)

if args.m:
    sys.argv[1:] = args.args
    importlib.import_module(args.m).main()
else:
    sys.argv[1:] = args.args[1:]
    with open(args.args[0]) as f:
        code = compile(f.read(), args.args[0], 'exec')
        exec(code)
