"""Import a boundary scan result into the viewer.

The scan carries a navigation-v1 verdict for every panorama it stores, so no second audit
pass is needed:

  * hidden  -> ``hidden_<adcode>``
  * regular -> the city layer ``data_<adcode>.js`` (split into ``_2``, ``_3`` … at 180k)

Hong Kong and Macao are province-level and prefecture-level at the same time, so the city
layer key equals the adcode. Existing entries are unioned, never replaced.
"""
import argparse
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from import_gap_scan_batch import (  # noqa: E402
    HIDDEN_MARKER, HIDDEN_SUFFIX,
    build_entry, load_hidden_collections, load_meta, update_meta_file, write_hidden_collections,
)

PART_SIZE = 180000
JS_HEADER = "window.PANO_CITY=window.PANO_CITY||{};"
CITY_PAYLOAD = re.compile(r"PANO_CITY\[(.+?)\]=(\[.*\]);\s*$", re.S)


def read_scan(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def read_city_parts(viewer, adcode):
    entries = []
    pattern = re.compile(r"^data_%s(?:_\d+)?\.js$" % re.escape(adcode))
    for path in sorted(viewer.glob("data_*.js")):
        if not pattern.match(path.name):
            continue
        match = CITY_PAYLOAD.search(path.read_text(encoding="utf-8"))
        if match:
            entries.extend(json.loads(match.group(2)))
    return entries


def write_city_parts(viewer, adcode, entries):
    pattern = re.compile(r"^data_%s(?:_\d+)?\.js$" % re.escape(adcode))
    for path in sorted(viewer.glob("data_*.js")):
        if pattern.match(path.name):
            path.unlink()
    parts = max(1, math.ceil(len(entries) / PART_SIZE))
    written = []
    for index in range(parts):
        key = adcode if index == 0 else "%s_%d" % (adcode, index + 1)
        chunk = entries[index * PART_SIZE:(index + 1) * PART_SIZE]
        payload = JS_HEADER + "window.PANO_CITY[%s]=%s;" % (
            json.dumps(key), json.dumps(chunk, ensure_ascii=False, separators=(",", ":")))
        (viewer / ("data_%s.js" % key)).write_text(payload, encoding="utf-8", newline="\n")
        written.append((key, len(chunk)))
    return written


def shard_keys(viewer, adcode):
    keys = []
    for path in viewer.glob("data_%s*.js" % adcode):
        match = re.match(r"^data_(%s(?:_\d+)?)\.js$" % re.escape(adcode), path.name)
        if match:
            keys.append(match.group(1))
    return sorted(keys, key=lambda key: (0 if key == adcode else int(key.rsplit("_", 1)[1])))


def append_city(viewer, adcode, city_name, province_name, records, dry_run):
    """Append only the new panoramas to the last shard.

    A municipality already holds millions of points across dozens of shards; rewriting all
    of them to add a corridor would cost minutes and gigabytes. Only the new ids are
    looked up, and the tail shard is rewritten on its own.
    """
    keys = shard_keys(viewer, adcode)
    if not keys:
        raise SystemExit("no existing shard for %s" % adcode)
    wanted = {str(record["sid"]) for record in records}
    known = set()
    last_entries = []
    last_key = keys[-1]
    for key in keys:
        path = viewer / ("data_%s.js" % key)
        match = CITY_PAYLOAD.search(path.read_text(encoding="utf-8"))
        if not match:
            continue
        entries = json.loads(match.group(2))
        for entry in entries:
            if str(entry[0]) in wanted:
                known.add(str(entry[0]))
        if key == last_key:
            last_entries = entries
    fresh = [record for record in records if str(record["sid"]) not in known]
    result = {"append_to": last_key, "shard_before": len(last_entries),
              "known": len(known), "fresh": len(fresh), "shard_after": len(last_entries) + len(fresh)}
    if dry_run or not fresh:
        return result
    merged = last_entries + [build_entry(record, "腾讯常规") for record in fresh]
    merged.sort(key=lambda entry: str(entry[0]))
    viewer_path = viewer / ("data_%s.js" % last_key)
    if len(merged) <= PART_SIZE:
        payload = JS_HEADER + "window.PANO_CITY[%s]=%s;" % (
            json.dumps(last_key), json.dumps(merged, ensure_ascii=False, separators=(",", ":")))
        viewer_path.write_text(payload, encoding="utf-8", newline="\n")
        _, meta, counts = load_meta(viewer)
        meta[last_key] = {"name": city_name, "province": province_name, "pref": adcode}
        counts[last_key] = len(merged)
        update_meta_file(viewer, meta, counts)
        return result
    # The tail shard is full: split it and register the new key.
    written = write_city_parts(viewer, adcode, _all_city_entries(viewer, adcode, merged, last_key))
    _, meta, counts = load_meta(viewer)
    for key in [item for item in meta if re.match(r"^%s(_\d+)?$" % re.escape(adcode), item)]:
        meta.pop(key, None)
        counts.pop(key, None)
    for key, count in written:
        meta[key] = {"name": city_name, "province": province_name, "pref": adcode}
        counts[key] = count
    update_meta_file(viewer, meta, counts)
    result["split_into"] = [{"key": key, "count": count} for key, count in written]
    return result


def _all_city_entries(viewer, adcode, merged_tail, last_key):
    entries = []
    for key in shard_keys(viewer, adcode):
        path = viewer / ("data_%s.js" % key)
        match = CITY_PAYLOAD.search(path.read_text(encoding="utf-8"))
        if not match:
            continue
        entries.extend(merged_tail if key == last_key else json.loads(match.group(2)))
    return sorted(entries, key=lambda entry: str(entry[0]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--adcode", required=True)
    parser.add_argument("--city-name", required=True)
    parser.add_argument("--province-name", required=True)
    parser.add_argument("--viewer", type=Path, default=Path("city-viewer"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--append", action="store_true",
                        help="append to the last shard instead of rewriting every shard")
    args = parser.parse_args()

    records = {str(record["sid"]): record for record in read_scan(args.records)}
    hidden_key = "hidden_" + args.adcode

    _, meta, counts = load_meta(args.viewer)
    hidden = load_hidden_collections(args.viewer)
    hidden_meta = {key: meta.get(key) or {"name": key, "province": key, "pref": key} for key in hidden}

    hidden_records = [record for record in records.values() if record.get("status") == "hidden"]
    regular_records = [record for record in records.values() if record.get("status") == "regular"]
    report = {"adcode": args.adcode, "records": len(records), "hidden": len(hidden_records),
              "regular": len(regular_records), "origins": {}, "imported_hidden": 0,
              "imported_regular": 0, "already": 0, "parts": []}
    for record in records.values():
        origin = record.get("origin") or "measured"
        report["origins"][origin] = report["origins"].get(origin, 0) + 1

    known_hidden = {str(entry[0]) for entry in hidden.get(hidden_key, [])}
    fresh_hidden = [record for record in hidden_records if str(record["sid"]) not in known_hidden]
    report["imported_hidden"] = len(fresh_hidden)
    if fresh_hidden:
        entries = hidden.get(hidden_key, []) + [build_entry(record, HIDDEN_MARKER) for record in fresh_hidden]
        hidden[hidden_key] = sorted(entries, key=lambda entry: str(entry[0]))
        hidden_meta.setdefault(hidden_key, {"name": args.city_name + HIDDEN_SUFFIX,
                                            "province": args.province_name, "pref": hidden_key})
        meta[hidden_key] = hidden_meta[hidden_key]
        counts[hidden_key] = len(hidden[hidden_key])

    if args.append:
        report.update(append_city(args.viewer, args.adcode, args.city_name, args.province_name,
                                  regular_records, args.dry_run))
        print(json.dumps(report, ensure_ascii=False, indent=1))
        return

    existing = read_city_parts(args.viewer, args.adcode)
    known_city = {str(entry[0]) for entry in existing}
    fresh_city = [record for record in regular_records if str(record["sid"]) not in known_city]
    report["imported_regular"] = len(fresh_city)
    report["already"] = len(records) - len(fresh_hidden) - len(fresh_city)
    merged = sorted(existing + [build_entry(record, "腾讯常规") for record in fresh_city],
                    key=lambda entry: str(entry[0]))
    if fresh_city:
        parts = write_city_parts(args.viewer, args.adcode, merged) if not args.dry_run else []
        report["parts"] = [{"key": key, "count": count} for key, count in parts] or [
            {"key": args.adcode, "count": len(merged), "dry_run": True}]
        # Drop stale shard keys before writing the new metadata.
        if not args.dry_run:
            for key in [item for item in meta if re.match(r"^%s(_\d+)?$" % re.escape(args.adcode), item)]:
                meta.pop(key, None)
                counts.pop(key, None)
        for index, (key, count) in enumerate(parts):
            info = {"name": args.city_name, "province": args.province_name, "pref": args.adcode}
            meta[key] = info
            counts[key] = count

    if not args.dry_run:
        if fresh_city:
            update_meta_file(args.viewer, meta, counts)
        if fresh_hidden:
            write_hidden_collections(args.viewer, hidden, hidden_meta)
            meta[hidden_key] = hidden_meta[hidden_key]
            counts[hidden_key] = len(hidden[hidden_key])
            update_meta_file(args.viewer, meta, counts)
    report["city_total"] = len(merged)
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
