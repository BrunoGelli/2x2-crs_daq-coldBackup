#!/usr/bin/env python3
import argparse, time, sys, warnings
warnings.filterwarnings("ignore")

import larpix
import larpix.io

# --- Compatibility shims ---
try:
    from larpix.key import ChipKey              # newer
except Exception:
    from larpix.key import Key as ChipKey       # older

try:
    from larpix import Configuration            # common
except Exception:
    # very old packaging sometimes puts Configuration elsewhere
    from larpix.larpix import Configuration

# Optional helper (OK if missing)
try:
    from base import pacman_base
except Exception:
    pacman_base = None

def set_one_channel_bits(cfg, ch):
    # Ensure arrays exist and have 64 entries
    def ensure_len64(arr, fill):
        arr = list(arr) if arr is not None else []
        if len(arr) < 64:
            arr = arr + [fill] * (64 - len(arr))
        return arr[:64]

    # Ensure fields exist
    periodic_trigger_mask = ensure_len64(getattr(cfg, 'periodic_trigger_mask', [0]*64), 0)
    channel_mask          = ensure_len64(getattr(cfg, 'channel_mask', [0]*64), 0)
    csa_enable            = ensure_len64(getattr(cfg, 'csa_enable', [1]*64), 1)

    # Set exactly what we want for this channel
    periodic_trigger_mask[ch] = 1
    channel_mask[ch]          = 1
    csa_enable[ch]            = 0

    # Assign back (supporting both property and attribute styles)
    try: cfg.periodic_trigger_mask = periodic_trigger_mask
    except Exception: setattr(cfg, 'periodic_trigger_mask', periodic_trigger_mask)
    try: cfg.channel_mask = channel_mask
    except Exception: setattr(cfg, 'channel_mask', channel_mask)
    try: cfg.csa_enable = csa_enable
    except Exception: setattr(cfg, 'csa_enable', csa_enable)

def main():
    ap = argparse.ArgumentParser(
        description="FLOOD disable one noisy LArPix channel: ptm=1, mask=1, csa=0."
    )
    ap.add_argument("--pacman-config", required=True)
    ap.add_argument("--io-group",    type=int, required=True)
    ap.add_argument("--io-channel",  type=int, required=True)
    ap.add_argument("--chip-id",     type=int, required=True)
    ap.add_argument("--channel",     type=int, required=True, help="0–63")
    ap.add_argument("--duration",    type=float, default=8.0)
    ap.add_argument("--batch",       type=int,   default=128,
                    help="writes per inner burst (per register)")
    ap.add_argument("--readback",    action="store_true",
                    help="Try a final readback after flooding (usually unnecessary).")
    ap.add_argument("--quiet",       action="store_true")
    args = ap.parse_args()

    if args.channel < 0 or args.channel > 63:
        print(f"[error] channel must be 0..63 (got {args.channel})")
        sys.exit(2)

    if not args.quiet:
        print(f"[info] Target: io_group={args.io_group} io_channel={args.io_channel} "
              f"chip_id={args.chip_id} channel={args.channel}")

    # Controller + PACMAN
    c = larpix.Controller()
    # relaxed=True prevents some strict checks; asic_version omitted to match your env
    c.io = larpix.io.PACMAN_IO(relaxed=True, config_filepath=args.pacman_config)

    # Enable UARTs if helper is available
    if pacman_base is not None:
        try:
            pacman_base.enable_all_pacman_uart_from_io_group(c.io, args.io_group)
        except Exception as e:
            if not args.quiet:
                print(f"[warn] UART enable helper failed ({e}); proceeding anyway.")
    else:
        if not args.quiet:
            print("[warn] pacman_base not available; assuming UARTs are already enabled.")

    ck = ChipKey(args.io_group, args.io_channel, args.chip_id)
    if ck not in c.chips and str(ck) not in c.chips:
        c.add_chip(ck)

    # Attach a transient Configuration to this chip entry and set the 3 fields
    # Access style supports both c[ck] (new) and c.get_chip(ck) (old)
    try:
        chip_obj = c[ck]
    except Exception:
        chip_obj = c.get_chip(ck)

    # If chip_obj already has a config, use it; otherwise make a fresh one
    cfg = getattr(chip_obj, 'config', None)
    if cfg is None:
        cfg = Configuration()
        chip_obj.config = cfg  # so write_configuration('register') can find values

    set_one_channel_bits(cfg, args.channel)

    # Flood writes: write JUST these registers many times
    t_end = time.time() + args.duration
    if not args.quiet:
        print("[info] Flooding writes (no verify, no readbacks during flood)...")

    writes = 0
    while time.time() < t_end:
        # We split by register to keep each packet minimal and focused
        for _ in range(args.batch):
            c.write_configuration(ck, 'channel_mask')
        for _ in range(args.batch):
            c.write_configuration(ck, 'periodic_trigger_mask')
        for _ in range(args.batch):
            c.write_configuration(ck, 'csa_enable')
        writes += 3 * args.batch

    if not args.quiet:
        print(f"[info] Sent ~{writes} register writes")

    # Optional final readback (best-effort; skip by default)
    if args.readback:
        try:
            # Some versions accept a list of registers to read
            rb = None
            try:
                rb = c.read_configuration(ck, registers=['channel_mask','periodic_trigger_mask','csa_enable'],
                                          timeout=0.05, retries=0)
            except TypeError:
                rb = c.read_configuration(ck, timeout=0.05, retries=0)

            ok = (rb.channel_mask[args.channel] == 1 and
                  rb.periodic_trigger_mask[args.channel] == 1 and
                  rb.csa_enable[args.channel] == 0)
            if ok:
                print(f"[SUCCESS] Readback: channel {args.channel} disabled (ptm=1, mask=1, csa=0).")
                sys.exit(0)
            else:
                print("[WARN] Readback mismatch; flood may still have stuck amidst noise.")
                sys.exit(1)
        except Exception:
            print("[WARN] Readback failed (expected under heavy noise).")
            sys.exit(1)
    else:
        # No readback requested: rely on flood doing its job
        print("[DONE] Flood complete (no readback). If noise drops, verify via your usual path.")
        sys.exit(0)

if __name__ == "__main__":
    main()
