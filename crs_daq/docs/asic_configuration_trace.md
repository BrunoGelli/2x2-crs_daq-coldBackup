# ASIC configuration enforcement trace

This note traces the progress bar shown by `run/iog/network.sh` and
`run/iog/configure.sh`, and summarizes where time is spent.

## Entry points

- `run/iog/network.sh <iog-list>` starts one background `network_larpix.py`
  process per selected IO group.  Each process uses a single-IO-group PACMAN
  JSON (`io/pacman_ioN.json`) and records its PID in `.envrc` so the Python
  process can choose a stable progress-bar line.
- `run/iog/configure.sh <iog-list> [asic-config-dir]` does the same for
  `configure_larpix.py`.  With an ASIC config directory argument it loads the
  module subdirectory (`m0` ... `m3`); otherwise it reloads the last config path
  recorded in `.asic_configs_.json`.

The visible progress bars are produced below these shell wrappers by
`base.enforce_parallel.enforce_parallel(...)`, not by the wrappers themselves.
Both Python entry points pass a `pbar_desc` and `pbar_position` into that helper.

## Network path

`network_larpix.py` loads `configs/controller_config.json`, then for every IO
 group in the selected PACMAN JSON:

1. Saves the network-config path to `.network_configs_.json`.
2. Builds an in-memory hydra network with `base.network_base.network_v2b(...)`
   or `base.network_base.network_v2a(...)` depending on `io_group_asic_version_`.
3. Converts the network file into ordered per-UART chip lists with
   `base.enforce_parallel.get_chips_by_io_group_io_channel(...)`.
4. Creates a fresh `larpix.Controller` with `larpix.io.PACMAN_IO(relaxed=True)`.
5. Loads default ASIC config files into that controller.
6. Enables the PACMAN UARTs used by those chips.
7. Calls `enforce_iterative(...)`, which calls
   `base.enforce_parallel.enforce_parallel(...)`.

If enforcement fails, `enforce_iterative(...)` rebuilds smaller network lists for
only chips reported in `diff` or `unconfigured`, then retries up to five times.
This retry loop is a likely source of unexpectedly long network operations.

## Configure path

`configure_larpix.py` loads one or more ASIC config directories into a
`larpix.Controller`, reads the existing network path for each IO group from
`.network_configs_.json`, and asks
`base.enforce_parallel.get_chips_by_io_group_io_channel(...)` for ordered
per-UART chip lists.  It then maps those keys onto the loaded controller chips,
enables all UARTs for the selected IO group, and calls
`base.enforce_parallel.enforce_parallel(...)` once.

## Parallelism model

The current code already parallelizes at two levels:

1. **Across IO groups**: `run/iog/*.sh` starts each selected IO group as a
   background Python process.
2. **Within an IO group**: `enforce_parallel(...)` receives `all_network_keys` as
   a list of per-IO-channel chip chains.  The intended scheduling is one chip
   per IO channel per cycle, preserving root-to-edge ordering within each UART
   while allowing different UARTs to advance together.

Because each UART chain has ordering dependencies, the expected lower bound is
roughly the depth of the longest configured chain, not the total chip count.
If wall time looks closer to total chip count, the bottleneck is probably inside
`enforce_parallel(...)` or in the larpix-control/PACMAN IO transaction path.

## Why it can take a long time

- **Longest-chain limit**: downstream chips cannot be configured before the
  upstream path is functional, so a deep UART dominates the progress bar.
- **Per-chip verification**: enforcement typically writes registers and reads
  them back; readback latency and retries add up.
- **Iterative network retries**: `network_larpix.py` retries failed subsets up to
  five times.
- **Repeated config loading**: `network_larpix.py` currently loads the default
  config directories inside a loop over IO groups, which is harmless for the
  single-IO-group `io/pacman_ioN.json` wrappers but would repeat work for a
  multi-IO-group PACMAN JSON.
- **Multiple Python processes**: IO-group parallelism is convenient, but each
  process owns its own controller/PACMAN_IO instance.  If several selected IO
  groups share a PACMAN or network resource, contention may reduce the expected
  speedup.

## Speed-up ideas

1. Instrument `enforce_parallel(...)` with per-cycle/per-UART timing so slow
   UARTs, chips, register writes, readbacks, and retries are visible.
2. Confirm that `enforce_parallel(...)` batches writes/reads across UARTs rather
   than looping `Controller.write_configuration`/`read_configuration` one chip at
   a time.
3. In `network_larpix.py`, avoid re-loading the same `DCONFIGS` inside nested
   IO-group loops when using a multi-IO-group PACMAN config.
4. Add a fast path for unchanged ASIC configs, similar to `diff_configure_larpix.py`,
   so only changed registers/chips are enforced.
5. Consider lowering retry count or making it configurable during routine runs,
   while keeping the current conservative retry count for recovery/debug runs.
6. Keep per-UART scheduling, but test whether PACMAN can safely accept larger
   per-cycle packet batches before readback.  If so, batching is likely a better
   optimization than adding more OS processes.
