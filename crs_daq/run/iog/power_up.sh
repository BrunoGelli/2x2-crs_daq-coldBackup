#!/usr/bin/env bash

if [[ "$1" == *"1"* ]]; then
python configure_pacman.py --pacman_config io/pacman_io1.json 
fi

if [[ "$1" == *"2"* ]]; then
python configure_pacman.py --pacman_config io/pacman_io2.json 
fi

if [[ "$1" == *"3"* ]]; then
python configure_pacman.py --pacman_config io/pacman_io3.json 
fi

if [[ "$1" == *"4"* ]]; then
python configure_pacman.py --pacman_config io/pacman_io4.json 
fi

if [[ "$1" == *"5"* ]]; then
python configure_pacman.py --pacman_config io/pacman_io5.json 
fi

if [[ "$1" == *"6"* ]]; then
python configure_pacman.py --pacman_config io/pacman_io6.json 
fi

if [[ "$1" == *"7"* ]]; then
python configure_pacman.py --pacman_config io/pacman_io7.json 
fi

if [[ "$1" == *"8"* ]]; then
python configure_pacman.py --pacman_config io/pacman_io8.json 
fi

