import warnings
warnings.filterwarnings("ignore")
import json
import os
import sys

class runenv:
       
        #INITIATE DEFAULT PARAMETERS FROM DEFAULT FILE
        config_file = 'RUN_CONFIG.json'
        config = {}
        with open(config_file, 'r') as f:
            config=json.load(f)
        
        for key in config.keys():
            vars()[key] = config[key] 
            if type(vars()[key])==dict: 
                
                subkeys = list(vars()[key].keys()).copy()
                for subkey in subkeys:
                    try:
                        vars()[key][int(subkey)] = vars()[key][subkey] 
                        del vars()[key][subkey]
                    except:
                        pass

        if not os.path.isdir(destination_dir_): os.mkdir(destination_dir_)
        if not os.path.isdir(log_dir): os.mkdir(log_dir)
        if not os.path.isdir(monitor_dir_): os.mkdir(monitor_dir_)
        if not os.path.isdir(asic_config_dir): os.mkdir(asic_config_dir)

        if not os.path.isfile(archive_status_file):
            os.system('echo 0 > {}'.format(archive_status_file))
        if not os.path.isfile(default_asic_config_paths_file_):
            d={}
            with open(default_asic_config_paths_file_, 'w') as f:
                json.dump(d, f)

        if not os.path.isfile(network_config_paths_file_):
            d={}
            with open(network_config_paths_file_, 'w') as f:
                json.dump(d, f)

        if not os.path.isfile(asic_config_paths_file_):
            d={}
            with open(asic_config_paths_file_, 'w') as f:
                json.dump(d, f)

        if not os.path.isfile(disabled_list_log_file_):
            d={}
            with open(disabled_list_log_file_, 'w') as f:
                json.dump(d, f)

        def __init__(self, config_file='RUN_CONFIG.json'):
            
            ''' Constructor for specific instance with non-default config file name''' 

            self.config_file = 'RUN_CONFIG.json'
            self.config = {}
            with open(self.config_file, 'r') as f:
                self.config=json.load(f)

            for key in config.keys():
                vars()[key] = config[key] 
                if type(vars()[key])==dict: 
                
                    subkeys = list(vars()[key].keys()).copy()
                    for subkey in subkeys:
                        try:
                            vars()[key][int(subkey)] = vars()[key][subkey] 
                            del vars()[key][subkey]
                        except:
                            pass

            if not os.path.isdir(self.destination_dir_): os.mkdir(self.destination_dir_)
            if not os.path.isdir(self.log_dir): os.mkdir(self.log_dir)
            if not os.path.isdir(self.asic_config_dir): os.mkdir(self.asic_config_dir)

            if not os.path.isfile(self.default_asic_config_paths_file_):
                d={'configs':{}}
                with open(self.default_asic_config_paths_file_, 'w') as f:
                    json.dump(d, f)

            if not os.path.isfile(self.network_config_paths_file_):
                d={'configs':{}}
                with open(self.network_config_paths_file_, 'w') as f:
                    json.dump(d, f)

            if not os.path.isfile(self.asic_config_paths_file_):
                d={'configs':{}}
                with open(self.asic_config_paths_file_, 'w') as f:
                    json.dump(d, f)

            if not os.path.isfile(self.disabled_list_log_file_):
                d={}
                with open(self.disabled_list_log_file_, 'w') as f:
                    json.dump(d, f)

if __name__=='__main__':
    runenv()
