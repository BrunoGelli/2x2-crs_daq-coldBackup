import argparse
import os
import larpix
import larpix.io

PACMAN_CONFIG_DIR = "io"


def pacman_config_from_io_group(io_group: int) -> str:
    return os.path.join(PACMAN_CONFIG_DIR, f"pacman_io{io_group}.json")


def tile_to_uart_channels(tile_idx: int):
    # tile_idx is 0-based; UART channels are 1-based
    start = tile_idx * 4 + 1
    return list(range(start, start + 4))


def read_uart_rx_mask(io, io_group: int):
    val = io.get_reg(0x18, io_group=io_group)
    print(f"io_group={io_group}: UART RX mask (reg 0x18) = {hex(val)}")
    return val


def read_tile_enable_mask(io, io_group: int):
    val = io.get_reg(io._base_ctrl_reg, io_group=io_group) & 0xFF
    print(f"io_group={io_group}: tile enable mask = 0x{val:02x}")
    return val


def enable_uart_channels(io, io_group: int, uart_channels: list[int], dry_run=False):
    cur = io.get_reg(0x18, io_group=io_group)
    new = cur

    for ch in uart_channels:
        bit = ch - 1  # channel 1 -> bit 0
        new |= (1 << bit)

    if dry_run:
        print(f"[dry-run] RX mask would change: {hex(cur)} -> {hex(new)}")
    else:
        io.set_reg(0x18, new, io_group=io_group)

    return cur, new


def main(io_group: int, tile: int, dry_run: bool):
    pacman_config = pacman_config_from_io_group(io_group)
    if not os.path.exists(pacman_config):
        raise FileNotFoundError(f"PACMAN config not found: {pacman_config}")

    print(f"Using pacman config: {pacman_config}")

    c = larpix.Controller()
    c.io = larpix.io.PACMAN_IO(relaxed=True, config_filepath=pacman_config)

    print(f"\n=== IO Group {io_group} ===")

    # Read current state (safe)
    read_uart_rx_mask(c.io, io_group)
    read_tile_enable_mask(c.io, io_group)

    uart_channels = tile_to_uart_channels(tile)
    print(f"Tile {tile} corresponds to UART channels {uart_channels}")

    if dry_run:
        print("[dry-run] No registers will be modified")
    else:
        new_tile_mask = c.io.enable_tile(tile_indices=tile, io_group=io_group)
        print(f"Enabled tile {tile}, new tile mask = 0x{new_tile_mask:02x}")

    enable_uart_channels(c.io, io_group, uart_channels, dry_run=dry_run)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Enable one PACMAN tile and unmute its UART RX channels"
    )
    parser.add_argument("--io_group", type=int, required=True,
                        help="io_group number (e.g. 1,2,3,...)")
    parser.add_argument("--tile", type=int, required=True,
                        help="Tile index (0-based: physical Tile 1 = 0)")
    parser.add_argument("--dry_run", action="store_true",
                        help="Read-only mode; do not write registers")

    args = parser.parse_args()
    main(args.io_group, args.tile, args.dry_run)
