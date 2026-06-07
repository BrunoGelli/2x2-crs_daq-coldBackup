import sys
import time
import argparse
from base import graphs
import larpix
import larpix.io
import larpix.logger
from base import generate_config
from base import pacman_base
from tqdm import tqdm
import numpy as np
import json
from base import utility_base
from base.network_base import _default_clk_ctrl, clk_ctrl_2_clk_ratio_map
import time
import sys
import os
from runenv import runenv as RUN

module = sys.modules[__name__]
for var in RUN.config.keys():
    setattr(module, var, getattr(RUN, var))

arr = graphs.NumberedArrangement()

def string_to_chips_list(string):
        chiplist = string.split(',')
        return [int(chip) for chip in chiplist]

def convert_voltage_for_pacman(voltage):
        max_voltage, max_scale = 1.8, 46020
        v = voltage
        if v > max_voltage: v=max_voltage
        return int( (v/max_voltage)*max_scale )

def get_temp_key(io_group, io_channel):
        return larpix.key.Key(io_group, io_channel, 1)

def get_good_roots(c, io_group, io_channels, root_chips=[11, 41, 71, 101]):
        #root chips with external connections to pacman
        print('getting good roots...')
        good_tile_channel_indices = []
        for n, io_channel in enumerate(io_channels):

                #writing initial config
                key = larpix.key.Key(io_group, io_channel, 1)
                c.add_chip(key)

                c[key].config.chip_id = root_chips[n]
                c.write_configuration(key, 'chip_id')
                c.remove_chip(key)

                key = larpix.key.Key(io_group, io_channel, root_chips[n])
                c.add_chip(key)
                c[key].config.chip_id = key.chip_id

                c[key].config.enable_miso_downstream = [1,0,0,0]
                c[key].config.enable_miso_differential = [1,1,1,1]
                c.write_configuration(key, 'enable_miso_downstream')

                ###############################################################################


                #resetting clocks

                c[key].config.enable_miso_downstream=[0]*4
                c[key].config.enable_miso_upstream=[0]*4
                c.write_configuration(key, 'enable_miso_downstream')
                c.write_configuration(key, 'enable_miso_upstream')
                c[key].config.clk_ctrl = _default_clk_ctrl
                c.write_configuration(key, 'clk_ctrl')
                c.io.set_uart_clock_ratio(io_channel, clk_ctrl_2_clk_ratio_map[_default_clk_ctrl], io_group=io_group)
                #print("setting uart clock ratio to:",clk_ctrl_2_clk_ratio_map[_default_clk_ctrl]) 
         
                ################################################################################

                #rewriting config
                c[key].config.enable_miso_downstream = [1,0,0,0]
                c[key].config.enable_miso_differential = [1,1,1,1]
                c.write_configuration(key, 'enable_miso_differential')
                c.write_configuration(key, 'enable_miso_downstream')

                #enforcing configuration on chip
                ok,diff = c.enforce_registers([(key,122), (key, 125)], timeout=0.01, n=5, n_verify=5)
                if ok:
                        good_tile_channel_indices.append(n)
                        print('verified root chip ' + str(root_chips[n]))
                else:
                        print('unable to verify root chip ' + str(root_chips[n]))

        #checking each connection for every chip
        good_roots = [root_chips[n] for n in good_tile_channel_indices]
        good_channels = [io_channels[n] for n in good_tile_channel_indices]

        print('Found working root chips: ', good_roots)

        return good_roots, good_channels

def get_initial_controller(io_group, io_channels, vdda=0, pacman_version='v1rev3b'):
        #creating controller with pacman io
        c = larpix.Controller()
        c.io = larpix.io.PACMAN_IO(relaxed=True, config_filepath=f'io/pacman_io{io_group}.json')
        c.io.double_send_packets = True
        print('getting initial controller')
        
        tiles = set()
        for io_channel in io_channels:
            tiles.add( utility_base.io_channel_to_tile(io_channel) )
        tiles=list(tiles)
        #resetting larpix
        c.io.reset_tiles(tiles=tiles, length=10240, io_group=io_group)
        time.sleep(10240*1e-6)
        c.io.reset_tiles(tiles=tiles, length=10240, io_group=io_group)
        time.sleep(10240*1e-6)
        
        for io_channel in io_channels:
            c.add_network_node(io_group, io_channel, c.network_names, 'ext', root=True)
       
        for io_channel in io_channels:
            c.io.set_uart_clock_ratio(io_channel, clk_ctrl_2_clk_ratio_map[0], io_group=io_group)



        #!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        
        return c

