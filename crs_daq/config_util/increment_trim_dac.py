import argparse
import json

chan=7
def main(*files, inc=0, **kwargs):
        for file in files:
                config={}
                with open(file, 'r') as f: config=json.load(f)
                
                if config['pixel_trim_dac'][chan] + inc >= 31:
                        config['pixel_trim_dac'][chan] = 31
                else: 
                        config['pixel_trim_dac'][chan] += inc

                with open(file, 'w') as f: json.dump(config, f, indent=4)

                
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('input_files', nargs='+', help='''files to modify''')
    parser.add_argument('--inc', type=int, default=0, help='''amount to change trim threshold by''')
    args = parser.parse_args()
    
    main(
        *args.input_files,
        inc=args.inc
    )
