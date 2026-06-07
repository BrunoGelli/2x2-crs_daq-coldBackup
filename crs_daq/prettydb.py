import json
import argparse

def main(input_file):
    
    d={}
    with open(input_file, 'r') as f:
        d=json.load(f)
    with open(input_file, 'w') as f:
        json.dump(d, f, indent=4)

if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input_file', '-i', default='None', \
                        type=str)
    args=parser.parse_args()
    c = main(**vars(args))
