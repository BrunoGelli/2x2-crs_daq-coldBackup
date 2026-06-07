import larpix
import larpix.io
import argparse
import time
import json
import copy
import numpy as np
from runenv import runenv as RUN
from base import pacman_base
from base import config_loader
from base import enforce_parallel
from base import utility_base
from base.utility_base import *
import os

import sys
from runenv import runenv as RUN

module = sys.modules[__name__]
for var in RUN.config.keys():
    setattr(module, var, getattr(RUN, var))


_initial_global_dac=60 #100 ### initial global DAC set value
_runtime_global=0.5 #0.1 ### runtime to assess chip trigger rate
_maxrate_global=1000. ### maximum chip trigger rate to set global DAC
_minrate_global=10. ### minimum chip trigger rate to set global DAC
_maxdac_global=50 ### disable maximum rate channel, and reassess rate if global DAC above this value
_mindac_global=20 ### re-evaluate chip if global DAC set below this value
_maxtriggers=1e6 #200000. ### do not lower global DACs if total packet count exceeds this value
_bail_threshold=3

_v2a_nonrouted=[6,7,8,9,22,23,24,25,38,39,40,54,55,56,57]
_vref_dac=223
_vcm_dac=68 


_default_disabled_list=None
_default_chip_list=None



def disable_dict_from_file(c, disabled_list):
    csa_disable=dict()
    if disabled_list:
        print('\nloading disabled list: ', disabled_list)
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



def chips_to_test_from_file(chip_list):
    print('\n loading chip list: ', chip_list)
    with open(chip_list,'r') as f: asic_id_list=json.load(f)
    return asic_id_list



def initial_asic_config(c, chips):
    chip_register_pairs = []
    for chip in chips:
        c[chip].config.vref_dac=_vref_dac #register 82
        c[chip].config.vcm_dac=_vcm_dac # register 82
        c[chip].config.threshold_global=_initial_global_dac # register 64
        c[chip].config.enable_periodic_reset = 1 # register 128
        c[chip].config.enable_rolling_periodic_reset = 1 # regiseter 128
        c[chip].config.adc_hold_delay = 15 # register 129        
        c[chip].config.periodic_reset_cycles=64 # registers [163-165]
        chip_register_pairs.append( (chip, [64,82,83,128,129,163,164,165]) )

    for i in range(10):
        c.multi_write_configuration(chip_register_pairs, connection_delay=0.01)
    return



def enable_frontend(c, chips_to_test, csa_disable, all_network_keys, pacman_configs):
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
            if chip_key not in chips_to_test: continue
            c[chip_key].config.channel_mask=[0]*64
            c[chip_key].config.csa_enable=[1]*64
            asic_id = chip_key_to_asic_id(chip_key)
            if asic_id in csa_disable.keys():
                for channel in csa_disable[asic_id]:
                    c[chip_key].config.channel_mask[channel]=1
                    c[chip_key].config.csa_enable[channel]=0
            chip_register_pairs.append( (chip_key, list(range(66,74))+list(range(131,139))) )

        for i in range(10):
            c.multi_write_configuration(chip_register_pairs, connection_delay=0.01)
            
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

    
def silence_highest_rate(c, chip, channel_rate, toggle_global_csa_disable):
    highest_rate=-1.
    highest_channel=None
    for channel in channel_rate:
        if channel_rate[channel]>highest_rate:
            highest_rate=channel_rate[channel]
            highest_channel=int(channel)
    if highest_channel!=None:
        c[chip].config.channel_mask[highest_channel]=1
        c[chip].config.csa_enable[highest_channel]=0
        asic_id=chip_key_to_asic_id(chip)
        if asic_id not in toggle_global_csa_disable.keys(): toggle_global_csa_disable[asic_id]=[]
        toggle_global_csa_disable[asic_id].append(highest_channel)

        

