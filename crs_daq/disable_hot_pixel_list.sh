#!/usr/bin/env bash

# Usage: ./disable_hot_pixels.sh hot_pixels.txt

HOTPIXELS_FILE="$1"
ASIC_CONFIG="/data/CRS/asic_configs/ParameterScan/NominalConfigs"
SCRIPT_PATH="config_util/disable_single_channel.py"

if [[ -z "$HOTPIXELS_FILE" ]]; then
    echo "❌ No input file specified."
    echo "Usage: $0 hot_pixels.txt"
    exit 1
fi

if [[ ! -f "$HOTPIXELS_FILE" ]]; then
    echo "❌ File not found: $HOTPIXELS_FILE"
    exit 1
fi

echo "🔧 Disabling hot pixels listed in $HOTPIXELS_FILE ..."
echo "-----------------------------------------------"

while IFS= read -r tag; do
    # skip empty lines or comment lines
    [[ -z "$tag" || "$tag" =~ ^# ]] && continue

    echo "➡️  Disabling: $tag"
    python "$SCRIPT_PATH" \
        --asic_config "$ASIC_CONFIG" \
        --channel "$tag"
done < "$HOTPIXELS_FILE"

echo "✅ Done!"

#all chatGPT...
