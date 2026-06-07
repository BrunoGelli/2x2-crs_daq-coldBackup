#!/usr/bin/env python3
"""
compare_std_diff.py

Compute per-channel std difference between two datasets (each given as many HDF5 files),
then display "the usual way" using analysis.plot_metric_anode.plot_xy.

Usage example:
  python analysis/compare_std_diff.py \
      --filesA /data/runA/*.h5 \
      --filesB /data/runB/*.h5 \
      --abs \
      --norm 5 \
      --outprefix std_diff_runB_minus_runA

Notes:
- By default we plot |std_B - std_A| (non-negative) to be compatible with the existing plotter.
- Use --signed if you want signed differences (negative values will be clipped by the plotter).
"""

import argparse
import h5py
import numpy as np
import csv
from pathlib import Path
from typing import Dict, Tuple, Iterable

# Import geometry plotter & helpers from your existing script
from analysis.plot_metric_anode import (
    plot_xy,
    _default_geometry_yaml,
    _default_geometry_yaml_mod2,
)

def unique_channel_id(view):
    # matches your plot_metric_anode.py
    return ((view['io_group'].astype(np.int64) * 1000 + view['io_channel'].astype(np.int64)) * 1000
            + view['chip_id'].astype(np.int64)) * 100 + view['channel_id'].astype(np.int64)

def accumulate_file(fname: str,
                    max_entries: int = -1) -> Tuple[Dict[int, Tuple[int, float, float]], float]:
    """
    Return:
      stats: dict[uid] = (count, sum, sumsq) for data packets with valid parity
      livetime: seconds computed from packet_type==4 timestamps (if present; 0 if missing)
    """
    stats: Dict[int, Tuple[int, float, float]] = {}
    with h5py.File(fname, 'r') as f:
        pk = f['packets']
        n = pk.shape[0] if max_entries < 0 else min(max_entries, pk.shape[0])

        view = pk[:n]
        # livetime from sync (packet_type==4) if available
        ts = view['timestamp'][view['packet_type'] == 4]
        livetime = float(np.max(ts) - np.min(ts)) if ts.size else 0.0

        mask = (view['packet_type'] == 0) & (view['valid_parity'] == 1)
        if not np.any(mask):
            return stats, livetime

        adc = view['dataword'][mask].astype(np.float32)
        uid = unique_channel_id(view[mask])

        # group by uid via sort + reduceat
        order = np.argsort(uid, kind='mergesort')
        uid_s = uid[order]
        adc_s = adc[order]

        starts = np.concatenate(([0], np.flatnonzero(np.diff(uid_s)) + 1))
        ends = np.concatenate((starts[1:], [uid_s.size]))
        counts = ends - starts

        sums = np.add.reduceat(adc_s.astype(np.float64), starts)
        sumsq = np.add.reduceat((adc_s * adc_s).astype(np.float64), starts)
        uniques = uid_s[starts]

        # pack into dict (as Python types to be JSON/CSV friendly later)
        for u, c, s, ss in zip(uniques.tolist(),
                                counts.astype(int).tolist(),
                                sums.astype(float).tolist(),
                                sumsq.astype(float).tolist()):
            stats[u] = (c, s, ss)

    return stats, livetime

def merge_running_stats(dicts: Iterable[Dict[int, Tuple[int, float, float]]]) -> Dict[int, Tuple[int, float, float]]:
    """
    Sum (count, sum, sumsq) across files for each uid.
    """
    out: Dict[int, Tuple[int, float, float]] = {}
    for d in dicts:
        for u, (c, s, ss) in d.items():
            C, S, SS = out.get(u, (0, 0.0, 0.0))
            out[u] = (C + c, S + s, SS + ss)
    return out

def stats_to_std(stats: Dict[int, Tuple[int, float, float]],
                 min_hits: int) -> Dict[int, float]:
    """
    Convert running stats to std per uid; drop channels with count < min_hits.
    """
    stds: Dict[int, float] = {}
    for u, (c, s, ss) in stats.items():
        if c < min_hits:
            continue
        mean = s / c
        var = ss / c - mean * mean
        if var < 0:
            var = 0.0
        stds[u] = float(np.sqrt(var))
    return stds

