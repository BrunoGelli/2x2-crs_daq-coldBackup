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
import time
import tqdm

_default_filename=None
_default_min_rate=0.01
_default_max_rate=1.

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
    packets=f['packets'][:]
    unixtime = packets['timestamp'][packets['packet_type'] == 4]
    livetime = np.max(unixtime)-np.min(unixtime)
    data_mask = packets['packet_type'] == 0
    valid_parity_mask = packets['valid_parity'] == 1
    mask = np.logical_and(data_mask, valid_parity_mask)
    adc = packets['dataword'][mask][:max_entries]
    unique_id = unique_channel_id(packets[mask][:max_entries])
    unique_id_set = np.unique(unique_id)
    chips = packets['chip_id'][mask][:max_entries]
    
    fifo_full_mask=packets['shared_fifo']>0
    
    fifo_full_io_group   = packets[fifo_full_mask]['io_group']
    fifo_full_io_channel = packets[fifo_full_mask]['io_channel']

    print("Number of packets in parsed files =", len(unique_id))
    for chip in tqdm.tqdm(range(11, 111), desc='parsing data...'):
        _iomask = chips==chip
        _adc = adc[_iomask]
        _unique_id = unique_id[_iomask]
        for i in set(_unique_id):
            id_mask = _unique_id == i
            masked_adc = _adc[id_mask]
            d[i] = dict(
                mean=np.mean(masked_adc),
                std=np.std(masked_adc),
                rate=len(masked_adc) / (livetime + 1e-9))

    return d, fifo_full_io_group, fifo_full_io_channel


def toggle_trims_write_increments(d,min_rate,max_rate,file,toggle_filename, fifo_iog, fifo_chan):
    nonrouted_v2a_channels=[6,7,8,9,22,23,24,25,38,39,40,54,55,56,57]
    routed_v2a_channels=[i for i in range(64) if i not in nonrouted_v2a_channels]
    
    io_groups = set(unique_to_io_group( np.array(list(d.keys())) ))
    tiles = set(unique_to_tiles( np.array(list(d.keys())) ))

    toggle_list = {}
    
    timestamp=datetime_now()
    fname=toggle_filename
    if fname is None: fname='toggle-'+timestamp+'.json'
    toggle_list['meta']={ \
            fname : {\
            'min_rate'   : min_rate,
            'max_rate'   : max_rate,
            'created': timestamp,
            'datafile' : file
            }
        }

    count_in_range=0
    for io_group in io_groups:
        #fifo_full_mask=fifo_iog==io_iog
        #fifo_full_io_chan=fifo_chan[fifo_full_mask]

        for tile in tiles:
            io_channels = [4*tile - i for i in range(4) ]
    

            nchan=0
            mask = unique_to_io_group( np.array(list(d.keys())) ) == io_group
            mask = np.logical_and(mask, unique_to_tiles( np.array(list(d.keys())) )==tile )
            
            if not np.any(mask): continue
            
            used_chip_chan = []

            d_keys = np.array(list(d.keys()) )[mask]

            for key in d_keys:
                channel_id = unique_to_channel_id(key)
                chip_id = unique_to_chip_id(key)
                used_chip_chan.append((chip_id, channel_id))

                if chip_id not in range(11,111): continue
                if channel_id not in range(64): continue
                weight = d[key]["rate"]
                if weight > min_rate and weight < max_rate: count_in_range+=1
                if weight>max_rate:
                    tog = int(np.log10(weight/max_rate))+1
                    if tog < 1: tog=1
                    key='{}-{}-{}'.format(io_group, tile, chip_id)
                    if not key in toggle_list.keys(): toggle_list[key]=[]
                    toggle_list[key].append( (int(channel_id), tog) )
                    nchan+=1
                elif weight<min_rate:
                    key='{}-{}-{}'.format(io_group, tile, chip_id)
                    if not key in toggle_list.keys(): toggle_list[key]=[]
                    toggle_list[key].append( (int(channel_id), -1) )
                    nchan+=1
            
            for chipid in range(11,111):
                key='{}-{}-{}'.format(io_group, tile, chipid)
                if not key in toggle_list.keys(): toggle_list[key]=[]
                for chanid in range(64):
                    if (chipid, chanid) in used_chip_chan: continue
                    #print(chipid, chanid)
                    if min_rate > 0:
                        toggle_list[key].append( (int(chanid), -1) )
                        nchan+=1

            print('Number of channels toggled on tile {}-{}: {}'.format(io_group, tile, nchan))
    
    with open(fname, 'w') as f:
        json.dump(toggle_list, f, indent=4)

    print('Toggle list written to {}'.format(fname))
    print('total in range channels:', count_in_range)
    return

def main(filename=_default_filename,
         min_rate=_default_min_rate,
         max_rate=_default_max_rate,
         toggle_filename=None,
         **kwargs):

    d, fifo_iog, fifo_chan = parse_file( filename )

    toggle_trims_write_increments( d, min_rate, max_rate, filename, toggle_filename, fifo_iog, fifo_chan)

    
if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--filename', default=_default_filename, type=str, help='''HDF5 filename''')
    parser.add_argument('--toggle_filename', default=None, type=str, help='''Filename to write toggle list to''')
    parser.add_argument('--max_rate', default=_default_max_rate, type=float, help='''Maximum pixel target rate [Hz] ''')
    parser.add_argument('--min_rate', default=_default_min_rate, type=float, help='''Minimum pixel target rate [Hz]''')
    
    args = parser.parse_args()
    main(**vars(args))

