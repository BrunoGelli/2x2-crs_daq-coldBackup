#!/usr/bin/env bash


if [[ $# -eq 2 ]]; then
	CONFIG_DIR=$2
	echo "Using asic_config dir $CONFIG_DIR"

	if [[ "$1" == *"0"* ]]; then
	python diff_configure_larpix.py --pacman_config io/pacman_m0.json --config_subdir "m0" --asic_config $CONFIG_DIR --pid_logged &
	PID=$!
	sed -i "s/MOD0_PID=[0-9]*/MOD0_PID=${PID}/" .envrc
	fi

	if [[ "$1" == *"1"* ]]; then
	python diff_configure_larpix.py --pacman_config io/pacman_m1.json --config_subdir "m1" --asic_config $CONFIG_DIR --pid_logged  &
	PID=$!
        sed -i "s/MOD1_PID=[0-9]*/MOD1_PID=${PID}/" .envrc
	fi

	if [[ "$1" == *"2"* ]]; then
	python diff_configure_larpix.py --pacman_config io/pacman_m2.json --config_subdir "m2" --asic_config $CONFIG_DIR --pid_logged &
	PID=$!
        sed -i "s/MOD2_PID=[0-9]*/MOD2_PID=${PID}/" .envrc
	fi

	if [[ "$1" == *"3"* ]]; then
	python diff_configure_larpix.py --pacman_config io/pacman_m3.json --config_subdir "m3" --asic_config $CONFIG_DIR --pid_logged &
	PID=$!
        sed -i "s/MOD3_PID=[0-9]*/MOD3_PID=${PID}/" .envrc
	fi

else
	echo "#######################################################"
	echo "#                                                     #"
	echo "#  Must specify a new configuration at a physically   #"
	echo "#  distinct directory from the current configuration  #"
	echo "#                                                     #"
	echo "# usage:                                              #"
	echo "# ./run/diff_configure.sh <modules> /path/to/config   #"
	echo "#                                                     #"
	echo "#######################################################"

fi


