import warnings
warnings.filterwarnings("ignore")
import argparse
import time
import sys
import os
from runenv import runenv as RUN
from base import utility_base
from base.utility_base import get_from_json
import numpy as np
import shutil

module = sys.modules[__name__]
for var in RUN.config.keys():
    setattr(module, var, getattr(RUN, var))

def copy_directory_files(src, dest):
    files = os.listdir(src)
    
    copy_name = src
    if '/' in copy_name: copy_name = src.split('/')[-1]

    if not os.path.exists(dest): os.mkdir(dest)

    for file in files:
        old = '{}/{}'.format(src, file)
        if not os.path.isfile(old): continue
        shutil.copy(old, dest)

    return 0


def main(monitor_dir, ignore_busy):

    # monitor_dir is dir to write files for influx or other db, if available
   
    #LOG EVERYTHING:
    # 1) CURRENT ASIC CONFIGURATION
    # 2) CURRENT HYDRA NETWORK
    # 3) ...
 
    #WRITE status=1 (BUSY) into logger_status_file
    
    print('archiving process: {}'.format(os.getpid()))
    now = utility_base.now()
    monitor_name = '.temp.monitor-{}'.format(now)
    os.mkdir(monitor_name)

    # PARSE current asic_config and copy those files to temp dir
 
    config_paths = get_from_json(asic_config_paths_file_,'all',meta_field='configs')

    config_monitor_dir = '{}/{}'.format(monitor_name, 'asic_configs')
    for io_group in config_paths.keys():
        path = config_paths[io_group]
        if path is None: continue
        copy_directory_files(path, config_monitor_dir )

    # PARSE current hydra network and copy to temp dir
    
    hydra_paths = get_from_json(network_config_paths_file_,'all',meta_field='configs')

    hydra_monitor_dir = '{}/{}'.format(monitor_name, 'hydra_network')
    os.mkdir(hydra_monitor_dir)

    for io_group in hydra_paths.keys():
        path = hydra_paths[io_group]
        if path is None: continue
        tile_config_files = get_from_json(path,'all',meta_field='_include')
        for file in tile_config_files:
            shutil.copy(file, hydra_monitor_dir )

    # ORGANIZE temp dir and move to monitor_dir with timestamp
    shutil.move(monitor_name,'{}/{}'.format(monitor_dir, monitor_name.split('.')[-1]) )


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--monitor_dir', type=str, default=monitor_dir_, \
                        help='''Directory to write archive to''')
    parser.add_argument('--ignore_busy', action='store_true', default=False, \
                        help='''Write anyway even if another process is archiving''')
    args=parser.parse_args()
    main(**vars(args))

