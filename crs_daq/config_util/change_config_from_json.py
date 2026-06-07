import argparse
import json
import numpy as np
import os
from config_dtime import datetime_now

v2a_nonrouted_channels = [6,7,8,9,22,23,24,25,38,39,40,54,55,56,57]

def parse_json(toggle_json):

    if not os.path.isfile(toggle_json):
        raise RuntimeError('Toggle list does not exist')

    toggle_list = {}
    with open(toggle_json, 'r') as f: toggle_list=json.load(f)

    return toggle_list

def main(*files, change_json, **kwargs):
    
    change_list=parse_json(change_json)
    
    for file in files:
        config={}
        with open(file, 'r') as f: config=json.load(f)
                
        asic_id=config['meta']['ASIC_ID']
        version = config['meta']['ASIC_VERSION']

        if asic_id in change_list.keys():
            for register in change_list[asic_id].keys():
                config[register]=change_list[asic_id][register]
    
        
        with open(file, 'w') as f: json.dump(config, f, indent=4)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('input_files', nargs='+', help='''files to modify''')
    parser.add_argument('--change_json', type=str, default=None, help='''JSON file with (chip, {register : value}) to change in config''')
    args = parser.parse_args()
    
    main(
        *args.input_files,
        change_json=args.change_json
    )
