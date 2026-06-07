import warnings
warnings.filterwarnings("ignore")

import larpix
import argparse

import sys

from runenv import runenv as RUN

module = sys.modules[__name__]
for var in RUN.config.keys():
    setattr(module, var, getattr(RUN, var))


from base import config_loader
import shutil
import time
import os
from base import utility_base
from signal import signal, SIGINT
import subprocess
import base.utility_base
from base.utility_base import now

_default_file_count=-1
_default_runtime=300
_default_message='collecting data...'
_default_packet=False

def ctrlc_handler(signal_received, frame):
    
    base.utility_base._dump_and_exit_ = True
    print('CTRL-C detected. Starting Dump.')

def datetime_now():
	''' Return string with year, month, day, hour, minute '''
	return time.strftime("%Y_%m_%d_%H_%M_%Z_%S")

def main(file_count, runtime, message, packet, filename, file_tag, pacman_config, return_filename, record_metadata, run, data_stream, ignore_embed=False, **args):


    if not filename is None and file_count > 1:
        raise RuntimeError('All files will have same filename and will be overwritten')

    global _global_record_metadata_
    _global_record_metadata_ = record_metadata
    #Launch archiving process in the background to copy ASIC configs / detector parameters
    if monitor:
        #check if destination_dir_ ends with "/"
        copy_configs_here_=None
        if destination_dir_.endswith('/'):
            copy_configs_here = '{}.configs'.format(destination_dir_[:-1])
        else:
            copy_configs_here = '{}.configs'.format(destination_dir_)
        
        #check if copy_configs_here directory exists
        if not os.path.exists(copy_configs_here):
            os.mkdir(copy_configs_here)
        os.system('python archive.py --ignore_busy --monitor_dir {} &'.format(copy_configs_here))

    # dump ASIC configs to temporary directory to embed in data files
    if not ignore_embed: os.system('./dump_temp_archive.sh &')

    c = larpix.Controller()
    c.io = larpix.io.PACMAN_IO(relaxed=True, config_filepath=pacman_config)

    #data taking loop
    ctr=0
    while (ctr<file_count or file_count < 0) and not base.utility_base._dump_and_exit_:
        
        run_start = datetime_now()
        if filename is None or ctr>0: filename = destination_dir_ + '/' + utility_base.data_filename(c, packet, file_tag)
        elif ctr==0: filename = destination_dir_ + '/' + filename 
        
        # set command to archive in case of ctrl+c
        
        embed_command = './embed_configs.sh {} &'.format(filename.split('/')[-1])
        dump_command = './dump_metadata.sh {} {} {} &'.format(filename.split('/')[-1], run, data_stream)
        
        utility_base.data(c, runtime, packet, False, filename)
        #metadata handling here
        
        #embed configs in data file
        if not ignore_embed: 
            os.system(embed_command)
        
        #dump metadata file
        if record_metadata: os.system(dump_command)
        
        ctr+=1
         
    if return_filename:
        return filename

    return  

if __name__=='__main__':
    signal(SIGINT, ctrlc_handler)
    parser = argparse.ArgumentParser()
    parser.add_argument('--message', '-m', default=_default_message, \
                        type=str,  help='''Message logged with file''')
    parser.add_argument('--runtime', default=_default_runtime, \
                        type=int, help='''Runtime duration, default 5 minutes''')
    parser.add_argument('--file_count', default=_default_file_count, \
                        type=int, help='''Number of output files to create, default inf''')
    parser.add_argument('--packet', action='store_true', default=False,\
                        help='''Generate packet file (default binary)''')
    parser.add_argument('--pacman_config', default="io/pacman.json", \
                        type=str, help='''Config specifying PACMANs''')
    parser.add_argument('--filename', '-f', default=None, \
                        type=str,  help='''Specifiy a file name''')
    parser.add_argument('--file_tag', default=None, \
                        type=str, help='''Automatic filename generation including this tag''')
    parser.add_argument('--record_metadata', default=False, \
                        action='store_true', help='''Dump metadata''')
    parser.add_argument('--run', default=-1, \
                        type=int, help='''Run number, passed from combined run control''')
    parser.add_argument('--data_stream', default='', \
                        type=str, help='''Data stream, passed from combined run control''')
    parser.add_argument('--return_filename', action='store_true', help='''Return last filename''')
    parser.add_argument('--ignore_embed', default=False, \
                        action='store_true', help='''Don't embed configs. Necessary for runtime<~30 seconds''')
    args=parser.parse_args()
    c = main(**vars(args))