def toggle_global_dac(c, toggled_chips, csa_disable, all_network_keys, pacman_configs, max_channel_fraction=0.8):
    chip_reevaluate_queue=set()
    
    toggle_global_csa_disable={}
    
    bookkeep_masked_channels=0
    track_triggers={}
    track_progress={}
    
    high_rate=True
    iteration=0
    masked_chip_count=0
    masked_chip_set=set()
    offenders={}
    while high_rate:
        iteration+=1
        high_rate=False
        
        c.reads.clear()
        c.run(_runtime_global,'check rate')
        all_packets = np.array(c.reads[-1])
        print('\n\niteration {}, packet count {}'.format(iteration,all_packets.shape[0]))

        if all_packets.shape[0]==0: packets = np.array([])
        else: packets = all_packets[np.vectorize(lambda x: x.packet_type)(all_packets)==0]
        
        if packets.shape[0]>0:
            iog_triggers = np.vectorize(lambda x: x.io_group)(packets).astype(int)
            ioc_triggers = np.vectorize(lambda x: x.io_channel)(packets).astype(int)
            chip_triggers = np.vectorize(lambda x: x.chip_id)(packets).astype(int)
            channel_triggers = np.vectorize(lambda x: x.channel_id)(packets).astype(int)
            chip_keys = np.vectorize(get_chip_key)(packets)
            triggered_chips = set(chip_keys)
            track_triggers[iteration]=(packets.shape[0],len(triggered_chips))
        else:
            track_triggers[iteration]=(0,0)
            chip_register_pairs = []
            all_lowered_active_chips=0
            for chip in toggled_chips:
                if chip in  masked_chip_set: continue
                all_lowered_active_chips+=1
                if c[chip].config.threshold_global==0:
                    mask_chip(c, chip, chip_register_pairs)
                    masked_chip_count+=1
                    masked_chip_set.add( chip )
                else:
                    c[chip].config.threshold_global -= 1
                chip_register_pairs.append( (chip, [64]) )
            if all_lowered_active_chips>0:
                for _ in range(3):
                    c.multi_write_configuration(chip_register_pairs, connection_delay=0.01)
                print('Lowering threshold on all active chips\t',all_lowered_active_chips)
                print('masked count: ',len(masked_chip_set),'\n')
            high_rate=True
            if all_lowered_active_chips==0: high_rate=False; print('No remaining active chips. Exiting at iteration ',iteration)
            continue

        channel_mask_count=0
        increment_count=0
        decrement_count=0
        untriggered_count=0
        chip_register_pairs=[]
        for chip in toggled_chips:
            if c[chip].config.threshold_global<_mindac_global and chip not in masked_chip_set:
                chip_reevaluate_queue.add(chip)
                mask_chip(c, chip, chip_register_pairs)
                masked_chip_count+=1
                masked_chip_set.add( chip )
                    
            if chip in triggered_chips:
                ids = np.array(str(chip).split('-')).astype(int)
                mask = np.logical_and( iog_triggers==ids[0], ioc_triggers==ids[1] )
                mask = np.logical_and(mask, chip_triggers==ids[2])
                channels = channel_triggers[mask]
                set_channels=set(channels)
                asic_id=chip_key_to_asic_id(chip)
                if asic_id in toggle_global_csa_disable.keys():
                    channel_intersection=list(set_channels & set(toggle_global_csa_disable[asic_id]))
                    if len(channel_intersection)>0:
                        if chip not in offenders.keys(): offenders[chip]={}
                        for cid in channel_intersection:
                            if cid not in offenders[chip].keys(): offenders[chip][cid]=1
                            else: offenders[chip][cid]+=1

                chip_rate = np.sum(mask)/_runtime_global
                channel_rate={}
                kill_fraction={}
                for channel in set_channels:
                    channel_rate[channel]=np.sum(channel==channels)/_runtime_global
                    kill_fraction[channel]=channel_rate[channel]/chip_rate
                kill_channel=[]
                for channel in channel_rate.keys():
                    if kill_fraction[channel]>max_channel_fraction and channel_rate[channel]>_maxrate_global:
                        kill_channel.append(channel)
                for channel in kill_channel:
                    if chip not in toggled_chips:
                        print('Noisy chip missing from controller!')
                        continue
                    
                    channel_mask_count+=1
                    c[chip].config.channel_mask[int(channel)]=1
                    c[chip].config.csa_enable[int(channel)]=0
                    if asic_id not in toggle_global_csa_disable.keys(): toggle_global_csa_disable[asic_id]=[]
                    toggle_global_csa_disable[asic_id].append(int(channel))
                    chip_register_pairs.append( (chip, list(range(66,74))+list(range(131,139))) )
                if len(kill_channel)!=0: continue # re-assess chip if channel disabled; DO NOT toggle global DAC
                
                if chip_rate>_maxrate_global:
                    increment_count+=1
                    if c[chip].config.threshold_global>=253:
                        c[chip].config.threshold_global=255
                        mask_chip(c, chip, chip_register_pairs)
                    else:
                        c[chip].config.threshold_global+=1
                    chip_register_pairs.append( (chip, [64]) )                    
                if chip_rate>_minrate_global and chip_rate<_maxrate_global:
                    if c[chip].config.threshold_global>_maxdac_global:
                        silence_highest_rate(c, chip, channel_rate, toggle_global_csa_disable)
                        chip_register_pairs.append( (chip, list(range(66,74))+list(range(131,139))) )
                        continue
                    else:
                        mask_chip(c, chip, chip_register_pairs)
                        masked_chip_count+=1
                        masked_chip_set.add( chip )
                if chip_rate<_minrate_global:
                    if packets.shape[0]>_maxtriggers: high_rate=True; continue
                    decrement_count+=1
                    if c[chip].config.threshold_global==0:
                        mask_chip(c, chip, chip_register_pairs)
                        masked_chip_count+=1
                        masked_chip_set.add( chip )
                    else:
                        c[chip].config.threshold_global -= 1
                    chip_register_pairs.append( (chip, [64]) )
            else: # untriggered chips
                untriggered_count+=1
                if packets.shape[0]>_maxtriggers: high_rate=True; continue
                if chip in  masked_chip_set:
                    mask_chip(c, chip, chip_register_pairs)
                    continue
                decrement_count+=1
                if c[chip].config.threshold_global==0:
                    mask_chip(c, chip, chip_register_pairs)
                    masked_chip_count+=1
                    masked_chip_set.add( chip )
                else:
                    c[chip].config.threshold_global -= 1
                chip_register_pairs.append( (chip, [64]) )
                high_rate=True
        for _ in range(10):
            for chip in toggled_chips:
                asic_id = chip_key_to_asic_id(chip)
                if asic_id in toggle_global_csa_disable.keys():
                    for channel in set(toggle_global_csa_disable[asic_id]):
                        c[chip].config.channel_mask[channel]=1
                        c[chip].config.csa_enable[channel]=0
                    chip_register_pairs.append( (chip, list(range(66,74))+list(range(131,139))) )
            c.multi_write_configuration(chip_register_pairs, connection_delay=0.01)


        for ck in offenders.keys():
            for cid in offenders[ck]:
                if offenders[ck][cid]>_bail_threshold:
                    print('BAIL ========= ',ck,' ',cid,' fired ',offenders[ck][cid])
                    high_rate=False
                    break
            if high_rate==False: break

        print('==>\ttriggered: ',len(triggered_chips),'\tuntriggered: ',untriggered_count,'\t resolved: ',len(masked_chip_set),'\t total: ',len(toggled_chips),'\n==>\tincremented: ',increment_count,'\t decremented: ',decrement_count,'\t channels masked: ',channel_mask_count)
        track_progress[iteration]=len(masked_chip_set)

        haha=0
        for key in toggle_global_csa_disable.keys(): haha+=len(set(toggle_global_csa_disable[key]))
        print('==>\tCSA disable size: ',haha,'\t keys: ',len(toggle_global_csa_disable.keys()),'\n')

    for chip in toggled_chips:
        if chip not in masked_chip_set: chip_reevaluate_queue.add(chip)
        
    return track_triggers, toggle_global_csa_disable, track_progress, chip_reevaluate_queue


