import argparse
import json
import numpy as np
import os
from config_dtime import datetime_now

v2a_nonrouted_channels = [6,7,8,9,22,23,24,25,38,39,40,54,55,56,57]

def main(*files, disabled_json, **kwargs):
        for file in files:
                config={}
                with open(file, 'r') as f: config=json.load(f)
                
                chip_key=config['meta']['ASIC_ID']
                version = config['meta']['ASIC_VERSION']

                if version==2:
                    for channel in v2a_nonrouted_channels:
                        if not 'channel_mask' in config.keys():
                            config['channel_mask']=[0]*64
                        if not 'csa_enable' in config.keys():
                            config['csa_enable']=[1]*64
                        config['channel_mask'][channel]=1
                        config['csa_enable'][channel]=0
                
                if 'meta' in config.keys():
                    config['meta']['last_update'] = datetime_now()

                with open(file, 'w') as f: json.dump(config, f, indent=4)

                
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('input_files', nargs='+', help='''files to modify''')
    parser.add_argument('--disabled_json', type=str, default=None, help='''Disabled list to merge to config''')
    args = parser.parse_args()
    
    main(
        *args.input_files,
        disabled_json=args.disabled_json
    )
