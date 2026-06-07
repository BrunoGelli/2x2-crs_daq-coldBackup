#!/usr/bin/env bash

if [[ "$1" == *"0"* ]]; then
python configure_pacman.py --pacman_config io/pacman_m0.json 
fi

if [[ "$1" == *"1"* ]]; then
python configure_pacman.py --pacman_config io/pacman_m1.json 
fi

if [[ "$1" == *"2"* ]]; then
python configure_pacman.py --pacman_config io/pacman_m2.json 
fi

if [[ "$1" == *"3"* ]]; then
python configure_pacman.py --pacman_config io/pacman_m3.json 
fi
