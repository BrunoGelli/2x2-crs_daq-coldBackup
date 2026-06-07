import larpix
import larpix.io
import argparse
import tqdm
import os
import json
import h5py
import numpy as np
_default_verbose=False
_default_periodic_reset_cycles=64
_default_adc_hold_delay=15
_default_vref_dac=185 ###cold 223 ### warm 185
_default_vcm_dac=45 ### cold 68 ### warm 45
_default_hit_veto=1
_rms_multiplier=3
_offset_warm=210
_offset_cryo=365
_default_ped_vref_dac=185
_default_ped_vcm_dac=50
_default_cryo=False
_VDDA=1800
glob_scale=_VDDA/256.

def adc_to_mV(adc, vref_dac, vcm_dac, vdda=_VDDA):
    vref = vref_dac/256*vdda
    vcm  = vcm_dac/256*vdda
    scale = (vref-vcm)/256
    return vcm + scale*adc

def io_channel_to_tile(io_channel):
    return np.floor((io_channel-1-((io_channel-1)%4))/4+1)

def unique_channel_id(d):
    return ((d['io_group'].astype(int)*1000+io_channel_to_tile(d['io_channel'].astype(int)))*1000
            + d['chip_id'].astype(int))*100 + d['channel_id'].astype(int)

def unique_chip_id(d):
    return ((d['io_group'].astype(int)*1000+io_channel_to_tile(d['io_channel'].astype(int)))*1000
            + d['chip_id'].astype(int))*100

def unique_channel_id_from_asic(asic_id, channel):
    io_group, tile, chip = str(asic_id).split('-')
    return ((int(io_group)*1000+int(tile))*1000+ int(chip))*100 + int(channel)

def unique_chip_id_from_asic(asic_id):
    io_group, tile, chip = str(asic_id).split('-')
    return ((int(io_group)*1000+int(tile))*1000+ int(chip))*100 

def unique_to_asic_id(unique):
    return '{}-{}-{}'.format( unique_to_io_group(unique), unique_to_tiles(unique), unique_to_chip_id(unique))

def unique_to_channel_id(unique):
    return unique % 100


