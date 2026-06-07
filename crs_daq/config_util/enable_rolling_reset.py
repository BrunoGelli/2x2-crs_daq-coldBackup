#!/usr/bin/env python3
import json
import sys
from pathlib import Path

def patch_config(path):
    with open(path, 'r') as f:
        cfg = json.load(f)
    cfg['enable_rolling_periodic_reset'] = 1
    with open(path, 'w') as f:
        json.dump(cfg, f, indent=4)

if __name__ == "__main__":
    for fname in sys.argv[1:]:
        path = Path(fname)
        if not path.exists():
            print(f"File {path} not found, skipping")
            continue
        patch_config(path)
        print(f"Patched {path}")
