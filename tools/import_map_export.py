"""Import a GeoGuessr-style map export into the viewer.

The export is a flat list of ``{panoId, lng, lat, source}``; mobility is not part of it, so a
navigation-v1 audit has to run first. The verdict decides the destination, following the same
rule as every other import:

  * regular (movable) -> ``qq_<province code>``
  * hidden            -> ``hidden_<prefecture adcode>``

Points already present in the viewer are counted but not written again.

Usage:
  python tools/import_map_export.py --export map.json --verification verify.json \\
      --boundaries <dir> --provinces 51 52 61 62 --viewer city-viewer
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from import_gap_scan_batch import (  # noqa: E402
    HIDDEN_MARKER, HIDDEN_SUFFIX, REGULAR_MARKER, REGULAR_NAME,
    build_entry, load_hidden_collections, load_meta, load_prefectures, locate,
    update_meta_file, write_hidden_collections, write_regular_shard,
)


def read_points(path):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("customCoordinates") or []
    points = []
    for item in payload:
        sid = str(item.get("panoId") or item.get("sid") or "").strip()
        lng, lat = item.get("lng"), item.get("lat")
        if not sid or lng is None or lat is None:
            continue
        points.append({"sid": sid, "lng": float(lng), "lat": float(lat)})
    return points


def read_verification(path):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return payload.get("records") or {}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", type=Path, required=True)
    parser.add_argument("--verification", type=Path, required=True)
    parser.add_argument("--boundaries", type=Path, required=True)
    parser.add_argument("--provinces", nargs="+", required=True)
    parser.add_argument("--viewer", type=Path, default=Path("city-viewer"))
    parser.add_argument("--existing", type=Path,
                        help="JSON list of sids already stored somewhere in the viewer")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    points = read_points(args.export)
    skip = set(json.loads(args.existing.read_text(encoding="utf-8"))) if args.existing else set()
    verdicts = read_verification(args.verification)
    items = load_prefectures(args.boundaries, args.provinces)

    _, meta, counts = load_meta(args.viewer)
    hidden = load_hidden_collections(args.viewer)
    hidden_meta = {key: meta.get(key) or {"name": key, "province": key, "pref": key} for key in hidden}

    buckets = {}      # key -> new records
    unresolved = []
    stats = Counter()

    for point in points:
        if point["sid"] in skip:
            stats["already_present"] += 1
            continue
        verdict = verdicts.get(point["sid"])
        if not verdict:
            stats["no_verdict"] += 1
            continue
        status = verdict.get("status")
        if status not in ("hidden", "regular"):
            stats["invalid_or_error"] += 1
            continue
        if status == "regular":
            item, _ = locate(items, point["lng"], point["lat"])
            if item is None:
                unresolved.append(point["sid"])
                continue
            key = "qq_" + item["province_code"][:2]
        else:
            item, _ = locate(items, point["lng"], point["lat"])
            if item is None:
                unresolved.append(point["sid"])
                continue
            key = "hidden_" + item["adcode"]
        buckets.setdefault(key, {"item": item, "records": [], "status": status})["records"].append(point)
        stats[status] += 1

    report = {"points": len(points), "verdicts": dict(stats), "unresolved": len(unresolved), "keys": {}}
    for key, bucket in sorted(buckets.items()):
        item = bucket["item"]
        if bucket["status"] == "hidden":
            known = {str(entry[0]) for entry in hidden.get(key, [])}
            fresh = [record for record in bucket["records"] if record["sid"] not in known]
            if fresh:
                entries = hidden.get(key, []) + [build_entry(record, HIDDEN_MARKER) for record in fresh]
                hidden[key] = sorted(entries, key=lambda entry: str(entry[0]))
                hidden_meta.setdefault(key, {"name": item["name"] + HIDDEN_SUFFIX,
                                             "province": item["province"], "pref": key})
                meta[key] = hidden_meta[key]
                counts[key] = len(hidden[key])
            report["keys"][key] = {"kind": "hidden", "name": item["name"], "added": len(fresh),
                                   "total": len(hidden.get(key, []))}
        else:
            path = args.viewer / ("data_%s.js" % key)
            existing = []
            if path.is_file():
                source = path.read_text(encoding="utf-8")
                start = source.find("window.PANO_CITY[")
                end = source.index("]=", start)
                existing, _ = json.JSONDecoder().raw_decode(source, end + 2)
            known = {str(entry[0]) for entry in existing}
            fresh = [record for record in bucket["records"] if record["sid"] not in known]
            if fresh:
                entries = sorted(existing + [build_entry(record, REGULAR_MARKER) for record in fresh],
                                 key=lambda entry: str(entry[0]))
                meta.setdefault(key, {"name": REGULAR_NAME + "·" + item["province"],
                                      "province": item["province"], "pref": key})
                counts[key] = len(entries)
                if not args.dry_run:
                    write_regular_shard(args.viewer, key, entries)
            report["keys"][key] = {"kind": "regular", "province": item["province"],
                                   "added": len(fresh), "total": counts.get(key, len(existing))}

    if not args.dry_run:
        if any(bucket["status"] == "hidden" and report["keys"].get(key, {}).get("added")
               for key, bucket in buckets.items()):
            write_hidden_collections(args.viewer, hidden, hidden_meta)
        update_meta_file(args.viewer, meta, counts)

    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
