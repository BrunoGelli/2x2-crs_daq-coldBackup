#!/usr/bin/env python3
import warnings
warnings.filterwarnings("ignore")

import argparse, csv, json, sys, traceback
from collections import defaultdict
from datetime import datetime, timezone
import larpix, larpix.io

from base import network_base, pacman_base, utility_base, enforce_parallel
from runenv import runenv as RUN

# expose RUN.config keys
module = sys.modules[__name__]
for var in RUN.config.keys():
    setattr(module, var, getattr(RUN, var))

def _load_json(p):
    with open(p, 'r') as f: return json.load(f)

def _keys_for_tiles_from_controller(controller, io_group, tiles_set):
    keys = []
    for k in controller.chips.keys():  # larpix.Key
        if k.io_group != io_group: continue
        if utility_base.io_channel_to_tile(k.io_channel) in tiles_set:
            keys.append(k)
    return keys

def _group_by_network(keys):
    # list[list(Key,...)] grouped by (io_group, io_channel), sorted by chip_id
    grouped = defaultdict(list)
    for k in keys:
        grouped[(k.io_group, k.io_channel)].append(k)
    nets = []
    for net in grouped.values():
        net.sort(key=lambda kk: kk.chip_id)
        nets.append(net)
    return nets

def _key_fields(key):
    return {
        'io_group': getattr(key, 'io_group', None),
        'tile': utility_base.io_channel_to_tile(key.io_channel) if hasattr(key, 'io_channel') else None,
        'io_channel': getattr(key, 'io_channel', None),
        'chip_id': getattr(key, 'chip_id', None),
    }

def _json_safe(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(_json_safe(k)): _json_safe(v) for k, v in value.items()}
    if all(hasattr(value, attr) for attr in ('io_group', 'io_channel', 'chip_id')):
        return _key_fields(value)
    return str(value)

def _network_context(controller, key):
    context = {'root_chip': None, 'network_path': None}
    try:
        network = controller.network[key.io_group][key.io_channel]
        graph = network.get('miso_us')
        if graph is None:
            return context
        root_nodes = [node for node, attrs in graph.nodes(data=True)
                      if attrs.get('root') and node != 'ext']
        if root_nodes:
            context['root_chip'] = root_nodes[0]
            try:
                context['network_path'] = list(graph.shortest_path(context['root_chip'], key.chip_id))
            except AttributeError:
                # networkx Graph/DiGraph exposes shortest paths via module functions,
                # but some larpix graph wrappers expose it as a method.
                try:
                    import networkx as nx
                    context['network_path'] = list(nx.shortest_path(graph, context['root_chip'], key.chip_id))
                except Exception:
                    context['network_path'] = None
            except Exception:
                context['network_path'] = None
    except Exception:
        pass
    return context

def _format_detail(register=None, expected=None, actual=None, exception_class=None, exception_message=None):
    parts = []
    if register is not None:
        parts.append(f"register {register}")
    if expected is not None or actual is not None:
        parts.append(f"expected {expected} got {actual}")
    if exception_class or exception_message:
        parts.append(f"{exception_class}: {exception_message}")
    return '; '.join(parts)

def _make_row(controller, key, operation, status, attempt=0, retry_attempted=False,
              register=None, expected=None, actual=None, exception=None, details=None):
    row = _key_fields(key)
    row.update(_network_context(controller, key))
    row.update({
        'operation': operation,
        'register': register,
        'expected': _json_safe(expected),
        'actual': _json_safe(actual),
        'exception_class': exception.__class__.__name__ if exception else None,
        'exception_message': str(exception) if exception else None,
        'retry_attempted': bool(retry_attempted),
        'attempt': attempt,
        'status': status,
        'details': details,
    })
    if not row['details']:
        row['details'] = _format_detail(register, row['expected'], row['actual'],
                                        row['exception_class'], row['exception_message'])
    return row

