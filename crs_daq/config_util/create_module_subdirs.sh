#!/usr/bin/env bash

# $1 asic config file path

mkdir $1/m0
mkdir $1/m1
mkdir $1/m2
mkdir $1/m3

mv $1/config_1*.json $1/m0
mv $1/config_2*.json $1/m0
mv $1/config_3*.json $1/m1
mv $1/config_4*.json $1/m1
mv $1/config_5*.json $1/m2
mv $1/config_6*.json $1/m2
mv $1/config_7*.json $1/m3
mv $1/config_8*.json $1/m3
