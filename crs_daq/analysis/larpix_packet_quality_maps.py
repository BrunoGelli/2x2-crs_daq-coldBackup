#!/usr/bin/env python3
"""
Bruno Testing...

LArPix packet counters + pixel/ASIC/tile maps

Features
========
- Opens one or more LArPix HDF5 files and counts, per pixel/ASIC/tile:
    * total number of data packets (packet_type == 0)
    * number of **valid** data packets (packet_type == 0 AND valid_parity == 1)
    * percent of valid packets
- Outputs tidy CSV tables for further analysis.
- (Optional) Plots chip-level 8×8 pixel heatmaps and a tile mosaic.
- Flexible aggregation by channel (pixel), chip, or tile.
- Works with typical LArPix packet schemas (`/packets` dataset with fields
  `io_group, io_channel, chip_id, channel_id, packet_type, valid_parity, timestamp`).

Usage
=====
    python larpix_packet_quality_maps.py file1.h5 [file2.h5 ...] \
        --mode packets|valid|percent_valid \
        --agg channel|chip|tile \
        --outdir results/ \
        --plot  \
        [--chip-xy-map chip_xy_map.json] \
        [--tile-xy-map tile_xy_map.json]

Notes
=====
- "channel" aggregation produces counts per (io_group, io_channel, chip_id, channel_id).
- "chip" aggregation produces counts per (io_group, io_channel, chip_id).
- "tile" aggregation produces counts per (io_group, io_channel) — i.e., a tile keyed
  by (io_group, io_channel). If your definition differs, adjust as needed.
- Plotting a full tile mosaic requires knowing where each `chip_id` sits in the tile grid.
  Provide `--chip-xy-map` as a JSON mapping like:
      {"<io_group>_<io_channel>_<chip_id>": {"x": COL, "y": ROW}}
  where (x,y) are integer positions of the 8×8 **chip** on the tile mosaic grid.
  If not provided, chips are arranged automatically in a compact grid by chip_id order.

Output
======
- CSV: `<outdir>/<basename>_<agg>_<mode>.csv`
- Plots (if `--plot`):
  * Chip maps: `<outdir>/<basename>_chip_<chip_id>_<mode>.png`
  * Tile mosaic: `<outdir>/<basename>_tile_<iog>_<ioc>_<mode>.png`

"""
import argparse
import json
import math
import os
from pathlib import Path
from typing import Dict, Tuple, Optional, Iterable

import h5py
import numpy as np
import matplotlib.pyplot as plt

# -----------------------
# Core data access
# -----------------------

def open_packets(h5path: Path):
    """Return a dict of needed packet fields as NumPy arrays.

    Supports standard LArPix /packets structured dataset.
    """
    with h5py.File(h5path, 'r') as f:
        if 'packets' not in f:
            raise RuntimeError(f"'{h5path}': missing '/packets' dataset")
        pk = f['packets']
        # Load only the fields we need into simple ndarrays for speed
        fields = {}
        for name in ['io_group', 'io_channel', 'chip_id', 'channel_id',
                     'packet_type', 'valid_parity']:
            if name not in pk.dtype.fields:
                raise RuntimeError(f"'{h5path}': '/packets' missing field '{name}'")
            fields[name] = pk[name][:]
    return fields


def make_masks(fields: Dict[str, np.ndarray]):
    """Return boolean masks for data packets and valid data packets."""
    data_mask = (fields['packet_type'] == 0)
    valid_mask = data_mask & (fields['valid_parity'] == 1)
    return data_mask, valid_mask


# -----------------------
# Aggregations
# -----------------------

KeyChannel = Tuple[int, int, int, int]  # (io_group, io_channel, chip_id, channel_id)
KeyChip    = Tuple[int, int, int]        # (io_group, io_channel, chip_id)
KeyTile    = Tuple[int, int]             # (io_group, io_channel)


def count_by_channel(fields, mask) -> Dict[KeyChannel, int]:
    keys = np.stack([
        fields['io_group'][mask],
        fields['io_channel'][mask],
        fields['chip_id'][mask],
        fields['channel_id'][mask]
    ], axis=1)
    # Use np.unique for fast counting
    uniq, counts = np.unique(keys, axis=0, return_counts=True)
    return {tuple(map(int, k)): int(c) for k, c in zip(uniq, counts)}


