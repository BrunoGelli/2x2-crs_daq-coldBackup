#!/usr/bin/env python3

import argparse
import io
from pathlib import Path
import tarfile

import h5py
import numpy as np

from embed_config import NAME


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('hdf5_file', type=Path)
    args = ap.parse_args()

    with h5py.File(args.hdf5_file) as h5f:
        buf = io.BytesIO(np.array(h5f[NAME]).data)

    with tarfile.open(fileobj=buf) as tarf:
        name = tarf.getmembers()[0].name
        if Path(name).exists():
            msg = f'Directory {name} already exists; not extracting, sorry'
            raise RuntimeError(msg)
        tarf.extractall()


if __name__ == '__main__':
    main()