def write_topdiff_csv(out_csv: Path,
                      diffs: Dict[int, float],
                      topn: int = 200):
    """
    Save top-|diff| channels for quick inspection.
    """
    items = sorted(diffs.items(), key=lambda kv: abs(kv[1]), reverse=True)[:topn]
    with out_csv.open('w', newline='') as fo:
        w = csv.writer(fo)
        w.writerow(['uid', 'std_diff'])
        for uid, d in items:
            w.writerow([uid, d])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--filesA', nargs='+', required=True, help='HDF5 files for dataset A')
    ap.add_argument('--filesB', nargs='+', required=True, help='HDF5 files for dataset B')
    ap.add_argument('--min_hits', type=int, default=50, help='Per-channel minimum hits to keep (default: 50)')
    ap.add_argument('--abs', dest='use_abs', action='store_true',
                    help='Plot absolute difference |std_B - std_A| (default for compatibility)')
    ap.add_argument('--signed', dest='use_abs', action='store_false',
                    help='Plot signed difference std_B - std_A (negative values will be clipped by the plotter)')
    ap.set_defaults(use_abs=True)
    ap.add_argument('--norm', type=float, default=5.0,
                    help='Normalization for colorbar (plotter maps metric/norm ∈ [0,1])')
    ap.add_argument('--geometry_yaml', type=str, default=_default_geometry_yaml)
    ap.add_argument('--geometry_yaml_mod2', type=str, default=_default_geometry_yaml_mod2)
    ap.add_argument('--outprefix', type=str, default='std_diff')
    ap.add_argument('--max', type=int, default=-1, help='Max packets to read per file (-1 = all)')
    args = ap.parse_args()

    # Accumulate per-file stats
    stats_As = []
    for f in args.filesA:
        sA, _ = accumulate_file(f, max_entries=args.max)
        stats_As.append(sA)
    stats_Bs = []
    for f in args.filesB:
        sB, _ = accumulate_file(f, max_entries=args.max)
        stats_Bs.append(sB)

    # Merge across files in each dataset
    merged_A = merge_running_stats(stats_As)
    merged_B = merge_running_stats(stats_Bs)

    # Convert to std, with a hit-count floor
    std_A = stats_to_std(merged_A, args.min_hits)
    std_B = stats_to_std(merged_B, args.min_hits)

    # Intersect uids present in both (with enough hits)
    uids = sorted(set(std_A.keys()) & set(std_B.keys()))
    diffs = {u: (std_B[u] - std_A[u]) for u in uids}
    if args.use_abs:
        diffs = {u: abs(v) for u, v in diffs.items()}

    # Prepare dict for the existing plotter: expect d[uid]['std'] as the metric
    d_for_plot = {u: {'std': diffs[u]} for u in diffs.keys()}

    # CSV of biggest changes
    outcsv = Path(f"{args.outprefix}_topdiff.csv")
    write_topdiff_csv(outcsv, diffs, topn=200)
    print(f"Wrote top-|diff| CSV: {outcsv}")

    # Plot using your existing geometry plotter
    # NOTE: colorbar label will say [ADC] (fine), and values are clipped at 'norm'
    print("Plotting…")
    plot_xy(d_for_plot, "std", args.geometry_yaml, args.geometry_yaml_mod2, args.norm)
    # plot_xy saves to 2x2-xy-std.png by its own logic; rename for clarity
    outpng = Path("2x2-xy-std.png")
    if outpng.exists():
        renamed = Path(f"{args.outprefix}_2x2-xy-std.png")
        outpng.replace(renamed)
        print(f"Saved: {renamed}")
    else:
        print("Warning: expected 2x2-xy-std.png not found; check plotter output.")

if __name__ == '__main__':
    main()
