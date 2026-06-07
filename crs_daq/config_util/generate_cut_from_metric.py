import h5py
import matplotlib.pyplot as plt
import yaml
import numpy as np
import argparse
import json
from matplotlib.patches import Rectangle
from matplotlib.collections import PatchCollection
from matplotlib import cm
from matplotlib.colors import Normalize
import merge_disabled_to_config
import time
import tqdm

_default_filename=None

_default_metric='mean'
_default_std_cut =2
_default_mean_cut=50
_default_rate_cut=10

def datetime_now():
	''' Return string with year, month, day, hour, minute '''
	return time.strftime("%Y_%m_%d_%H_%M_%Z")

def unique_channel_id(d):
    return ((d['io_group'].astype(int)*1000+d['io_channel'].astype(int))*1000 \
            + d['chip_id'].astype(int))*100 + d['channel_id'].astype(int)

def unique_to_channel_id(unique):
    return unique % 100

def unique_to_chip_id(unique):
    return (unique// 100) % 1000

def unique_to_io_channel(unique):
    return(unique//(100*1000)) % 1000

def unique_to_tiles(unique):
    return ( (unique_to_io_channel(unique)-1) // 4) + 1

def unique_to_io_group(unique):
    return(unique // (100*1000*1000)) % 1000

def parse_file(filename, max_entries=-1):
    d = dict()
    f = h5py.File(filename, 'r')
    unixtime = f['packets'][:]['timestamp'][f['packets']
                                            [:]['packet_type'] == 4]
    livetime = np.max(unixtime)-np.min(unixtime)
    data_mask = f['packets'][:]['packet_type'] == 0
    valid_parity_mask = f['packets'][:]['valid_parity'] == 1
    mask = np.logical_and(data_mask, valid_parity_mask)
    adc = f['packets']['dataword'][mask][:max_entries]
    unique_id = unique_channel_id(f['packets'][mask][:max_entries])
    unique_id_set = np.unique(unique_id)
    chips = f['packets']['chip_id'][mask][:max_entries]

    print("Number of packets in parsed files =", len(unique_id))
    for chip in tqdm.tqdm(range(0, 255), desc='parsing data...'):
        _iomask = chips==chip
        _adc = adc[_iomask]
        _unique_id = unique_id[_iomask]
        for i in set(_unique_id):
            id_mask = _unique_id == i
            masked_adc = _adc[id_mask].astype(float)
            n=masked_adc.shape[0]
           # if n > 10:
           #         use_perc = 200./n
           #         perc0 = np.percentile(masked_adc, use_perc)
           #         perc1 = np.percentile(masked_adc, 100.-use_perc)
           #         mask = np.logical_and(masked_adc < perc1+1,  masked_adc > perc0-1)  
           #         masked_adc = masked_adc[mask]
            d[i] = dict(
                mean=np.mean(masked_adc),
                std=np.std(masked_adc),
                rate=n / (livetime + 1e-9))
    return d


def apply_cut_generate_disabled(d, metric, cut, polarity, file):
    nonrouted_v2a_channels=[6,7,8,9,22,23,24,25,38,39,40,54,55,56,57]
    routed_v2a_channels=[i for i in range(64) if i not in nonrouted_v2a_channels]
    
    io_groups = set(unique_to_io_group( np.array(list(d.keys())) ))
    tiles = set(unique_to_tiles( np.array(list(d.keys())) ))

    disabled_list = {}
    
    timestamp=datetime_now()
    fname='cut-'+timestamp+'.json'
    disabled_list['meta']={ \
            fname : {\
            'metric'   : metric,
            'polarity' : polarity,
            'cut'      : cut,
            'created': timestamp,
            'datafile' : file
            }
        }

    for io_group in io_groups:
        for tile in tiles:
            nchan=0
            mask = unique_to_io_group( np.array(list(d.keys())) ) == io_group
            mask = np.logical_and(mask, unique_to_tiles( np.array(list(d.keys())) )==tile )
            
            if not np.any(mask): continue
            
            d_keys = np.array(list(d.keys()) )[mask]

            for key in d_keys:
                channel_id = unique_to_channel_id(key)
                chip_id = unique_to_chip_id(key)
                if chip_id not in range(11,111): continue
                if channel_id not in range(64): continue
                weight = d[key][metric]
                if (weight>cut and not polarity) or (weight<cut and polarity): 
                    key='{}-{}-{}'.format(io_group, tile, chip_id)
                    if not key in disabled_list.keys(): disabled_list[key]=[]
                    disabled_list[key].append(int(channel_id))
                    nchan+=1

            print('Number of channels disabled on tile {}-{}: {}'.format(io_group, tile, nchan))
    
    with open(fname, 'w') as f:
        json.dump(disabled_list, f, indent=4)

    print('Disabled list written to {}'.format(fname))
    return

def main(filename=_default_filename,
         metric=_default_metric,
         cut=None,
         polarity=False,
         **kwargs):

    d = parse_file( filename )

    if cut is None:
        if metric=='std':
            cut=_default_std_cut 
        elif metric=='mean':
            cut=_default_mean_cut
        elif metric=='rate':
            cut=_default_rate_cut

    apply_cut_generate_disabled( d, metric, cut, polarity, filename)

    
if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--filename', default=_default_filename, type=str, help='''HDF5 fielname''')
    parser.add_argument('--cut', default=None, type=float, help='''Value to apply cut''')
    parser.add_argument('--polarity', default=False, action='store_true', help='''Cut BELOW cut value. Default behavior to cut above.''')
    parser.add_argument('--metric', default=_default_metric, type=str, help='''metric to plot; options: 'mean', 'std', 'rate' ''')
    args = parser.parse_args()
    main(**vars(args))
