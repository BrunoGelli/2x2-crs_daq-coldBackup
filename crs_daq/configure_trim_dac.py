import larpix
import larpix.io
import argparse
import time
import json
import copy
import numpy as np
from runenv import runenv as RUN
#from RUNENV import *
from base import pacman_base
from base import config_loader
from base import enforce_parallel
from base import utility_base
from base.utility_base import *
from tqdm import tqdm
import matplotlib.pyplot as plt

import sys
from runenv import runenv as RUN

module = sys.modules[__name__]
for var in RUN.config.keys():
    setattr(module, var, getattr(RUN, var))

_v2a_nonrouted=[6,7,8,9,22,23,24,25,38,39,40,54,55,56,57]

_initial_trim_dac=16
_runtime_trim=0.1
_maxrate_trim=100
_minrate_trim=0.1

_vref_dac=185
_vcm_dac=41 # 50


_default_disabled_list=None
_default_iteration=999

def disable_dict_from_file(c, disabled_list):
    csa_disable=dict()
    if disabled_list:
        print('\nloading disabled list: ',disabled_list)
        with open(disabled_list,'r') as f: csa_disable=json.load(f)
    else:
        print('No disabled list provided.')

    for chip_key in c.chips:
        if c[chip_key].asic_version==2:
            asic_id = chip_key_to_asic_id(chip_key)
            if asic_id in csa_disable.keys():
                for chan in _v2a_nonrouted: csa_disable[asic_id].append(chan)
            else:
                csa_disable[asic_id]=_v2a_nonrouted
    return csa_disable


def initial_asic_config(c, chips, trim_dac):
    chip_register_pairs = []
    for chip in chips:
        c[chip].config.vref_dac=_vref_dac #register 82
        c[chip].config.vcm_dac=_vcm_dac # register 82
        c[chip].config.pixel_trim_dac=[trim_dac]*64 # regiseters [0-63]
        c[chip].config.enable_periodic_reset = 1 # register 128
        c[chip].config.enable_rolling_periodic_reset = 1 # regiseter 128
        c[chip].config.adc_hold_delay = 15 # register 129        
        c[chip].config.periodic_reset_cycles=64 # registers [163-165]
        c[chip].config.channel_mask=[1]*64
        c[chip].config.csa_enable=[0]*64
        chip_register_pairs.append( (chip, list(range(0,64))+[82,83,128,129,163,164,165]+list(range(66,74))+list(range(131,139)) ) )

    for i in range(10):
        c.multi_write_configuration(chip_register_pairs, connection_delay=0.1)

    return


def enable_frontend(c, chips, csa_disable, all_network_keys, pacman_configs):
    ichip=-1
    while True:
        chip_register_pairs = []
        current_chips = []
        ichip+=1
        working=False
        for net in all_network_keys:
            if ichip>=len(net): continue
            working=True
            current_chips.append(net[ichip])
        if not working: break
       
        for chip_key in current_chips:
            if chip_key not in chips: continue
            c[chip_key].config.channel_mask=[0]*64
            c[chip_key].config.csa_enable=[1]*64
            asic_id = chip_key_to_asic_id(chip_key)
            if asic_id in csa_disable.keys():
                for channel in csa_disable[asic_id]:
                    c[chip_key].config.channel_mask[channel]=1
                    c[chip_key].config.csa_enable[channel]=0
            chip_register_pairs.append( (chip_key, list(range(66,74))+list(range(131,139))) )

        #ATTENTION: huge time sink. need to check if this can be parallellized
        for i in range(3):
            c.multi_write_configuration(chip_register_pairs, connection_delay=0.1)
            c.multi_write_configuration(chip_register_pairs, connection_delay=0.1)
            
    for io_group_ip_pair in pacman_configs['io_group']:
        io_group = io_group_ip_pair[0]
        pacman_base.enable_all_pacman_uart_from_io_group(c.io, io_group)
        
    return


def get_chip_key(packet):
    return '{}-{}-{}'.format(packet.io_group, packet.io_channel, packet.chip_id)


def mask_chip(c,chip,chip_register_pairs):
    c[chip].config.channel_mask=[1]*64
    c[chip].config.csa_enable=[0]*64
    chip_register_pairs.append( (chip, list(range(66,74))+list(range(131,139))) )

    
