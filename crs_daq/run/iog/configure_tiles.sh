#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./run/iog/configure_tiles.sh <IO_GROUP> <TILES_CSV> <SOURCE_CONFIG_DIR>
# Example:
#   ./run/iog/configure_tiles.sh 7 1,2 /data/CRS/asic_configs/ParameterScan/NominalConfigs

IOG="${1:?need IO group 1-8}"
TILES_CSV="${2:?need tiles list like 1 or 1,2}"
SRC_DIR="${3:?need source config dir (contains m0..m3)}"

die(){ echo "[err] $*" >&2; exit 1; }

# --- figure out important paths based on where this script lives ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# repo root is two levels up from run/iog/
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

PY_CONFIG="$REPO_ROOT/configure_larpix.py"
PACMAN_JSON="$REPO_ROOT/io/pacman_io${IOG}.json"
[[ -f "$PY_CONFIG" ]] || die "cannot find configure_larpix.py at $PY_CONFIG"
[[ -f "$PACMAN_JSON" ]] || die "missing $PACMAN_JSON"

# map IO group to module subdir m0..m3
case "$IOG" in
  1|2) SUBDIR="m0" ;; 3|4) SUBDIR="m1" ;; 5|6) SUBDIR="m2" ;; 7|8) SUBDIR="m3" ;;
  *) die "IO group must be 1..8" ;;
esac

SRC_SUB="$SRC_DIR/$SUBDIR"
[[ -d "$SRC_SUB" ]] || die "missing source subdir: $SRC_SUB"

# parse tiles CSV
IFS=',' read -r -a TILES <<< "$TILES_CSV"
for t in "${TILES[@]}"; do [[ "$t" =~ ^[0-9]+$ ]] || die "tiles must be integers (got '$t')"; done

# output (under repo root so it's always writable/nearby)
stamp="$(date +%Y_%m_%d_%H_%M_%S_%Z)"
OUT_ROOT="$REPO_ROOT/tmp/asic_configs_tiles-$stamp"
OUT_SUB="$OUT_ROOT/$SUBDIR"
mkdir -p "$OUT_SUB"

echo "[info] repo root: $REPO_ROOT"
echo "[info] source:    $SRC_SUB"
echo "[info] io_group:  $IOG   tiles: $TILES_CSV   → subdir: $SUBDIR"
echo "[info] output:    $OUT_SUB"

# copy by filename schema: config_<IOG>-<io_channel>-<chip>.json
copied=0
shopt -s nullglob
for t in "${TILES[@]}"; do
  base=$(( 4 * (t - 1) ))   # tile T → channels base+{1,2,3,4}
  for off in 1 2 3 4; do
    ch=$(( base + off ))
    for f in "$SRC_SUB/config_${IOG}-${ch}-"*.json; do
      cp -p -- "$f" "$OUT_SUB/"; ((copied++)) || true
    done
  done
done
(( copied > 0 )) || die "no matching config files copied; check filenames and inputs"

echo "[info] copied $copied file(s). Example:"
ls -1 "$OUT_SUB" | head -n 10 | sed 's/^/  - /'

# make absolute for the Python call
if command -v realpath >/dev/null 2>&1; then
  OUT_ROOT_ABS="$(realpath "$OUT_ROOT")"
else
  OUT_ROOT_ABS="$(cd "$OUT_ROOT" && pwd)"
fi

# run configure_larpix.py from repo root so imports & relatives work
echo "[info] running configure_larpix.py (foreground):"
echo "  cd $REPO_ROOT && python -u configure_larpix.py --pacman_config $PACMAN_JSON --config_subdir $SUBDIR --asic_config $OUT_ROOT_ABS"
cd "$REPO_ROOT"
python -u configure_larpix.py \
  --pacman_config "$PACMAN_JSON" \
  --config_subdir "$SUBDIR" \
  --asic_config "$OUT_ROOT_ABS"

echo "[ok] configure_larpix.py finished for io_group=$IOG tiles=$TILES_CSV"
