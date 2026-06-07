import larpix
import larpix.io
import argparse
import pickledb
from tqdm import tqdm
import os
import json


def main(input_files, register, value, \
         **kwargs):
        if register is None or value is None:
            print('No register and/or value specified')
        for file in input_files:
            config={}
            with open(file, 'r') as f: config=json.load(f)
            config[register]=value
            with open(file, 'w') as f: json.dump(config, f, indent=4)
                           
if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('input_files', nargs='+', help='''files to modify''')
    parser.add_argument('--register', \
                        default=None, type=str, \
                        help='''Register to write''')

    parser.add_argument('--value', \
                        default=None, type=int, \
                        help='''Value to write''')
    
    args=parser.parse_args()
    c = main(args.input_files, \
            register=args.register, \
            value   =args.value)
