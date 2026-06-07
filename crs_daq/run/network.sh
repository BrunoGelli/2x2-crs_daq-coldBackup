#!/usr/bin/env bash

if ! [ -f .default_asic_configs_.json ]; then
	echo "{}" > .default_asic_configs_.json
fi

default_file=$(jq '.default_asic_config_paths_file_' <<< cat RUN_CONFIG.json)
has_default_m00=$(jq -r 'has("1")' <<< cat .default_asic_configs_.json)
has_default_m01=$(jq -r 'has("2")' <<< cat .default_asic_configs_.json)
has_default_m10=$(jq -r 'has("3")' <<< cat .default_asic_configs_.json)
has_default_m11=$(jq -r 'has("4")' <<< cat .default_asic_configs_.json)
has_default_m20=$(jq -r 'has("5")' <<< cat .default_asic_configs_.json)
has_default_m21=$(jq -r 'has("6")' <<< cat .default_asic_configs_.json)
has_default_m30=$(jq -r 'has("7")' <<< cat .default_asic_configs_.json)
has_default_m31=$(jq -r 'has("8")' <<< cat .default_asic_configs_.json)

write_default_m0=false
write_default_m1=false
write_default_m2=false
write_default_m3=false
write_any=false

if ! $has_default_m00; then
	write_default_m0=true
	write_any=true
fi

if ! $has_default_m01; then
	write_default_m0=true
	write_any=true
fi

if ! $has_default_m10; then
	write_default_m1=true
	write_any=true
fi

if ! $has_default_m11; then
	write_default_m1=true
	write_any=true
fi

if ! $has_default_m20; then
	write_default_m2=true
	write_any=true
fi

if ! $has_default_m21; then
	write_default_m2=true
	write_any=true
fi

if ! $has_default_m30; then
	write_default_m3=true
	write_any=true
fi

if ! $has_default_m31; then
	write_default_m3=true
	write_any=true
fi

now=`date +%Y_%m_%d_%H_%M_%S_%Z`
config_dir="asic_configs/asic_configs-$now"
config_dir_m0="$config_dir/m0"
config_dir_m1="$config_dir/m1"
config_dir_m2="$config_dir/m2"
config_dir_m3="$config_dir/m3"

if $write_any; then	

	mkdir $config_dir

fi

if [[ "$1" == *"0"* ]]; then
	if $write_default_m0; then
		mkdir $config_dir_m0
		echo "Saving Module0 configuration files to: $config_dir_m0"
	fi

	echo "config dir: $config_dir_m0"
	python network_larpix.py --controller_config configs/controller_config.json --pacman_config io/pacman_m0.json --config_path $config_dir_m0 --pid_logged &
	PID=$!
	sed -i "s/MOD0_PID=[0-9]*/MOD0_PID=${PID}/" .envrc
	
fi

if [[ "$1" == *"1"* ]]; then
	if $write_default_m1; then
		mkdir $config_dir_m1
		echo "Saving Module1 configuration files to: $config_dir_m1"
	fi
	python network_larpix.py --controller_config configs/controller_config.json --pacman_config io/pacman_m1.json --config_path $config_dir_m1 --pid_logged &
	PID=$!
	sed -i "s/MOD1_PID=[0-9]*/MOD1_PID=${PID}/" .envrc
	
fi

if [[ "$1" == *"2"* ]]; then
	if $write_default_m2; then
		mkdir $config_dir_m2
		echo "Saving Module2 configuration files to: $config_dir_m2"
        fi
	python network_larpix.py --controller_config configs/controller_config.json --pacman_config io/pacman_m2.json --config_path $config_dir_m2 --pid_logged  &
	PID=$!
	sed -i "s/MOD2_PID=[0-9]*/MOD2_PID=${PID}/" .envrc
	
fi

if [[ "$1" == *"3"* ]]; then
	if $write_default_m3; then
		mkdir $config_dir_m3
		echo "Saving Module3 configuration files to: $config_dir_m3"
        fi
	python network_larpix.py --controller_config configs/controller_config.json --pacman_config io/pacman_m3.json --config_path $config_dir_m3 --pid_logged  &
	PID=$!
	sed -i "s/MOD3_PID=[0-9]*/MOD3_PID=${PID}/" .envrc
	
fi
