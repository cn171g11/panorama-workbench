"""Helpers for per-province collections stored in city-viewer/hidden_pano.js."""
import json
import math
from pathlib import Path

GRID_RESOLUTION = 0.004
HIDDEN_NAME = "腾讯隐藏街景/时光机"
HIDDEN_MARKER = "腾讯隐藏"


def read_assignment(source, name):
    marker = "window.%s=" % name
    start = source.index(marker) + len(marker)
    value, end = json.JSONDecoder().raw_decode(source, start)
    return value, start, end


def build_grid(entries):
    counts = {}
    for entry in entries:
        cell = (math.floor(entry[1] / GRID_RESOLUTION), math.floor(entry[2] / GRID_RESOLUTION))
        counts[cell] = counts.get(cell, 0) + 1
    return [[x, y, count] for (x, y), count in counts.items()]


def _block_span(source, key):
    marker = 'window.PANO_CITY["%s"]=' % key
    start = source.index(marker)
    value_start = start + len(marker)
    _, value_end = json.JSONDecoder().raw_decode(source, value_start)
    return start, value_end + (1 if source[value_end:value_end + 1] == ";" else 0)


def read_collection(viewer_root, key):
    source = (Path(viewer_root) / "hidden_pano.js").read_text(encoding="utf-8")
    marker = 'window.PANO_CITY["%s"]=' % key
    if marker not in source:
        return []
    start = source.index(marker) + len(marker)
    value, _ = json.JSONDecoder().raw_decode(source, start)
    return value


def upsert_collection(viewer_root, key, entries, province, name=HIDDEN_NAME, marker=HIDDEN_MARKER):
    """Insert or replace one collection inside hidden_pano.js, leaving others untouched."""
    path = Path(viewer_root) / "hidden_pano.js"
    source = path.read_text(encoding="utf-8")
    counts = len(entries)
    grid = json.dumps(build_grid(entries), separators=(",", ":"))
    city = json.dumps(entries, ensure_ascii=False, separators=(",", ":"))
    meta = json.dumps({"name": name, "province": province, "pref": key}, ensure_ascii=False, separators=(",", ":"))

    if 'window.PANO_CITY["%s"]=' % key in source:
        start, end = _block_span(source, key)
        block = 'window.PANO_CITY["%s"]=%s;' % (key, city)
        source = source[:start] + block + source[end:]
        # Replace the sibling assignments that belong to this key.
        meta_start = source.index('window.PANO_META["%s"]=' % key)
        _, meta_end = json.JSONDecoder().raw_decode(source, meta_start + len('window.PANO_META["%s"]=' % key))
        source = source[:meta_start] + 'window.PANO_META["%s"]=%s' % (key, meta) + source[meta_end:]
        count_start = source.index('window.PANO_COUNT["%s"]=' % key)
        count_end = source.index(";", count_start)
        source = source[:count_start] + 'window.PANO_COUNT["%s"]=%d' % (key, counts) + source[count_end:]
        grid_start = source.index('window.PANO_GRID_ALL["%s"]=' % key)
        _, grid_end = json.JSONDecoder().raw_decode(source, grid_start + len('window.PANO_GRID_ALL["%s"]=' % key))
        source = source[:grid_start] + 'window.PANO_GRID_ALL["%s"]=%s' % (key, grid) + source[grid_end:]
    else:
        if not source.endswith("\n"):
            source += "\n"
        source += (
            'window.PANO_META["%s"]=%s;\n' % (key, meta)
            + 'window.PANO_COUNT["%s"]=%d;\n' % (key, counts)
            + 'window.PANO_GRID_ALL["%s"]=%s;\n' % (key, grid)
            + 'window.PANO_CITY["%s"]=%s;\n' % (key, city)
        )
    path.write_text(source, encoding="utf-8", newline="\n")


def upsert_metadata(viewer_root, updates):
    """updates: {key: {"name","province","pref","count"}} applied to data_meta.js."""
    path = Path(viewer_root) / "data_meta.js"
    source = path.read_text(encoding="utf-8")
    meta, meta_start, meta_end = read_assignment(source, "PANO_META")
    counts, counts_start, counts_end = read_assignment(source, "PANO_COUNT")
    for key, update in updates.items():
        meta[key] = {"name": update["name"], "province": update["province"], "pref": update.get("pref", key)}
        counts[key] = update["count"]
    updated = (source[:meta_start] + json.dumps(meta, ensure_ascii=False, separators=(",", ":"))
               + source[meta_end:counts_start] + json.dumps(counts, ensure_ascii=False, separators=(",", ":"))
               + source[counts_end:])
    path.write_text(updated, encoding="utf-8", newline="\n")
    return meta, counts
