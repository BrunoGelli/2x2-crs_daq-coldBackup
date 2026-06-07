#!/usr/bin/env bash

if [[ "$1" == *"1"* ]]; then
python power_down_larpix.py --pacman_config io/pacman_io1.json 
echo "Module0 TPC1 powered down"
fi

if [[ "$1" == *"2"* ]]; then
python power_down_larpix.py --pacman_config io/pacman_io2.json 
echo "Module0 TPC2 powered down"
fi

if [[ "$1" == *"3"* ]]; then
python power_down_larpix.py --pacman_config io/pacman_io3.json 
echo "Module1 TPC1 powered down"
fi

if [[ "$1" == *"4"* ]]; then
python power_down_larpix.py --pacman_config io/pacman_io4.json 
echo "Module1 TPC2 powered down"
fi

if [[ "$1" == *"5"* ]]; then
echo "Don't power down Module2...."
fi

if [[ "$1" == *"6"* ]]; then
echo "Don't power down Module2...."
fi

if [[ "$1" == *"7"* ]]; then
python power_down_larpix.py --pacman_config io/pacman_io7.json 
echo "Module3 TPC1 powered down"
fi

if [[ "$1" == *"8"* ]]; then
python power_down_larpix.py --pacman_config io/pacman_io8.json 
echo "Module3 TPC2 powered down"
fi

