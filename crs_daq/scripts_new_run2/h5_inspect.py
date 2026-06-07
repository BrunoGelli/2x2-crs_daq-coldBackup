#!/usr/bin/env python3
import h5py, sys, numpy as np
from pathlib import Path

fn = sys.argv[1]
with h5py.File(fn, 'r') as f:
    print(f"\nFile: {Path(fn).name}")
    print("Top-level keys:", list(f.keys()))
    if 'packets' in f:
        ds = f['packets']
        print("\n[packets] shape:", ds.shape, "dtype:", ds.dtype)
        print("  chunks:", ds.chunks, "compression:", ds.compression, ds.compression_opts)
        # Show first 5 field names
        try:
            print("  fields:", [n for n,_ in ds.dtype.fields.items()][:10])
        except:
            pass
        # Quick counts by packet_type
        pt = ds['packet_type'][:]
        vals, cnts = np.unique(pt, return_counts=True)
        print("  packet_type counts:", dict(zip(vals.tolist(), cnts.tolist())))
