import json

#dictionary of io_group to network_config.json file 
config = {1: "singlechip.json"}

with open('controller_config.json', 'w') as f:
    json.dump(config, f)

