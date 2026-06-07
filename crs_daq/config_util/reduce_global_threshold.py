import larpix
import larpix.io
import argparse
import pickledb
from tqdm import tqdm
import os
import json


def main(asic_config, chip_list, value):
    
    chip_key_list = []
    with open(chip_list,'r') as f: 
        chip_key_list=json.load(f)

    for n in os.listdir(asic_config):
        conf = dict()
        if 'json' not in n:
            continue
    
        with open(asic_config+'/'+n) as c:
            conf = json.load(c)

            chip_key = conf['meta']['CHIP_KEY']

            if chip_key not in chip_key_list:
                continue

            conf['threshold_global'] -= value
            if conf['threshold_global'] < 0: 
                print('tdac = 0 for ', n)
                conf['threshold_global'] = 0
            if conf['threshold_global'] > 255: 
                print('tdac = 255 for ', n)
                conf['threshold_global'] = 255
            old_pixel_trim = conf['pixel_trim_dac']
            new_pixel_trim = [p+16 for p in old_pixel_trim]
            new_pixel_trim = [31 if p > 31 else p for p in new_pixel_trim]
            conf['pixel_trim_dac'] = new_pixel_trim

        with open(asic_config+'/'+n, 'w') as f: json.dump(conf, f, indent=4)
                           
if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--asic_config', \
                        default=None, type=str, \
                        help='''Register to write''')

    parser.add_argument('--chip_list', \
                        default=None, type=str, \
                        help='''Register to write''')

    parser.add_argument('--value', \
                        default=None, type=int, \
                        help='''Value to write''')
    
    args=parser.parse_args()
    c = main(asic_config=args.asic_config, \
            chip_list=args.chip_list, \
            value   =args.value)
