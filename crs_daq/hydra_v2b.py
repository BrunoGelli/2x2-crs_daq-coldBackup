

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

module = sys.modules[__name__]
for var in RUN.config.keys():
    setattr(module, var, getattr(RUN, var))

_default_file_prefix=None
_default_disable_logger=True
_default_verbose=False
_default_ref_current_trim=0
_default_tx_diff=0
_default_tx_slice=15
_default_r_term=2
_default_i_rx=8
_default_recheck=False
v2b_root_ids=[21, 41, 71, 91]

def _parse_csv_ints(value):
    if value is None:
        return None
    values = []
    for item in str(value).split(','):
        item = item.strip()
        if item:
            values.append(int(item))
    return sorted(set(values))

def _excluded_chips_for_tile(io_group, tile):
    try:
        exclude_entry = iog_exclude.get(io_group, None)
    except Exception:
        return set()
    if exclude_entry is None:
        return set()
    if isinstance(exclude_entry, dict):
        excluded = exclude_entry.get(str(tile), exclude_entry.get(tile, []))
    else:
        excluded = exclude_entry
    if excluded is None:
        return set()
    if isinstance(excluded, str):
        excluded = [item.strip() for item in excluded.split(',') if item.strip()]
    if isinstance(excluded, int):
        excluded = [excluded]
    return set(int(chip_id) for chip_id in excluded)

def _exclude_for_network_base(io_group, tile):
    return {str(tile): sorted(_excluded_chips_for_tile(io_group, tile))}

def _ensure_empty_network_entries(c, iog, io_channels):
    if not hasattr(c, 'network') or c.network is None:
        c.network = {}
    if iog not in c.network or c.network[iog] is None:
        c.network[iog] = {}
    for io_channel in io_channels:
        if io_channel not in c.network[iog]:
            c.network[iog][io_channel] = {'miso_us': [], 'miso_ds': [], 'mosi': []}