def reset_board_get_controller(c, io_group, io_channels):
        tiles = set()
        for io_channel in io_channels:
            tiles.add( utility_base.io_channel_to_tile(io_channel) )
        tiles=list(tiles)
        #resetting larpix
        c.io.reset_tiles(tiles=tiles, length=10240, io_group=io_group)
        time.sleep(10240*1e-6)
        c.io.reset_tiles(tiles=tiles, length=10240, io_group=io_group)
        time.sleep(10240*1e-6)
        
        for io_channel in io_channels:
                c.io.set_uart_clock_ratio(io_channel, clk_ctrl_2_clk_ratio_map[0], io_group=io_group)
                #print("setting uart clock ratio to:",clk_ctrl_2_clk_ratio_map[0]) 
        c.chips.clear()
        
        return c

def init_initial_network(c, io_group, io_channels, paths):
        root_chips = [path[0] for path in paths]

        still_stepping = [True for root in root_chips]
        ordered_chips_by_channel = [ [] for io_channel in io_channels  ]

        for ipath, path in enumerate(paths):

                step = 0

                while step < len(path)-1:
                        step += 1
                        next_key = larpix.key.Key(io_group, io_channels[ipath], path[step])
                        prev_key = larpix.key.Key(io_group, io_channels[ipath], path[step-1])

                        if prev_key.chip_id in root_chips:
                                #this is the first step. need to re-add root chip
                                temp_key = get_temp_key(io_group, io_channels[ipath])
                                c.add_chip(temp_key)
                                c[temp_key].config.chip_id = prev_key.chip_id
                                c.write_configuration(temp_key, 'chip_id')
                                c.write_configuration(temp_key, 'chip_id')
                                c.remove_chip(temp_key)
                                c.add_chip(prev_key)
                                c[prev_key].config.chip_id = prev_key.chip_id
                                c[prev_key].config.enable_miso_downstream = arr.get_uart_enable_list(prev_key.chip_id)
                                c[prev_key].config.enable_miso_differential = [1,1,1,1]
                                c.write_configuration(prev_key, 'enable_miso_downstream')
                                c.write_configuration(prev_key, 'enable_miso_differential')
                                ordered_chips_by_channel[ipath].append(prev_key.chip_id)
                        
                        c[prev_key].config.enable_miso_upstream = arr.get_uart_enable_list(prev_key.chip_id, next_key.chip_id)
                        c.write_configuration(prev_key, 'enable_miso_upstream')

                        temp_key = get_temp_key(io_group, io_channels[ipath])
                        c.add_chip(temp_key)
                        c[temp_key].config.chip_id = next_key.chip_id
                        c.write_configuration(temp_key, 'chip_id')
                        c.remove_chip(temp_key)

                        c.add_chip(next_key)
                        c[next_key].config.chip_id = next_key.chip_id
                        c[next_key].config.enable_miso_downstream = arr.get_uart_enable_list(next_key.chip_id, prev_key.chip_id)
                        c[next_key].config.enable_miso_differential =[1,1,1,1]
                        c.write_configuration(next_key, 'enable_miso_downstream')
                        ordered_chips_by_channel[ipath].append(next_key.chip_id)
                        
                for chip_ids in ordered_chips_by_channel[ipath][::-1]:
                        key = larpix.key.Key(io_group, io_channels[ipath], chip_ids)
                        c[key].config.enable_miso_downstream=[0]*4
                        c[key].config.enable_miso_upstream=[0]*4
                        c.write_configuration(key, 'enable_miso_downstream')
                        c.write_configuration(key, 'enable_miso_upstream')
                        c[key].config.clk_ctrl = _default_clk_ctrl
                        c.write_configuration(key, 'clk_ctrl')
                
                c.io.set_uart_clock_ratio(io_channels[ipath], clk_ctrl_2_clk_ratio_map[_default_clk_ctrl], io_group=io_group)

        return True

