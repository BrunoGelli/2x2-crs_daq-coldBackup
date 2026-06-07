import argparse
import json
import numpy as np
import os
from config_dtime import datetime_now

v2a_nonrouted_channels = [6,7,8,9,22,23,24,25,38,39,40,54,55,56,57]

def parse_disabled_json(disabled_json):

    if not os.path.isfile(disabled_json):
        raise RuntimeError('Disabled list does not exist')

    disabled_list = {}
    with open(disabled_json, 'r') as f: disabled_list=json.load(f)

    channel_masks = {}
    for key in disabled_list:
        if key=='meta': continue
        channel_masks[key] = [1 if channel in disabled_list[key] else 0 for channel in range(64)]

    meta = None
    if 'meta' in disabled_list.keys():
        meta = disabled_list['meta']
    
    return channel_masks, meta

def main(*files, disabled_json, **kwargs):
        channel_masks, meta =parse_disabled_json(disabled_json)
        for file in files:
                config={}
                with open(file, 'r') as f: config=json.load(f)
                
                chip_key=config['meta']['ASIC_ID']
                version = config['meta']['ASIC_VERSION']

                if chip_key in channel_masks.keys():
                    if not 'channel_mask' in config.keys(): config['channel_mask']=[1]*64
                    _s = sum(config['channel_mask'])
                    mask = np.array(config['channel_mask'])+np.array(channel_masks[chip_key]) 
                    config['channel_mask'] = [1 if val>0 else 0 for val in mask]
                    if not 'periodic_trigger_mask' in config.keys(): config['periodic_trigger_mask']=[1]*64
                    mask = np.array(config['periodic_trigger_mask'])+np.array(channel_masks[chip_key])
                    config['periodic_trigger_mask'] = [1 if val>0 else 0 for val in mask]
                    if version==2: 
                        for channel in v2a_nonrouted_channels:
                            config['channel_mask'][channel]=1
                    print(chip_key, ': disabled', sum(config['channel_mask'])-_s, 'keys')
                    config['csa_enable']=[1 if val==0 else 0 for val in channel_masks[chip_key]]

                
                if 'meta' in config.keys():
                    config['meta']['last_update'] = datetime_now()
                    if not 'disabled_lists' in config['meta'].keys(): config['meta']['disabled_lists'] = []
                    config['meta']['disabled_lists'].append(meta)

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