def unique_to_chip_id(unique):
    return (unique // 100) % 1000


def unique_to_io_channel(unique):
    return (unique//(100*1000)) % 1000


def unique_to_tiles(unique):
    return ((unique_to_io_channel(unique)-1) // 4) + 1


def unique_to_io_group(unique):
    return (unique // (100*1000*1000)) % 1000


def parse_file(filename, max_entries=-1):
    d, d_chip = dict(), dict()
    f = h5py.File(filename, 'r')
    unixtime = f['packets'][:]['timestamp'][f['packets']
                                            [:]['packet_type'] == 4]
    livetime = np.max(unixtime)-np.min(unixtime)
    data_mask = f['packets'][:]['packet_type'] == 0
    valid_parity_mask = f['packets'][:]['valid_parity'] == 1
    mask = np.logical_and(data_mask, valid_parity_mask)
    adc = f['packets']['dataword'][mask][:max_entries]
    unique_id = unique_channel_id(f['packets'][mask][:max_entries])
    unique_id__chip = unique_chip_id(f['packets'][mask][:max_entries])
    unique_id_set = np.unique(unique_id)
    chips = f['packets']['chip_id'][mask][:max_entries]

    #get chip means and channel_means
    print("Number of packets in parsed files=", len(unique_id))
    for chip in tqdm.tqdm(range(11, 111), desc='looping over chip_id'):
        _iomask = chips==chip
        _adc = adc[_iomask]
        _unique_id = unique_id[_iomask]
        _unique_id_chip = unique_id__chip[_iomask]
        
        for i in set(_unique_id_chip):
            id_mask = _unique_id == i
            masked_adc = _adc[id_mask]
            d_chip[int(i)] = dict(
                mean=np.mean(masked_adc),
                std=np.std(masked_adc),
                rate=len(masked_adc) / (livetime + 1e-9))

        for i in set(_unique_id):
            id_mask = _unique_id == i
            masked_adc = _adc[id_mask]
            d[int(i)] = dict(
                mean=np.mean(masked_adc),
                std=np.std(masked_adc),
                rate=len(masked_adc) / (livetime + 1e-9))
    
    return d, d_chip


def main(input_files, verbose, \
         periodic_reset_cycles=_default_periodic_reset_cycles, \
         adc_hold_delay=_default_adc_hold_delay,\
         vref_dac=_default_vref_dac, \
         vcm_dac=_default_vcm_dac, \
         hit_veto=_default_hit_veto,\
         pedestal_file=None,
         ped_vref_dac=_default_ped_vref_dac,\
         ped_vcm_dac=_default_ped_vcm_dac,\
         cryo=_default_cryo,\
         **kwargs):
       
        offset=_offset_warm
        if cryo:offset=_offset_cryo
        d, d_chip={},{}
        if not pedestal_file is None:
            d, d_chip =parse_file(pedestal_file)
            #print(d_chip.keys())
        for file in input_files:
            config={}
            try:
                with open(file, 'r') as f: config=json.load(f)
            except:
                print('Unable to open file {}'.format(file))
                continue
            asic_id = config['ASIC_ID']
            config['enable_periodic_trigger']=0
            config['enable_periodic_reset']=1
            config['enable_rolling_periodic_reset']=1
            config['enable_hit_veto']=hit_veto
            config['vcm_dac'] = vcm_dac
            config['vref_dac'] = vref_dac
            config['periodic_reset_cycles'] = periodic_reset_cycles
            config['adc_hold_delay']=adc_hold_delay
            
            threshold_global=255
            if len(d_chip.keys())>0:
                unique = unique_chip_id_from_asic(asic_id)
                
                if int(unique) in d_chip.keys():
                    mean= adc_to_mV(d_chip[unique]['mean'], ped_vref_dac, ped_vcm_dac)
                    std = adc_to_mV(d_chip[unique]['std'], ped_vref_dac, ped_vcm_dac)
                    if np.isnan(mean) or np.isnan(std):
                        mean=600
                        std =8
                    threshold_global = int(((mean + _rms_multiplier*std)-offset)/glob_scale)
                        
            config['threshold_global']=threshold_global

            with open(file, 'w') as f: json.dump(config, f, indent=4)
                           
if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('input_files', nargs='+', help='''files to modify''')
    parser.add_argument('--verbose', default=_default_verbose, \
                        action='store_true', help='''Enable verbose mode''')
    parser.add_argument('--periodic_reset_cycles', \
                        default=_default_periodic_reset_cycles, type=int, \
                        help='''Periodic reset cycles [MCLK]''')
    parser.add_argument('--vref_dac', default=_default_vref_dac, type=int, \
                        help='''Vref DAC''')
    parser.add_argument('--vcm_dac', default=_default_vcm_dac, type=int, \
                        help='''Vcm DAC''')
    parser.add_argument('--adc_hold_delay', default=_default_adc_hold_delay, type=int, \
                        help='''adc_hold_delay, default=15''')
    parser.add_argument('--hit_veto', default=_default_hit_veto, type=int, \
                        help='''hit_veto, default=1''')    
    parser.add_argument('--pedestal_file', default=None, type=str, \
                        help='''Packet-format pedestal data. If provided, use to guess at initial thresholds''')
    parser.add_argument('--ped_vref_dac', default=_default_ped_vref_dac, type=int, \
                        help='''Vref DAC used when taking pedestal darta''')
    parser.add_argument('--ped_vcm_dac', default=_default_ped_vcm_dac, type=int, \
                        help='''Vcm DAC used when taking pedestal data''')
    parser.add_argument('--cryo',
                        default=_default_cryo,
                        action='store_true',
                        help='''Flag for cryogenic operation''')

    args=parser.parse_args()
    c = main(args.input_files, verbose=args.verbose, \
            periodic_reset_cycles=args.periodic_reset_cycles, \
            vref_dac=args.vref_dac, \
            adc_hold_delay=args.adc_hold_delay,\
            hit_veto=args.hit_veto,\
            vcm_dac=args.vcm_dac,\
            ped_vcm_dac=args.ped_vcm_dac,\
            ped_vref_dac=args.ped_vref_dac,\
            cryo=args.cryo,\
            pedestal_file=args.pedestal_file)
