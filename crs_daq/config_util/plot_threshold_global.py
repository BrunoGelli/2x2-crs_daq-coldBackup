import argparse
import json
import numpy as np
from matplotlib import pyplot as plt

def main(*files, inc=0, **kwargs):
        globs = []
        total=0
        for file in files:
                config={}
                with open(file, 'r') as f: config=json.load(f)
                
                try:
                    glob = config['threshold_global']
                    total+=1
                    if glob > 45: print(config['meta']['CHIP_KEY'],':', glob)
                except:
                    glob=255
                globs.append(glob)
        print(total)

        vals, bins = np.histogram(globs, range=(-0.5, 31.5), bins=32)
        globs=np.array(globs)
        for val in  set(globs) :
            print('{}: {}'.format(val, np.sum(globs==val)))

        return
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
