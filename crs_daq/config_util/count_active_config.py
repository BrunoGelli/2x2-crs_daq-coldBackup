import argparse
import json
import numpy as np

def main(*files, disabled_json, **kwargs):
        total=0
        used=[]
        chips=0
        count=0
        for file in files:
                config={}
                with open(file, 'r') as f: config=json.load(f)
                if not 'csa_enable' in config.keys(): 
                    total+=64
                    chips+=1
                    continue
                if not 'channel_mask' in config.keys():
                    continue
                asic_key=config['meta']['ASIC_ID']
                if asic_key in used:
                    print(asic_key)
                    continue
                chips+=1
                used.append(asic_key)
                mask = np.logical_and(config['csa_enable'], np.logical_not(config['channel_mask'])  )
                _s = np.sum(mask)
                version=config['meta']['ASIC_VERSION']
                if not version=='2b':
                    if _s>49:
                        print(asic_key)
                        _s=49
                total+=_s
        
#        print('n channels: {} ( {:0.4f}% )'.format(total, 100*total/(49*16*100*3+64*16*100)) )
        print('n channels: {} ( {:0.4f}% )'.format(total, 100*total/(64*8*100)) )
        print('n chips: {} ( {:0.3f}% )'.format(chips, 8*100*chips/6400) )
        print(count)
                
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('input_files', nargs='+', help='''files to modify''')
    parser.add_argument('--disabled_json', type=str, default=None, help='''Disabled list to merge to config''')
    args = parser.parse_args()
    
    main(
        *args.input_files,
        disabled_json=args.disabled_json
    )
