import time, cProfile as profile, pstats

def benchmark(f, name):
    profiler = profile.Profile()
    profiler.enable()

    start = time.perf_counter()
    end   = 0
    runs  = 0
    while end - start < 5 or runs < 10:
        f()
        runs += 1
        end = time.perf_counter()

    profiler.create_stats()

    print("{} {} runs: {:.2f}s, {:.2f}ms/run".format(
            runs, name, end - start, (end - start) / runs * 1000))

    stats = pstats.Stats(profiler)
    stats.strip_dirs().sort_stats('time').print_stats(10)
