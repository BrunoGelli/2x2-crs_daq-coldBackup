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
_initial_global_dac=255
_runtime_global=0.05
# may1_2024
#lower maxrate_global to 100
_maxrate_global=100.
_minrate_global=10. 
_maxdac_global=50
_maxtriggers=500000.

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


def initial_asic_config(c):
    chip_register_pairs = []
    for chip in c.chips:
        c[chip].config.vref_dac=_vref_dac #register 82
        c[chip].config.vcm_dac=_vcm_dac # register 82
        c[chip].config.pixel_trim_dac=[_initial_trim_dac]*64 # regiseters [0-63]
        c[chip].config.threshold_global=_initial_global_dac # register 64
        c[chip].config.enable_periodic_reset = 1 # register 128
        c[chip].config.enable_rolling_periodic_reset = 1 # regiseter 128
        c[chip].config.adc_hold_delay = 15 # register 129        
        c[chip].config.periodic_reset_cycles=64 # registers [163-165]
        chip_register_pairs.append( (chip, list(range(0,65))+[82,83,128,129,163,164,165]) )

    #ATTENTION: huge time sink. need to check if this can be parallellized
    for i in range(1):
        c.multi_write_configuration(chip_register_pairs, connection_delay=0.1)

    return


def enable_frontend(c, csa_disable, all_network_keys, pacman_configs):
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

    
def silence_highest_rate(c, chip, channel_rate):
    highest_rate=-1.
    highest_channel=None
    for channel in channel_rate:
        if channel_rate[channel]>highest_rate:
            highest_rate=channel_rate[channel]
            highest_channel=int(channel)
    if highest_channel!=None:
        c[chip].config.channel_mask[highest_channel]=1
        c[chip].config.csa_enable[highest_channel]=0

    
