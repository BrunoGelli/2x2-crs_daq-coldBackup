#!/usr/bin/env bash


if [[ $# -eq 2 ]]; then
	CONFIG_DIR=$2
	echo "Using asic_config dir $CONFIG_DIR"

	if [[ "$1" == *"0"* ]]; then
	python configure_larpix.py --pacman_config io/pacman_m0.json --config_subdir "m0" --asic_config $CONFIG_DIR --pid_logged &
	PID=$!
	sed -i "s/MOD0_PID=[0-9]*/MOD0_PID=${PID}/" .envrc
	fi

	if [[ "$1" == *"1"* ]]; then
	python configure_larpix.py --pacman_config io/pacman_m1.json --config_subdir "m1" --asic_config $CONFIG_DIR --pid_logged  &
	PID=$!
        sed -i "s/MOD1_PID=[0-9]*/MOD1_PID=${PID}/" .envrc
	fi

	if [[ "$1" == *"2"* ]]; then
	python configure_larpix.py --pacman_config io/pacman_m2.json --config_subdir "m2" --asic_config $CONFIG_DIR --pid_logged &
	PID=$!
        sed -i "s/MOD2_PID=[0-9]*/MOD2_PID=${PID}/" .envrc
	fi

	if [[ "$1" == *"3"* ]]; then
	python configure_larpix.py --pacman_config io/pacman_m3.json --config_subdir "m3" --asic_config $CONFIG_DIR --pid_logged &
	PID=$!
        sed -i "s/MOD3_PID=[0-9]*/MOD3_PID=${PID}/" .envrc
	fi

else

	if [[ "$1" == *"0"* ]]; then
	python configure_larpix.py --pacman_config io/pacman_m0.json --config_subdir "m0" --pid_logged &
	PID=$!
        sed -i "s/MOD0_PID=[0-9]*/MOD0_PID=${PID}/" .envrc
	fi

	if [[ "$1" == *"1"* ]]; then
	python configure_larpix.py --pacman_config io/pacman_m1.json --config_subdir "m1" --pid_logged &
	PID=$!
        sed -i "s/MOD1_PID=[0-9]*/MOD1_PID=${PID}/" .envrc
	fi

	if [[ "$1" == *"2"* ]]; then
	python configure_larpix.py --pacman_config io/pacman_m2.json --config_subdir "m2" --pid_logged &
	PID=$!
        sed -i "s/MOD2_PID=[0-9]*/MOD2_PID=${PID}/" .envrc
	fi

	if [[ "$1" == *"3"* ]]; then
	python configure_larpix.py --pacman_config io/pacman_m3.json --config_subdir "m3" --pid_logged &
	PID=$!
        sed -i "s/MOD3_PID=[0-9]*/MOD3_PID=${PID}/" .envrc
	fi

fi


