from collections import OrderedDict
from operator import itemgetter
import csv

from misoc.interconnect.csr import CSRStatus, CSRStorage


def _get_csr_data(csv_file):
    csr_data = OrderedDict()
    with open(csv_file) as csv_file_f:
        csv_reader = csv.reader(csv_file_f)
        for name, address, length, ro in csv_reader:
            region_name, csr_name = name.split(".")
            address = int(address, 0)
            length = int(length, 0)
            if ro == "ro":
                ro = True
            elif ro == "rw":
                ro = False
            else:
                raise ValueError
            if region_name not in csr_data:
                csr_data[region_name] = []
            csr_data[region_name].append((csr_name, address, length, ro))
    return csr_data


def get_remote_csr_regions(offset, csv_file):
    busword = 32
    regions = []
    for region_name, csrs_info in _get_csr_data(csv_file).items():
        csrs_info = sorted(csrs_info, key=itemgetter(1))
        origin = csrs_info[0][1]
        next_address = origin
        csrs = []
        for csr_name, address, length, ro in csrs_info:
            if address != next_address:
                raise ValueError("CSRs are not contiguous")
            nr = (length + busword - 1)//busword
            next_address += nr*busword//8
            if ro:
                csr = CSRStatus(length, name=csr_name)
            else:
                csr = CSRStorage(length, name=csr_name)
            csrs.append(csr)
        regions.append((region_name, offset + origin, busword, csrs))
    return regions
