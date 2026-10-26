"""Split the hidden collection into per-prefecture collections using prefecture polygons.

Boundaries come from the DataV GeoAtlas cache (GCJ-02, same datum as the panorama
coordinates, so no reprojection is applied). Points outside every polygon stay in the
fallback `hidden` collection.
"""
import argparse
import json
from pathlib import Path

MUNICIPALITIES = {"110000", "120000", "310000", "500000"}
HIDDEN_NAME = "腾讯隐藏街景/时光机"
FALLBACK_KEY = "hidden"


def read_assignment(source, name):
    marker = "window.%s=" % name
    start = source.index(marker) + len(marker)
    return json.JSONDecoder().raw_decode(source, start)


def write_assignment(source, name, value, bounds):
    _, start, end = bounds
    return source[:start] + json.dumps(value, ensure_ascii=False, separators=(",", ":")) + source[end:]


def bounds_of(source, name):
    marker = "window.%s=" % name
    start = source.index(marker) + len(marker)
    _, end = json.JSONDecoder().raw_decode(source, start)
    return name, start, end


def load_prefectures(boundaries):
    country = json.loads((boundaries / "country.json").read_text(encoding="utf-8"))
    provinces = {str(f["properties"]["adcode"]): f for f in country["features"]
                 if f["properties"].get("level") == "province" and f["properties"].get("name")}
    items = []
    for code, feature in provinces.items():
        if code in ("710000", "810000", "820000"):
            continue
        province = feature["properties"]["name"]
        if code in MUNICIPALITIES:
            children = [(code, province, feature["geometry"])]
        else:
            path = boundaries / ("%s.json" % code)
            if not path.is_file():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            children = [(str(f["properties"]["adcode"]), f["properties"]["name"], f["geometry"])
                        for f in data["features"] if f["properties"].get("name")]
        for adcode, name, geometry in children:
            polygons = (geometry["coordinates"] if geometry["type"] == "MultiPolygon"
                        else [geometry["coordinates"]] if geometry["type"] == "Polygon" else [])
            if not polygons:
                continue
            lngs = [pt[0] for poly in polygons for ring in poly for pt in ring]
            lats = [pt[1] for poly in polygons for ring in poly for pt in ring]
            items.append({"adcode": adcode, "name": name, "province": province,
                          "bbox": (min(lngs), min(lats), max(lngs), max(lats)), "polygons": polygons})
    return items


def in_ring(lng, lat, ring):
    inside = False
    j = len(ring) - 1
    for i, point in enumerate(ring):
        xi, yi = point[0], point[1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat):
            cross = (xj - xi) * (lat - yi) / (yj - yi) + xi
            if lng < cross:
                inside = not inside
        j = i
    return inside


def contains(item, lng, lat):
    for polygon in item["polygons"]:
        if not in_ring(lng, lat, polygon[0]):
            continue
        if any(in_ring(lng, lat, hole) for hole in polygon[1:]):
            continue
        return True
    return False


def locate(items, lng, lat):
    for item in items:
        box = item["bbox"]
        if box[0] <= lng <= box[2] and box[1] <= lat <= box[3] and contains(item, lng, lat):
            return item
    return None


def grid_of(entries):
    cells = {}
    for entry in entries:
        key = "%d,%d" % (int(entry[1] / 0.004), int(entry[2] / 0.004))
        cells[key] = cells.get(key, 0) + 1
    return [[int(k.split(",")[0]), int(k.split(",")[1]), v] for k, v in cells.items()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--viewer", type=Path, required=True)
    parser.add_argument("--boundaries", type=Path, required=True)
    args = parser.parse_args()

    viewer = args.viewer
    items = load_prefectures(args.boundaries)
    source = (viewer / "hidden_pano.js").read_text(encoding="utf-8")

    entries = []
    collections = {}
    cursor = 0
    while True:
        marker = 'window.PANO_CITY["'
        start = source.find(marker, cursor)
        if start == -1:
            break
        name_end = source.index('"]=', start)
        key = source[start + len(marker):name_end]
        value_start = name_end + 3
        value, value_end = json.JSONDecoder().raw_decode(source, value_start)
        collections[key] = len(value)
        entries.extend(value)
        cursor = value_end
    print(json.dumps({"existing_collections": len(collections), "entries": len(entries)}))

    groups, unassigned = {}, 0
    name_by_adcode = {}
    for entry in entries:
        located = locate(items, entry[1], entry[2])
        if not located:
            unassigned += 1
            groups.setdefault(FALLBACK_KEY, {"province": HIDDEN_NAME, "name": HIDDEN_NAME, "entries": []})["entries"].append(entry)
            continue
        key = "hidden_" + located["adcode"]
        group = groups.setdefault(key, {"province": located["province"],
                                        "name": located["name"] + "·隐藏街景", "entries": []})
        group["entries"].append(entry)
        name_by_adcode[located["adcode"]] = located["name"]

    order = sorted(groups, key=lambda key: (key == FALLBACK_KEY, key))
    parts = [
        "window.PANO_META=window.PANO_META||{};window.PANO_COUNT=window.PANO_COUNT||{};\n",
        "window.PANO_GRID_ALL=window.PANO_GRID_ALL||{};window.PANO_CITY=window.PANO_CITY||{};\n",
    ]
    for key in order:
        group = groups[key]
        meta = {"name": group["name"], "province": group["province"], "pref": key}
        parts.append('window.PANO_META["%s"]=%s;\n' % (key, json.dumps(meta, ensure_ascii=False, separators=(",", ":"))))
        parts.append('window.PANO_COUNT["%s"]=%d;\n' % (key, len(group["entries"])))
        parts.append('window.PANO_GRID_ALL["%s"]=%s;\n' % (key, json.dumps(grid_of(group["entries"]), separators=(",", ":"))))
        parts.append('window.PANO_CITY["%s"]=%s;\n' % (key, json.dumps(group["entries"], ensure_ascii=False, separators=(",", ":"))))
    (viewer / "hidden_pano.js").write_text("".join(parts), encoding="utf-8", newline="\n")

    meta_source = (viewer / "data_meta.js").read_text(encoding="utf-8")
    meta_bounds = bounds_of(meta_source, "PANO_META")
    count_bounds = bounds_of(meta_source, "PANO_COUNT")
    meta = read_assignment(meta_source, "PANO_META")[0]
    counts = read_assignment(meta_source, "PANO_COUNT")[0]
    for key in list(meta):
        if key == FALLBACK_KEY or key.startswith("hidden_"):
            meta.pop(key)
            counts.pop(key, None)
    for key in order:
        meta[key] = {"name": groups[key]["name"], "province": groups[key]["province"], "pref": key}
        counts[key] = len(groups[key]["entries"])
    updated = (meta_source[:meta_bounds[1]] + json.dumps(meta, ensure_ascii=False, separators=(",", ":"))
               + meta_source[meta_bounds[2]:count_bounds[1]] + json.dumps(counts, ensure_ascii=False, separators=(",", ":"))
               + meta_source[count_bounds[2]:])
    (viewer / "data_meta.js").write_text(updated, encoding="utf-8", newline="\n")

    provinces = {}
    for key in order:
        if key == FALLBACK_KEY:
            continue
        provinces.setdefault(groups[key]["province"], set()).add(key)
    print(json.dumps({"collections": len(order), "provinces": len(provinces), "unassigned": unassigned,
                      "total": len(entries),
                      "top": sorted(((k, len(g["entries"])) for k, g in groups.items() if k != FALLBACK_KEY),
                                    key=lambda pair: -pair[1])[:10]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