def rollup_counts_channel_to_chip(ch_counts: Dict[KeyChannel, int]) -> Dict[KeyChip, int]:
    chip_counts: Dict[KeyChip, int] = {}
    for (iog, ioc, chip, ch), c in ch_counts.items():
        chip_counts[(iog, ioc, chip)] = chip_counts.get((iog, ioc, chip), 0) + c
    return chip_counts


def rollup_counts_chip_to_tile(chip_counts: Dict[KeyChip, int]) -> Dict[KeyTile, int]:
    tile_counts: Dict[KeyTile, int] = {}
    for (iog, ioc, chip), c in chip_counts.items():
        tile_counts[(iog, ioc)] = tile_counts.get((iog, ioc), 0) + c
    return tile_counts


# -----------------------
# Plotting helpers
# -----------------------

def ensure_outdir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def chip_heatmap(values_by_channel: Dict[KeyChannel, float], iog: int, ioc: int, chip: int,
                  title: str, outpng: Path):
    """Plot an 8×8 heatmap for a single chip based on per-channel values.

    LArPix channel_id spans 0..63, typically arranged 8×8.
    """
    grid = np.full((8, 8), np.nan, dtype=float)
    for (giog, gioc, gchip, ch), val in values_by_channel.items():
        if giog == iog and gioc == ioc and gchip == chip:
            row = ch // 8
            col = ch % 8
            grid[row, col] = val

    plt.figure(figsize=(5, 4))
    plt.imshow(grid, origin='lower', aspect='equal')  # color left to default
    plt.title(title)
    plt.xlabel('col (ch % 8)')
    plt.ylabel('row (ch // 8)')
    cbar = plt.colorbar()
    cbar.set_label('value')
    plt.tight_layout()
    plt.savefig(outpng)
    plt.close()


def auto_chip_positions(chips: Iterable[int]) -> Dict[int, Tuple[int, int]]:
    """Place chips on a compact grid in ascending chip_id order.

    Returns mapping chip_id -> (x, y) tile-cell coordinates.
    """
    chips = sorted(set(chips))
    n = len(chips)
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    pos = {}
    for idx, chip in enumerate(chips):
        r = idx // cols
        c = idx % cols
        pos[chip] = (c, r)
    return pos


def tile_mosaic(values_by_channel: Dict[KeyChannel, float], iog: int, ioc: int,
                title: str, outpng: Path,
                chip_xy_map: Optional[Dict[str, Dict[str, int]]] = None):
    """Plot a tile mosaic by stitching chip 8×8 blocks according to a map.

    Each chip occupies an 8×8 block; chips arranged on a (Cx, Ry) coarse grid.
    If chip_xy_map is None, chips are auto-arranged.
    chip_xy_map schema: {
        "<io_group>_<io_channel>_<chip_id>": {"x": int, "y": int}, ...
    }
    """
    # Collect channels for this (iog, ioc)
    per_chip_channels: Dict[int, Dict[int, float]] = {}
    for (giog, gioc, gchip, ch), val in values_by_channel.items():
        if giog == iog and gioc == ioc:
            per_chip_channels.setdefault(int(gchip), {})[int(ch)] = float(val)

    if not per_chip_channels:
        return  # nothing to plot

    # Determine chip positions
    if chip_xy_map:
        pos_map: Dict[int, Tuple[int, int]] = {}
        for chip in per_chip_channels.keys():
            key = f"{iog}_{ioc}_{chip}"
            if key not in chip_xy_map:
                raise RuntimeError(f"chip_xy_map missing key '{key}'")
            pos = chip_xy_map[key]
            pos_map[chip] = (int(pos['x']), int(pos['y']))
    else:
        pos_map = auto_chip_positions(per_chip_channels.keys())

    # Canvas size in pixels: (tile_cols*8, tile_rows*8)
    max_x = max(x for x, y in pos_map.values())
    max_y = max(y for x, y in pos_map.values())
    tile_cols = max_x + 1
    tile_rows = max_y + 1
    H = tile_rows * 8
    W = tile_cols * 8
    canvas = np.full((H, W), np.nan, dtype=float)

    # Paste each 8×8 chip
    for chip, chvals in per_chip_channels.items():
        chip_grid = np.full((8, 8), np.nan, dtype=float)
        for ch, val in chvals.items():
            r = ch // 8
            c = ch % 8
            chip_grid[r, c] = val
        cx, cy = pos_map[chip]
        r0 = cy * 8
        c0 = cx * 8
        canvas[r0:r0+8, c0:c0+8] = chip_grid

    plt.figure(figsize=(max(6, W/4), max(5, H/4)))
    plt.imshow(canvas, origin='lower', aspect='equal')
    plt.title(title)
    plt.xlabel('tile X (chip cols × 8)')
    plt.ylabel('tile Y (chip rows × 8)')
    cbar = plt.colorbar()
    cbar.set_label('value')
    plt.tight_layout()
    plt.savefig(outpng)
    plt.close()


