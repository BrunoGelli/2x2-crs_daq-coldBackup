import argparse
import json
import numpy as np
import os
from config_dtime import datetime_now

v2a_nonrouted_channels = [6,7,8,9,22,23,24,25,38,39,40,54,55,56,57]

trim_scale_=1.45        #mV / DAC
cryo_scale_=2.34        #mV / DAC
glob_scale_=1800/256    #mV / DAC

def parse_toggle_json(toggle_json):

    if not os.path.isfile(toggle_json):
        raise RuntimeError('Toggle list does not exist')

    toggle_list = {}
    with open(toggle_json, 'r') as f: toggle_list=json.load(f)

    return toggle_list

def main(*files, toggle_json, toggle_global, cryo, **kwargs):
    
    global trim_scale_
    global glob_scale_
    if cryo: trim_scale_=cryo_scale_ 
    
    toggle_list=parse_toggle_json(toggle_json)
    meta='unknown-toggle'
    if 'meta' in toggle_list.keys():
        meta=toggle_list['meta']
        meta['toggle_global']=toggle_global
    disabled=0
    bottomed=0
    for file in files:
        config={}
        with open(file, 'r') as f: config=json.load(f)
                
        chip_key=config['meta']['ASIC_ID']
        version = config['meta']['ASIC_VERSION']

        if chip_key in toggle_list.keys():
            if not 'pixel_trim_dac' in config.keys():
                config['pixel_trim_dac']=[16]*64

            #if toggle_global:
            #    #global toggling code here
            #    for pair in toggle_list[chip_key]:
            #        config['pixel_trim_dac'][pair[0]] += pair[1]
            #    
            #    #check for bottomed out trims
            #    if np.any(np.array(config['pixel_trim_dac']) < 0):
            #        decrement=False
            #        #check for room to decrease global threshold
            #        max_ptd = np.max(config['pixel_trim_dac'])
            #        if (31-max_ptd) > glob_scale_ / trim_scale_:
            #            decrement=True
            #        else:
            #            count_bottomed=np.sum([ 1 if ptd < 1 else 0 for ptd in config['pixel_trim_dac']   ] )
            #            if count_bottomed > 32:
            #                decrement=True
            #    
            #        if decrement:
            #            config['threshold_global'] -= 1
            #            config['pixel_trim_dac'] = [ ptd + int(glob_scale_/trim_scale_) for ptd in config['pixel_trim_dac'] ]
            #
            #    #check for maxed out trims, see if room to incrememnt global up
            #    if np.any( np.array(config['pixel_trim_dac']) > 31):
            #        # some channels too high, might need to raise global threshold
            #        min_ptd = np.min(config['pixel_trim_dac'])
            #        if min_ptd > glob_scale_ / trim_scale_:
            #            #room to increment global up
            #            config['threshold_global'] += 1 
            #            config['pixel_trim_dac'] = [ ptd - int(glob_scale_/trim_scale_) + 1 for ptd in config['pixel_trim_dac'] ] 
            #        
            
        
            if True:
                for pair in toggle_list[chip_key]:
                    config['pixel_trim_dac'][pair[0]] += pair[1]
            
            # check all values in range
            for chan in range(64):
                if config['pixel_trim_dac'][chan] > 31:
                    config['pixel_trim_dac'][chan] = 31
                    config['channel_mask'][chan]=1
                    if not 'csa_enable' in config.keys():
                        config['csa_enable']=[1]*64
                    if not 'channel_mask' in config.keys():
                        config['channel_mask']=[0]*64
                    config['csa_enable'][chan]=0
                    disabled+=1
                if config['pixel_trim_dac'][chan] < 0:
                    config['pixel_trim_dac'][chan] = 0
                    bottomed+=1
                
            if 'meta' in config.keys():
                config['meta']['last_update'] = datetime_now()
                if not 'toggle_lists' in config['meta'].keys(): config['meta']['toggle_lists'] = []
                config['meta']['toggle_lists'].append(meta)

            with open(file, 'w') as f: json.dump(config, f, indent=4)

    print('disabled {} channels'.format(disabled))
    print('bottomed out {} channels'.format(bottomed))
                
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('input_files', nargs='+', help='''files to modify''')
    parser.add_argument('--toggle_json', type=str, default=None, help='''List of (channel, toggle_value) to merge to config pixel trims''')
    parser.add_argument('--toggle_global', action='store_true', default=False, help='''Allow freedom to change global DACs also''')
    parser.add_argument('--cryo', action='store_true', default=False, help='''If toggle_global also set, adjust trim_scale for cryo''')
    args = parser.parse_args()
    
    main(
        *args.input_files,
        toggle_json=args.toggle_json,
        toggle_global=args.toggle_global,
        cryo=args.cryo
    )
