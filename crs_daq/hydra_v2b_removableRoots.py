#TO DO: FIX ISSUE WITH MULTIPLE IO CHANNEL NETWORKS
#RIGHT NOW SECOND IO_CHANNEL CONTROLLER OVERWRITES FIRST

import larpix
import larpix.io
from base import pacman_base
from base import network_base
from base import utility_base
from base import generate_config
import argparse
import json
import time
from time import perf_counter
import shutil
from base import config_loader
from tqdm import tqdm

import sys
import os
from runenv import runenv as RUN

# Inject RUN_CONFIG values into module namespace (same pattern as your original)
module = sys.modules[__name__]
for var in RUN.config.keys():
    setattr(module, var, getattr(RUN, var))

_default_file_prefix = None
_default_disable_logger = True
_default_verbose = False
_default_debug = False
_default_ref_current_trim = 0
_default_tx_diff = 0
_default_tx_slice = 15
_default_r_term = 2
_default_i_rx = 8
_default_recheck = False

# Mapping used by your original v2b script
v2b_root_ids = [21, 41, 71, 91]


def _normalize_tile_exclude(exclude_entry, tile):
    """
    Return a set of excluded chip IDs for a specific tile.

    Supports common RUN_CONFIG styles:
      - iog_exclude[iog] = {"5": [91], "6": [61], ...}   (dict keyed by tile string)
      - iog_exclude[iog] = {5: [91], 6: [61], ...}       (dict keyed by tile int)
      - iog_exclude[iog] = [91, 61, ...]                 (flat list)
      - iog_exclude[iog] = "91,61"                       (comma-separated string)
      - None                                             (no exclude)
    """
    if exclude_entry is None:
        return set()

    if isinstance(exclude_entry, dict):
        ex = exclude_entry.get(str(tile), exclude_entry.get(tile, []))
    else:
        ex = exclude_entry

    if ex is None:
        return set()

    if isinstance(ex, str):
        ex = [x.strip() for x in ex.split(",") if x.strip() != ""]

    if isinstance(ex, int):
        ex = [ex]

    return set(int(x) for x in ex)


def _ensure_empty_network_entries(c, iog, io_channels, debug=False):
    """
    network_base.write_network_to_file() assumes c.network[iog][ioc] exists for all ioc's it will write.
    If we skip a root on an io_channel, that io_channel might never get created in c.network[iog].
    Create safe empty stubs so serialization won't crash.
    """
    if not hasattr(c, "network") or c.network is None:
        c.network = {}

    if iog not in c.network or c.network[iog] is None:
        c.network[iog] = {}

    for ioc in io_channels:
        if ioc not in c.network[iog]:
            if debug:
                print(f"[DEBUG] Creating empty c.network[{iog}][{ioc}] stub (root was skipped or no network built).")
            # Minimal keys that the writer commonly touches; harmless if empty
            c.network[iog][ioc] = {
                "miso_us": [],
                "miso_ds": [],
                "mosi": [],
            }


