import json
from RUNENV import *
import argparse

_default_verbose=False

def main(verbose):
    
    for io_group in io_group_pacman_tile_.keys():
        if io_group_asic_version_==2:
            print('add code here')



if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', '-v', action='store_true', \
                        default=_default_verbose)
    args=parser.parse_args()
    c = main(**vars(args))


