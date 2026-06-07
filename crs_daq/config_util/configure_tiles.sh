#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./configure_tiles.sh <IO_GROUP> <TILES_CSV> [SOURCE_CONFIG_DIR]
#
# Examples:
#   ./configure_tiles.sh 8 0               # only tile 0 in IOGroup 8, using latest snapshot
#   ./configure_tiles.sh 8 1,3             # tiles 1 and 3 in IOGroup 8, using latest snapshot
#   ./configure_tiles.sh 3 0,1 asic_configs/asic_configs-2025_10_30_21_18_05_CDT  # explicit source

IOG="${1:?need IO group 1-8}"
TILES_CSV="${2:?need tiles list like 0 or 0,1,3}"
SRC_DIR="${3:-}"

# ---------- helpers ----------
die(){ echo "[err] $*" >&2; exit 1; }
need(){ command -v "$1" >/dev/null || die "need '$1' in PATH"; }
need jq

# Validate IO group
[[ "$IOG" =~ ^[1-8]$ ]] || die "IO group must be 1..8"

# Parse tiles into an array of integers
IFS=',' read -r -a TILES <<< "$TILES_CSV"
for t in "${TILES[@]}"; do
  [[ "$t" =~ ^[0-9]+$ ]] || die "tiles must be integers (got '$t')"
done

# Figure out module subdir from IO group (1-2:m0, 3-4:m1, 5-6:m2, 7-8:m3)
case "$IOG" in
  1|2) SUBDIR="m0" ;;
  3|4) SUBDIR="m1" ;;
  5|6) SUBDIR="m2" ;;
  7|8) SUBDIR="m3" ;;
  *) die "unexpected IO group mapping" ;;
esac

# Find source snapshot dir if not provided: pick newest asic_configs-*/SUBDIR that exists
if [[ -z "$SRC_DIR" ]]; then
  base="asic_configs"
  [[ -d "$base" ]] || die "no '$base' directory found"
  # newest snapshot containing our SUBDIR
  SRC_DIR="$(ls -1dt "${base}"/asic_configs-* 2>/dev/null | head -n1)"
  [[ -n "$SRC_DIR" && -d "$SRC_DIR/$SUBDIR" ]] || die "couldn't find a recent '$base/asic_configs-*/$SUBDIR'"
fi

[[ -d "$SRC_DIR/$SUBDIR" ]] || die "source subdir '$SRC_DIR/$SUBDIR' not found"

echo "[info] source snapshot: $SRC_DIR"
echo "[info] restricting to IO group $IOG, tiles ${TILES_CSV}, subdir $SUBDIR"

# Create temp filtered tree
stamp="$(date +%Y_%m_%d_%H_%M_%S_%Z)"
OUT_ROOT="tmp/asic_configs_tiles-$stamp"
OUT_SUB="$OUT_ROOT/$SUBDIR"
mkdir -p "$OUT_SUB"

# Walk all JSON files under the chosen subdir and copy only those matching io_group & tile(s).
# We accept either:
#   .io_group (int) and .io_channel (int)   OR
#   .chip_id/ .root info with nested fields (rare)
# Adjust this predicate if your schema differs.
copied=0
shopt -s nullglob
for f in "$SRC_DIR/$SUBDIR"/*.json; do
  # Extract values (silently ignore files that are not ASIC configs)
  og=$(jq -r 'try .io_group // empty' "$f")
  oc=$(jq -r 'try (.io_channel // .tile // .tile_id) // empty' "$f")

  # If not directly available, skip
  [[ -n "$og" && -n "$oc" ]] || continue

  if [[ "$og" == "$IOG" ]]; then
    for t in "${TILES[@]}"; do
      if [[ "$oc" == "$t" ]]; then
        cp -p "$f" "$OUT_SUB/"
        ((copied++))
        break
      fi
    done
  fi
done

[[ "$copied" -gt 0 ]] || die "no ASIC JSONs matched IO group $IOG and tiles ${TILES_CSV} in $SRC_DIR/$SUBDIR"

echo "[info] copied $copied file(s) into $OUT_SUB"

# Now call your existing configure.sh with the filtered directory
# This preserves your route to the correct pacman config & --config_subdir.
./configure.sh "$IOG" "$OUT_ROOT"

echo "[ok] configure.sh launched for IO group $IOG using filtered configs at $OUT_ROOT"
echo "[hint] tail -f .envrc to see updated IOGx PIDs, or ps -fp \$(grep -oE 'IOG${IOG}_PID=[0-9]+' .envrc | cut -d= -f2)"