def combine_disabled_lists(original, updated):
    result={}
    for key in original.keys():
        if key not in result: result[key]=[]
        for chan in original[key]:
            if chan not in result[key]: result[key].append(chan)
    for key in updated.keys():
        if key not in result: result[key]=[]
        for chan in updated[key]:
            if chan not in result[key]: result[key].append(chan)
    return result


def disable_frontend_downstream_uart(c, all_network_keys):
    ichip=-1
    while True:
        chip_register_pairs = []
        current_chips = []
        ichip+=1
        working=False
        for net in all_network_keys:
            if ichip>=len(net): continue
            working=True
            current_chips.append(net[ichip])
        if not working: break

        for chip_key in current_chips:
            c[chip_key].config.channel_mask=[1]*64
            c[chip_key].config.csa_enable=[0]*64
            if c[chip_key].asic_version==2:
                c[chip_key].config.enable_miso_downstream=[0]*4
            else:
                c[chip_key].config.enable_piso_downstream=[0]*4
            chip_register_pairs.append( (chip_key, list(range(66,74))+list(range(131,139))+[125]) )

        if len(chip_register_pairs)>0:
            for i in range(10):
                c.multi_write_configuration(chip_register_pairs, connection_delay=0.1)
                c.multi_write_configuration(chip_register_pairs, connection_delay=0.1)

    return


def reenable_downstream(c, all_network_keys, config_downstream):
    ichip=-1
    while True:
        chip_register_pairs = []
        current_chips = []
        ichip+=1
        working=False
        for net in all_network_keys:
            if ichip>=len(net): continue
            working=True
            current_chips.append(net[ichip])
        if not working: break

        for chip_key in current_chips:
            if c[chip_key].asic_version==2: c[chip_key].config.enable_miso_downstream=config_downstream[chip_key]
            else: c[chip_key].config.enable_piso_downstream=config_downstream[chip_key]
            chip_register_pairs.append( (chip_key, [125]) )
        if len(chip_register_pairs)>0:
            for i in range(10):
                c.multi_write_configuration(chip_register_pairs, connection_delay=0.1)
                c.multi_write_configuration(chip_register_pairs, connection_delay=0.1)
    return



def bail(c, all_network_keys, bar_reenable):
    print('===== BAIL =====')
    config_downstream={}
    for chip in c.chips:
        if c[chip].asic_version==2: config_downstream[chip]= c[chip].config.enable_miso_downstream
        else: config_downstream[chip]= c[chip].config.enable_piso_downstream

    disabled_firing=True
    while disabled_firing==True:                                           
        disable_frontend_downstream_uart(c, all_network_keys)
        c.run(_runtime_trim,'check rate')
        all_packets = np.array(c.reads[-1])
        print('packet count {}'.format(all_packets.shape[0]))
        if all_packets.shape[0]==0: packets = np.array([]); disabled_firing=False
        else:
            packets = all_packets[np.vectorize(lambda x: x.packet_type)(all_packets)==0]
            disabled_firing=True

    reenable_downstream(c, all_network_keys, config_downstream)
    return

    

def setup_status(c, chips, csa_disable):
    status={}
    for chip in chips:
        asic_id = chip_key_to_asic_id(chip)
        trim = list(c[chip].config.pixel_trim_dac)
        status[chip] = dict( pixel_trim=trim,
                             active=[True]*64,
                             disable=[False]*64 )

        if asic_id in csa_disable.keys():
            for channel in range(64):
                if channel in csa_disable[asic_id]:
                    status[chip]['active'][channel]=False
                    status[chip]['disable'][channel]=True

    return status


def deactivate_status(status, chip, channel):
    status[chip]['active'][channel]=False
    status[chip]['disable'][channel]=True


def update_chip(c, status, iteration, track_progress, incremented, decremented):
    chip_register_pairs = []
    active_chips=0; active_channels=0
    for chip_key in status.keys():
        chip_register_pairs.append( (chip_key, list(range(64))+list(range(66,74))+list(range(131,139)) ) )
        c[chip_key].config.pixel_trim_dac=status[chip_key]['pixel_trim']
        for channel in range(64):
            if status[chip_key]['disable'][channel]==True or status[chip_key]['active'][channel]==False:
                c[chip_key].config.csa_enable[channel]=0
                c[chip_key].config.channel_mask[channel]=1
            else:
                active_channels+=1
        if True in status[chip_key]['active']: active_chips+=1
    c.multi_write_configuration(chip_register_pairs, connection_delay=0.01)
    print('active chips: ',active_chips,'\t active channels: ',active_channels)
    track_progress[iteration]=(active_channels, active_chips, incremented, decremented)
    return 


