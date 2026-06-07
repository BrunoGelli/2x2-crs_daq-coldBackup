#!/usr/bin/env python3
import warnings
warnings.filterwarnings("ignore")

import argparse, json, sys
from collections import defaultdict
import larpix, larpix.io

from base import network_base, pacman_base, utility_base, enforce_parallel
from runenv import runenv as RUN

# expose RUN.config keys
module = sys.modules[__name__]
for var in RUN.config.keys():
    setattr(module, var, getattr(RUN, var))

def _load_json(p):
    with open(p, 'r') as f: return json.load(f)

def _keys_for_tiles_from_controller(controller, io_group, tiles_set):
    keys = []
    for k in controller.chips.keys():  # larpix.Key
        if k.io_group != io_group: continue
        if utility_base.io_channel_to_tile(k.io_channel) in tiles_set:
            keys.append(k)
    return keys

def _group_by_network(keys):
    # → list[list(Key,...)] grouped by (io_group, io_channel), sorted by chip_id
    grouped = defaultdict(list)
    for k in keys:
        grouped[(k.io_group, k.io_channel)].append(k)
    nets = []
    for net in grouped.values():
        net.sort(key=lambda kk: kk.chip_id)
        nets.append(net)
    return nets

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--verbose','-v',action='store_true',default=False)
    ap.add_argument('--io_group', type=int, required=True)
    # single-tile (backward-compat) OR multi-tile CSV
    ap.add_argument('--pacman_tile', type=int, default=None, help='Single tile')
    ap.add_argument('--tiles', type=str, default=None, help='CSV of tiles, e.g. "1,3,5"')
    ap.add_argument('--controller_config', type=str, required=True)
    ap.add_argument('--pacman_config', type=str, required=True)
    ap.add_argument('--retries', type=int, default=2)
    ap.add_argument('--exclusive-uart', action='store_true', default=False,
                    help='Enable UART exclusively for these tiles (others disabled).')
    args = ap.parse_args()

    io_group = args.io_group
    # parse tiles
    if args.tiles:
        tiles = sorted({int(t.strip()) for t in args.tiles.split(',') if t.strip()!=''})
    elif args.pacman_tile is not None:
        tiles = [int(args.pacman_tile)]
    else:
        print("Provide --pacman_tile N or --tiles CSV"); sys.exit(1)

    pacman_cfg = _load_json(args.pacman_config)
    ctrl_cfg = _load_json(args.controller_config)

    if 'io_group' not in pacman_cfg or not any(io_group == pair[0] for pair in pacman_cfg['io_group']):
        print('Missing io_group in PACMAN config file!'); sys.exit(1)

    if args.verbose:
        print(f"Configuring io_group={io_group}, tiles={tiles} (targeted; no global re-network)")

    # Restricted bring-up for ONLY these tiles
    if io_group_asic_version_[io_group] == '2b':
        if args.verbose: print('init network_v2b (restricted)')
        c = network_base.network_v2b(ctrl_cfg[str(io_group)], tiles=tiles, io_group=io_group)
    elif io_group_asic_version_[io_group] in [2, 'lightpix-1']:
        if args.verbose: print('init network_v2a (restricted)')
        c = network_base.network_v2a(ctrl_cfg[str(io_group)], tiles=tiles, io_group=io_group)
    else:
        raise RuntimeError(f"Unknown ASIC version for io_group {io_group}: {io_group_asic_version_[io_group]}")

    # Optional UART isolation (will silence other tiles)
    if args.exclusive_uart:
        if args.verbose: print('[UART] exclusive enable for these tiles (others disabled)')
        pacman_base.enable_pacman_uart_from_tile(c.io, io_group, tiles)

    # Build chip set for the union of requested tiles
    tiles_set = set(tiles)
    keys_flat = _keys_for_tiles_from_controller(c, io_group, tiles_set)
    if not keys_flat:
        print("[ERR] No chips discovered on requested tiles; cannot enforce."); sys.exit(2)

    network_keys = _group_by_network(keys_flat)

    if args.verbose:
        print(f"[keys] {len(keys_flat)} chip(s) across {len(network_keys)} link(s) "
              f"for io_group={io_group}, tiles={tiles}")
        for k in keys_flat[:8]:
            print(f"  - key(io_group={k.io_group}, io_channel={k.io_channel}, chip_id={k.chip_id})")

    # Enforce (no re-networking), with limited retries
    ok, diff, unconfigured = enforce_parallel.enforce_parallel(
        c, network_keys, pbar_desc=f'io_group {io_group}, tiles {tiles}', pbar_position=0
    )
    attempts = 0
    while (not ok) and attempts < args.retries:
        if args.verbose:
            print(f"[enforce] retry {attempts+1}/{args.retries} (same {len(network_keys)} links)")
        ok, diff, unconfigured = enforce_parallel.enforce_parallel(
            c, network_keys, pbar_desc=f'io_group {io_group}, tiles {tiles}', pbar_position=0
        )
        attempts += 1

    if not ok:
        raise RuntimeError("Enforcement did not converge for the requested tiles", diff)

    if args.verbose:
        print("[ok] enforcement complete for requested tiles")

if __name__ == '__main__':
    main()
