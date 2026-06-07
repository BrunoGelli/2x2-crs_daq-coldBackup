#!/usr/bin/env python3

# https://dune.github.io/DataCatalogDocs/template.html

import argparse
import datetime
import json
from pathlib import Path
import zlib

import h5py


def get_checksum(path: Path):
    cksum = 1
    with open(path, 'rb') as f:
        chunksize = int(1e9)
        while data := f.read(chunksize):
            cksum = zlib.adler32(data, cksum)
    return cksum & 0xffffffff


def get_start_time(f: h5py.File):
    return f['meta'].attrs['created']


def get_end_time(f: h5py.File):
    return f['meta'].attrs['modified']


def get_data_stream(f: h5py.File, args: argparse.Namespace):
    if ds := args.data_stream:
        return ds

    if ds := f['meta'].attrs.get('data_stream'):
        return ds

    return 'commissioning'


def get_data_tier(f: h5py.File):
    if 'packet' in Path(f.filename).name:
        return 'decoded-raw'
    return 'raw'


def get_run(f: h5py.File, args: argparse.Namespace):
    if run := args.run:
        return run

    if run := f['meta'].attrs.get('run'):
        return run

    return None


def get_subrun(f: h5py.File, args: argparse.Namespace):
    if subrun := args.subrun:
        return subrun

    if subrun := f['meta'].attrs.get('subrun'):
        return subrun

    run = get_run(f, args)
    return 10000 * run + 1


def get_first_event(f: h5py.File, args: argparse.Namespace):
    if first_event := args.first_event:
        return first_event

    if first_event := f['meta'].attrs.get('first_event'):
        return first_event

    return int(get_start_time(f))

def get_last_event(f: h5py.File, args: argparse.Namespace):
    if last_event := args.last_event:
        return last_event

    if last_event := f['meta'].attrs.get('last_event'):
        return last_event

    return int(get_end_time(f))

def get_metadata(f: h5py.File, args: argparse.Namespace):
    meta = {}
    path = Path(f.filename)

    meta['name'] = path.name
    meta['namespace'] = 'neardet-2x2-lar-charge'
    meta['checksums'] = {
        'adler32': f'{get_checksum(path):08x}'}
    meta['size'] = path.stat().st_size

    md = meta['metadata'] = {
        'core.application.family': 'larpix',
        'core.application.name': 'crs_daq',
        'core.application.version': '2x2',

        'core.data_stream': get_data_stream(f, args),
        'core.data_tier': get_data_tier(f),
        'core.file_type': 'detector',
        'core.file_format': 'hdf5',
        'core.file_content_status': 'good',

        'core.start_time': get_start_time(f),
        'core.end_time': get_end_time(f),

        'core.run_type': 'neardet-2x2-lar-charge',

        'core.runs': [get_run(f, args)],
        'core.runs_subruns': [get_subrun(f, args)],

        'core.first_event_number': get_first_event(f, args),
        'core.last_event_number': get_last_event(f, args),

        'retention.class': 'rawdata',
        'retention.status': 'active'
    }

    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('datafile', type=Path)

    # NOTE: If any of the following are specified on the command line, they
    # override whatever might be stored in the attrs of `/meta` in the hdf5
    # file. If nothing is specified on the command line, and nothing is in
    # `/meta`, then `get_data_stream` etc. will return a default value.
    ap.add_argument('--data-stream')
    # ap.add_argument('--run-type')
    ap.add_argument('--run', type=int)
    ap.add_argument('--subrun', type=int)
    ap.add_argument('--first-event', type=int)
    ap.add_argument('--last-event', type=int)

    args = ap.parse_args()

    conf = json.load(open('RUN_CONFIG.json'))
    dest = conf['destination_dir_']

    with h5py.File(f'{dest}/{args.datafile}') as f:
        meta = get_metadata(f, args)

    jsonfile = args.datafile.with_suffix(args.datafile.suffix + '.json')
    with open(f'{dest}/{jsonfile}', 'w') as outf:
        json.dump(meta, outf, indent=4)
        outf.write('\n')


if __name__ == '__main__':
    main()
