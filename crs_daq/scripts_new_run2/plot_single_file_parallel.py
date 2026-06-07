#!/usr/bin/env python3
"""
plot_single_file_parallel.py

Open ONE LArPix HDF5 file, compute per-channel metrics (mean/std/rate) in parallel,
and plot using the existing geometry plotter from analysis.plot_metric_anode.

Examples:
  # std only (default), 6 workers, 5e6 rows/chunk
  python -m analysis.plot_single_file_parallel \
      --file /data/myrun.h5 \
      --workers 6 --chunk_rows 5000000 \
      --outprefix run_std --norm_std 5

  # mean + std + rate
  python -m analysis.plot_single_file_parallel \
      --file /data/myrun.h5 \
      --metrics mean,std,rate \
      --outprefix run_all --norm_mean 50 --norm_std 5 --norm_rate 10
"""

import argparse
import math
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import numpy as np
import h5py
import sys

# --- import the existing plotter (works both as package or direct script) ---
try:
    from .plot_metric_anode import (
        plot_xy,
        _default_geometry_yaml,
        _default_geometry_yaml_mod2,
    )
except Exception:
    # fallback: allow running as a plain script from repo root
    import pathlib as _pl
    sys.path.append(str(_pl.Path(__file__).resolve().parents[1]))
    from analysis.plot_metric_anode import (
        plot_xy,
        _default_geometry_yaml,
        _default_geometry_yaml_mod2,
    )


def unique_channel_id(view):
    """Same definition as your other scripts."""
    return ((view['io_group'].astype(np.int64) * 1000 + view['io_channel'].astype(np.int64)) * 1000
            + view['chip_id'].astype(np.int64)) * 100 + view['channel_id'].astype(np.int64)


def _process_chunk(args):
    """
    Worker: read a slice [start:stop) from 'packets', compute running stats per uid,
    and min/max sync timestamps for livetime.
    Returns: (dict{uid:(count,sum,sumsq)}, p4_min_ts or None, p4_max_ts or None)
    """
    filename, start, stop = args
    stats = {}
    p4_min = None
    p4_max = None

    with h5py.File(filename, 'r') as f:
        pk = f['packets']
        sl = pk[start:stop]

        # livetime from packet_type==4 timestamps
        ts = sl['timestamp'][sl['packet_type'] == 4]
        if ts.size:
            p4_min = int(ts.min())
            p4_max = int(ts.max())

        # data packets with valid parity
        mask = (sl['packet_type'] == 0) & (sl['valid_parity'] == 1)
        if not np.any(mask):
            return stats, p4_min, p4_max

        view = sl[mask]
        uid = unique_channel_id(view)
        adc = view['dataword'].astype(np.float32)

        # group by uid via sort + reduceat
        order = np.argsort(uid, kind='mergesort')
        uid_s = uid[order]
        adc_s = adc[order]

        starts = np.concatenate(([0], np.flatnonzero(np.diff(uid_s)) + 1))
        ends = np.concatenate((starts[1:], [uid_s.size]))
        counts = ends - starts

        sums = np.add.reduceat(adc_s.astype(np.float64), starts)
        sumsq = np.add.reduceat((adc_s * adc_s).astype(np.float64), starts)
        uids = uid_s[starts]

        # convert to small python types for pickling
        for u, c, s, ss in zip(uids.tolist(),
                                counts.astype(int).tolist(),
                                sums.astype(float).tolist(),
                                sumsq.astype(float).tolist()):
            stats[int(u)] = (int(c), float(s), float(ss))

    return stats, p4_min, p4_max


def _merge_stats(partials):
    """Sum (count,sum,sumsq) across partial dicts."""
    out = {}
    for d in partials:
        for u, (c, s, ss) in d.items():
            C, S, SS = out.get(u, (0, 0.0, 0.0))
            out[u] = (C + c, S + s, SS + ss)
    return out


