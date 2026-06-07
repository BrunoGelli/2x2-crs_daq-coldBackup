#!/usr/bin/env bash

#COMMAND LINE ARGUMENTS
# $1 FILENAME
# $2 RUN NUMBER
# $3 DATA-STREAM

python dump_metadata.py $1 --run $2 --data-stream $3