# -----------------------
# CSV writers
# -----------------------

def write_csv_channel(path: Path, values: Dict[KeyChannel, float]):
    with open(path, 'w') as f:
        f.write('io_group,io_channel,chip_id,channel_id,value\n')
        for (iog, ioc, chip, ch), v in sorted(values.items()):
            f.write(f"{iog},{ioc},{chip},{ch},{v}\n")


def write_csv_chip(path: Path, values: Dict[KeyChip, float]):
    with open(path, 'w') as f:
        f.write('io_group,io_channel,chip_id,value\n')
        for (iog, ioc, chip), v in sorted(values.items()):
            f.write(f"{iog},{ioc},{chip},{v}\n")


def write_csv_tile(path: Path, values: Dict[KeyTile, float]):
    with open(path, 'w') as f:
        f.write('io_group,io_channel,value\n')
        for (iog, ioc), v in sorted(values.items()):
            f.write(f"{iog},{ioc},{v}\n")


# -----------------------
# Main pipeline
# -----------------------

def process_file(h5path: Path, mode: str, agg: str, outdir: Path,
                 do_plot: bool,
                 chip_xy_map: Optional[Dict[str, Dict[str, int]]] = None,
                 tile_xy_map: Optional[Dict[str, Dict[str, int]]] = None):
    print(f"Processing {h5path} ...")
    fields = open_packets(h5path)
    data_mask, valid_mask = make_masks(fields)

    # Base counts at channel granularity
    packets = count_by_channel(fields, data_mask)
    valid   = count_by_channel(fields, valid_mask)

    # Build the requested value per channel
    values_channel: Dict[KeyChannel, float] = {}
    if mode == 'packets':
        values_channel = {k: float(packets.get(k, 0)) for k in packets.keys() | valid.keys()}
    elif mode == 'valid':
        values_channel = {k: float(valid.get(k, 0)) for k in packets.keys() | valid.keys()}
    elif mode == 'percent_valid':
        for k in packets.keys() | valid.keys():
            tot = packets.get(k, 0)
            val = valid.get(k, 0)
            pct = (100.0 * val / tot) if tot > 0 else np.nan
            values_channel[k] = pct
    else:
        raise ValueError("mode must be one of: packets, valid, percent_valid")

    # Aggregate as requested
    base = h5path.stem
    ensure_outdir(outdir)

    if agg == 'channel':
        csv_path = outdir / f"{base}_channel_{mode}.csv"
        write_csv_channel(csv_path, values_channel)
        print(f"Wrote {csv_path}")

        if do_plot:
            # Plot each chip heatmap (can be many)
            seen_chips = sorted(set((iog, ioc, chip) for (iog, ioc, chip, ch) in values_channel.keys()))
            for iog, ioc, chip in seen_chips:
                outpng = outdir / f"{base}_chip_{iog}_{ioc}_{chip}_{mode}.png"
                title = f"{base} — chip {chip} (iog={iog}, ioc={ioc}) — {mode}"
                chip_heatmap(values_channel, iog, ioc, chip, title, outpng)

            # Tile mosaics per (iog,ioc)
            seen_tiles = sorted(set((iog, ioc) for (iog, ioc, chip, ch) in values_channel.keys()))
            for iog, ioc in seen_tiles:
                outpng = outdir / f"{base}_tile_{iog}_{ioc}_{mode}.png"
                title = f"{base} — tile (iog={iog}, ioc={ioc}) — {mode}"
                tile_mosaic(values_channel, iog, ioc, title, outpng, chip_xy_map)

    elif agg == 'chip':
        chip_counts = rollup_counts_channel_to_chip(values_channel)
        csv_path = outdir / f"{base}_chip_{mode}.csv"
        write_csv_chip(csv_path, chip_counts)
        print(f"Wrote {csv_path}")

        if do_plot:
            # Heatmap requires channel-level detail; instead, make a simple bar chart per tile
            by_tile: Dict[KeyTile, Dict[int, float]] = {}
            for (iog, ioc, chip), v in chip_counts.items():
                by_tile.setdefault((iog, ioc), {})[chip] = v
            for (iog, ioc), chipmap in by_tile.items():
                chips = sorted(chipmap)
                vals = [chipmap[c] for c in chips]
                plt.figure(figsize=(max(6, len(chips)*0.5), 4))
                plt.bar([str(c) for c in chips], vals)
                plt.xlabel('chip_id')
                plt.ylabel(mode)
                plt.title(f"{base} — chip totals (iog={iog}, ioc={ioc}) — {mode}")
                plt.tight_layout()
                outpng = outdir / f"{base}_chips_{iog}_{ioc}_{mode}.png"
                plt.savefig(outpng)
                plt.close()

    elif agg == 'tile':
        chip_counts = rollup_counts_channel_to_chip(values_channel)
        tile_counts = rollup_counts_chip_to_tile(chip_counts)
        csv_path = outdir / f"{base}_tile_{mode}.csv"
        write_csv_tile(csv_path, tile_counts)
        print(f"Wrote {csv_path}")

        if do_plot:
            # Simple bar per tile
            tiles = [f"{iog}_{ioc}" for (iog, ioc) in tile_counts]
            vals = [tile_counts[(iog, ioc)] for (iog, ioc) in tile_counts]
            plt.figure(figsize=(max(6, len(tiles)*0.6), 4))
            plt.bar(tiles, vals)
            plt.xlabel('tile (io_group_io_channel)')
            plt.ylabel(mode)
            plt.title(f"{base} — tile totals — {mode}")
            plt.tight_layout()
            outpng = outdir / f"{base}_tiles_{mode}.png"
            plt.savefig(outpng)
            plt.close()
    else:
        raise ValueError("agg must be one of: channel, chip, tile")


