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
        pacman_config,\
        no_unmask_last=False,\
        pid_logged=False):
       
        unmask_last = not no_unmask_last
        pacman_configs = {}
        with open(pacman_config, 'r') as f:
            pacman_configs = json.load(f)
        
        c = larpix.Controller()
        c.io = larpix.io.PACMAN_IO(relaxed=True, config_filepath=pacman_config)
        
        #list of network keys in order from root chip, for parallel configuration enforcement
        all_network_keys = []
       

        for io_group_ip_pair in pacman_configs['io_group']:
            io_group = io_group_ip_pair[0]   
            
            CONFIG=None
            if asic_config is None:
                print('Loading current config...')
                CONFIG=utility_base.get_from_json(asic_config_paths_file_,io_group)
            else:
                CONFIG='{}/{}'.format(asic_config, config_subdir)
                utility_base.update_json(asic_config_paths_file_, io_group,CONFIG )

            network_config_file = utility_base.get_from_json(network_config_paths_file_, io_group)
            all_network_keys += enforce_parallel.get_chips_by_io_group_io_channel( network_config_file ) 
            config_loader.load_config_from_directory(c, CONFIG) 
            
            #make the network keys io channel agnostic
            remove = [] 
            for i in range(len(all_network_keys)):
                for j in range(len(all_network_keys[i])):
                    if not all_network_keys[i][j] in c.chips:
                        
                        found=False
                        chip = all_network_keys[i][j]
                        tile =  utility_base.io_channel_to_tile(chip.io_channel)
                        io_channels = [ 1 + 4*(tile - 1) + n for n in range(4)]
                        
                        for io_channel in io_channels:
                            chip_key = '{}-{}-{}'.format(chip.io_group, io_channel, chip.chip_id)
                            if chip_key in c.chips:
                                all_network_keys[i][j] = chip_key
                                found=True
                                break

                        if not found:
                            remove.append(chip)


            for chip in remove:

                for i in range(len(all_network_keys)):
                    if chip in all_network_keys[i]:\
                            all_network_keys[i].remove(chip)

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
        ok, diff, unconfigured = enforce_parallel.enforce_parallel(c, all_network_keys, unmask_last=unmask_last, pbar_desc=tag, pbar_position=pos)
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
    parser.add_argument('--no_unmask_last', action='store_true',  default=False)
    parser.add_argument('--verbose', '-v', action='store_true',  default=_default_verbose)
    args=parser.parse_args()
    c = main(**vars(args))

