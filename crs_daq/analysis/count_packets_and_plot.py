#!/usr/bin/env python3
"""
Open a LArPix HDF5 file, print a quick sanity summary, compute per-pixel
packet counts (total data vs. valid data), save results, and (optionally)
plot using the repo's analysis.plot_metric_anode.plot_xy (same call pattern
as analysis/plot_single_file_parallel.py).

Steps:
  1) Count how many packets of each packet_type are present.
  2) For data packets (packet_type==0), count per-pixel total vs valid (valid_parity==1).
  3) Save a text summary and a CSV with per-pixel totals/valid/percent.
  4) Print and save totals per io_group and per tile (io_group, io_channel).
  5) Optionally build the plot_xy dictionary and render maps.

Outputs (by default, next to the input file):
  - <input>.packet_type_counts.txt
  - <input>.pixel.total_valid.csv
  - <input>.pixel.summary.txt
  - <input>.tile_counts.txt
  - (if --plot) PNGs named 2x2-xy-<label>.png, then renamed beside the CSV for clarity.
"""

from __future__ import annotations
import argparse
import os
import sys
from dataclasses import dataclass
from typing import Dict, Iterable, Optional

import numpy as np
import h5py
import pandas as pd

# --- Ensure repo root on path ---------------------------------------------------
try:
    from pathlib import Path
    REPO_ROOT = Path(__file__).resolve().parents[1]
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
except Exception:
    pass

# --- Try to import the repo plotter --------------------------------------------
try:
    from analysis.plot_metric_anode import (
        plot_xy,
        _default_geometry_yaml,
        _default_geometry_yaml_mod2,
    )
except Exception:
    plot_xy = None
    _default_geometry_yaml = None
    _default_geometry_yaml_mod2 = None

# --- UID helper (match your plot_single_file_parallel.py encoding) --------------
try:
    from analysis.utils import unique_channel_id  # type: ignore
except Exception:
    def unique_channel_id(view: np.ndarray) -> np.ndarray:
        ig = view['io_group'] if 'io_group' in view.dtype.names else np.zeros(len(view), dtype=np.int64)
        ic = view['io_channel'] if 'io_channel' in view.dtype.names else np.zeros(len(view), dtype=np.int64)
        ch = view['channel_id'].astype(np.int64)
        chip = view['chip_id'].astype(np.int64)
        return ((ig.astype(np.int64) * 1000 + ic.astype(np.int64)) * 1000 + chip) * 100 + ch


@dataclass(frozen=True)
class Paths:
    csv: str
    txt: str


# ------------------------------------------------------------------------------

def _save_packet_type_counts(fname: str, pk: np.ndarray) -> str:
    types, counts = np.unique(pk['packet_type'], return_counts=True)
    lines = [f"packet_type counts for {os.path.basename(fname)}:"]
    total = int(pk.shape[0])
    for t, c in zip(types.tolist(), counts.tolist()):
        lines.append(f"  type {t:>2}: {c:,}")
    lines.append(f"  total  : {total:,}")

    out = f"{os.path.splitext(fname)[0]}.packet_type_counts.txt"
    with open(out, 'w') as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"Saved: {out}")
    return out


def _per_pixel_counts(pk: np.ndarray) -> pd.DataFrame:
    is_data = (pk['packet_type'] == 0)
    is_valid = is_data & (pk['valid_parity'] == 1)
    uid_all = unique_channel_id(pk[is_data])
    uid_val = unique_channel_id(pk[is_valid])

    u_all, c_all = np.unique(uid_all, return_counts=True)
    u_val, c_val = np.unique(uid_val, return_counts=True)
    val_map: Dict[int, int] = {int(u): int(c) for u, c in zip(u_val.tolist(), c_val.tolist())}

    rows = []
    for u, tot in zip(u_all.tolist(), c_all.tolist()):
        v = val_map.get(int(u), 0)
        pct = (100.0 * v / tot) if tot > 0 else np.nan
        rows.append({'uid': int(u), 'total': int(tot), 'valid': int(v), 'percent_valid': float(pct)})

    df = pd.DataFrame(rows)
    return df


def _write_pixel_csv_and_txt(fname: str, df: pd.DataFrame) -> Paths:
    csv = f"{os.path.splitext(fname)[0]}.pixel.total_valid.csv"
    df.sort_values('uid').to_csv(csv, index=False)

    total_hits = int(df['total'].sum()) if not df.empty else 0
    total_valid = int(df['valid'].sum()) if not df.empty else 0
    overall_pct = (100.0 * total_valid / total_hits) if total_hits > 0 else float('nan')

    txt = f"{os.path.splitext(fname)[0]}.pixel.summary.txt"
    with open(txt, 'w') as f:
        f.write(f"Per-pixel totals for {os.path.basename(fname)}\n")
        f.write(f"  channels: {len(df):,}\n")
        f.write(f"  total data packets: {total_hits:,}\n")
        f.write(f"  valid data packets: {total_valid:,}\n")
        f.write(f"  overall % valid: {overall_pct:.3f}\n")
    print(f"Saved: {csv}\nSaved: {txt}")
    return Paths(csv=csv, txt=txt)