def _rows_from_diff(controller, diff, operation='verify_config', attempt=0, retry_attempted=False):
    rows = []
    for key, registers in (diff or {}).items():
        if not registers:
            rows.append(_make_row(controller, key, operation, 'FAILED', attempt, retry_attempted,
                                  details='chip reported in diff with no register details'))
            continue
        for register, values in registers.items():
            expected, actual = None, None
            if isinstance(values, (list, tuple)) and len(values) >= 2:
                expected, actual = values[0], values[1]
            else:
                actual = values
            rows.append(_make_row(controller, key, operation, 'FAILED', attempt, retry_attempted,
                                  register=register, expected=expected, actual=actual))
    return rows

def _rows_from_unconfigured(controller, unconfigured, attempt=0, retry_attempted=False):
    rows = []
    for item in unconfigured or []:
        if all(hasattr(item, attr) for attr in ('io_group', 'io_channel', 'chip_id')):
            rows.append(_make_row(controller, item, 'enforce_parallel', 'FAILED', attempt, retry_attempted,
                                  details='reported unconfigured'))
            continue
        if isinstance(item, (list, tuple)):
            for maybe_key in item:
                if all(hasattr(maybe_key, attr) for attr in ('io_group', 'io_channel', 'chip_id')):
                    rows.append(_make_row(controller, maybe_key, 'enforce_parallel', 'FAILED', attempt, retry_attempted,
                                          details='reported unconfigured'))
    return rows

def _print_verbose_network(net, controller):
    if not net:
        return
    first = net[0]
    tile = utility_base.io_channel_to_tile(first.io_channel)
    root = _network_context(controller, first).get('root_chip')
    print(f"[enforce] io_group={first.io_group} tile={tile} io_channel={first.io_channel} "
          f"root={root} chips={len(net)}")
    for key in net:
        path = _network_context(controller, key).get('network_path')
        print(f"  -> chip_id={key.chip_id} path={path}")

def _enforce_with_diagnostics(controller, network_keys, args, io_group, tiles):
    rows = []
    final_ok = True
    final_diff = {}
    final_unconfigured = []
    max_retries = args.max_retries if args.max_retries is not None else args.retries

    for index, net in enumerate(network_keys):
        if args.verbose:
            _print_verbose_network(net, controller)
        net_ok = False
        net_diff = {}
        net_unconfigured = []
        last_exception = None
        for attempt in range(max_retries + 1):
            retry_attempted = attempt > 0
            try:
                if args.verbose:
                    print(f"[enforce] link {index + 1}/{len(network_keys)} attempt {attempt + 1}/{max_retries + 1}")
                net_ok, net_diff, net_unconfigured = enforce_parallel.enforce_parallel(
                    controller, [net], pbar_desc=f'io_group {io_group}, tiles {tiles}, link {index + 1}',
                    pbar_position=0
                )
                last_exception = None
            except Exception as exc:
                last_exception = exc
                net_ok = False
                net_diff = {}
                net_unconfigured = list(net)
                if args.verbose:
                    print(f"[enforce] exception on link {index + 1}: {exc.__class__.__name__}: {exc}")
                    traceback.print_exc()
            if net_ok:
                for key in net:
                    rows.append(_make_row(controller, key, 'enforce_parallel', 'OK', attempt,
                                          retry_attempted=retry_attempted))
                break
            if attempt < max_retries:
                if args.verbose:
                    print(f"[enforce] retrying link {index + 1}; diff_keys={len(net_diff or {})} "
                          f"unconfigured={len(net_unconfigured or [])}")
                continue

            final_ok = False
            final_diff.update(net_diff or {})
            final_unconfigured.extend(net_unconfigured or [])
            if last_exception is not None:
                for key in net:
                    rows.append(_make_row(controller, key, 'enforce_parallel', 'FAILED', attempt,
                                          retry_attempted=max_retries > 0, exception=last_exception))
            diff_rows = _rows_from_diff(controller, net_diff, attempt=attempt,
                                        retry_attempted=max_retries > 0)
            unconfigured_rows = _rows_from_unconfigured(controller, net_unconfigured, attempt=attempt,
                                                        retry_attempted=max_retries > 0)
            rows.extend(diff_rows)
            rows.extend(unconfigured_rows)
            if not diff_rows and not unconfigured_rows and last_exception is None:
                for key in net:
                    rows.append(_make_row(controller, key, 'enforce_parallel', 'FAILED', attempt,
                                          retry_attempted=max_retries > 0,
                                          details='enforce_parallel returned ok=False without diff/unconfigured details'))
            if not args.continue_on_error:
                remaining = [key for future_net in network_keys[index + 1:] for key in future_net]
                for key in remaining:
                    rows.append(_make_row(controller, key, 'enforce_parallel', 'SKIPPED', attempt,
                                          details='skipped after earlier failure; pass --continue-on-error to keep going'))
                return final_ok, final_diff, final_unconfigured, rows
    return final_ok, final_diff, final_unconfigured, rows

