import warnings
warnings.filterwarnings("ignore")
import larpix
import time
import larpix.io
import argparse
from base import config_loader
from base import network_base
from tqdm import tqdm
from base import pacman_base
from base import utility_base
from base import enforce_parallel
import json
from base.utility_base import now
import sys
from runenv import runenv as RUN

module = sys.modules[__name__]
for var in RUN.config.keys():
    setattr(module, var, getattr(RUN, var))

_default_verbose = False
_default_controller_config = None


def enforce_iterative(nc, all_network_keys, n=3, configs=None, pbar_desc='p', pbar_position=0):
    ok, diff, unconfigured = enforce_parallel.enforce_parallel(nc, all_network_keys, pbar_desc=pbar_desc, pbar_position=pbar_position)
    if ok: return ok, diff, unconfigured
    elif n==0: 
        return ok, diff, unconfigured 
    else:
        all_keys = list(diff.keys())
        for net in unconfigured:
            all_keys += list(net)

        all_network_keys = []
        io_group_tiles = {}
        for chip_key in diff.keys():
            if not chip_key.io_group in io_group_tiles.keys(): io_group_tiles[chip_key.io_group] = set()
            io_group_tiles[chip_key.io_group].add(utility_base.io_channel_to_tile(chip_key.io_channel))  

        for chip_key in all_keys:
            if not chip_key.io_group in io_group_tiles: io_group_tiles[chip_key.io_group] = None

        for io_group in io_group_tiles.keys():
            tiles = io_group_tiles[io_group]
            config = configs[str(io_group)]
            if io_group_asic_version_[io_group]=='2b':
                c =  network_base.network_v2b(config, tiles=tiles, io_group=io_group, pacman_config=pacman_config)

            elif io_group_asic_version_[io_group] in [2, 'lightpix-1']:
                c = network_base.network_v2a(config, tiles=tiles, io_group=io_group) #, pacman_config=pacman_config)
           
            all_network_keys += enforce_parallel.get_chips_by_io_group_io_channel(config, use_keys=all_keys)

        return enforce_iterative(nc, all_network_keys, n=n-1, configs=configs, pbar_desc=pbar_desc, pbar_position=pbar_position)

def main(verbose,\
        controller_config, \
        io_group=None,
        pacman_tile=None,
        pacman_config=None):
    
    pacman_configs = {}
    with open(pacman_config, 'r') as f:
        pacman_configs = json.load(f)
    
    configs = {}
    with open(controller_config, 'r') as f:
        configs = json.load(f)
 
    # for each io_group, perform networking     
    good_io=False
    all_network_keys = []
    for io_group_ip_pair in pacman_configs['io_group']:
        _io_group = io_group_ip_pair[0]
        if io_group==_io_group:
            good_io=True
            break
    if not good_io:
        print('Missing io_group in PACMAN config file!')
        return

    if pacman_tile is None: 
        print('No tile specified')
        return

    tiles = [pacman_tile]

    if verbose: print('Configuring io_group={}, tile {}'.format(io_group, pacman_tile))
    
    c = None
    config = configs[str(io_group)]
    if io_group_asic_version_[io_group]=='2b':
        if verbose: print('loading network_v2b') 
        c =  network_base.network_v2b(config, tiles=tiles, io_group=io_group)
        if verbose: print('done') 
    
    elif io_group_asic_version_[io_group] in [2, 'lightpix-1']:
        if verbose: print('loading network_v2a')
        c = network_base.network_v2a(config, tiles=tiles, io_group=io_group) 
        if verbose: print('done') 
    
    all_network_keys += enforce_parallel.get_chips_by_io_group_io_channel(config, tiles)
        
    _tiles = []
    for _, io_channels in c.network.items(): _tiles += utility_base.io_channel_list_to_tile(list(io_channels.keys()) )    
    pacman_base.enable_pacman_uart_from_tile(c.io, io_group, [pacman_tile]) 
    if True:
        ok, diff, unconfigured = enforce_iterative(c, all_network_keys, configs=configs, pbar_desc='io_group {}, tile {}'.format(io_group, pacman_tile), pbar_position=0)
        if not ok:
            raise RuntimeError('Unconfigured chips!', diff)
    return c

if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', '-v', action='store_true',  default=_default_verbose)
    parser.add_argument('--io_group', default=None, \
                        type=int, help='''io_group of tile to network''')
    parser.add_argument('--pacman_tile', default=None, \
                        type=int, help='''tile to network''')
    parser.add_argument('--controller_config', default=_default_controller_config, \
                        type=str, help='''Controller config specifying hydra network''')                  
    parser.add_argument('--pacman_config', default="io/pacman.json", \
                        type=str, help='''Config specifying PACMANs''')
    args=parser.parse_args()
    c = main(**vars(args))

