# RUN: %python -m artiq.compiler.testbench.jit %s

#
# Check various sret-ized return types integrate properly with try/finally, which lowers
# to `invoke` on the LLVM level (code adapted from GitHub #1506).
#

LIST = [1, 2]


def get_tuple():
    return (1, 2)


def get_list():
    return LIST


def get_range():
    return range(10)


def main():
    try:
        a, b = get_tuple()
        assert a == 1
        assert b == 2
    finally:
        pass

    try:
        for _ in get_list():
            pass
    finally:
        pass

    try:
        for _ in get_range():
            pass
    finally:
        pass


main()
