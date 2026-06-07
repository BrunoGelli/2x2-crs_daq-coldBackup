import warnings
warnings.filterwarnings("ignore")

import larpix
import larpix.io
import argparse
from base import config_loader
from tqdm import tqdm
from base import pacman_base
from base import utility_base
from base import enforce_parallel
from base.utility_base import now
import json
import sys
import os
from runenv import runenv as RUN

module = sys.modules[__name__]
for var in RUN.config.keys():
    setattr(module, var, getattr(RUN, var))

_default_verbose=False

def main(verbose, \
        asic_config, \
        config_subdir,\
        pacman_config,
        pid_logged=False):
        
        pacman_configs = {}
        with open(pacman_config, 'r') as f:
            pacman_configs = json.load(f)
        
        c = larpix.Controller()
        c.io = larpix.io.PACMAN_IO(relaxed=True, config_filepath=pacman_config)
        
        #list of network keys in order from root chip, for parallel configuration enforcement
        all_network_keys = []
 
        ## LOAD DEFAULT CONFIG FIRST

        for io_group_ip_pair in pacman_configs['io_group']:
            io_group = io_group_ip_pair[0]   
            
            CONFIG=None
            print('Loading current config...')
            CONFIG=utility_base.get_from_json(asic_config_paths_file_,io_group)

            network_config_file = utility_base.get_from_json(network_config_paths_file_, io_group)
            all_network_keys += enforce_parallel.get_chips_by_io_group_io_channel( network_config_file ) 
            config_loader.load_config_from_directory(c, CONFIG) 
            
        
        # Make a second controller but now load the new configuration

        nc = larpix.Controller()
        nc.io = larpix.io.PACMAN_IO(relaxed=True, config_filepath=pacman_config)
        
        for io_group_ip_pair in pacman_configs['io_group']:
            io_group = io_group_ip_pair[0]   
            CONFIG=None
            CONFIG='{}/{}'.format(asic_config, config_subdir)

            network_config_file = utility_base.get_from_json(network_config_paths_file_, io_group)
            config_loader.load_config_from_directory(nc, CONFIG)
            utility_base.update_json(asic_config_paths_file_, io_group,CONFIG )

        # now, nc has the new configuration loaded, c has the old configuration
        # parse these and get all differences

        # loop over every chip in c and get the corresponding chip in nc
        # compare all registers
        # if the same, remove the chip from all_network_keys
        remove=[]
        for chip in c.chips:
            diff = c[chip].config.compare( nc[chip].config )
            if len(diff.keys())==0:
                remove.append(chip)

        for chip in remove:
            for io_chan_list in all_network_keys:
                if str(chip) in io_chan_list:
                    io_chan_list.remove(str(chip))

        #ensure UARTs are enable on pacman to receive configuration packets
        for io_group_ip_pair in pacman_configs['io_group']:
            io_group = io_group_ip_pair[0]
            pacman_base.enable_all_pacman_uart_from_io_group(c.io, io_group)
        
        pos=0
        tag='configuring...'
        if pid_logged:
            pid = os.getpid()
            tag = utility_base.get_from_process_log(pid)
            pos = enforce_parallel.tag_to_config_map[tag]

        #enforce all configurations in parallel (one chip per io channel per cycle)
        #note: using nc here, not c
        ok, diff, unconfigured = enforce_parallel.enforce_parallel(nc, all_network_keys,unmask_last=False, pbar_desc=tag, pbar_position=pos)
        if not ok:
            raise RuntimeError(diff)

        if pid_logged: print('\n{} configured successfully'.format(tag))
        return


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--asic_config', default=None, \
                        type=str, help='''ASIC config to load and enforce''')
    parser.add_argument('--config_subdir', default=None, \
                        type=str, help='''Subdirectory in larger config dir. Ignroed if asic_config not specified''')
    parser.add_argument('--pacman_config', default="io/pacman.json", \
                        type=str, help='''Config specifying PACMANs''')
    parser.add_argument('--pid_logged', action='store_true', default=False) 
    parser.add_argument('--verbose', '-v', action='store_true',  default=_default_verbose)
    args=parser.parse_args()
    c = main(**vars(args))

