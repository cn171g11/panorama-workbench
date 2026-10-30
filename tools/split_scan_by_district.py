"""Split a province scan into per-prefecture record files.

The scanner stores everything it finds inside one boundary; the viewer stores points per
prefecture. This assigns every record to the prefecture polygon that contains it and
writes one JSONL per viewer key, so each key can go through the normal import path.

County-level divisions that report directly to the province are folded into one key
(`469000` for Hainan) to match how the viewer already groups them.

Usage:
  python tools/split_scan_by_district.py --records scan.jsonl --boundary 460000.json \\
      --out split/ --aggregate 469001-469030=469000
"""
import argparse
import json
import math
from collections import Counter
from pathlib import Path


def rings_of(feature):
    geometry = feature["geometry"]
    polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
    rings = []
    for polygon in polygons:
        for index, ring in enumerate(polygon):
            if len(ring) > 3:
                rings.append((ring, index == 0))
    return rings


def point_in_ring(lng, lat, ring):
    inside = False
    for index in range(len(ring)):
        x1, y1 = ring[index][0], ring[index][1]
        x2, y2 = ring[index - 1][0], ring[index - 1][1]
        if (y1 > lat) != (y2 > lat) and lng < ((x2 - x1) * (lat - y1)) / (y2 - y1) + x1:
            inside = not inside
    return inside


def contains(feature, lng, lat):
    hit = False
    for ring, is_outer in rings_of(feature):
        if point_in_ring(lng, lat, ring):
            hit = is_outer  # inner rings punch holes
    return hit


def distance_to_ring(lng, lat, ring):
    best = float("inf")
    for index in range(len(ring)):
        x1, y1 = ring[index][0], ring[index][1]
        x2, y2 = ring[(index + 1) % len(ring)][0], ring[(index + 1) % len(ring)][1]
        dx, dy = x2 - x1, y2 - y1
        length = dx * dx + dy * dy
        t = 0.0 if length == 0 else max(0.0, min(1.0, ((lng - x1) * dx + (lat - y1) * dy) / length))
        px, py = x1 + t * dx, y1 + t * dy
        best = min(best, math.hypot((lng - px) * 95000, (lat - py) * 111000))
    return best


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--boundary", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--aggregate", action="append", default=[],
                        help="range=key, e.g. 469001-469030=469000 (repeatable)")
    parser.add_argument("--max-distance", type=float, default=2000,
                        help="fallback assignment radius in metres for points just outside a polygon")
    args = parser.parse_args()

    features = [item for item in json.loads(args.boundary.read_text(encoding="utf-8"))["features"]
                if item["properties"].get("name")]

    def key_of(adcode):
        code = int(adcode)
        for rule in args.aggregate:
            span, target = rule.split("=")
            low, _, high = span.partition("-")
            if int(low) <= code <= int(high or low):
                return target, "aggregate"
        return str(code), "direct"

    args.out.mkdir(parents=True, exist_ok=True)

    records = [json.loads(line) for line in args.records.read_text(encoding="utf-8").splitlines() if line.strip()]
    buckets = {}
    stats = Counter()
    outside = 0

    for record in records:
        lng, lat = record["lng"], record["lat"]
        feature = next((item for item in features if contains(item, lng, lat)), None)
        if feature is None:
            nearest = min(features, key=lambda item: min(distance_to_ring(lng, lat, ring) for ring, _ in rings_of(item)))
            if min(distance_to_ring(lng, lat, ring) for ring, _ in rings_of(nearest)) > args.max_distance:
                outside += 1
                continue
            feature = nearest
            stats["nearest_fallback"] += 1
        key, mode = key_of(feature["properties"]["adcode"])
        buckets.setdefault(key, []).append(record)
        stats[mode] += 1

    report = {"records": len(records), "keys": {}, "outside": outside, "modes": dict(stats)}
    for key, items in sorted(buckets.items()):
        name = next((item["properties"]["name"] for item in features
                     if key_of(item["properties"]["adcode"])[0] == key), key)
        path = args.out / ("%s.jsonl" % key)
        path.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in items) + "\n", encoding="utf-8")
        report["keys"][key] = {"name": name, "records": len(items)}
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
