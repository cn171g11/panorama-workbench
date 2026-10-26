"""Split the hidden collection into per-prefecture collections using prefecture polygons.

Rules:
  * Blade & Soul game panoramas (listed in tools/data/tencent-game-exceptions.json or
    whose road contains 剑灵) go to a dedicated `hidden_game` collection: their
    coordinates are fictional and cannot be placed by geography.
  * Everything else is assigned by point-in-polygon (DataV GeoAtlas, GCJ-02).
  * Points outside every polygon fall back to the nearest boundary within 120 km, which
    covers Sansha islets, the Yalu river bank and similar edge cases.
"""
import argparse
import json
import math
from pathlib import Path

SINGLE_PREFECTURE = {"110000", "120000", "310000", "500000", "810000", "820000"}
SKIP_PROVINCES = {"710000"}
HIDDEN_NAME = "腾讯隐藏街景/时光机"
FALLBACK_KEY = "hidden"
GAME_KEY = "hidden_game"
GAME_NAME = "剑灵游戏街景"
GAME_PROVINCE = "腾讯游戏街景"
NEAREST_LIMIT_KM = 120


def read_assignment(source, name):
    marker = "window.%s=" % name
    start = source.index(marker) + len(marker)
    return json.JSONDecoder().raw_decode(source, start)


def bounds_of(source, name):
    marker = "window.%s=" % name
    start = source.index(marker) + len(marker)
    _, end = json.JSONDecoder().raw_decode(source, start)
    return start, end


def load_prefectures(boundaries):
    country = json.loads((boundaries / "country.json").read_text(encoding="utf-8"))
    provinces = {str(f["properties"]["adcode"]): f for f in country["features"]
                 if f["properties"].get("level") == "province" and f["properties"].get("name")}
    items = []
    for code, feature in provinces.items():
        if code in SKIP_PROVINCES:
            continue
        province = feature["properties"]["name"]
        if code in SINGLE_PREFECTURE:
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


def segment_km(lng, lat, a, b):
    kx = 111.0 * math.cos(math.radians(lat))
    ky = 111.0
    ax, ay = (a[0] - lng) * kx, (a[1] - lat) * ky
    bx, by = (b[0] - lng) * kx, (b[1] - lat) * ky
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(ax, ay)
    t = -(ax * dx + ay * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(ax + t * dx, ay + t * dy)


def nearest(items, lng, lat, limit_km=NEAREST_LIMIT_KM):
    best, best_distance = None, limit_km
    for item in items:
        box = item["bbox"]
        # cheap lower bound from the bounding box
        dx = max(box[0] - lng, 0, lng - box[2]) * 111.0 * math.cos(math.radians(lat))
        dy = max(box[1] - lat, 0, lat - box[3]) * 111.0
        if math.hypot(dx, dy) > best_distance:
            continue
        for polygon in item["polygons"]:
            for ring in polygon:
                for index in range(len(ring) - 1):
                    distance = segment_km(lng, lat, ring[index], ring[index + 1])
                    if distance < best_distance:
                        best_distance, best = distance, item
    return best


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

    game_ids = set()
    exceptions = viewer.parent / "tools" / "data" / "tencent-game-exceptions.json"
    if exceptions.is_file():
        game_ids = set(json.loads(exceptions.read_text(encoding="utf-8"))["panoramaIds"])

    entries, collections = [], {}
    cursor = 0
    while True:
        marker = 'window.PANO_CITY["'
        start = source.find(marker, cursor)
        if start == -1:
            break
        name_end = source.index('"]=', start)
        key = source[start + len(marker):name_end]
        value, value_end = json.JSONDecoder().raw_decode(source, name_end + 3)
        collections[key] = len(value)
        entries.extend(value)
        cursor = value_end
    print(json.dumps({"existing_collections": len(collections), "entries": len(entries),
                      "game_exceptions": len(game_ids)}))

    groups = {}
    placed, by_nearest, game_count, unassigned = 0, [], 0, 0
    for entry in entries:
        sid = str(entry[0])
        if sid in game_ids or "剑灵" in str(entry[3]):
            game_count += 1
            groups.setdefault(GAME_KEY, {"province": GAME_PROVINCE, "name": GAME_NAME, "entries": []})["entries"].append(entry)
            continue
        located = locate(items, entry[1], entry[2])
        method = "polygon"
        if not located:
            located = nearest(items, entry[1], entry[2])
            method = "nearest"
        if not located:
            unassigned += 1
            groups.setdefault(FALLBACK_KEY, {"province": HIDDEN_NAME, "name": HIDDEN_NAME, "entries": []})["entries"].append(entry)
            continue
        if method == "nearest":
            by_nearest.append((sid, located["name"], round(entry[1], 3), round(entry[2], 3)))
        else:
            placed += 1
        key = "hidden_" + located["adcode"]
        group = groups.setdefault(key, {"province": located["province"],
                                        "name": located["name"] + "·隐藏街景", "entries": []})
        group["entries"].append(entry)

    order = sorted(groups, key=lambda key: (key == FALLBACK_KEY, key == GAME_KEY, key))
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
    updated = (meta_source[:meta_bounds[0]] + json.dumps(meta, ensure_ascii=False, separators=(",", ":"))
               + meta_source[meta_bounds[1]:count_bounds[0]] + json.dumps(counts, ensure_ascii=False, separators=(",", ":"))
               + meta_source[count_bounds[1]:])
    (viewer / "data_meta.js").write_text(updated, encoding="utf-8", newline="\n")

    print(json.dumps({"collections": len(order), "polygon": placed, "nearest": len(by_nearest),
                      "game": game_count, "unassigned": unassigned, "total": len(entries),
                      "game_key": GAME_KEY, "game_count": groups.get(GAME_KEY, {}).get("entries", []).__len__(),
                      "nearest_samples": by_nearest[:12]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
