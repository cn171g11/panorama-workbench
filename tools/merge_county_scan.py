"""Merge a county-level scan package into prefecture-level viewer shards.

Packages such as ``Zhejiang_Data.zip`` ship one ``data_<county adcode>.js`` per county.
The viewer stores points per prefecture, so the county files are folded into
``data_<prefecture adcode>.js`` (split into ``_2``, ``_3`` … at ``--part-size``).

Existing points are unioned rather than replaced: a county file may not contain every
point the repository already had, and a full rescan that misses a tile must not delete
data. Duplicates are removed by panorama id across the whole province, never by the
county file a point happens to appear in.
"""
import argparse
import json
import math
import re
from pathlib import Path

DEFAULT_PART_SIZE = 180000
JS_HEADER = "window.PANO_CITY=window.PANO_CITY||{};"
COUNTY_FILE = re.compile(r"^data_(\d{6})\.js$")


def read_assignment(source, name):
    marker = "window.%s=" % name
    start = source.index(marker) + len(marker)
    # raw_decode returns an index relative to the string it receives; slicing keeps the
    # returned offset comparable with ``start`` (passing the whole source double-counts it).
    value, end = json.JSONDecoder().raw_decode(source[start:])
    return value, start, start + end


def read_city_payload(path):
    source = path.read_text(encoding="utf-8")
    match = re.search(r"PANO_CITY\[(.+?)\]=(\[.*\]);\s*$", source, re.S)
    if not match:
        return None, []
    return json.loads(match.group(1)), json.loads(match.group(2))


def existing_entries(viewer, pref):
    entries = []
    pattern = re.compile(r"^data_%s(?:_\d+)?\.js$" % re.escape(pref))
    for path in sorted(viewer.glob("data_*.js")):
        if not pattern.match(path.name):
            continue
        key, payload = read_city_payload(path)
        if key:
            entries.extend(payload)
    return entries


def drop_existing_parts(viewer, pref):
    pattern = re.compile(r"^data_%s(?:_\d+)?\.js$" % re.escape(pref))
    removed = []
    for path in sorted(viewer.glob("data_*.js")):
        if pattern.match(path.name):
            removed.append(path.name)
            path.unlink()
    return removed


def write_parts(viewer, pref, entries, part_size):
    parts = max(1, math.ceil(len(entries) / part_size))
    written = []
    for index in range(parts):
        key = pref if index == 0 else "%s_%d" % (pref, index + 1)
        chunk = entries[index * part_size:(index + 1) * part_size]
        payload = JS_HEADER + 'window.PANO_CITY[%s]=%s;' % (
            json.dumps(key), json.dumps(chunk, ensure_ascii=False, separators=(",", ":")))
        (viewer / ("data_%s.js" % key)).write_text(payload, encoding="utf-8", newline="\n")
        written.append((key, len(chunk)))
    return written


def update_meta(viewer, updates, removals):
    path = viewer / "data_meta.js"
    source = path.read_text(encoding="utf-8")
    meta, meta_start, meta_end = read_assignment(source, "PANO_META")
    counts, counts_start, counts_end = read_assignment(source, "PANO_COUNT")
    for key in removals:
        meta.pop(key, None)
        counts.pop(key, None)
    for key, info in updates.items():
        meta[key] = info["meta"]
        counts[key] = info["count"]
    updated = (source[:meta_start] + json.dumps(meta, ensure_ascii=False, separators=(",", ":"))
               + source[meta_end:counts_start] + json.dumps(counts, ensure_ascii=False, separators=(",", ":"))
               + source[counts_end:])
    path.write_text(updated, encoding="utf-8", newline="\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="directory holding data_<county>.js files")
    parser.add_argument("--viewer", type=Path, default=Path("city-viewer"))
    parser.add_argument("--province-prefix", required=True, help="two-digit province code, e.g. 33")
    parser.add_argument("--province-name", required=True)
    parser.add_argument("--part-size", type=int, default=DEFAULT_PART_SIZE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    counties = {}
    for path in sorted(args.source.glob("data_*.js")):
        match = COUNTY_FILE.match(path.name)
        if not match:
            continue
        code = match.group(1)
        if not code.startswith(args.province_prefix):
            continue
        counties.setdefault(code[:4] + "00", []).append(path)

    meta_source = (args.viewer / "data_meta.js").read_text(encoding="utf-8")
    meta = read_assignment(meta_source, "PANO_META")[0]
    counts = read_assignment(meta_source, "PANO_COUNT")[0]

    report = {"prefectures": {}, "source_points": 0, "existing_points": 0,
              "added": 0, "final_points": 0, "missing_names": []}
    updates, removals = {}, []

    for pref in sorted(counties):
        existing = existing_entries(args.viewer, pref)
        merged = {str(entry[0]): entry for entry in existing}
        before = len(merged)
        source_points = 0
        for path in counties[pref]:
            key, payload = read_city_payload(path)
            source_points += len(payload)
            for entry in payload:
                if len(entry) != 9:
                    raise ValueError("%s: entry shape %d" % (path.name, len(entry)))
                merged[str(entry[0])] = entry
        entries = sorted(merged.values(), key=lambda entry: str(entry[0]))
        info = meta.get(pref)
        if not info:
            report["missing_names"].append(pref)
            info = {"name": pref, "province": args.province_name, "pref": pref}
        report["source_points"] += source_points
        report["existing_points"] += before
        report["added"] += len(entries) - before
        report["final_points"] += len(entries)
        report["prefectures"][pref] = {"name": info.get("name"), "counties": len(counties[pref]),
                                       "source": source_points, "existing": before,
                                       "total": len(entries), "added": len(entries) - before}
        if not args.dry_run:
            removed = drop_existing_parts(args.viewer, pref)
            parts = write_parts(args.viewer, pref, entries, args.part_size)
            removals.extend(name[len("data_"):-3] for name in removed)
            for key, count in parts:
                updates[key] = {"meta": {"name": info.get("name"), "province": info.get("province", args.province_name),
                                         "pref": pref}, "count": count}
            # Keep the prefecture head entry when the first part is written.
            updates[pref]["meta"]["pref"] = pref

    if not args.dry_run:
        update_meta(args.viewer, updates, [key for key in removals if key not in updates])
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
