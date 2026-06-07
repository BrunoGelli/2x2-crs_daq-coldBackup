#!/usr/bin/env bash

for file in "$@"
do
    	echo "converting $file ---> ${file/binary/'packet/packet'}"
	python ../larpix-control/scripts/convert_rawhdf5_to_hdf5.py -i $file -o "${file/binary/'packet/packet'}"
done

