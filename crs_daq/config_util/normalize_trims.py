import argparse
import json
import numpy as np
import os
from config_dtime import datetime_now

v2a_nonrouted_channels = [6,7,8,9,22,23,24,25,38,39,40,54,55,56,57]

def parse_toggle_json(toggle_json):

    if not os.path.isfile(toggle_json):
        raise RuntimeError('Toggle list does not exist')

    toggle_list = {}
    with open(toggle_json, 'r') as f: toggle_list=json.load(f)

    return toggle_list

def main(*files, **kwargs):
        for file in files:
                config={}
                with open(file, 'r') as f: config=json.load(f)
                
                chip_key=config['meta']['ASIC_ID']
                version = config['meta']['ASIC_VERSION']

                if True:
                    for chan in range(64):
                        if config['pixel_trim_dac'][chan] > 31:
                            config['pixel_trim_dac'][chan] = 31
                        if config['pixel_trim_dac'][chan] < 0:
                            config['pixel_trim_dac'][chan] = 0
                
                with open(file, 'w') as f: json.dump(config, f, indent=4)

                
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('input_files', nargs='+', help='''files to modify''')
    args = parser.parse_args()
    
    main(
        *args.input_files
    )
