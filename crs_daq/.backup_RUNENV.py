import os
import warnings
import json

warnings.filterwarnings("ignore")
##
##
## Specify detector and run dependent constants here
##
##

######################################################
## Parameters for automatic file transfer to data drive 
## SHOULD END with /'
destination_dir_='/data/commission/April2024/continued_pedestal/'
##3###################################################

asic_config_paths_file_='.asic_configs_.json'
default_asic_config_paths_file_='.default_asic_configs_.json'
network_config_paths_file_='.network_configs_.json'

log_dir='log/'
disabled_list_log_file_='disabled_list_log.json'
asic_config_log_file_='asic_config_log.json'

#####################################################
## Mappings of io_group-->pacman version and io_group/tile-->ASIC version
io_group_pacman_tile_={\
                    1:list(range(1,9)), 
                    2:list(range(1,9)), 
                    3:list(range(1,9)),
                    4:list(range(1,9)),
                    5:list(range(1,9)), 
                    6:list(range(1,9)),
                    7:list(range(1,9)),
                    8:list(range(1,9))
                    }

iog_pacman_version_={\
                    1: 'v1rev3b', 
                    2:'v1rev3b', 
                    3:'v1rev3b', 
                    4:'v1rev3b', 
                    5:'v1rev4', 
                    6:'v1rev4',
                    7:'v1rev3b',
                    8:'v1rev3b'
                    }

io_group_asic_version_={1:2, 2:2, 3:2, 4:2, 5:'2b', 6:'2b', 7:2, 8:2}
#####################################################

#####################################################
## Chips to exclude by io_group, tile from new networks being created.
## For example, {1: {}, 2:{ 1 : [11, 12], 4: [55] }} excludes on io_group 2 chips 11,12 on tile 1, and chip 55 on tile 4 
iog_exclude={
        1: {1:[], 2:[37], 3:[], 4:[], 5:[], 6:[], 7:[], 8:[]},
        2: {1:[], 2:[], 3:[], 4:[], 5:[], 6:[], 7:[71], 8:[11]},
        3: {1:[], 2:[], 3:[], 4:[], 5:[], 6:[], 7:[], 8:[]},
        4: {2:[],5:[60], 7:[]},
        5: {1:[], 2:[56, 80, 100], 3:[18], 4:[], 5:[], 6:[], 7:[106], 8:[]}, 
        6: {1:[], 2:[], 3:[], 4:[], 5:[72,73,83,92,93,102, 106], 6:[43], 7:[], 8:[108]},
        8: {2:[101]}
        }
####################################################

###################################################
asic_config_dir='asic_configs/'
##################################################

###################################################
iog_VDDD_DAC = {1 : 40000, 2: 40000, 3 : 40000, 4: 40000, 5:31000, 6:31000, 7 : 40000, 8: 40000}
iog_VDDA_DAC = {1 : 46500, 2: 46500, 3 : 46500, 4: 46500, 5:46500, 6:46500, 7 : 46500, 8: 46500 }
###################################################


######################################################################################################################3

if not os.path.isdir(destination_dir_): os.mkdir(destination_dir_)
if not os.path.isdir(log_dir): os.mkdir(log_dir)
if not os.path.isdir(asic_config_dir): os.mkdir(asic_config_dir)

if not os.path.isfile(default_asic_config_paths_file_):
    d={'configs':{}}
    with open(default_asic_config_paths_file_, 'w') as f:
        json.dump(d, f)

if not os.path.isfile(network_config_paths_file_):
    d={'configs':{}}
    with open(network_config_paths_file_, 'w') as f:
        json.dump(d, f)

if not os.path.isfile(asic_config_paths_file_):
    d={'configs':{}}
    with open(asic_config_paths_file_, 'w') as f:
        json.dump(d, f)

if not os.path.isfile(disabled_list_log_file_):
    d={}
    with open(disabled_list_log_file_, 'w') as f:
        json.dump(d, f)
