#!/usr/bin/env python3
"""Validate exact PANO_CITY inventories and SID uniqueness without rewriting data."""
import argparse
import gc
import json
from pathlib import Path
import os
import sys
import re


def check(viewer, *, fast_exit=False):
    gc.disable()
    decoder = json.JSONDecoder()
    meta_source = (viewer / 'data_meta.js').read_text(encoding='utf-8')
    marker = 'window.PANO_COUNT='
    counts, _ = decoder.raw_decode(meta_source, meta_source.index(marker) + len(marker))
    seen = set()
    collections = {}
    game_ids = set()
    registered_games = set(json.loads((Path(__file__).resolve().parent / 'data/tencent-game-exceptions.json').read_text(encoding='utf-8'))['panoramaIds'])
    duplicate_count = 0
    samples = []
    total = 0
    paths = sorted(p for p in viewer.glob('data_*.js') if p.name not in ('data_meta.js', 'data_districts.js'))
    paths.append(viewer / 'hidden_pano.js')
    pattern = re.compile(r'window\.PANO_CITY\["([^"\\]+)"\]\s*=')
    for number, path in enumerate(paths, 1):
        source = path.read_text(encoding='utf-8')
        position = 0
        found = False
        while True:
            match = pattern.search(source, position)
            if not match:
                break
            rows, position = decoder.raw_decode(source, match.end())
            key = match.group(1)
            if key in collections:
                raise ValueError('Duplicate PANO_CITY assignment: ' + key)
            if not isinstance(rows, list) or counts.get(key) != len(rows):
                raise ValueError('Collection/count mismatch: ' + key)
            found = True
            collections[key] = len(rows)
            if key == 'hidden_game':
                game_ids.update(row[0] for row in rows)
            for row in rows:
                # Legacy Nanjing has eight fields; never omit those SIDs.
                if not isinstance(row, list) or len(row) not in (8, 9) or not isinstance(row[0], str) or not row[0]:
                    raise ValueError('Invalid panorama row in ' + key)
                total += 1
                if row[0] in seen:
                    duplicate_count += 1
                    if len(samples) < 8:
                        samples.append([row[0], key])
                else:
                    seen.add(row[0])
        if not found:
            raise ValueError('Point source has no PANO_CITY assignment: ' + path.name)
        if number % 50 == 0:
            print('SID progress files=%d/%d records=%d' % (number, len(paths), total), flush=True)
    if set(collections) != set(counts) or total != sum(counts.values()):
        raise ValueError('Point inventory does not match all PANO_COUNT keys')
    if game_ids != registered_games:
        raise ValueError('Registered game SID inventory is missing or altered')
    result = {'collections': len(collections), 'records': total, 'uniqueSid': len(seen), 'duplicateExtra': duplicate_count, 'gamePoints': len(game_ids)}
    print(json.dumps(result), flush=True)
    if duplicate_count:
        raise ValueError('Duplicate SIDs: ' + json.dumps(samples))
    if fast_exit:
        # All integrity checks above have completed; no source writes are pending.
        # Let the OS release the 40M-SID heap instead of paging through every object
        # during Python reference-count cleanup on low-memory Windows machines.
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--viewer', type=Path, default=Path(__file__).resolve().parents[1] / 'city-viewer')
    check(parser.parse_args().viewer, fast_exit=True)
