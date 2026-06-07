#!/usr/bin/env python3
import json
from pathlib import Path
import argparse

def main():
    ap = argparse.ArgumentParser(description="Update global threshold in ASIC configs")
    ap.add_argument("asic_list", help="JSON file with list of ASIC IDs (e.g. chip_reevaluation_list.json)")
    ap.add_argument("config_dir", help="Path to config directory (contains m0, m1, ...)")
    ap.add_argument("--threshold", type=int, default=38, help="Threshold value to set (default: 38)")
    args = ap.parse_args()

    # Load ASIC list
    with open(args.asic_list) as f:
        asics = json.load(f)

    config_dir = Path(args.config_dir)

    updated = []
    missing = []

    for asic in asics:
        # Find config file (search in m0, m1, m2, m3)
        found = False
        for mdir in config_dir.glob("m*"):
            cfg_file = mdir / f"config_{asic}.json"
            if cfg_file.exists():
                with open(cfg_file) as cf:
                    cfg = json.load(cf)

                # Update threshold
                cfg["threshold_global"] = args.threshold

                with open(cfg_file, "w") as cf:
                    json.dump(cfg, cf, indent=2, sort_keys=True)

                updated.append(str(cfg_file))
                found = True
                break
        if not found:
            missing.append(asic)

    print(f"Updated {len(updated)} configs.")
    if missing:
        print("Missing configs for:", missing)

if __name__ == "__main__":
    main()