def toggle_global_dac(c, all_network_keys,max_channel_fraction=0.9):
    toggle_global_csa_disable={}
    
    bookkeep_masked_channels=0
    track_triggers={}
    track_progress={}
    
    high_rate=True
    iteration=0
    masked_chip_count=0
    masked_chip_set=set()
    while high_rate:
        iteration+=1
        high_rate=False
        
        c.reads.clear()
        c.run(_runtime_global,'check rate')
        all_packets = np.array(c.reads[-1])
        print('iteration {}, packet count {}'.format(iteration,all_packets.shape[0]))

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
            print('Lowering threshold on all active chips\n')
            chip_register_pairs = []
            for chip in c.chips:
                if chip in  masked_chip_set: continue
                if c[chip].config.threshold_global==0:
                    mask_chip(c, chip, chip_register_pairs)
                    masked_chip_count+=1
                    masked_chip_set.add( chip )
                else:
                    c[chip].config.threshold_global -= 1
                chip_register_pairs.append( (chip, [64]) )
            for _ in range(3):
                c.multi_write_configuration(chip_register_pairs, connection_delay=0.01)
            high_rate=True
            if iteration==270: high_rate=False
            continue

        channel_mask_count=0
        increment_count=0
        decrement_count=0
        untriggered_count=0
        chip_register_pairs=[]
        for chip in c.chips:
            if chip in triggered_chips:
                ids = np.array(str(chip).split('-')).astype(int)
                mask = np.logical_and( iog_triggers==ids[0], ioc_triggers==ids[1] )
                mask = np.logical_and(mask, chip_triggers==ids[2])
                channels = channel_triggers[mask]
                set_channels=set(channels)
                ####
                ## may1_2024
                ##
                # Add here to flag "disabled" channels that still trigger
                # Some action could be taken here, but right now it just ignores it
                asic_id=chip_key_to_asic_id(chip)
                if asic_id in toggle_global_csa_disable.keys():    
                    if not (len(set_channels)==len(set_channels- set(toggle_global_csa_disable[asic_id]))):
                            # DISABLED_CHANNELS_TRIGGERED!
                            # maybe do something here?
                            print('disabled channels still firing!!')
                            pass
                    set_channels = set_channels - set(toggle_global_csa_disable[asic_id])
                ##
                ##
                chip_rate = np.sum(mask)/_runtime_global
                channel_rate={}
                kill_fraction={}
                for channel in set_channels:
                    channel_rate[channel]=np.sum(channel==channels)/_runtime_global
                    kill_fraction[channel]=channel_rate[channel]/chip_rate
                exceed_channel=[]
                kill_channel=[]
                for channel in channel_rate.keys():
                    if channel_rate[channel]>1e2: exceed_channel.append(channel)
                    if kill_fraction[channel]>max_channel_fraction and channel_rate[channel]>_maxrate_global: #*2:
                        kill_channel.append(channel)
                for channel in kill_channel:
                    print('High rate channel disabled!\t{}-{}\trate: {} Hz  (chip rate {} Hz)'.format(chip,channel,channel_rate[channel],chip_rate))
                    if chip not in c.chips:
                        print('Noisy chip missing from controller!')
                        continue
                    channel_mask_count+=1
                    c[chip].config.channel_mask[int(channel)]=1
                    c[chip].config.csa_enable[int(channel)]=0
                    if asic_id not in toggle_global_csa_disable.keys(): toggle_global_csa_disable[asic_id]=[]
                    toggle_global_csa_disable[asic_id].append(int(channel))
                    chip_register_pairs.append( (chip, list(range(66,74))+list(range(131,139))) )
                    # may1_2024
                    # subtract rate of channels to be disabled from total chip rate
                    # If only a few channels pushes total rate above threshold, shouldn't raise threshold_global until these are masked
                    chip_rate = chip_rate - channel_rate[channel]
                if chip_rate>_maxrate_global:
                    increment_count+=1
                    if c[chip].config.threshold_global>=253:
                        c[chip].config.threshold_global=255
                        mask_chip(c, chip, chip_register_pairs)
                    else:
                        c[chip].config.threshold_global+=2
                    chip_register_pairs.append( (chip, [64]) )                    
                if chip_rate>_minrate_global and chip_rate<_maxrate_global:
                    # may1_2024
                    # It might make sense to leave this to the trim toggling?
                    if c[chip].config.threshold_global>_maxdac_global:
                        silence_highest_rate(c, chip, channel_rate)
                        chip_register_pairs.append( (chip, list(range(66,74))+list(range(131,139))) )
                        continue
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
                if iteration==270: high_rate=False; continue 
                if packets.shape[0]>_maxtriggers: high_rate=True; continue
                if chip in  masked_chip_set:
                    mask_chip(c, chip, chip_register_pairs)
                    continue
                untriggered_count+=1
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
            c.multi_write_configuration(chip_register_pairs, connection_delay=0.01)
        print('triggered count: ',len(triggered_chips),'\tuntriggered count: ',untriggered_count,'\t masked count: ',len(masked_chip_set),'\nincremented: ',increment_count,'\t decremented: ',decrement_count,'\t channels masked: ',channel_mask_count)
        track_progress[iteration]=len(masked_chip_set)
        bookkeep_masked_channels+=channel_mask_count

        haha=0
        for key in toggle_global_csa_disable.keys(): haha+=len(set(toggle_global_csa_disable[key]))
        print('CSA disable size: ',haha,'\t keys: ',len(toggle_global_csa_disable.keys()),'\n')

    print(bookkeep_masked_channels,'\t==> total masked channels while toggling global DAC')
    return track_triggers, toggle_global_csa_disable, track_progress


def setup_status(c, csa_disable):
    status={}
    for chip in c.chips:
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
    

