#!/usr/bin/env bash


if ! [ -f .archive_status ]; then
	echo 0 > .archive_status
fi

if grep -wq "0" .archive_status; then
	echo "Copying configuration data to archive..."
	python archive.py
	echo "done"
else
	pid=$(cat .archive_status)
	echo "################################################################################"
	echo " "
	echo "Archiver busy with process ID $pid"
	echo "Process is either still working or may have failed. Stop now and contact expert."
	echo " "
	echo "################################################################################"

fi
