import larpix
import larpix.io
import argparse
from tqdm import tqdm
import os
import json
from config_dtime import datetime_now

_default_verbose=False
_default_periodic_trigger_cycles=400000
_default_periodic_reset_cycles=4096 #409600
_default_vref_dac=None ###cold 223 ### warm 185
_default_vcm_dac=None ### cold 68 ### warm 50
_default_ref_current_trim=0
_default_tx_diff=0
_default_tx_slice=15
_default_r_term=2
_default_i_rx=8



def main(input_files, verbose, \
         periodic_trigger_cycles=_default_periodic_trigger_cycles, \
         periodic_reset_cycles=_default_periodic_reset_cycles, \
         vref_dac=_default_vref_dac, \
         vcm_dac=_default_vcm_dac, \
         ref_current_trim=_default_ref_current_trim, \
         tx_diff=_default_tx_diff, \
         tx_slice=_default_tx_slice, \
         r_term=_default_r_term, \
         i_rx=_default_i_rx, \
         **kwargs):
        
        for file in input_files:
            config={}
            with open(file, 'r') as f: config=json.load(f)
            config['enable_periodic_trigger']=1
            config['enable_rolling_periodic_trigger']=1
            config['enable_periodic_reset']=1
            config['enable_rolling_periodic_reset']=0
            config['enable_hit_veto']=0
            config['enable_periodic_trigger_veto']=0
            config['periodic_trigger_mask']=[0]*64
            config['threshold_global'] = 255
            if not vcm_dac is None:  config['vcm_dac'] = vcm_dac
            if not vref_dac is None: config['vref_dac'] = vref_dac
            config['periodic_trigger_cycles'] = periodic_trigger_cycles
            config['periodic_reset_cycles'] = periodic_reset_cycles
            if 'meta' in config.keys():
                config['meta']['last_update'] = datetime_now()
                config['meta']['description']  = 'pedestal'

            with open(file, 'w') as f: json.dump(config, f, indent=4)
                           
if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('input_files', nargs='+', help='''files to modify''')
    parser.add_argument('--verbose', default=_default_verbose, \
                        action='store_true', help='''Enable verbose mode''')
    parser.add_argument('--periodic_trigger_cycles', \
                        default=_default_periodic_trigger_cycles, type=int, \
                        help='''Periodic trigger cycles [MCLK]''')
    parser.add_argument('--periodic_reset_cycles', \
                        default=_default_periodic_reset_cycles, type=int, \
                        help='''Periodic reset cycles [MCLK]''')
    parser.add_argument('--vref_dac', default=_default_vref_dac, type=int, \
                        help='''Vref DAC''')
    parser.add_argument('--vcm_dac', default=_default_vcm_dac, type=int, \
                        help='''Vcm DAC''')
    parser.add_argument('--ref_current_trim', \
                        default=_default_ref_current_trim, \
	                    type=int, \
                        help='''Trim DAC for primary reference current''')
    parser.add_argument('--tx_diff', \
                        default=_default_tx_diff, \
                        type=int, \
                        help='''Differential per-slice loop current DAC''')
    parser.add_argument('--tx_slice', \
                        default=_default_tx_slice, \
                        type=int, \
                        help='''Slices enabled per transmitter DAC''')
    parser.add_argument('--r_term', \
                        default=_default_r_term, \
                        type=int, \
                        help='''Receiver termination DAC''')
    parser.add_argument('--i_rx', \
                        default=_default_i_rx, \
                        type=int, \
                        help='''Receiver bias current DAC''')

    args=parser.parse_args()
    c = main(args.input_files, verbose=args.verbose, \
            periodic_trigger_cycles=args.periodic_trigger_cycles, \
            periodic_reset_cycles=args.periodic_reset_cycles, \
            vref_dac=args.vref_dac, \
            vcm_dac=args.vcm_dac, \
            ref_current_trim=args.ref_current_trim, \
            tx_diff=args.tx_diff, \
            tx_slice=args.tx_slice, \
            r_term=args.r_term, \
            i_rx=args.i_rx)