def toggle_trim_dac(c, csa_disable, minrate_trim=_minrate_trim, maxrate_trim=_maxrate_trim, runtime_trim=_runtime_trim):
    toggle_trim_csa_disable={}
    track_triggers={}
    track_progress={}
    status = setup_status(c, csa_disable)

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

        start=time.time()
        if all_packets.shape[0]==0: packets = np.array([])
        else: packets = all_packets[np.vectorize(lambda x: x.packet_type)(all_packets)==0]
        print('time to extract data packets:', start-time.time())
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

        print('time to extract from packets', start-time.time())
        for chip in tqdm(c.chips):
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
        
    #ATTENTION: is this called implicitly within enforce_parallel above
    for io_group_ip_pair in pacman_configs['io_group']:
        io_group = io_group_ip_pair[0]
        pacman_base.enable_all_pacman_uart_from_io_group(c.io, io_group)
        
    timeStart = time.time()
    csa_disable = disable_dict_from_file(c, disabled_list) #, csa_disable)
    timeEnd = time.time()-timeStart
    print('==> %.2f seconds --- disabled channels from input list\n'%timeEnd)
    save_to_json('input_disabled_list_iteration'+str(iteration), csa_disable, recast=False)
    time_log['disabled_input']=timeEnd

    timeStart = time.time()
    initial_asic_config(c)
    timeEnd = time.time()-timeStart
    print('==> %.2f seconds --- setup initial ASIC configuration\n'%timeEnd)
    time_log['initial_config']=timeEnd

    timeStart = time.time()
    enable_frontend(c, csa_disable, all_network_keys, pacman_configs)
    timeEnd = time.time()-timeStart
    print('==> %.2f seconds --- enable channel front-ends\n'%timeEnd)
    time_log['enable_frontend']=timeEnd

    timeStart = time.time()
    global_track_triggers, toggle_global_csa_disable, global_track_progress = toggle_global_dac(c, all_network_keys)
    timeEnd = time.time()-timeStart
    print('==> %.2f seconds --- toggle global DACs\n'%timeEnd)
    save_to_json('global_disabled_list_iteration'+str(iteration), toggle_global_csa_disable, recast=False)
    time_log['toggle_global']=timeEnd

    after_global={}
    for key in csa_disable.keys():
        if key not in after_global: after_global[key]=[]
        for chan in csa_disable[key]:
            if chan not in after_global[key]: after_global[key].append(chan)
    for key in toggle_global_csa_disable.keys():
        if key not in after_global: after_global[key]=[]
        for chan in toggle_global_csa_disable[key]:
            if chan not in after_global[key]: after_global[key].append(chan)
            
    save_to_json('combined_global_disabled_list_iteration'+str(iteration), after_global, recast=False)
    save_to_json('global_configuration_iteration'+str(iteration), global_track_progress, recast=True)
    save_to_json('global_triggers_iteration'+str(iteration), global_track_triggers, recast=True)

    timeStart = time.time()
    enable_frontend(c, after_global, all_network_keys, pacman_configs)
    timeEnd = time.time()-timeStart
    print('==> %.2f seconds --- re-enable channel front-ends\n'%timeEnd)
    time_log['reenable_frontend']=timeEnd

    timeStart = time.time()
    toggle_trim_csa_disable_0, trim_track_progress_0, trim_track_triggers_ = toggle_trim_dac(c, after_global)
    timeEnd = time.time()-timeStart
    print('==> %.2f seconds --- toggle trim DACs\n'%timeEnd)
    save_to_json('trim_disabled_list_iteration'+str(iteration), toggle_trim_csa_disable_0, recast=False)
    time_log['toggle_trim_it0']=timeEnd

#    timeStart = time.time()
#    toggle_trim_csa_disable, trim_track_progress, trim_track_triggers = toggle_trim_dac(c, toggle_trim_csa_disable_0, minrate_trim=0.1, maxrate_trim=1, runtime_trim=10)
#    timeEnd = time.time()-timeStart
#    print('==> %.2f seconds --- toggle trim DACs\n'%timeEnd)
#    save_to_json('trim_disabled_list_iteration'+str(iteration), toggle_trim_csa_disable, recast=False)
#    time_log['toggle_trim_it']=timeEnd

    after_trim={}
    for key in after_global.keys():
        if key not in after_trim: after_trim[key]=[]
        for chan in after_global[key]:
            if chan not in after_trim[key]: after_trim[key].append(chan)
    for key in toggle_trim_csa_disable.keys():
        if key not in after_trim: after_trim[key]=[]
        for chan in toggle_trim_csa_disable[key]:
            if chan not in after_trim[key]: after_trim[key].append(chan)
    
    save_to_json('time_log_iteration'+str(iteration), time_log, recast=False)
    save_to_json('combined_trim_disabled_list_iteration'+str(iteration), after_trim, recast=False)
    save_to_json('trim_configuration_iteration'+str(iteration), trim_track_progress, recast=True)
    save_to_json('trim_triggers_iteration'+str(iteration), trim_track_triggers, recast=True)

    global_dac={}; trim_dac={}
    global_chip_disabled=[]; global_total_disabled=0; global_all_channel_id=[]
    trim_chip_disabled=[]; trim_total_disabled=0; trim_all_channel_id=[]
    for chip in c.chips:
        chip_string=str(chip.io_group)+'-'+str(chip.io_channel)+'-'+str(chip.chip_id)
        global_dac[chip_string]=c[chip].config.threshold_global        
        asic_id = chip_key_to_asic_id(chip)
        if asic_id in csa_disable.keys():
            trim_dac[chip_string]=[-1]*64
            for channel in range(64):
                if channel in csa_disable[asic_id]: continue
                trim_dac[chip_string][channel]=c[chip].config.pixel_trim_dac[channel]

    save_to_json('global_dac_iteration'+str(iteration), global_dac, recast=False)
    save_to_json('trim_dac_iteration'+str(iteration), trim_dac, recast=False)

    timeStart = time.time()
    save_config_to_file(c, after_trim)
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