def test_network(c, io_group, io_channels, paths):
        print('Testing io-group {} io_channels'.format(io_group), io_channels)
        root_chips = [path[0] for path in paths]
        step = 0
        still_stepping = [True for path in paths]
        valid = [True for path in paths]
        pbar=tqdm(total=np.sum([len(p) for p in paths]))
        while any(still_stepping):
                step += 1 
                for ipath, path in enumerate(paths):
                         
                        if not still_stepping[ipath] or not valid[ipath]:
                                continue

                        if step > len(path)-1:
                                still_stepping[ipath] = False
                                continue
                        next_key = larpix.key.Key(io_group, io_channels[ipath], path[step])
                        print(next_key)
                        #pacman_base.enable_pacman_uart_from_io_channel(c.io, next_key.io_group, [next_key.io_channel])
                        #time.sleep(2)
                        prev_key = larpix.key.Key(io_group, io_channels[ipath], path[step-1])
                        
                        #print('writing to prev key', prev_key)
                        if prev_key.chip_id in root_chips:
                                c[prev_key].config.chip_id = prev_key.chip_id
                                c[prev_key].config.enable_miso_downstream = arr.get_uart_enable_list(prev_key.chip_id)
                                c[prev_key].config.enable_miso_differential = [1,1,1,1]
                                c.write_configuration(prev_key, 'enable_miso_downstream')
                                c.write_configuration(prev_key, 'enable_miso_downstream')

                        c[prev_key].config.enable_miso_upstream = arr.get_uart_enable_list(prev_key.chip_id, next_key.chip_id)
                        c.write_configuration(prev_key, 'enable_miso_upstream')
                        c.write_configuration(prev_key, 'enable_miso_upstream')
                        
                        #time.sleep(2)
                        #print('writing to next key', next_key)

                        c[next_key].config.chip_id = next_key.chip_id
                        c[next_key].config.enable_miso_downstream = arr.get_uart_enable_list(next_key.chip_id, prev_key.chip_id)
                        c[next_key].config.enable_miso_differential =[1,1,1,1]
                        c.write_configuration(next_key, 'enable_miso_downstream')
                        c.write_configuration(next_key, 'enable_miso_downstream')

                        #time.sleep(2)
                        #print('enforcing')

                        ok, diff = c.enforce_configuration(next_key, timeout=0.02, n=5, n_verify=3)
                        #print('enabled', next_key)
                        #time.sleep(1)

                        if False and next_key.chip_id>40 and next_key.chip_id < 61:
                            print('checking', next_key)
                            for i in range(500):
                                c.verify_registers( [(next_key, 0)], timeout=0.01 )
                                
                                #if not ok: print(diff)
                            time.sleep(1)
                        pbar.update(1)
                        #pacman_base.disable_all_pacman_uart(c.io, next_key.io_group)
                        if ok:
                                continue

                        else:
                                #planned path to traverse has been interrupted... restart with adding excluded link
                                arr.add_onesided_excluded_link((prev_key.chip_id, next_key.chip_id))
                                arr.add_onesided_excluded_link((next_key.chip_id, prev_key.chip_id))
                                still_stepping[ipath] = False
                                valid[ipath] = False
                                still_stepping = [False]*len(still_stepping)
                                break
        pbar.close()
        return all(valid)

def main(pacman_tile, io_group, pacman_version, vdda=0, config_name=None, exclude=iog_exclude, exclude_roots=None):
    
    d = {'_config_type' : 'controller', '_include':[]}
    print(exclude)
    exclude = exclude[io_group] if io_group in exclude.keys() else None
    if isinstance(pacman_tile, list) or pacman_tile is None:
        if pacman_tile is None: pacman_tile = io_group_pacman_tile_[io_group]
        if exclude is None: exclude = {t : None for t in pacman_tile}
        if exclude_roots is None: exclude_roots = {t : None for t in pacman_tile}
        for tile in pacman_tile:
            if not tile in exclude.keys(): exclude[tile]=None
            print('excluding chips {} on tile {}'.format(exclude[tile], tile))
            d['_include'].append(hydra_chain(io_group, tile, pacman_version, vdda, exclude[tile], first=True, exclude_roots=exclude_roots[tile]))
    if isinstance(pacman_tile, int):
        print('excluding chips {} on tile {}'.format(exclude[str(pacman_tile)], pacman_tile))
        d['_include'].append(hydra_chain(io_group, pacman_tile, pacman_version, vdda, exclude[str(pacman_tile)], first=True, exclude_roots=exclude_roots))
    
    fname=config_name

    if config_name is None:  #no input file to incluce
        fname='config-{}.json'.format(time.strftime("%Y_%m_%d_%H_%M_%Z"))
        with open(fname, 'w') as f: json.dump(d, f)
        return fname
    else:
        ed = {}
        try:
            with open(config_name, 'r')  as f: ed = json.load(f)
            for file in ed['_include']:
                d['_include'].append(file)
            with open(fname, 'w') as f: json.dump(d, f) 
            print('writing', fname)
        except:
            with open(fname, 'w') as f: json.dump(d, f) 
            print('writing', fname)
            return fname
        
    return fname