def main(io_group, file_prefix=_default_file_prefix, \
         disable_logger=_default_disable_logger, \
         verbose=_default_verbose, \
         ref_current_trim=_default_ref_current_trim, \
         tx_diff=_default_tx_diff, \
         tx_slice=_default_tx_slice, \
         r_term=_default_r_term, \
         i_rx=_default_i_rx,
         pacman_tile=None,\
         io_channels=None,\
         **kwargs):
   
    c = larpix.Controller()
    c.io = larpix.io.PACMAN_IO(relaxed=True, config_filepath=f'io/pacman_io{io_group}.json')
    c.io.reset_larpix(length=4096*4, io_group=io_group) #2048 
    time.sleep(4096*4*1e-6)
    c.io.reset_larpix(length=4096*4, io_group=io_group) #2048 
    time.sleep(4096*4*1e-6)

    _file_prefix = file_prefix

    if True:
        now=time.strftime("%Y_%m_%d_%H_%M_%Z")
        config_name='controller-config-'+now+'.json'
        #VERSION_SPECIFIC
   

    for iog in [io_group]:
        print('inverting io group {} tiles {}'.format(iog, io_group_pacman_tile_[iog]))
        pacman_base.invert_pacman_uart(c.io, iog, io_group_asic_version_[iog], \
                                       io_group_pacman_tile_[iog]) 
    
        print('Working on io_group={}'.format(iog))
        if io_group_asic_version_[iog]=='2b':
            tiles=pacman_tile
            if pacman_tile is None:
                tiles = io_group_pacman_tile_[iog]
            else:
                tiles = [pacman_tile]
            requested_io_channels = _parse_csv_ints(io_channels)
            for tile in tiles:

                root_keys=[]
                tile_io_channels = utility_base.tile_to_io_channel([tile])
                if requested_io_channels is not None:
                    invalid_io_channels = sorted(set(requested_io_channels) - set(tile_io_channels))
                    if invalid_io_channels:
                        raise RuntimeError(
                            f'Requested io_channel(s) {invalid_io_channels} are not in tile {tile}; '
                            f'valid channels are {tile_io_channels}'
                        )
                    tile_io_channels = [ioc for ioc in tile_io_channels if ioc in requested_io_channels]
                tile_excluded_chips = _excluded_chips_for_tile(iog, tile)
                exclude_for_network_base = _exclude_for_network_base(iog, tile)
                for io_channel in tile_io_channels:
                    c.io.set_uart_clock_ratio(io_channel, 10, io_group=iog)
                    cid =  v2b_root_ids[ (io_channel-1) % 4]
                    if cid in tile_excluded_chips:
                        print(f'Skipping excluded ROOT chip {cid} on io_group={iog}, tile={tile}, io_channel={io_channel}')
                        continue
                    network_base.network_ext_node_from_tuple(c, iog, io_channel, cid)
                    candidate_root = network_base.setup_root(c, c.io, iog, \
                                                          io_channel,\
                                                          cid, verbose, \
                                                          io_group_asic_version_[iog], \
                                                          0, 0, 15, 2, 8)
                    if candidate_root!=None: root_keys.append(candidate_root)
           
                print('ROOT KEYS: ',root_keys)

                unconfigured=[]
                iog_tile_to_root_keys=utility_base.partition_chip_keys_by_io_group_tile(root_keys)
                print(iog_tile_to_root_keys)
                for iog_tile in iog_tile_to_root_keys.keys():
                    network_base.initial_network(c, c.io, iog_tile[0], \
                                             iog_tile_to_root_keys[iog_tile], \
                                             verbose, \
                                             io_group_asic_version_[iog], ref_current_trim, \
                                             tx_diff, tx_slice, r_term, i_rx, exclude=exclude_for_network_base)
                    if True:
                            
                        out_of_network=network_base.iterate_waitlist(c, c.io, iog, \
                                                                 tile_io_channels,
                                                                 verbose, \
                                                                 io_group_asic_version_[iog], \
                                                                 ref_current_trim,\
                                                                 tx_diff, tx_slice, \
                                                                 r_term, i_rx, exclude=exclude_for_network_base)
                        unconfigured.extend(out_of_network)
                _ensure_empty_network_entries(c, iog, utility_base.tile_to_io_channel([tile]))
                if _file_prefix is None: file_prefix='iog-{}-pacman-tile-{}-hydra-network'.format(iog, tile) 
                network_file = network_base.write_network_to_file(c, file_prefix, {io_group : [tile] },\
                                       unconfigured)

            return c, c.io

    

if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--io_group', default=None, \
                        type=int, help='''io group to network''')
    parser.add_argument('--pacman_tile', default=None, \
                        type=int, help='''PACMAN tile to work with''') 
    parser.add_argument('--io_channels', '--io-channels', dest='io_channels', default=None, type=str,
                        help='''Optional CSV of PACMAN io_channels to discover, e.g. 20 or 18,20''')
    parser.add_argument('--file_prefix', default=_default_file_prefix, \
                        type=str, help='''String prepended to filename''')
    parser.add_argument('--disable_logger', default=_default_disable_logger, \
                        action='store_true', help='''Disable logger''')
    parser.add_argument('--verbose', default=_default_verbose, \
                        action='store_true', help='''Enable verbose mode''')
    parser.add_argument('--ref_current_trim', \
                        default=_default_ref_current_trim, \
                        type=int, \
                        help='''Trim DAC for primary reference current''')
    parser.add_argument('--tx_diff', \
                        default=_default_tx_diff, \
                        type=int, \
                        help='''Differential per-slice loop current DAC''')
    parser.add_argument('--tx_slice', \
                        default=_default_tx_slice, \
                        type=int, \
                        help='''Slices enabled per transmitter DAC''')
    parser.add_argument('--r_term', \
                        default=_default_r_term, \
                        type=int, \
                        help='''Receiver termination DAC''')
    parser.add_argument('--i_rx', \
                        default=_default_i_rx, \
                        type=int, \
                        help='''Receiver bias current DAC''')
    args = parser.parse_args()
    main(**vars(args))

