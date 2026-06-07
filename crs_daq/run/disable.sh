#!/usr/bin/env bash

if ! [ $# -eq 1 ]; then
	echo "---------------------------------------------------------"
	echo "Please specify a disabled list as a command line argument"
	echo "---------------------------------------------------------"
	exit
fi

#Copy the current ASIC configuration to a new directory

now=`date +%Y_%m_%d_%H_%M_%S_%Z`
config_dir="asic_configs/asic_configs-$now"
mkdir $config_dir

config1=$(jq '."1"' .asic_configs_.json)
config2=$(jq '."2"' .asic_configs_.json)
config3=$(jq '."3"' .asic_configs_.json)
config4=$(jq '."4"' .asic_configs_.json)
config5=$(jq '."5"' .asic_configs_.json)
config6=$(jq '."6"' .asic_configs_.json)
config7=$(jq '."7"' .asic_configs_.json)
config8=$(jq '."8"' .asic_configs_.json)

for config in $config1 $config2 $config3 $config4 $config5 $config6 $config7 $config8; do
 	stripped=$(echo "$config" | tr -d "'\"")
	if [ -d $stripped ]; then
		cp -r $stripped $config_dir
	fi
done

python config_util/merge_disabled_to_config.py "$config_dir"/m*/* --disabled_json $1

echo "---------------------------------------------------------------------------------------"
echo "New ASIC config written to $config_dir"
echo "Note: new ASIC config NOT sent to detector! To load onto detector, use run/configure.sh"
echo "---------------------------------------------------------------------------------------"
