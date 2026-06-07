#!/usr/bin/env bash


source .envrc

if [[ "$1" == *"1"* ]]; then
	kill $IOG1_PID
fi

if [[ "$1" == *"2"* ]]; then
        kill $IOG2_PID
fi

if [[ "$1" == *"3"* ]]; then
        kill $IOG3_PID
fi

if [[ "$1" == *"4"* ]]; then
        kill $IOG4_PID
fi

if [[ "$1" == *"5"* ]]; then
        kill $IOG5_PID
fi

if [[ "$1" == *"6"* ]]; then
        kill $IOG6_PID
fi

if [[ "$1" == *"7"* ]]; then
        kill $IOG7_PID
fi

if [[ "$1" == *"8"* ]]; then
        kill $IOG8_PID
fi


