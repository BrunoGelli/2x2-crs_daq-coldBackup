#!/usr/bin/env bash

if [[ $# -eq 2 ]]; then
	CONFIG_DIR=$2
	echo "Using asic_config dir $CONFIG_DIR"

	if [[ "$1" == *"1"* ]]; then
	python configure_larpix.py --pacman_config io/pacman_io1.json --config_subdir "m0" --asic_config $CONFIG_DIR --pid_logged &
	PID=$!
        sed -i "s/IOG1_PID=[0-9]*/IOG1_PID=${PID}/" .envrc
	fi

	if [[ "$1" == *"2"* ]]; then
	python configure_larpix.py --pacman_config io/pacman_io2.json --config_subdir "m0" --asic_config $CONFIG_DIR --pid_logged &
	PID=$!
        sed -i "s/IOG2_PID=[0-9]*/IOG2_PID=${PID}/" .envrc
	fi

	if [[ "$1" == *"3"* ]]; then
	python configure_larpix.py --pacman_config io/pacman_io3.json --config_subdir "m1" --asic_config $CONFIG_DIR --pid_logged &
	PID=$!
        sed -i "s/IOG3_PID=[0-9]*/IOG3_PID=${PID}/" .envrc
	fi

	if [[ "$1" == *"4"* ]]; then
	python configure_larpix.py --pacman_config io/pacman_io4.json --config_subdir "m1" --asic_config $CONFIG_DIR --pid_logged &
	PID=$!
        sed -i "s/IOG4_PID=[0-9]*/IOG4_PID=${PID}/" .envrc
	fi

	if [[ "$1" == *"5"* ]]; then
	python configure_larpix.py --pacman_config io/pacman_io5.json --config_subdir "m2" --asic_config $CONFIG_DIR --pid_logged &
	PID=$!
        sed -i "s/IOG5_PID=[0-9]*/IOG5_PID=${PID}/" .envrc
	fi

	if [[ "$1" == *"6"* ]]; then
	python configure_larpix.py --pacman_config io/pacman_io6.json --config_subdir "m2" --asic_config $CONFIG_DIR --pid_logged &
	PID=$!
        sed -i "s/IOG6_PID=[0-9]*/IOG6_PID=${PID}/" .envrc
	fi

	if [[ "$1" == *"7"* ]]; then
	python configure_larpix.py --pacman_config io/pacman_io7.json --config_subdir "m3" --asic_config $CONFIG_DIR --pid_logged &
	PID=$!
        sed -i "s/IOG7_PID=[0-9]*/IOG7_PID=${PID}/" .envrc
	fi

	if [[ "$1" == *"8"* ]]; then
	python configure_larpix.py --pacman_config io/pacman_io8.json --config_subdir "m3" --asic_config $CONFIG_DIR --pid_logged &
	PID=$!
        sed -i "s/IOG8_PID=[0-9]*/IOG8_PID=${PID}/" .envrc
	fi
else

	if [[ "$1" == *"1"* ]]; then
	python configure_larpix.py --pacman_config io/pacman_io1.json --config_subdir "m0" --pid_logged &
	PID=$!
        sed -i "s/IOG1_PID=[0-9]*/IOG1_PID=${PID}/" .envrc
	fi

	if [[ "$1" == *"2"* ]]; then
	python configure_larpix.py --pacman_config io/pacman_io2.json --config_subdir "m0" --pid_logged &
	PID=$!
        sed -i "s/IOG2_PID=[0-9]*/IOG2_PID=${PID}/" .envrc
	fi

	if [[ "$1" == *"3"* ]]; then
	python configure_larpix.py --pacman_config io/pacman_io3.json --config_subdir "m1" --pid_logged &
	PID=$!
        sed -i "s/IOG3_PID=[0-9]*/IOG3_PID=${PID}/" .envrc
	fi

	if [[ "$1" == *"4"* ]]; then
	python configure_larpix.py --pacman_config io/pacman_io4.json --config_subdir "m1" --pid_logged &
	PID=$!
        sed -i "s/IOG4_PID=[0-9]*/IOG4_PID=${PID}/" .envrc
	fi

	if [[ "$1" == *"5"* ]]; then
	python configure_larpix.py --pacman_config io/pacman_io5.json --config_subdir "m2" --pid_logged &
	PID=$!
        sed -i "s/IOG5_PID=[0-9]*/IOG5_PID=${PID}/" .envrc
	fi

	if [[ "$1" == *"6"* ]]; then
	python configure_larpix.py --pacman_config io/pacman_io6.json --config_subdir "m2" --pid_logged &
	PID=$!
        sed -i "s/IOG6_PID=[0-9]*/IOG6_PID=${PID}/" .envrc
	fi

	if [[ "$1" == *"7"* ]]; then
	python configure_larpix.py --pacman_config io/pacman_io7.json --config_subdir "m3" --pid_logged &
	PID=$!
        sed -i "s/IOG7_PID=[0-9]*/IOG7_PID=${PID}/" .envrc
	fi

	if [[ "$1" == *"8"* ]]; then
	python configure_larpix.py --pacman_config io/pacman_io8.json --config_subdir "m3" --pid_logged &
	PID=$!
        sed -i "s/IOG8_PID=[0-9]*/IOG8_PID=${PID}/" .envrc
	fi


fi