def hydra_chain(io_group, pacman_tile, pacman_version, vdda, exclude=None, first=False, exclude_roots=None): 
        if first: arr.clear()
        all_roots  = [11, 41, 71, 101]
        root_chips = [11, 41, 71, 101]
        if not exclude is None: 
            if type(exclude)==str:
                exclude=list(np.array(exclude.split(',')).astype(int))
        if not exclude_roots is None: 
            if type(exclude_roots)==str:
                exclude_roots=list(np.array(exclude_roots.split(',')).astype(int))
        if not exclude is None:
            if type(exclude)==int: 
                arr.add_excluded_chip(exclude)
                if exlude in root_chips: root_chips.remove(exclude) 
            else:
                print(exclude)
                for chip in exclude:
                    print('Excluding chip: {}'.format(chip))
                    arr.add_excluded_chip(chip)
                    if chip in root_chips: root_chips.remove(chip)

        if not exclude_roots is None:
            if type(exclude_roots)==int: 
                if exclude_roots in root_chips: root_chips.remove(exclude) 
            else:
                for chip in exclude_roots: 
                    if chip in root_chips: root_chips.remove(chip)

        
        io_channels = [ 1 + 4*(pacman_tile - 1) + n for n in range(4) if all_roots[n] in root_chips]
        print("--------------------------------------------")
        print("get_initial_controller(",io_group,",",io_channels,",",vdda,",",pacman_version,")")
        c = get_initial_controller(io_group, io_channels, vdda, pacman_version)

        
        pacman_base.enable_all_pacman_uart_from_io_group(c.io, io_group) 
        root_chips, io_channels = get_good_roots(c, io_group, io_channels, root_chips)
        print('found root chips:', root_chips)
        c = reset_board_get_controller(c, io_group, io_channels)

        #need to init whole network first and write clock frequency, then we can step through and test

        existing_paths = [ [chip] for chip in root_chips  ]

        #initial network
        paths = arr.get_path(existing_paths)
        print('path including', sum(  [len(path) for path in paths] ), 'chips' )

        #bring up initial network and set clock frequency
        init_initial_network(c, io_group, io_channels, paths)
        #test network to make sure all chips were brought up correctly
        ok = test_network(c, io_group, io_channels, paths)
        while not ok:
                c = reset_board_get_controller(c, io_group, io_channels)

                existing_paths = [ [chip] for chip in root_chips  ]
            
                #initial network
                print(arr.excluded_links)
                paths = arr.get_path(existing_paths) 
                print('path inlcuding', sum(  [len(path) for path in paths] ), 'chips' )

                #bring up initial network and set clock frequency
                init_initial_network(c, io_group, io_channels, paths)

                #test network to make sure all chips were brought up correctly
                ok = test_network(c, io_group, io_channels, paths)

        #existing network is full initialized, start tests
        ######
        ##generating config file
        _name = "iog-{}-".format(io_group)+"pacman-tile-"+str(pacman_tile)+"-hydra-network.json"

        if True:
                print('writing configuration', _name + ', including', sum(  [len(path) for path in paths] ), 'chips'  )
                generate_config.write_existing_path(_name, io_group, root_chips, io_channels, paths, ['no test performed'], arr.excluded_chips, asic_version=2)
        print(arr.excluded_links)
        return _name 

if __name__ == '__main__':
        parser = argparse.ArgumentParser()
        parser.add_argument('--pacman_tile', default=None, type=int, help='''Pacman software tile number; 1-8  for Pacman v1rev3; 1 for Pacman v1rev2''')
        parser.add_argument('--pacman_version', default='v1rev3b', type=str, help='''Pacman version; v1rev2 for SingleCube; otherwise, v1rev3''')
        parser.add_argument('--vdda', default=0, type=float, help='''VDDA setting during test [V]''')
        parser.add_argument('--io_group', default=1, type=int, help='''IO group to perform test on''')
        parser.add_argument('--exclude_roots', default=None, type=str, help='''Chips to exclude chip from root chips chip_id_1,chip_id_2,...''')
        args = parser.parse_args()
        c = main(**vars(args))
        ###### disable tile power


