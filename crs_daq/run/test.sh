#!/usr/bin/env bash

default_file=$(jq '.default_asic_config_paths_file_' <<< cat RUN_CONFIG.json)

echo $default_file
