#!/usr/bin/env python3
"""
plot_std_from_files.py

Compute per-channel std from one dataset (many HDF5 files)
and display using the usual plot_metric_anode geometry.
"""

import argparse
from pathlib import Path
import csv

from analysis.plot_metric_anode import (
    plot_xy,
    _default_geometry_yaml,
    _default_geometry_yaml_mod2,
)

#from compare_std_diff import accumulate_file, merge_running_stats, stats_to_std
from .compare_std_diff import accumulate_file, merge_running_stats, stats_to_std

def write_topstd_csv(out_csv: Path, stds: dict, topn: int = 200):
    items = sorted(stds.items(), key=lambda kv: kv[1], reverse=True)[:topn]
    with out_csv.open('w', newline='') as fo:
        w = csv.writer(fo)
        w.writerow(['uid', 'std'])
        for uid, s in items:
            w.writerow([uid, s])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--files', nargs='+', required=True, help='HDF5 files for dataset')
    ap.add_argument('--min_hits', type=int, default=50, help='Per-channel minimum hits to keep')
    ap.add_argument('--norm', type=float, default=5.0,
                    help='Normalization for colorbar (metric/norm ∈ [0,1])')
    ap.add_argument('--geometry_yaml', type=str, default=_default_geometry_yaml)
    ap.add_argument('--geometry_yaml_mod2', type=str, default=_default_geometry_yaml_mod2)
    ap.add_argument('--outprefix', type=str, default='std_single')
    ap.add_argument('--max', type=int, default=-1, help='Max packets to read per file (-1 = all)')
    args = ap.parse_args()

    # accumulate per-file stats
    stats_all = []
    for f in args.files:
        s, _ = accumulate_file(f, max_entries=args.max)
        stats_all.append(s)

    merged = merge_running_stats(stats_all)
    stds = stats_to_std(merged, args.min_hits)

    # prepare dict for plotter
    d_for_plot = {u: {'std': stds[u]} for u in stds.keys()}

    # optional CSV
    outcsv = Path(f"{args.outprefix}_topstd.csv")
    write_topstd_csv(outcsv, stds, topn=200)
    print(f"Wrote top std CSV: {outcsv}")

    print("Plotting…")
    plot_xy(d_for_plot, "std", args.geometry_yaml, args.geometry_yaml_mod2, args.norm)
    outpng = Path("2x2-xy-std.png")
    if outpng.exists():
        renamed = Path(f"{args.outprefix}_2x2-xy-std.png")
        outpng.replace(renamed)
        print(f"Saved: {renamed}")

if __name__ == '__main__':
    main()