def _finalize_metrics(global_stats, livetime, min_hits):
    """
    From (count,sum,sumsq) → per-uid metrics dicts.
    Returns: means, stds, rates (dicts keyed by uid). 'rates' empty if livetime<=0.
    """
    means, stds, rates = {}, {}, {}
    for u, (c, s, ss) in global_stats.items():
        if c < min_hits:
            continue
        mean = s / c
        var = ss / c - mean * mean
        if var < 0:
            var = 0.0
        std = float(np.sqrt(var))
        means[u] = float(mean)
        stds[u] = std
        if livetime > 0:
            rates[u] = float(c / livetime)
    return means, stds, rates


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--file', required=True, help='Path to a single HDF5 run file')
    ap.add_argument('--metrics', default='std', type=str,
                    help="Comma-separated list from: mean,std,rate (default: std)")
    ap.add_argument('--min_hits', type=int, default=50, help='Drop channels with fewer hits (default: 50)')
    ap.add_argument('--workers', type=int, default=4, help='Parallel processes (default: 4)')
    ap.add_argument('--chunk_rows', type=int, default=5_000_000, help='Rows per chunk (default: 5e6)')
    ap.add_argument('--max_rows', type=int, default=-1, help='Limit rows processed (default: -1 = all)')
    ap.add_argument('--geometry_yaml', type=str, default=_default_geometry_yaml)
    ap.add_argument('--geometry_yaml_mod2', type=str, default=_default_geometry_yaml_mod2)
    ap.add_argument('--outprefix', type=str, default='singlefile')
    ap.add_argument('--norm_mean', type=float, default=50.0)
    ap.add_argument('--norm_std', type=float, default=5.0)
    ap.add_argument('--norm_rate', type=float, default=10.0)
    ap.add_argument('--verbose', action='store_true')
    args = ap.parse_args()

    fname = args.file
    with h5py.File(fname, 'r') as f:
        total_rows = f['packets'].shape[0]
    if args.max_rows > 0:
        total_rows = min(total_rows, args.max_rows)

    # build chunk ranges
    n_chunks = max(1, math.ceil(total_rows / args.chunk_rows))
    ranges = []
    for k in range(n_chunks):
        start = k * args.chunk_rows
        stop = min(total_rows, (k + 1) * args.chunk_rows)
        if start < stop:
            ranges.append((fname, start, stop))

    if args.verbose:
        print(f"File: {fname}")
        print(f"Total rows: {total_rows:,} | chunks: {len(ranges)} | workers: {args.workers}")

    partial_stats = []
    p4_mins = []
    p4_maxs = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(_process_chunk, r) for r in ranges]
        for fut in as_completed(futs):
            stats, pmin, pmax = fut.result()
            partial_stats.append(stats)
            if pmin is not None:
                p4_mins.append(pmin)
            if pmax is not None:
                p4_maxs.append(pmax)

    global_stats = _merge_stats(partial_stats)
    if p4_mins and p4_maxs:
        livetime = float(max(p4_maxs) - min(p4_mins))
    else:
        livetime = 0.0

    if args.verbose:
        print(f"Unique channels (pre-cut): {len(global_stats):,}")
        print(f"Livetime (ticks): {livetime:.0f}")

    means, stds, rates = _finalize_metrics(global_stats, livetime, args.min_hits)
    if args.verbose:
        print(f"Kept channels (>= {args.min_hits} hits): {len(stds):,}")

    # Decide which metrics to plot
    req = {m.strip().lower() for m in args.metrics.split(',')}
    metric_norms = {
        'mean': args.norm_mean,
        'std': args.norm_std,
        'rate': args.norm_rate,
    }
    metric_maps = {
        'mean': means,
        'std': stds,
        'rate': rates,
    }

    for metric in ('mean', 'std', 'rate'):
        if metric not in req:
            continue
        if metric == 'rate' and livetime <= 0:
            print("Warning: no livetime info found; skipping 'rate'")
            continue

        # Build the dict expected by plot_xy: d[uid][metric] = value
        d_for_plot = {u: {metric: v} for u, v in metric_maps[metric].items()}
        norm = metric_norms[metric]

        if args.verbose:
            vmax = max(metric_maps[metric].values()) if metric_maps[metric] else 0.0
            print(f"Plotting {metric} (max ~ {vmax:.3f}, norm={norm}) ...")

        plot_xy(d_for_plot, metric, args.geometry_yaml, args.geometry_yaml_mod2, norm)

        # Rename the output for clarity
        outpng = Path(f"2x2-xy-{metric}.png")
        if outpng.exists():
            renamed = Path(f"{args.outprefix}_2x2-xy-{metric}.png")
            outpng.replace(renamed)
            print(f"Saved: {renamed}")
        else:
            print(f"Warning: expected {outpng} not found; check plotter output.")


if __name__ == '__main__':
    main()
