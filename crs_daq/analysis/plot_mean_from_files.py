#!/usr/bin/env python3
"""
plot_mean_from_files.py

Compute per-channel mean from one dataset (many HDF5 files)
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

from .compare_std_diff import accumulate_file, merge_running_stats, stats_to_mean
# If stats_to_mean is not available, see fallback note below.

def write_topmean_csv(out_csv: Path, means: dict, topn: int = 200):
    items = sorted(means.items(), key=lambda kv: kv[1], reverse=True)[:topn]
    with out_csv.open('w', newline='') as fo:
        w = csv.writer(fo)
        w.writerow(['uid', 'mean'])
        for uid, m in items:
            w.writerow([uid, m])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--files', nargs='+', required=True, help='HDF5 files for dataset')
    ap.add_argument('--min_hits', type=int, default=50, help='Per-channel minimum hits to keep')
    ap.add_argument('--norm', type=float, default=5.0,
                    help='Normalization for colorbar (metric/norm ∈ [0,1])')
    ap.add_argument('--geometry_yaml', type=str, default=_default_geometry_yaml)
    ap.add_argument('--geometry_yaml_mod2', type=str, default=_default_geometry_yaml_mod2)
    ap.add_argument('--outprefix', type=str, default='mean_single')
    ap.add_argument('--max', type=int, default=-1, help='Max packets to read per file (-1 = all)')
    args = ap.parse_args()

    # accumulate per-file stats
    stats_all = []
    for f in args.files:
        s, _ = accumulate_file(f, max_entries=args.max)
        stats_all.append(s)

    merged = merge_running_stats(stats_all)

    # Compute means
    means = stats_to_mean(merged, args.min_hits)

    # prepare dict for plotter (metric key must match the string passed to plot_xy)
    d_for_plot = {u: {'mean': means[u]} for u in means.keys()}

    # optional CSV
    outcsv = Path(f"{args.outprefix}_topmean.csv")
    write_topmean_csv(outcsv, means, topn=200)
    print(f"Wrote top mean CSV: {outcsv}")

    print("Plotting…")
    plot_xy(d_for_plot, "mean", args.geometry_yaml, args.geometry_yaml_mod2, args.norm)
    outpng = Path("2x2-xy-mean.png")
    if outpng.exists():
        renamed = Path(f"{args.outprefix}_2x2-xy-mean.png")
        outpng.replace(renamed)
        print(f"Saved: {renamed}")

if __name__ == '__main__':
    main()
