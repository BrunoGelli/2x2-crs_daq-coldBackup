import argparse
import json
from config_dtime import datetime_now

v2a_nonrouted_channels = [6,7,8,9,22,23,24,25,38,39,40,54,55,56,57]

def main(*files, disabled_list=None, **kwargs):
    disabled = {}
    if not disabled_list is None:
        with open(disabled_list, 'r') as f:
            disabled = json.load(f)

    for file in files:
            config={}
            with open(file, 'r') as f: config=json.load(f)
                
            config['csa_enable'] = [0]*64
            
            asic_id = config['meta']['ASIC_ID']
            if asic_id in disabled.keys():
                for channel in disabled[asic_id]:
                    config['channel_mask'][channel]=1
                    config['csa_enable'][channel]=0

            if config['meta']['ASIC_VERSION']==2:
                for channel in v2a_nonrouted_channels:
                    config['channel_mask'][channel]=1
                    config['csa_enable'][channel]=0

            if 'meta' in config.keys():
                    config['meta']['last_update'] = datetime_now()

            with open(file, 'w') as f: json.dump(config, f, indent=4)

                
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('input_files', nargs='+', help='''files to modify''')
    parser.add_argument('--inc', type=int, default=0, help='''amount to change global threshold by''')
    args = parser.parse_args()
    
    main(
        *args.input_files,
        inc=args.inc
    )
