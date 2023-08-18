import shutil
import os
import argparse
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", default=None, help="Variant name")
    parser.add_argument("-d", default="./artiq_kasli", help="path to built")
    parser.add_argument("-o", default=None, help="output zip (default: kasli-<variant>.zip")
    args = parser.parse_args()
    if not args.v:
        raise ValueError("need to specify variant!!")
    basepath = os.path.abspath(args.d)
    tempdir = os.path.join(basepath, "kasli-{}".format(args.v))
    try:
        os.mkdir(tempdir)
    except FileExistsError:
        pass
    shutil.copyfile(os.path.join(basepath, args.v, "gateware/top.bit"), os.path.join(tempdir, "top.bit"))
    shutil.copyfile(os.path.join(basepath, args.v, "software/bootloader/bootloader.bin"), os.path.join(tempdir, "bootloader.bin"))
    try:
        shutil.copyfile(os.path.join(basepath, args.v, "software/runtime/runtime.elf"), os.path.join(tempdir, "runtime.elf"))
        shutil.copyfile(os.path.join(basepath, args.v, "software/runtime/runtime.fbi"), os.path.join(tempdir, "runtime.fbi"))
    except FileNotFoundError:
        shutil.copyfile(os.path.join(basepath, args.v, "software/satman/satman.elf"), os.path.join(tempdir, "satman.elf"))
        shutil.copyfile(os.path.join(basepath, args.v, "software/satman/satman.fbi"), os.path.join(tempdir, "satman.fbi"))
    output = args.o if args.o else "kasli-{}".format(args.v)

    shutil.make_archive(output, "zip", tempdir)
    shutil.rmtree(tempdir)
    
if __name__ == "__main__":
    main()