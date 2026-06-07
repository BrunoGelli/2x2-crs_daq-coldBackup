#!/usr/bin/env bash


#Command line arguments
# $1 : sample runtime
# $2 : min_rate for toggling
# $3 : max_rate for toggling


##############################################################################################
##
## 	Make a copy of the current ASIC configs to modify
##
##
##

config_file=".asic_configs_.json"
now=`date +%Y_%m_%d_%H_%M_%S_%Z`

destination_dir_=$(jq -r '.destination_dir_' <<< cat RUN_CONFIG.json)
current_config_m0=$(jq '."1"' <<< cat $config_file)
current_config_m1=$(jq '."3"' <<< cat $config_file)
current_config_m2=$(jq '."5"' <<< cat $config_file)
current_config_m3=$(jq '."7"' <<< cat $config_file)

config_dir=/data/CRS/asic_configs/self_trigger-toggle-asic_configs-$now

mkdir $config_dir

if [ ! $current_config_m0 = null  ]; then
	
	current_config_m0=$(echo "$current_config_m0" | tr -d "'\"")
	cp -r $current_config_m0 $config_dir &
fi

if [ ! $current_config_m1 = null  ]; then
        current_config_m1=$(echo "$current_config_m1" | tr -d "'\"")
        cp -r $current_config_m1 $config_dir &
fi

if [ ! $current_config_m2 = null  ]; then
	current_config_m2=$(echo "$current_config_m2" | tr -d "'\"")
        cp -r $current_config_m2 $config_dir &
fi

if [ ! $current_config_m3 = null  ]; then
	current_config_m3=$(echo "$current_config_m3" | tr -d "'\"")
        cp -r $current_config_m3 $config_dir &
fi
#######################################################################################


#######################################################################################
##
## Take a data sample and convert it to packet format
##
##

filename="toggle-data-sample-binary-$now.h5"
full_path="$destination_dir_/$filename"
full_packet="${full_path/binary/"packet"}" 
echo "Writing sample data file to: $full_path"

python record_data.py --filename $filename --runtime $1 --file_count 1 --ignore_embed

echo "converting to $full_packet"
python ../larpix-control/scripts/convert_rawhdf5_to_hdf5.py -i $full_path -o $full_packet

########################################################################################

########################################################################################
##
## Parse data file and create toggle_list of how to move thresholds

toggle_filename="toggle-list-$now.json" 
python config_util/toggle_trims_from_rate.py --filename $full_packet --min_rate $2 --max_rate $3 --toggle_filename $toggle_filename

########################################################################################


########################################################################################
##
## Merge new toggle file to the newly copied ASIC config

python config_util/merge_toggle_list_to_config.py $config_dir/*/* --toggle_json $toggle_filename

#########################################################################################


echo "#                                                                 #"
echo "#                                                                 #"
echo "#                                                                 #"
echo "#   New ASIC configs written to: $config_dir"
echo "#                                                                 #"
echo "#                                                                 #"
echo "#                                                                 #"

