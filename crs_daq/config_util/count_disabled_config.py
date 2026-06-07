import argparse
import json
import numpy as np

def main(*files, disabled_json, **kwargs):
        total=0
        for file in files:
                config={}
                with open(file, 'r') as f: config=json.load(f)
                
                chip_key=config['meta']['CHIP_KEY']
                version=config['meta']['ASIC_VERSION']
                _s = sum(config['channel_mask'])
                if version=='2b': 
                    total+=_s
                else:
                    total+=(_s-(64-49))
        
        print('total: ', total)
                
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('input_files', nargs='+', help='''files to modify''')
    parser.add_argument('--disabled_json', type=str, default=None, help='''Disabled list to merge to config''')
    args = parser.parse_args()
    
    main(
        *args.input_files,
        disabled_json=args.disabled_json
    )
