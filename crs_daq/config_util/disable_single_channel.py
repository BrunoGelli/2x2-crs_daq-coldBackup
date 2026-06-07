import argparse
import json
from config_dtime import datetime_now

v2a_nonrouted_channels = [6,7,8,9,22,23,24,25,38,39,40,54,55,56,57]

def main(asic_config, channel, **kwargs):
    
    iog = int(channel.split('-')[0])
    ioch = int(channel.split('-')[1])
    chip = int(channel.split('-')[2])
    channel = int(channel.split('-')[3])
    mod = (iog-1)//2

    file = asic_config + f'/m{mod}/config_{iog}-{ioch}-{chip}.json'

    print(f'Disabling channel {channel} in {file}')

    config={}
    with open(file, 'r') as f: config=json.load(f)
                
    config['channel_mask'][channel]=1
    if 'csa_enable' not in config.keys():
        config['csa_enable']=[1]*64
    config['csa_enable'][channel]=0
    #config['periodic_trigger_mask'][channel]=1


    if 'meta' in config.keys():
        config['meta']['last_update'] = datetime_now()

    with open(file, 'w') as f: json.dump(config, f, indent=4)

    print('Channel disabled')
                
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--asic_config', type=str, default=None, help='''path to the asic config folder to change''')
    parser.add_argument('--channel', type=str, default=None, help='''channel to disable in the format io_group-io_channel-chip_id-channel_id''')

    args = parser.parse_args()
    c = main(**vars(args))