def increment_remaining_trim(c, status):
    chip_register_pairs = []
    for chip_key in status.keys():
        for channel in range(64):
            if status[chip_key]['disable'][channel]==False or status[chip_key]['active'][channel]==True:
                chip_register_pairs.append( (chip_key, list(range(64))+list(range(66,74))+list(range(131,139)) ) )
                if status[chip_key]['pixel_trim'][channel]<31:
                    c[chip_key].config.pixel_trim_dac[channel]=status[chip_key]['pixel_trim'][channel]+1
                c[chip_key].config.csa_enable[channel]=0
                c[chip_key].config.channel_mask[channel]=1
    c.multi_write_configuration(chip_register_pairs, connection_delay=0.01)
    return 
    

def toggle_trim_dac(c, chips, csa_disable, all_network_keys, minrate_trim=_minrate_trim, maxrate_trim=_maxrate_trim, runtime_trim=_runtime_trim):
    toggle_trim_csa_disable={}
    track_triggers={}
    track_progress={}
    status = setup_status(c, chips, csa_disable)

    iteration=0
    flag=True
    while flag:
        incremented=0; decremented=0
        timeStart = time.time()
        iteration +=1

        c.reads.clear()
        c.run(runtime_trim,'check rate')
        all_packets = np.array(c.reads[-1])
        print('iteration {}, packet count {}'.format(iteration,all_packets.shape[0]))

        if all_packets.shape[0]>4e6:
            bar_reenable = combine_disabled_lists(csa_disable, toggle_trim_csa_disable)
            bail(c, all_network_keys, bar_reenable)
            print('*****Breaking out of toggle dac function*****')
            flag=False
            break

        start=time.time()
        if all_packets.shape[0]==0: packets = np.array([])
        else: packets = all_packets[np.vectorize(lambda x: x.packet_type)(all_packets)==0]
        print('time to extract data packets:', time.time()-start)
        start=time.time()
        
        triggered_chips=set()
        if packets.shape[0]>0:
            iog_triggers = np.vectorize(lambda x: x.io_group)(packets).astype(int)
            ioc_triggers = np.vectorize(lambda x: x.io_channel)(packets).astype(int)
            chip_triggers = np.vectorize(lambda x: x.chip_id)(packets).astype(int)
            channel_triggers = np.vectorize(lambda x: x.channel_id)(packets).astype(int)
            chip_keys = np.vectorize(get_chip_key)(packets)
            triggered_chips = set(chip_keys)
            track_triggers[iteration]=(packets.shape[0],len(triggered_chips))

        print('time to extract from packets', time.time()-start)
        for chip in tqdm(chips):
            if chip in triggered_chips:
                ids = np.array(str(chip).split('-')).astype(int)
                mask = np.logical_and( iog_triggers==ids[0], ioc_triggers==ids[1] )
                mask = np.logical_and(mask, chip_triggers==ids[2])
                channels = channel_triggers[mask]
                triggered_channels = set(channels)
                channel_rate={}
                for channel in triggered_channels: channel_rate[channel]=np.sum(channel==channels)/runtime_trim

                for channel in range(64):
                    if status[chip]['active'][channel]==False: continue

                    if channel in channel_rate.keys():
                        if channel_rate[channel]>maxrate_trim:
                            status[chip]['pixel_trim'][channel] += 1
                            incremented+=1
                            if status[chip]['pixel_trim'][channel]>31:
                                status[chip]['pixel_trim'][channel]=31
                                deactivate_status(status, chip, channel)
                                asic_id = chip_key_to_asic_id(chip)
                                if asic_id not in toggle_trim_csa_disable.keys(): toggle_trim_csa_disable[asic_id]=[]
                                toggle_trim_csa_disable[asic_id].append(channel)
                        if channel_rate[channel]>=minrate_trim and channel_rate[channel]<=maxrate_trim:
                            deactivate_status(status, chip, channel)
                        if channel_rate[channel]<minrate_trim:
                            status[chip]['pixel_trim'][channel] -= 1
                            decremented+=1
                            if status[chip]['pixel_trim'][channel]<0:
                                status[chip]['pixel_trim'][channel]=0
                                deactivate_status(status, chip, channel)
                    else:
                        status[chip]['pixel_trim'][channel] -= 1
                        decremented+=1
                        if status[chip]['pixel_trim'][channel]<0:
                            status[chip]['pixel_trim'][channel]=0
                            deactivate_status(status, chip, channel)
            else:
                for channel in range(64):
                    if status[chip]['active'][channel]==False: continue
                    status[chip]['pixel_trim'][channel] -= 1
                    decremented+=1
                    if status[chip]['pixel_trim'][channel]<0:
                        status[chip]['pixel_trim'][channel]=0
                        deactivate_status(status, chip, channel)

        update_chip(c, status, iteration, track_progress, incremented, decremented)

        active_chip_count=0
        for chip_key in status.keys():
            if True in status[chip_key]['active']: active_chip_count+=1
            if active_chip_count == 1: break
        if active_chip_count==0: flag=False

        timeEnd = time.time()-timeStart
        print('incremented: ',incremented,'\t decremented: ',decremented,'\t processing time %.2f seconds\n'%timeEnd)

        if iteration==32:
            increment_remaining_trim(c, status)
            break
    
    return toggle_trim_csa_disable, track_progress, track_triggers


