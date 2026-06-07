import warnings
warnings.filterwarnings("ignore")
import larpix
import argparse
import larpix.io
import time
from base import pacman_base, utility_base
from base.utility_base import now
import json
import logging
import sys
import os

_default_verbose=False
skip_readback=False


from runenv import runenv as RUN
module = sys.modules[__name__]
for var in RUN.config.keys():
    setattr(module, var, getattr(RUN, var))

def main(verbose, pacman_config):
    
    #number of clock cycles to hold for hard reset of LArPix
    RESET_CYCLES=4096
    pacman_configs = {}
    with open(pacman_config, 'r') as f:
        pacman_configs = json.load(f)
    
    c = larpix.Controller()
    c.io = larpix.io.PACMAN_IO(relaxed=True, config_filepath=pacman_config)

    pacman_configs = {}
    with open(pacman_config, 'r') as f:
        pacman_configs = json.load(f)

    # for each io_group, perform networking 
    config_path = None
   

    for io_group_ip_pair in pacman_configs['io_group']:
        io_group = io_group_ip_pair[0]
        print('Configuring IO Group {}'.format(io_group))
        #read pacman information and metadata from RUNENV
        pacman_version = iog_pacman_version_[io_group]
        VDDD_DAC = iog_VDDD_DAC[io_group]
        VDDA_DAC = iog_VDDA_DAC[io_group]

        if verbose:
            print('disabling tile power and clock')
        # disable tile power, LARPIX clock
        c.io.set_reg(0x00000010, 0, io_group=io_group)
        c.io.set_reg(0x00000014, 0, io_group=io_group)
        
        if verbose:
            print('setting up mclk')       
        # set up mclk in pacman
        c.io.set_reg(0x101c, 0x4, io_group=io_group)
        time.sleep(0.1)
        
        if verbose:
            print('enabling power')  
        # enable pacman power
        c.io.set_reg(0x00000014, 1, io_group=io_group)
        
        pacman_version = iog_pacman_version_[io_group]
        
        VDDA_REG=None
        VDDD_REG=None

        if pacman_version=='v1rev3' or pacman_version=='v1revS1' or pacman_version=='v1rev3b':
            VDDD_REG=0x24131
            VDDA_REG=0x24130
            for PACMAN_TILE in io_group_pacman_tile_[io_group]:
                if verbose: print('powering pacman tile:', PACMAN_TILE, 'to', VDDD_DAC, VDDA_DAC) 
                #set voltage dacs to 0V  
                c.io.set_reg(VDDD_REG+2*(PACMAN_TILE-1), 0, io_group=io_group)
                c.io.set_reg(VDDA_REG+2*(PACMAN_TILE-1), 0, io_group=io_group)
                time.sleep(0.1)

                #set voltage dacs VDDD first 
                c.io.set_reg(VDDD_REG+2*(PACMAN_TILE-1), VDDD_DAC[PACMAN_TILE-1], io_group=io_group)
                c.io.set_reg(VDDA_REG+2*(PACMAN_TILE-1), VDDA_DAC[PACMAN_TILE-1], io_group=io_group)
        
        elif pacman_version=='v1rev4':
            VDDD_REG=0x24020
            VDDA_REG=0x24010
            for PACMAN_TILE in io_group_pacman_tile_[io_group]:
                if verbose: print('powering pacman tile:', PACMAN_TILE, 'to', VDDD_DAC, VDDA_DAC) 
                #set voltage dacs to 0V  
                c.io.set_reg(VDDD_REG+(PACMAN_TILE-1), 0, io_group=io_group)
                c.io.set_reg(VDDA_REG+(PACMAN_TILE-1), 0, io_group=io_group)
                time.sleep(0.2)

                #set voltage dacs VDDD first 
                c.io.set_reg(VDDD_REG+(PACMAN_TILE-1), VDDD_DAC[PACMAN_TILE-1], io_group=io_group)
                c.io.set_reg(VDDA_REG+(PACMAN_TILE-1), VDDA_DAC[PACMAN_TILE-1], io_group=io_group)

        if verbose:  print('reset larpix for n cycles',RESET_CYCLES)
        #   - set reset cycles

        c.io.set_reg(0x1014,RESET_CYCLES,io_group=io_group)
        #   - toggle reset bit
        
        clk_ctrl = c.io.get_reg(0x1010, io_group=io_group)
        c.io.set_reg(0x1010, clk_ctrl|4, io_group=io_group)
        c.io.set_reg(0x1010, clk_ctrl, io_group=io_group)
    
        #enable tile power
        tile_enable_sum=0
        tile_enable_val = 0
        for PACMAN_TILE in io_group_pacman_tile_[io_group]:
            tile_enable_sum = pow(2,PACMAN_TILE-1) + tile_enable_sum
            tile_enable_val=tile_enable_sum+0x0200  #enable one tile at a time    
            c.io.set_reg(0x00000010,tile_enable_val,io_group)
            time.sleep(0.1)
            if verbose: print('enabling tilereg 0x10: {0:b}'.format(tile_enable_val) )
        
        if io_group_asic_version_[io_group]=='2b':
            if verbose: print('Inverting PACMAN UARTs on io_group={}'.format(io_group))
            pacman_base.invert_pacman_uart(c.io, io_group, io_group_asic_version_[io_group], \
                                       io_group_pacman_tile_[io_group]) 

        if not skip_readback: readback=pacman_base.power_readback(c.io, io_group, pacman_version,io_group_pacman_tile_[io_group])
        #   - toggle reset bit
        c.io.set_reg(0x1014,RESET_CYCLES,io_group=io_group)
        clk_ctrl = c.io.get_reg(0x1010, io_group=io_group)
        c.io.set_reg(0x1010, clk_ctrl|4, io_group=io_group)
        c.io.set_reg(0x1010, clk_ctrl, io_group=io_group)
        #disable trigger forwarding
        c.io.set_reg(0x2014, 0xffffffff, io_group=io_group)
        c.io.set_reg(0x2014, 0xffffffff, io_group=io_group)
        print(c.io.get_reg(0x2014, io_group=io_group))
        time.sleep(0.01)
        
        utility_base.update_json(asic_config_paths_file_, io_group,None )
        utility_base.update_json(network_config_paths_file_, io_group,None )
        
    return


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pacman_config', default="io/pacman.json", \
                        type=str, help='''Config specifying PACMANs''')
    parser.add_argument('--verbose', '-v', action='store_true', \
                        default=_default_verbose)
    args=parser.parse_args()
    c = main(**vars(args))
