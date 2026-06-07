import warnings
warnings.filterwarnings("ignore")

import larpix
import larpix.io
import argparse
from tqdm import tqdm
import os
import json
from config_dtime import datetime_now
import numpy as np

hydra_registers = ['enable_piso_downstream', 'enable_piso_upstream', 'enable_posi', 'enable_miso_downstream', 'enable_miso_upstream', 'enable_mosi']

def io_channel_to_tile(io_channel):
    return int(np.floor((io_channel-1-((io_channel-1)%4))/4+1))

def get_asic_id(chip):
    return '{}-{}-{}'.format(chip.io_group, io_channel_to_tile(chip.io_channel), chip.chip_id)

def main(input_files, \
         **kwargs):
        
        #Take inventory of all chips in default config
        d_asic_ids =[]
        registers={}
        chip_keys={}
        
        _default_configs='.default_asic_configs_.json'

        with open(_default_configs, 'r') as f: default_paths=json.load(f)
        
        for io_group in default_paths.keys():
            config_dir = default_paths[io_group]
            for file in os.listdir(config_dir):
                with open('{}/{}'.format(config_dir, file), 'r') as f: asic_config=json.load(f)
                _chip_key=None
                _asic_id =None
                _version=None
                if 'meta' in asic_config.keys():
                    _chip_key=asic_config['meta']['CHIP_KEY']
                    _asic_id=asic_config['meta']['ASIC_ID']
                    _version=asic_config['meta']['ASIC_VERSION']
                else:
                    _chip_key=asic_config['CHIP_KEY']
                    _asic_id=asic_config['ASIC_ID']
                    _version=asic_config['ASIC_VERSION'] 

                chip_keys[_asic_id]= _chip_key
                d_asic_ids.append(_asic_id)

                registers[_asic_id]={}
                for register in hydra_registers:
                    if register in asic_config.keys():
                        registers[_asic_id][register] = asic_config[register]
               
        used_keys=[]
        for file in input_files:
            asic_config={}
            with open(file, 'r') as f: asic_config=json.load(f)

            _chip_key=None
            _asic_id =None
            _version=None
            if 'meta' in asic_config.keys():
                _chip_key=asic_config['meta']['CHIP_KEY']
                _asic_id=asic_config['meta']['ASIC_ID'] 
                _version=asic_config['meta']['ASIC_VERSION']
            else:
                _chip_key=asic_config['CHIP_KEY']
                _asic_id=asic_config['ASIC_ID']
                _version=asic_config['ASIC_VERSION']

            
            if _asic_id in d_asic_ids:
                for register in registers[_asic_id].keys():
                    asic_config[register]=registers[_asic_id][register]

                asic_config['meta']['CHIP_KEY'] = chip_keys[_asic_id]

            with open(file, 'w') as f: json.dump(asic_config, f, indent=4)

            if not _chip_key==chip_keys[_asic_id]: os.system('mv {} {}'.format( file, file.replace(_chip_key, chip_keys[_asic_id])  ))
            
            used_keys.append(_asic_id)

        print('Remove files:', set(d_asic_ids)-set(used_keys)) 
     
if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('input_files', nargs='+', help='''files to modify''')
    parser.add_argument('--controller_config', default='configs/controller_config.json', \
                        type=str, help='''Controller config for hydra networks''')

    args=parser.parse_args()
    c = main(args.input_files, controller_config=args.controller_config)