def _write_tile_counts(fname: str, pk: np.ndarray) -> str:
    if 'io_group' not in pk.dtype.names:
        return ""
    # mask for data packets only
    is_data = (pk['packet_type'] == 0)
    pk = pk[is_data]

    ig_counts: Dict[int, int] = {}
    tile_counts: Dict[tuple, int] = {}
    io_channel = pk['io_channel'] if 'io_channel' in pk.dtype.names else np.zeros(len(pk), dtype=int)
    for ig, ic in zip(pk['io_group'], io_channel):
        ig_counts[int(ig)] = ig_counts.get(int(ig), 0) + 1
        tile_counts[(int(ig), int(ic))] = tile_counts.get((int(ig), int(ic)), 0) + 1

    lines = [f"Data packet (type 0) totals per io_group and tile for {os.path.basename(fname)}:"]
    lines.append("Per io_group:")
    for ig, c in sorted(ig_counts.items()):
        lines.append(f"  io_group {ig}: {c:,}")
    lines.append("Per (io_group, io_channel):")
    for (ig, ic), c in sorted(tile_counts.items()):
        lines.append(f"  io_group {ig}, io_channel {ic}: {c:,}")

    out = f"{os.path.splitext(fname)[0]}.tile_counts.txt"
    with open(out, 'w') as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"Saved: {out}")
    return out


# ------------------------------------------------------------------------------
# Plotting (repo style)

def _plot_repo_style(df: pd.DataFrame,
                     which: Iterable[str],
                     geometry_yaml: Optional[str],
                     geometry_yaml_mod2: Optional[str],
                     norm_total: float,
                     norm_valid: float,
                     norm_percent: float,
                     base_out: str) -> None:
    if plot_xy is None:
        print("plot_xy not available; skipping plots.")
        return

    metrics = {}
    if 'total' in which:
        metrics['packets_total'] = (df['uid'].astype(int).tolist(), df['total'].astype(float).tolist(), norm_total)
    if 'valid' in which:
        metrics['packets_valid'] = (df['uid'].astype(int).tolist(), df['valid'].astype(float).tolist(), norm_valid)
    if 'percent' in which or 'percent_valid' in which:
        metrics['percent_valid'] = (df['uid'].astype(int).tolist(), df['percent_valid'].astype(float).tolist(), norm_percent)

    g_yaml = geometry_yaml or _default_geometry_yaml
    g_yaml_mod2 = geometry_yaml_mod2 or _default_geometry_yaml_mod2

    for label, (uids, vals, norm) in metrics.items():
        d_for_plot = {int(u): {label: float(v)} for u, v in zip(uids, vals)}
        plot_xy(d_for_plot, label, g_yaml, g_yaml_mod2, float(norm))

        from pathlib import Path
        outpng = Path(f"2x2-xy-{label}.png")
        if outpng.exists():
            renamed = Path(f"{base_out}_{label}.png")
            try:
                import shutil
                shutil.move(str(outpng), str(renamed))
                print(f"Saved plot: {renamed}")
            except OSError as e:
                if getattr(e, 'errno', None) == 18:
                    print(f"Cross-device move not possible; keeping plot at {outpng}")
                else:
                    print(f"Rename failed ({e}); keeping plot at {outpng}")
        else:
            print(f"Warning: expected {outpng} not found; check plotter output.")


# ------------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument('file', help='Path to LArPix HDF5 file')
    ap.add_argument('--geometry_yaml', default=_default_geometry_yaml)
    ap.add_argument('--geometry_yaml_mod2', default=_default_geometry_yaml_mod2)
    ap.add_argument('--plot', nargs='*', default=[], help="Which plots to make: choose from 'total', 'valid', 'percent' (or 'percent_valid')")
    ap.add_argument('--norm_total', type=float, default=1.0)
    ap.add_argument('--norm_valid', type=float, default=1.0)
    ap.add_argument('--norm_percent', type=float, default=100.0)
    args = ap.parse_args()

    fname = args.file
    with h5py.File(fname, 'r') as f:
        if 'packets' not in f:
            raise KeyError("Dataset 'packets' not found in file")
        pk = f['packets'][:]

    _save_packet_type_counts(fname, pk)
    df = _per_pixel_counts(pk)
    outs = _write_pixel_csv_and_txt(fname, df)
    _write_tile_counts(fname, pk)

    if args.plot:
        base_out = os.path.splitext(outs.csv)[0]
        _plot_repo_style(
            df=df,
            which=args.plot,
            geometry_yaml=args.geometry_yaml,
            geometry_yaml_mod2=args.geometry_yaml_mod2,
            norm_total=args.norm_total,
            norm_valid=args.norm_valid,
            norm_percent=args.norm_percent,
            base_out=base_out,
        )


if __name__ == '__main__':
    main()