def recast_dictionary(d):
    out={}
    for k in d.keys(): out[str(k)]=d[k]
    return out


def save_to_json(filename, d, recast=True):
    if recast: d = recast_dictionary(d)
    with open(filename+'.json','w') as outfile:
        json.dump(d, outfile, indent=4)


def save_chip_key_list(filename, chips_to_test):
    a=[str(ck) for ck in chips_to_test]
    with open(filename+'.json','w') as json_out: json.dump(a,json_out)


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

        
def main(pacman_config,
         disabled_list,
         chip_list,
         diagnostic_dir,
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
    save_to_json(diagnostic_dir+'/input_disabled_list_{}'.format(time.strftime("%Y_%m_%d_%H_%M_%S_%Z")), csa_disable, recast=False)
    time_log['disabled_input']=timeEnd

    print('CHIP LIST: ',chip_list)

    chips_to_test=[]
    if chip_list=='None': chips_to_test=c.chips
    else: chips_to_test=chips_to_test_from_file(chip_list)

    global_disable=csa_disable

    timeStart = time.time()
    initial_asic_config(c, chips_to_test)
    timeEnd = time.time()-timeStart
    print('\t==> %.2f seconds --- setup initial ASIC configuration\n'%timeEnd)
    time_log['initial_config']=timeEnd

    timeStart = time.time()
    enable_frontend(c, chips_to_test, global_disable, all_network_keys, pacman_configs)
    timeEnd = time.time()-timeStart
    print('\t==> %.2f seconds --- enable channel front-ends\n'%timeEnd)
    time_log['enable_frontend']=timeEnd

    timeStart = time.time()
    global_track_triggers, toggle_global_csa_disable, global_track_progress, chip_reevaluate = toggle_global_dac(c, chips_to_test, global_disable, all_network_keys, pacman_configs)
    timeEnd = time.time()-timeStart
    print('\t==> %.2f seconds --- toggle global DACs\n'%timeEnd)
    save_to_json(diagnostic_dir+'/global_disabled_list_{}'.format(time.strftime("%Y_%m_%d_%H_%M_%S_%Z")), toggle_global_csa_disable, recast=False)
    time_log['toggle_global']=timeEnd

    after_global={}
    for key in global_disable.keys():
        if key not in after_global: after_global[key]=[]
        for chan in global_disable[key]:
            if chan not in after_global[key]: after_global[key].append(chan)
    for key in toggle_global_csa_disable.keys():
        if key not in after_global: after_global[key]=[]
        for chan in toggle_global_csa_disable[key]:
            if chan not in after_global[key]: after_global[key].append(chan)

    global_disable=after_global
            
    save_to_json(diagnostic_dir+'/combined_global_disabled_list_{}'.format(time.strftime("%Y_%m_%d_%H_%M_%S_%Z")), global_disable, recast=False)
    save_to_json(diagnostic_dir+'/global_configuration_{}'.format(time.strftime("%Y_%m_%d_%H_%M_%S_%Z")), global_track_progress, recast=True)
    save_to_json(diagnostic_dir+'/global_triggers_{}'.format(time.strftime("%Y_%m_%d_%H_%M_%S_%Z")), global_track_triggers, recast=True)

    chips_to_test=[]
    for chip in chip_reevaluate:
        if chip in c.chips: chips_to_test.append(chip)
    this_chip_count=len(chips_to_test)
    print('reevaluate ',this_chip_count, ' global DACs\n')

    if this_chip_count>0: save_chip_key_list(diagnostic_dir+'/chip_reevaluation_list_{}'.format(time.strftime("%Y_%m_%d_%H_%M_%S_%Z")),chips_to_test)

        
    timeStart = time.time()
    save_config_to_file(c, global_disable)
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
    parser.add_argument('--chip_list',
                        default='None',
                        type=str,
                        help='''JSON-formatted list of ASIC ID''')
    parser.add_argument('--diagnostic_dir',
                        default='None',
                        type=str,
                        help='''diagnostic files output directory''')
    args = parser.parse_args()
    c = main(**vars(args))
