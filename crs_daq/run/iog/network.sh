#!/usr/bin/env bash

if ! [ -f .default_asic_configs_.json ]; then
	echo "{}" > .default_asic_configs_.json
fi

default_file=".default_asic_configs_.json"
has_default_m00=$(jq -r 'has("1")' <<< cat .default_asic_configs_.json)
has_default_m01=$(jq -r 'has("2")' <<< cat .default_asic_configs_.json)
has_default_m10=$(jq -r 'has("3")' <<< cat .default_asic_configs_.json)
has_default_m11=$(jq -r 'has("4")' <<< cat .default_asic_configs_.json)
has_default_m20=$(jq -r 'has("5")' <<< cat .default_asic_configs_.json)
has_default_m21=$(jq -r 'has("6")' <<< cat .default_asic_configs_.json)
has_default_m30=$(jq -r 'has("7")' <<< cat .default_asic_configs_.json)
has_default_m31=$(jq -r 'has("8")' <<< cat .default_asic_configs_.json)

write_any=false

if ! $has_default_m00; then
	write_any=true
fi

if ! $has_default_m01; then
	write_any=true
fi

if ! $has_default_m10; then
	write_any=true
fi

if ! $has_default_m11; then
	write_any=true
fi

if ! $has_default_m20; then
	write_any=true
fi

if ! $has_default_m21; then
	write_any=true
fi

if ! $has_default_m30; then
	write_any=true
fi

if ! $has_default_m31; then
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
## Module 0
########################################
if [[ "$1" == *"1"* ]]; then
	
	if ! $has_default_m00; then
		echo "Saving Module0 TPC1 configuration files to: $config_dir_m0"
		if ! [ -d $config_dir_m0 ]; then
			mkdir $config_dir_m0
		fi
	fi

	python network_larpix.py --controller_config configs/controller_config.json --pacman_config io/pacman_io1.json --config_path $config_dir_m0 --pid_logged &
	PID=$!
	sed -i "s/IOG1_PID=[0-9]*/IOG1_PID=${PID}/" .envrc

	

fi

if [[ "$1" == *"2"* ]]; then
	if ! $has_default_m01; then
		echo "Saving Module0 TPC2 configuration files to: $config_dir_m0"
		if ! [ -d $config_dir_m0 ]; then
			mkdir $config_dir_m0
		fi
	fi


		
	python network_larpix.py --controller_config configs/controller_config.json --pacman_config io/pacman_io2.json --config_path $config_dir_m0 --pid_logged &
	PID=$!
	sed -i "s/IOG2_PID=[0-9]*/IOG2_PID=${PID}/" .envrc

fi

## Module 1
#######################################
if [[ "$1" == *"3"* ]]; then

	if ! $has_default_m10; then
		echo "Saving Module1 TPC1 configuration files to: $config_dir_m1"
		if ! [ -d $config_dir_m1 ]; then
			mkdir $config_dir_m1
		fi
	fi
        python network_larpix.py --controller_config configs/controller_config.json --pacman_config io/pacman_io3.json --config_path $config_dir_m1 --pid_logged &
        PID=$!
        sed -i "s/IOG3_PID=[0-9]*/IOG3_PID=${PID}/" .envrc
fi

if [[ "$1" == *"4"* ]]; then
        
	if ! $has_default_m11; then
		echo "Saving Module1 TPC2 configuration files to: $config_dir_m1"
		if ! [ -d $config_dir_m1 ]; then
			mkdir $config_dir_m1
		fi
	fi



        python network_larpix.py --controller_config configs/controller_config.json --pacman_config io/pacman_io4.json --config_path $config_dir_m1 --pid_logged &
	PID=$!
        sed -i "s/IOG4_PID=[0-9]*/IOG4_PID=${PID}/" .envrc
fi

#######################################

## Module 2
#######################################
if [[ "$1" == *"5"* ]]; then

	if ! $has_default_m20; then
		echo "Saving Module2 TPC1 configuration files to: $config_dir_m2"
		if ! [ -d $config_dir_m2 ]; then
			mkdir $config_dir_m2
		fi
	fi

        python network_larpix.py --controller_config configs/controller_config.json --pacman_config io/pacman_io5.json --config_path $config_dir_m2 --pid_logged &
        PID=$!
        sed -i "s/IOG5_PID=[0-9]*/IOG5_PID=${PID}/" .envrc
fi

if [[ "$1" == *"6"* ]]; then

	if ! $has_default_m21; then
		echo "Saving Module2 TPC2 configuration files to: $config_dir_m2"
		if ! [ -d $config_dir_m2 ]; then
			mkdir $config_dir_m2
		fi
	fi

        python network_larpix.py --controller_config configs/controller_config.json --pacman_config io/pacman_io6.json --config_path $config_dir_m2 --pid_logged &
        PID=$!
        sed -i "s/IOG6_PID=[0-9]*/IOG6_PID=${PID}/" .envrc
fi

#######################################

## Module 3
#######################################
if [[ "$1" == *"7"* ]]; then
        
	if ! $has_default_m30; then
		echo "Saving Module3 TPC1 configuration files to: $config_dir_m3"
		if ! [ -d $config_dir_m3 ]; then
			mkdir $config_dir_m3
		fi
	fi

        python network_larpix.py --controller_config configs/controller_config.json --pacman_config io/pacman_io7.json --config_path $config_dir_m3 --pid_logged &
        PID=$!
        sed -i "s/IOG7_PID=[0-9]*/IOG7_PID=${PID}/" .envrc
fi

if [[ "$1" == *"8"* ]]; then
        
	if ! $has_default_m31; then
		echo "Saving Module3 TPC2 configuration files to: $config_dir_m3"
		if ! [ -d $config_dir_m3 ]; then
			mkdir $config_dir_m3
		fi
	fi

        python network_larpix.py --controller_config configs/controller_config.json --pacman_config io/pacman_io8.json --config_path $config_dir_m3 --pid_logged &
        PID=$!
        sed -i "s/IOG8_PID=[0-9]*/IOG8_PID=${PID}/" .envrc
fi

#######################################
