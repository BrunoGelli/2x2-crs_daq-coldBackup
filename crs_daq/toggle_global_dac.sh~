#!/usr/bin/env bash


############## Workflow
### (1) hardware reset and setup hydra network
### $ ./run/iog/network.sh 12345678
###
### (2) disable CSA and enable channel mask, if applicable
### $ python config_util/disable_all_channels.py <mod id> <path/to/asic_configs>

### (3) load ASIC configurations, if applicable
### $ ./run/iog/configure.sh 12345678
###

### ----- toggle_global_dac.py 
### (4) load chips under test, if none provided all chips in ASIC configurations are default under test
### (5) enable frontend for chips under test
### (7) toggle global DAC
### (8) save performance metrics to file
### (9) save chips to retest to file, if any
### (10) update asic configurations


############### Commandline arguments
### $1 pacman json
### $2 disabled list
### $3 chips under test

timestamp=$(date +%Y_%m_%d_%H_%M_%S_%Z)
echo $timestamp
mkdir -p threshold/global_dac_$timestamp

python3 toggle_global_dac.py --pacman_config $1 --disabled_list $2 --chip_list $3 --diagnostic_dir threshold/global_dac_$timestamp

#i=$1
#echo $i
#while(($i>0)); do
#    ./run/iog/network.sh $i
#    read -p "Re-network TPCs? 12345678     Or continue? 0: " i
#    echo $i
#    done
