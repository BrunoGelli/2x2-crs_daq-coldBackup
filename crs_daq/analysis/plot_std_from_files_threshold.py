#!/usr/bin/env python3
"""
plot_std_from_files.py

Compute per-channel std from one dataset (many HDF5 files)
and display a PASS/NO-PASS map using the usual plot_metric_anode geometry.

PASS  -> std <= threshold  -> value = 0   (plots white)
NO-PASS -> std > threshold -> value = norm (plots red/saturated)
"""

import argparse
from pathlib import Path
import csv

from analysis.plot_metric_anode import (
    plot_xy,
    _default_geometry_yaml,
    _default_geometry_yaml_mod2,
)

# from compare_std_diff import accumulate_file, merge_running_stats, stats_to_std
from .compare_std_diff import accumulate_file, merge_running_stats, stats_to_std


def write_noisy_lists(out_prefix: str, stds: dict, threshold: float) -> int:
    """Write lists of channels with std > threshold."""
    noisy_items = [(u, s) for u, s in stds.items() if s > threshold]
    noisy_items.sort(key=lambda kv: kv[1], reverse=True)

    out_csv = Path(f"{out_prefix}_noisy.csv")
    with out_csv.open("w", newline="") as fo:
        w = csv.writer(fo)
        w.writerow(["uid", "std"])
        for uid, s in noisy_items:
            w.writerow([uid, s])

    out_txt = Path(f"{out_prefix}_noisy.txt")
    with out_txt.open("w") as fo:
        for uid, _ in noisy_items:
            fo.write(f"{uid}\n")

    return len(noisy_items)


def write_topstd_csv(out_csv: Path, stds: dict, topn: int = 200):
    items = sorted(stds.items(), key=lambda kv: kv[1], reverse=True)[:topn]
    with out_csv.open("w", newline="") as fo:
        w = csv.writer(fo)
        w.writerow(["uid", "std"])
        for uid, s in items:
            w.writerow([uid, s])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", nargs="+", required=True, help="HDF5 files for dataset")
    ap.add_argument("--min_hits", type=int, default=50, help="Per-channel minimum hits to keep")
    ap.add_argument("--norm", type=float, default=5.0,
                    help="Normalization for colorbar (metric/norm ∈ [0,1])")
    ap.add_argument("--threshold", type=float, default=2.0,
                    help="STD threshold in ADC for NO-PASS")
    ap.add_argument("--geometry_yaml", type=str, default=_default_geometry_yaml)
    ap.add_argument("--geometry_yaml_mod2", type=str, default=_default_geometry_yaml_mod2)
    ap.add_argument("--outprefix", type=str, default="std_passfail")
    ap.add_argument("--max", type=int, default=-1, help="Max packets to read per file (-1 = all)")
    args = ap.parse_args()

    # accumulate per-file stats
    stats_all = []
    for f in args.files:
        s, _ = accumulate_file(f, max_entries=args.max)
        stats_all.append(s)

    merged = merge_running_stats(stats_all)
    stds = stats_to_std(merged, args.min_hits)

    # PASS/NO-PASS map: 0 for pass, norm for fail
    # Keep a separate dict with raw stds for saving lists/CSV.
    passfail = {}
    for u, s in stds.items():
        passfail[u] = args.norm if s > args.threshold else 0.0

    # Prepare dict for plotter
    d_for_plot = {u: {"passfail": passfail[u]} for u in passfail.keys()}

    # Optional CSV of top std (still handy for debugging)
    outcsv = Path(f"{args.outprefix}_topstd.csv")
    write_topstd_csv(outcsv, stds, topn=200)
    print(f"Wrote top std CSV: {outcsv}")

    # Noisy channel lists
    n_noisy = write_noisy_lists(args.outprefix, stds, args.threshold)
    print(f"Noisy channels (std > {args.threshold:.3f} ADC): {n_noisy} "
          f"→ {args.outprefix}_noisy.csv / {args.outprefix}_noisy.txt")

    # Plot
    print("Plotting PASS/NO-PASS…")
    plot_xy(d_for_plot, "passfail", args.geometry_yaml, args.geometry_yaml_mod2, args.norm)

    outpng = Path("2x2-xy-passfail.png")
    # Some plotters may still write "2x2-xy-passfail.png" or default to metric name;
    # if your plotter always writes "2x2-xy-<metric>.png", adjust below accordingly.
    if outpng.exists():
        renamed = Path(f"{args.outprefix}_2x2-xy-passfail.png")
        outpng.replace(renamed)
        print(f"Saved: {renamed}")
    else:
        # Fallback if the underlying plotter uses the metric in filename:
        candidate = Path("2x2-xy-passfail.png")
        if candidate.exists():
            renamed = Path(f"{args.outprefix}_2x2-xy-passfail.png")
            candidate.replace(renamed)
            print(f"Saved: {renamed}")
        else:
            # As a last resort, try the older std filename pattern:
            legacy = Path("2x2-xy-std.png")
            if legacy.exists():
                renamed = Path(f"{args.outprefix}_2x2-xy-passfail.png")
                legacy.replace(renamed)
                print(f"Saved (legacy name): {renamed}")
            else:
                print("Note: Could not find output PNG to rename. "
                      "Check plot_metric_anode filename behavior.")

if __name__ == "__main__":
    main()