def main(
    io_group,
    file_prefix=_default_file_prefix,
    disable_logger=_default_disable_logger,
    verbose=_default_verbose,
    debug=_default_debug,
    ref_current_trim=_default_ref_current_trim,
    tx_diff=_default_tx_diff,
    tx_slice=_default_tx_slice,
    r_term=_default_r_term,
    i_rx=_default_i_rx,
    pacman_tile=None,
    **kwargs
):
    c = larpix.Controller()
    c.io = larpix.io.PACMAN_IO(relaxed=True, config_filepath=f"io/pacman_io{io_group}.json")

    # Two resets, same as your original
    c.io.reset_larpix(length=4096 * 4, io_group=io_group)
    time.sleep(4096 * 4 * 1e-6)
    c.io.reset_larpix(length=4096 * 4, io_group=io_group)
    time.sleep(4096 * 4 * 1e-6)

    _file_prefix = file_prefix

    now = time.strftime("%Y_%m_%d_%H_%M_%Z")
    config_name = "controller-config-" + now + ".json"

    # Only working on this one io_group
    for iog in [io_group]:
        print(f"inverting io group {iog} tiles {io_group_pacman_tile_[iog]}")
        pacman_base.invert_pacman_uart(
            c.io, iog, io_group_asic_version_[iog], io_group_pacman_tile_[iog]
        )

        print(f"Working on io_group={iog}")

        if io_group_asic_version_[iog] != "2b":
            raise RuntimeError(
                f"This script is for v2b tiles, but io_group_asic_version_[{iog}] = {io_group_asic_version_[iog]}"
            )

        # tiles to operate on
        if pacman_tile is None:
            tiles = io_group_pacman_tile_[iog]
        else:
            tiles = [pacman_tile]

        # Pull the exclusion entry for this io_group (could be dict-of-tiles, etc.)
        exclude_entry_for_iog = None
        try:
            exclude_entry_for_iog = iog_exclude.get(iog, None)
        except Exception:
            exclude_entry_for_iog = None

        for tile in tiles:
            # Build:
            #  - tile_exclude_set: fast membership checks for skipping root chips
            #  - exclude_for_network_base: dict keyed by tile string (what network_base expects)
            tile_exclude_set = _normalize_tile_exclude(exclude_entry_for_iog, tile)
            exclude_for_network_base = {str(tile): sorted(tile_exclude_set)}

            if debug:
                print(f"\n[DEBUG] iog={iog}, tile={tile}")
                print(f"[DEBUG] raw iog_exclude[iog] = {exclude_entry_for_iog}")
                print(f"[DEBUG] tile_exclude_set = {sorted(tile_exclude_set)}")
                print(f"[DEBUG] exclude_for_network_base = {exclude_for_network_base}")

            root_keys = []
            io_channels = utility_base.tile_to_io_channel([tile])

            # Build candidate roots, skipping excluded root chips
            for io_channel in io_channels:
                c.io.set_uart_clock_ratio(io_channel, 10, io_group=iog)
                cid = v2b_root_ids[(io_channel - 1) % 4]

                if cid in tile_exclude_set:
                    if debug:
                        print(
                            f"[DEBUG] Skipping excluded ROOT chip {cid} on io_channel {io_channel} (tile {tile})"
                        )
                    continue

                network_base.network_ext_node_from_tuple(c, iog, io_channel, cid)
                candidate_root = network_base.setup_root(
                    c,
                    c.io,
                    iog,
                    io_channel,
                    cid,
                    verbose,
                    io_group_asic_version_[iog],
                    0,
                    0,
                    15,
                    2,
                    8,
                )
                if candidate_root is not None:
                    root_keys.append(candidate_root)

            print("ROOT KEYS: ", root_keys)

            # Partition roots by (io_group, tile)
            iog_tile_to_root_keys = utility_base.partition_chip_keys_by_io_group_tile(root_keys)
            if debug:
                print("[DEBUG] iog_tile_to_root_keys:", iog_tile_to_root_keys)
            else:
                print(iog_tile_to_root_keys)

            unconfigured = []

            # Now run initial network and waitlist iterations
            for iog_tile in iog_tile_to_root_keys.keys():
                network_base.initial_network(
                    c,
                    c.io,
                    iog_tile[0],
                    iog_tile_to_root_keys[iog_tile],
                    verbose,
                    io_group_asic_version_[iog],
                    ref_current_trim,
                    tx_diff,
                    tx_slice,
                    r_term,
                    i_rx,
                    exclude=exclude_for_network_base,   # dict keyed by tile str
                )

                out_of_network = network_base.iterate_waitlist(
                    c,
                    c.io,
                    iog,
                    utility_base.tile_to_io_channel([tile]),
                    verbose,
                    io_group_asic_version_[iog],
                    ref_current_trim,
                    tx_diff,
                    tx_slice,
                    r_term,
                    i_rx,
                    exclude=exclude_for_network_base,   # dict keyed by tile str
                )
                unconfigured.extend(out_of_network)

            # >>> FIX: ensure missing io_channels (e.g. skipped root) have empty network stubs
            _ensure_empty_network_entries(c, iog, io_channels, debug=debug)

            # Write network JSON
            if _file_prefix is None:
                file_prefix = f"iog-{iog}-pacman-tile-{tile}-hydra-network"
            network_file = network_base.write_network_to_file(
                c, file_prefix, {io_group: [tile]}, unconfigured
            )

        return c, c.io


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--io_group", default=None, type=int, help="io group to network")
    parser.add_argument("--pacman_tile", default=None, type=int, help="PACMAN tile to work with")
    parser.add_argument("--file_prefix", default=_default_file_prefix, type=str, help="String prepended to filename")
    parser.add_argument("--disable_logger", default=_default_disable_logger, action="store_true", help="Disable logger")
    parser.add_argument("--verbose", default=_default_verbose, action="store_true", help="Enable verbose mode")
    parser.add_argument(
        "--debug",
        default=_default_debug,
        action="store_true",
        help="Print debug information about exclusions and root selection",
    )
    parser.add_argument(
        "--ref_current_trim",
        default=_default_ref_current_trim,
        type=int,
        help="Trim DAC for primary reference current",
    )
    parser.add_argument(
        "--tx_diff",
        default=_default_tx_diff,
        type=int,
        help="Differential current per transmitter DAC",
    )
    parser.add_argument(
        "--tx_slice",
        default=_default_tx_slice,
        type=int,
        help="Slices enabled per transmitter DAC",
    )
    parser.add_argument(
        "--r_term",
        default=_default_r_term,
        type=int,
        help="Receiver termination DAC",
    )
    parser.add_argument(
        "--i_rx",
        default=_default_i_rx,
        type=int,
        help="Receiver bias current DAC",
    )
    args = parser.parse_args()
    main(**vars(args))

