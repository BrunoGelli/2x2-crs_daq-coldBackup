import warnings
warnings.filterwarnings("ignore")
import larpix
import argparse
import larpix.io
import time
from base import pacman_base, utility_base
import json
import os
from runenv import runenv as RUN
import sys
module = sys.modules[__name__]
for var in RUN.config.keys():
    setattr(module, var, getattr(RUN, var))


_default_verbose=False

def main(verbose, pacman_config):
    
    c = larpix.Controller()
    c.io = larpix.io.PACMAN_IO(relaxed=True, config_filepath=pacman_config)

    pacman_configs = {}
    with open(pacman_config, 'r') as f:
        pacman_configs = json.load(f)

    for io_group_ip_pair in pacman_configs['io_group']:
        io_group = io_group_ip_pair[0]

        # disable pacman receivers
        c.io.set_reg(0x18, 0, io_group=io_group)
        
        # disable tile power, LARPIX clock
        c.io.set_reg(0x00000010, 0, io_group=io_group)
        c.io.set_reg(0x00000014, 0, io_group=io_group)

        utility_base.update_json(asic_config_paths_file_, io_group,None )
        utility_base.update_json(network_config_paths_file_, io_group,None )

if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pacman_config', default="io/pacman.json", \
                        type=str, help='''Config specifying PACMANs''')
    parser.add_argument('--verbose', '-v', action='store_true', \
                        default=_default_verbose)
    args=parser.parse_args()
    c = main(**vars(args))
