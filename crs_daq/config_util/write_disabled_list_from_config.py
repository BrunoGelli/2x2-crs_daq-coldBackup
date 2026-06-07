import argparse
import json
import numpy as np

def main(*files, disabled_json, **kwargs):
        disabled={}
        for file in files:
                config={}
                with open(file, 'r') as f: config=json.load(f)
                
                chip_key=config['meta']['ASIC_ID']
                
                if True:
                    mask = np.array(config['channel_mask'])
                    vals = list(np.where(mask>0)[0].astype(int))
                    print(vals)
                    disabled[str(chip_key)]=list([int(val) for val in vals])
        with open('disable.json', 'w') as f: json.dump(disabled, f, indent=4)

                
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('input_files', nargs='+', help='''files to modify''')
    parser.add_argument('--disabled_json', type=str, default=None, help='''Disabled list to merge to config''')
    args = parser.parse_args()
    
    main(
        *args.input_files,
        disabled_json=args.disabled_json
    )