def recast_dictionary(d):
    out={}
    for k in d.keys(): out[str(k)]=d[k]
    return out


def save_to_json(filename, d, recast=True):
    if recast: d = recast_dictionary(d)
    with open(filename+'.json','w') as outfile:
        json.dump(d, outfile, indent=4)


def save_config_to_file(c, csa_disable):
    for chip in c.chips:
        c[chip].config.csa_enable=[1]*64
        c[chip].config.channel_mask=[0]*64
        asic_id = chip_key_to_asic_id(chip)
        if asic_id in csa_disable.keys():
            for channel in csa_disable[asic_id]:
                c[chip].config.csa_enable[channel]=0
                c[chip].config.channel_mask[channel]=1
    config_path=None
    config_path = config_loader.write_config_to_file(c, config_path)
    print('ASIC CONFIGURATION WRITTEN TO: ', config_path)
    return

        
def main(pacman_config='io/pacman.json',
         disabled_list=_default_disabled_list,
         iteration=_default_iteration,
         **kwargs):

    time_log={}
    time_initial = time.time()
    
    c = larpix.Controller()
    c.io = larpix.io.PACMAN_IO(relaxed=True, config_filepath=pacman_config)

    pacman_configs = {}
    with open(pacman_config, 'r') as f: pacman_configs = json.load(f)

    all_network_keys = []
    for io_group_ip_pair in pacman_configs['io_group']:
        io_group = io_group_ip_pair[0]

        CONFIG=None
        with open(asic_config_paths_file_, 'r') as ff:
            d=json.load(ff)
            CONFIG=d[str(io_group)]
        all_network_keys += enforce_parallel.get_chips_by_io_group_io_channel(utility_base.get_from_json(network_config_paths_file_, io_group) )
        config_loader.load_config_from_directory(c, CONFIG)
        
    for io_group_ip_pair in pacman_configs['io_group']:
        io_group = io_group_ip_pair[0]
        pacman_base.enable_all_pacman_uart_from_io_group(c.io, io_group)
        
    timeStart = time.time()
    csa_disable = disable_dict_from_file(c, disabled_list) #, csa_disable)
    timeEnd = time.time()-timeStart
    print('==> %.2f seconds --- disabled channels from input list\n'%timeEnd)
    save_to_json('input_disabled_list_iteration'+str(iteration), csa_disable, recast=False)
    time_log['disabled_input']=timeEnd

    chips_to_test=c.chips
    initial_chip_count=len(chips_to_test)
    last_chip_count=len(chips_to_test)
    ctr=-1
    trim_disable=csa_disable
    while len(chips_to_test):
        ctr+=1
        
        timeStart = time.time()
        if ctr==0: initial_asic_config(c, chips_to_test, 16)
        else: initial_asic_config(c, chips_to_test, 16)
        timeEnd = time.time()-timeStart
        print(ctr,'\t==> %.2f seconds --- setup initial ASIC configuration\n'%timeEnd)
        time_log['initial_config_'+str(ctr)]=timeEnd

        timeStart = time.time()
        enable_frontend(c, chips_to_test, csa_disable, all_network_keys, pacman_configs)
        timeEnd = time.time()-timeStart
        print(ctr,'\t==> %.2f seconds --- enable channel front-ends\n'%timeEnd)
        time_log['enable_frontend_'+str(ctr)]=timeEnd

        timeStart = time.time()
        toggle_trim_csa_disable, trim_track_progress, trim_track_triggers = toggle_trim_dac(c, chips_to_test, csa_disable, all_network_keys, minrate_trim=0.1, maxrate_trim=1, runtime_trim=10)
        timeEnd = time.time()-timeStart
        print(ctr,'\t==> %.2f seconds --- toggle trim DACs\n'%timeEnd)
        save_to_json('trim_disabled_list_ctr'+str(ctr)+'_iteration'+str(iteration), toggle_trim_csa_disable, recast=False)
        time_log['toggle_trim_itr_'+str(ctr)]=timeEnd

        after_trim={}
        for key in trim_disable.keys():
            if key not in after_trim: after_trim[key]=[]
            for chan in trim_disable[key]:
                if chan not in after_trim[key]: after_trim[key].append(chan)
        for key in toggle_trim_csa_disable.keys():
            if key not in after_trim: after_trim[key]=[]
            for chan in toggle_trim_csa_disable[key]:
                if chan not in after_trim[key]: after_trim[key].append(chan)

        trim_disable=after_trim
    
        save_to_json('time_log_ctr'+str(ctr)+'_iteration'+str(iteration), time_log, recast=False)
        save_to_json('combined_trim_disabled_list_ctr'+str(ctr)+'_iteration'+str(iteration), after_trim, recast=False)
        save_to_json('trim_configuration_ctr'+str(ctr)+'_iteration'+str(iteration), trim_track_progress, recast=True)
        save_to_json('trim_triggers_ctr'+str(ctr)+'_iteration'+str(iteration), trim_track_triggers, recast=True)

        revised_chips=[]
        for chip_key in chips_to_test:
            asic_id = chip_key_to_asic_id(chip_key)
            disabled_channels=set()
            if asic_id in trim_disable.keys(): disabled_channels=set(trim_disable[asic_id])
            active_channels=0; null_trim_channels=0
            for channel in range(64):
                if channel in disabled_channels: continue
                active_channels+=1
                if c[chip_key].config.pixel_trim_dac[channel]==0: null_trim_channels+=1
            if active_channels==null_trim_channels: revised_chips.append(chip_key)
            elif null_trim_channels/active_channels>=0.5 and active_channels>=20: revised_chips.append(chip_key)

        chip_register_pairs=[]
        for chip_key in revised_chips:
            if c[chip_key].config.threshold_global==0: continue
            c[chip_key].config.threshold_global=c[chip_key].config.threshold_global-1
            chip_register_pairs.append( (chip_key, [64]) )
        for i in range(10):
            c.multi_write_configuration(chip_register_pairs, connection_delay=0.01)

        chips_to_test=revised_chips
        this_chip_count=len(chips_to_test)
        print('reevaluate ',this_chip_count,' chips')
        if last_chip_count==this_chip_count and last_chip_count!=initial_chip_count: break
        last_chip_count=this_chip_count

        bail(c, all_network_keys, trim_disable)

    timeStart = time.time()
    save_config_to_file(c, trim_disable)
    timeEnd = time.time()-timeStart
    print('==> %.2f seconds --- save config to file'%timeEnd)
    time_log['save_config_to_file']=timeEnd
    
    return c


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pacman_config',
                        default='io/pacman.json',
                        type=str,
                        help='''PACMAN config file''')
    parser.add_argument('--disabled_list',
                        default=_default_disabled_list,
                        type=str,
                        help='''JSON-formatted dict of ASIC ID:[channels] to disable''')
    parser.add_argument('--iteration',
                        type=int,
                        help='''Iteration''')
    args = parser.parse_args()
    c = main(**vars(args))
