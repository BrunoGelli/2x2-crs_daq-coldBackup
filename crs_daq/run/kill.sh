#!/usr/bin/env bash


source .envrc

if [[ "$1" == *"0"* ]]; then
	kill $MOD0_PID
fi

if [[ "$1" == *"1"* ]]; then
        kill $MOD1_PID
fi

if [[ "$1" == *"2"* ]]; then
        kill $MOD2_PID
fi

if [[ "$1" == *"3"* ]]; then
        kill $MOD3_PID
fi



