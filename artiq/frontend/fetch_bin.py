import atexit
import os
import tempfile

from artiq.frontend.bit2bin import bit2bin


def fetch_bin(binary_dir, component, srcbuild=False):
    def artifact_path(this_binary_dir, *path_filename):
        if srcbuild:
            # source tree - use path elements to locate file
            return os.path.join(this_binary_dir, *path_filename)
        else:
            # flat tree - all files in the same directory, discard path elements
            *_, filename = path_filename
            return os.path.join(this_binary_dir, filename)

    def convert_gateware(bit_filename):
        bin_handle, bin_filename = tempfile.mkstemp(
            prefix="artiq_", suffix="_" + os.path.basename(bit_filename))
        with open(bit_filename, "rb") as bit_file, open(bin_handle, "wb") as bin_file:
            bit2bin(bit_file, bin_file)
        atexit.register(lambda: os.unlink(bin_filename))
        return bin_filename

    if type(component) == list:
        bins = []
        for option in component:
            try:
                bins.append(fetch_bin(binary_dir, option, srcbuild))
            except FileNotFoundError:
                pass

        if bins is None:
            raise FileNotFoundError("multiple components not found: {}".format(
                                        " ".join(component)))
        
        if len(bins) > 1:
            raise ValueError("more than one file, "
                             "please clean up your build directory. "
                             "Found files: {}".format(
                             " ".join(bins)))

        return bins[0]

    path = artifact_path(binary_dir, *{
        "gateware": ["gateware", "top.bit"],
        "bootloader": ["software", "bootloader", "bootloader.bin"],
        "runtime": ["software", "runtime", "runtime.fbi"],
        "satman": ["software", "satman", "satman.fbi"],
    }[component])

    if not os.path.exists(path):
        raise FileNotFoundError("{} not found".format(component))

    if component == "gateware":
        path = convert_gateware(path)

    return path
