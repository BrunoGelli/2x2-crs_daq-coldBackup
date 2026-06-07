import larpix
import larpix.io
import argparse
from base import config_loader
from RUNENV import *
import pickledb
import shutil
from tqdm import tqdm
from base import pacman_base
from base import utility_base
from base import enforce_parallel
from base.utility_base import now, chip_key_to_asic_id
import time
import record_data
import threading
import json

_default_verbose=False
_default_runtime=0.25
_default_disabled_list=None

v2a_nonrouted_channels = [6,7,8,9,22,23,24,25,38,39,40,54,55,56,57]

def main(verbose, \
        threshold,
        runtime,
        disabled_list):
        
        
        db = pickledb.load(env_db, True) 
        rundb = pickledb.load(run_db, True)
        #check DB file to ensure run conditions satisfy requirements
        for io_group in io_group_pacman_tile_.keys():

            #check that tiles are configured with hydra network
            TILES_CONFIGURED = db.get('IO_GROUP_{}_TILES_NETWORKED'.format(io_group))
            
            if not TILES_CONFIGURED:
                print('NO TILES  configured for io_group={}'.format(io_group))
                return

            if len(TILES_CONFIGURED)==0:
                print('NO TILES  configured for io_group={}'.format(io_group))
                return

            #check pacman is properly configured 
            PACMAN_CONFIGURED = db.get('IO_GROUP_{}_PACMAN_CONFIGURED'.format(io_group))
            if not PACMAN_CONFIGURED:
                print('PACMAN not configured for io_group={}'.format(io_group))
                return

            #check network config exists
            NETWORK_CONFIG =  db.get('IO_GROUP_{}_NETWORK_CONFIG'.format(io_group))
            if not NETWORK_CONFIG:
                print('NO existing network file for io_group={}'.format(io_group))
                return

        c = larpix.Controller()
        c.io = larpix.io.PACMAN_IO(relaxed=True)
        
        #list of network keys in order from root chip, for parallel configuration enforcement
        all_network_keys = []
       

        for io_group in io_group_pacman_tile_.keys():
            print('Using default config')
            CONFIG = db.get('DEFAULT_CONFIG_{}'.format(io_group))

            all_network_keys += enforce_parallel.get_chips_by_io_group_io_channel(db.get('IO_GROUP_{}_NETWORK_CONFIG'.format(io_group)) )  
            config_loader.load_config_from_directory(c, CONFIG) 
            
            db.set('IO_GROUP_{}_ASIC_CONFIGS'.format(io_group), CONFIG)
            db.set('LAST_UPDATE', now()) 
        #ensure UARTs are enable on pacman to receive configuration packets
        for io_group in io_group_pacman_tile_.keys(): 
            pacman_base.enable_all_pacman_uart_from_io_group(c.io, io_group)

        #Peform test in parallel for one chip per io channel
        # 1) enable all channels to trigger with default given threshold
        # 2) measure trigger rate
        # 3) disable channels with excessive rate
        
        disabled = {}
        if not disabled_list is None:
            with open(disabled_list, 'r') as f:
                disabled = json.load(f)
    
        ichip = -1 

        p_bar = tqdm(range(len(c.chips)))
        p_bar.refresh()
        ok, diff = False, {}

        while True:
            current_chips = []
            ichip += 1
            working=False
            for net in all_network_keys:
                if ichip>=len(net): continue
                working=True
                current_chips.append(net[ichip])
    
            if not working: break
            
            for chip in current_chips: 
                c[chip].config.channel_mask = [0]*64
                c[chip].config.csa_enable   = [1]*64
                c[chip].config.threshold_global = threshold
                c[chip].config.enable_hit_veto = 0
                if c[chip].asic_version==2: 
                    for channel in v2a_nonrouted_channels: c[chip].config.channel_mask[channel]=1
                
                asic_id = chip_key_to_asic_id(chip)

                if asic_id in disabled:
                    for channel in disabled[asic_id]: 
                        c[chip].config.channel_mask[channel] = 1
                        c[chip].config.csa_enable[channel]   = 0

            c.multi_write_configuration( [(chip, (range(c[chip].config.num_registers))) for chip in current_chips]  )
            time.sleep(runtime)

            for chip in current_chips: 
                c[chip].config.channel_mask = [1]*64
                c[chip].config.csa_enable   = [0]*64
                c[chip].config.threshold_global = 255
                c[chip].config.enable_hit_veto = 1
            ok, diff = c.enforce_configuration(current_chips, timeout=0.01, connection_delay=0.1, n=7, n_verify=3)
        
            p_bar.update(len(current_chips))
            p_bar.refresh()

        p_bar.close()
        
        return


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', '-v', action='store_true',  default=_default_verbose) 
    parser.add_argument('--threshold', type=int, default=128, help='Value to set for threshold_global register for test')
    parser.add_argument('--runtime', type=int, default=_default_runtime, help='Sample time for data rate for each iteration')
    parser.add_argument('--disabled_list', type=str, default=_default_disabled_list, help='JSON with asic_id : list of disabled channels')
    args=parser.parse_args()
    c = main(**vars(args))

