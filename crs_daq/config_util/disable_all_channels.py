import argparse
import json


v2a_nonrouted_channels = [6,7,8,9,22,23,24,25,38,39,40,54,55,56,57]

def main(*files, disabled_list=None, **kwargs):
    disabled = {}
    if not disabled_list is None:
        with open(disabled_list, 'r') as f:
            disabled = json.load(f)

    for file in files:
            config={}
            with open(file, 'r') as f: config=json.load(f)
                
            config['channel_mask'] = [1]*64
            config['csa_enable'] = [0]*64
            
            with open(file, 'w') as f: json.dump(config, f, indent=4)

                
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('input_files', nargs='+', help='''files to modify''')
    args = parser.parse_args()
    
    main(
        *args.input_files
    )