def _write_debug_reports(rows, args, metadata):
    if args.debug_report:
        payload = {'metadata': metadata, 'rows': rows}
        with open(args.debug_report, 'w') as out:
            json.dump(payload, out, indent=2, sort_keys=True, default=_json_safe)
        print(f"[debug] wrote JSON report: {args.debug_report}")
    if args.debug_report_csv:
        fieldnames = ['io_group', 'tile', 'io_channel', 'root_chip', 'chip_id', 'network_path',
                      'operation', 'register', 'expected', 'actual', 'exception_class',
                      'exception_message', 'retry_attempted', 'attempt', 'status', 'details']
        with open(args.debug_report_csv, 'w', newline='') as out:
            writer = csv.DictWriter(out, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                safe_row = {name: _json_safe(row.get(name)) for name in fieldnames}
                writer.writerow(safe_row)
        print(f"[debug] wrote CSV report: {args.debug_report_csv}")

def _print_summary(rows, io_group, tiles):
    print(f"\nNetwork enforcement summary: io_group={io_group} tiles={tiles}\n")
    columns = ['io_channel', 'root_chip', 'chip_id', 'operation', 'status', 'details']
    widths = {col: len(col) for col in columns}
    printable = []
    for row in rows:
        printable_row = {col: '' if row.get(col) is None else str(row.get(col)) for col in columns}
        printable.append(printable_row)
        for col in columns:
            widths[col] = min(max(widths[col], len(printable_row[col])), 80)
    header = '  '.join(col.ljust(widths[col]) for col in columns)
    print(header)
    print('  '.join('-' * widths[col] for col in columns))
    for row in printable:
        values = []
        for col in columns:
            value = row[col]
            if len(value) > widths[col]:
                value = value[:widths[col] - 3] + '...'
            values.append(value.ljust(widths[col]))
        print('  '.join(values))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--verbose','-v',action='store_true',default=False)
    ap.add_argument('--io_group', type=int, required=True)
    # single-tile (backward-compat) OR multi-tile CSV
    ap.add_argument('--pacman_tile', type=int, default=None, help='Single tile')
    ap.add_argument('--tiles', type=str, default=None, help='CSV of tiles, e.g. "1,3,5"')
    ap.add_argument('--controller_config', type=str, required=True)
    ap.add_argument('--pacman_config', type=str, required=True)
    ap.add_argument('--retries', type=int, default=2,
                    help='Legacy retry count for whole-request enforcement; also used by diagnostics if --max-retries is unset.')
    ap.add_argument('--max-retries', type=int, default=None,
                    help='Retry count per io_channel in diagnostic enforcement mode.')
    ap.add_argument('--continue-on-error', action='store_true', default=False,
                    help='Diagnostic mode: keep enforcing later io_channels after one link fails.')
    ap.add_argument('--debug-report', type=str, default=None,
                    help='Write machine-readable JSON diagnostic report.')
    ap.add_argument('--debug-report-csv', type=str, default=None,
                    help='Write machine-readable CSV diagnostic report.')
    ap.add_argument('--exclusive-uart', action='store_true', default=False,
                    help='Enable UART exclusively for these tiles (others disabled).')
    args = ap.parse_args()

    io_group = args.io_group
    # parse tiles
    if args.tiles:
        tiles = sorted({int(t.strip()) for t in args.tiles.split(',') if t.strip()!=''})
    elif args.pacman_tile is not None:
        tiles = [int(args.pacman_tile)]
    else:
        print("Provide --pacman_tile N or --tiles CSV"); sys.exit(1)

    pacman_cfg = _load_json(args.pacman_config)
    ctrl_cfg = _load_json(args.controller_config)

    if 'io_group' not in pacman_cfg or not any(io_group == pair[0] for pair in pacman_cfg['io_group']):
        print('Missing io_group in PACMAN config file!'); sys.exit(1)

    if args.verbose:
        print(f"Configuring io_group={io_group}, tiles={tiles} (targeted; no global re-network)")

    # Restricted bring-up for ONLY these tiles
    if io_group_asic_version_[io_group] == '2b':
        if args.verbose: print('init network_v2b (restricted)')
        c = network_base.network_v2b(ctrl_cfg[str(io_group)], tiles=tiles, io_group=io_group)
    elif io_group_asic_version_[io_group] in [2, 'lightpix-1']:
        if args.verbose: print('init network_v2a (restricted)')
        c = network_base.network_v2a(ctrl_cfg[str(io_group)], tiles=tiles, io_group=io_group)
    else:
        raise RuntimeError(f"Unknown ASIC version for io_group {io_group}: {io_group_asic_version_[io_group]}")

    # Optional UART isolation (will silence other tiles)
    if args.exclusive_uart:
        if args.verbose: print('[UART] exclusive enable for these tiles (others disabled)')
        pacman_base.enable_pacman_uart_from_tile(c.io, io_group, tiles)

    # Build chip set for the union of requested tiles
    tiles_set = set(tiles)
    keys_flat = _keys_for_tiles_from_controller(c, io_group, tiles_set)
    if not keys_flat:
        print("[ERR] No chips discovered on requested tiles; cannot enforce."); sys.exit(2)

    network_keys = _group_by_network(keys_flat)

    if args.verbose:
        print(f"[keys] {len(keys_flat)} chip(s) across {len(network_keys)} link(s) "
              f"for io_group={io_group}, tiles={tiles}")
        for k in keys_flat[:8]:
            print(f"  - key(io_group={k.io_group}, io_channel={k.io_channel}, chip_id={k.chip_id})")

    diagnostic_mode = bool(args.continue_on_error or args.debug_report or args.debug_report_csv or args.max_retries is not None)

    if diagnostic_mode:
        ok, diff, unconfigured, rows = _enforce_with_diagnostics(c, network_keys, args, io_group, tiles)
        metadata = {
            'created_utc': datetime.now(timezone.utc).isoformat(),
            'command': sys.argv,
            'io_group': io_group,
            'tiles': tiles,
            'controller_config': args.controller_config,
            'pacman_config': args.pacman_config,
            'continue_on_error': args.continue_on_error,
            'max_retries': args.max_retries if args.max_retries is not None else args.retries,
            'ok': ok,
        }
        _print_summary(rows, io_group, tiles)
        _write_debug_reports(rows, args, metadata)
        if not ok:
            raise RuntimeError("Enforcement did not converge for the requested tiles", diff)
    else:
        # Enforce (no re-networking), with limited retries. This preserves the legacy behavior.
        ok, diff, unconfigured = enforce_parallel.enforce_parallel(
            c, network_keys, pbar_desc=f'io_group {io_group}, tiles {tiles}', pbar_position=0
        )
        attempts = 0
        while (not ok) and attempts < args.retries:
            if args.verbose:
                print(f"[enforce] retry {attempts+1}/{args.retries} (same {len(network_keys)} links)")
            ok, diff, unconfigured = enforce_parallel.enforce_parallel(
                c, network_keys, pbar_desc=f'io_group {io_group}, tiles {tiles}', pbar_position=0
            )
            attempts += 1

        if not ok:
            raise RuntimeError("Enforcement did not converge for the requested tiles", diff)

    if args.verbose:
        print("[ok] enforcement complete for requested tiles")

if __name__ == '__main__':
    main()
