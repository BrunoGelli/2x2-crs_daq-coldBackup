import argparse
import json
import numpy as np
from matplotlib import pyplot as plt

ignore_csa=False

def main(*files, inc=0, **kwargs):
        trims = []
        l_low_trim_chips = []
        for file in files:
                config={}
                with open(file, 'r') as f: config=json.load(f)
               
                try:
                    ptd = np.array(config['pixel_trim_dac'])
                    if any(ptd < 0) or any(ptd > 31):
                        print(file, ptd)
                except:
                    ptd=np.array([16]*64)
                try:
                    csa = np.array(config['csa_enable'])
                    csa = np.logical_and( csa, np.logical_not(config['channel_mask']) )
                except:
                    csa=np.array([1]*64)

                if not np.any(csa) and not ignore_csa: continue
                if ignore_csa:
                    csa=[1]*64
                trims += list( ptd[csa]  )
                
                if np.percentile(ptd[csa], 80) < 4: 
                    print('Low Trims!!', config['meta']['CHIP_KEY'], ptd[csa], 'tdac = ', config['threshold_global']) 
                    l_low_trim_chips.append(config['meta']['CHIP_KEY'])
                if np.percentile(ptd[csa], 40) > 20: print('High Trims!!', config['meta']['CHIP_KEY'], ptd[csa]) 


        vals, bins = np.histogram(trims, range=(-0.5, 31.5), bins=32)

        for ival, val in enumerate(vals):
            print('{}: {}'.format(ival, val))

        print(','.join([str(v) for v in vals]))

        print('Number of low trim chips: ', len(l_low_trim_chips))
        with open('low_trim_chips.json', 'w') as f:
            json.dump(l_low_trim_chips, f)
        fig=plt.figure()
        ax=fig.add_subplot()
        ax.hist(trims,range=(-0.5, 31.5), bins=32 )
        ax.grid()
        ax.set_xlabel('pixel trim dac', fontsize=14)
        ax.set_ylabel('channel count', fontsize=14)
        fig.savefig('ptd.png')
                
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('input_files', nargs='+', help='''files to modify''')
    parser.add_argument('--inc', type=int, default=0, help='''amount to change global threshold by''')
    args = parser.parse_args()
    
    main(
        *args.input_files,
        inc=args.inc
    )