# -----------------------
# CLI
# -----------------------

def parse_args():
    p = argparse.ArgumentParser(description="Count LArPix packets and visualize per pixel/ASIC/tile")
    p.add_argument('files', nargs='+', help='Input HDF5 files with /packets dataset')
    p.add_argument('--mode', default='packets', choices=['packets', 'valid', 'percent_valid'],
                   help='Metric to compute (default: packets)')
    p.add_argument('--agg', default='channel', choices=['channel', 'chip', 'tile'],
                   help='Aggregation level (default: channel)')
    p.add_argument('--outdir', default='packet_maps_out', help='Output directory for CSV/plots')
    p.add_argument('--plot', action='store_true', help='Generate plots')
    p.add_argument('--chip-xy-map', default=None,
                   help='JSON mapping of chip positions for tile mosaic (optional)')
    p.add_argument('--tile-xy-map', default=None,
                   help='(Reserved) JSON mapping of tile positions (not required)')
    return p.parse_args()


def maybe_load_json(path: Optional[str]):
    if not path:
        return None
    with open(path, 'r') as f:
        return json.load(f)


def main():
    args = parse_args()
    outdir = Path(args.outdir)
    ensure_outdir(outdir)

    chip_xy_map = maybe_load_json(args.chip_xy_map)
    tile_xy_map = maybe_load_json(args.tile_xy_map)

    for fpath in args.files:
        process_file(Path(fpath), args.mode, args.agg, outdir,
                     args.plot, chip_xy_map, tile_xy_map)


if __name__ == '__main__':
    main()
