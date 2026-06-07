#!/usr/bin/env python3

import argparse
import io
import json
from pathlib import Path
import tarfile

import numpy as np
import h5py


NAME = 'daq_configs'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('hdf5_file', type=Path)
    ap.add_argument('config_dir', type=Path)
    ap.add_argument('--use-destination-dir', action='store_true',
                    help='Assume hdf5_file is a path relative to destination_dir_ from RUN_CONFIG.kson')
    args = ap.parse_args()

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='x:xz') as tarf:
        dirname = NAME + '.' + args.hdf5_file.stem
        tarf.add(args.config_dir, arcname=dirname)

    hdf5_file = args.hdf5_file
    if args.use_destination_dir:
        conf = json.load(open('RUN_CONFIG.json'))
        dest = conf['destination_dir_']
        hdf5_file = f'{dest}/{args.hdf5_file}'

    with h5py.File(hdf5_file, 'a') as h5f:
        data = np.frombuffer(buf.getvalue(), dtype=np.uint8)
        dset = h5f.create_dataset(NAME, data=data)
        # for convenience:
        dset.attrs['dirname'] = dirname


if __name__ == '__main__':
    main()
