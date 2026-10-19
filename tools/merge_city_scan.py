"""Merge one scanned city directory into city-viewer data files.

The scan output is a flat list of records. City data is split into parts so
that one script file stays below the browser and GitHub file-size comfort
limit. Metadata and counts are updated in data_meta.js.
"""
import argparse
import json
import math
import re
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
VIEWER_ROOT = REPOSITORY_ROOT / "city-viewer"
DEFAULT_PART_SIZE = 180000
JS_HEADER = "window.PANO_CITY=window.PANO_CITY||{};"


def read_assignment(source: str, variable_name: str):
    marker = f"window.{variable_name}="
    start = source.index(marker) + len(marker)
    value, end = json.JSONDecoder().raw_decode(source[start:])
    return value, start, start + end


def read_existing_entries(key: str) -> list:
    entries = []
    pattern = re.compile(r"^data_%s(?:_\d+)?\.js$" % re.escape(key))
    for path in sorted(VIEWER_ROOT.glob("data_*.js")):
        if not pattern.match(path.name):
            continue
        source = path.read_text(encoding="utf-8")
        match = re.search(r"PANO_CITY\[(.+?)\]=(\[.*\]);\s*$", source, re.S)
        if match:
            entries.extend(json.loads(match.group(2)))
    return entries


def read_scan_records(raw_path: Path) -> list:
    if raw_path.name == "_state.json" or raw_path.name.endswith("_state.json"):
        return json.loads(raw_path.read_text(encoding="utf-8")).get("recs", [])
    return json.loads(raw_path.read_text(encoding="utf-8"))


def build_entry(record: dict) -> list:
    panorama_id = str(record.get("svid") or record.get("panoid") or "")
    longitude = record.get("lng")
    latitude = record.get("lat")
    if not panorama_id or longitude is None or latitude is None:
        return []
    return [
        panorama_id,
        float(longitude),
        float(latitude),
        record.get("addr") or record.get("road") or "",
        "",
        str(record.get("dir") or ""),
        0,
        0,
        record.get("source") or "nj_scan",
    ]


def merge_entries(existing: list, scanned: list) -> tuple[list, int]:
    entries_by_id = {str(entry[0]): entry for entry in existing}
    added_count = 0
    for record in scanned:
        entry = build_entry(record)
        if not entry or entry[0] in entries_by_id:
            continue
        entries_by_id[entry[0]] = entry
        added_count += 1
    merged = sorted(entries_by_id.values(), key=lambda entry: str(entry[0]))
    return merged, added_count


def write_parts(key: str, entries: list, part_size: int) -> list[tuple[str, int]]:
    old_parts = VIEWER_ROOT.glob("data_%s.js" % key)
    old_parts = list(old_parts) + list(VIEWER_ROOT.glob("data_%s_*.js" % key))
    for path in old_parts:
        path.unlink()
    part_count = math.ceil(len(entries) / part_size) if entries else 1
    written = []
    for index in range(part_count):
        part_key = key if index == 0 else f"{key}_{index + 1}"
        part_entries = entries[index * part_size:(index + 1) * part_size]
        payload = (
            JS_HEADER
            + "window.PANO_CITY[%s]=%s;"
            % (
                json.dumps(part_key),
                json.dumps(part_entries, ensure_ascii=False, separators=(",", ":")),
            )
        )
        (VIEWER_ROOT / f"data_{part_key}.js").write_text(payload, encoding="utf-8")
        written.append((part_key, len(part_entries)))
    return written


def update_metadata(key: str, name: str, province: str, parts: list[tuple[str, int]]) -> None:
    path = VIEWER_ROOT / "data_meta.js"
    source = path.read_text(encoding="utf-8")
    meta, meta_start, meta_end = read_assignment(source, "PANO_META")
    counts, counts_start, counts_end = read_assignment(source, "PANO_COUNT")
    part_pattern = re.compile(r"^%s(?:_\d+)?$" % re.escape(key))
    for stale_key in [item for item in meta if part_pattern.match(item)]:
        meta.pop(stale_key)
        counts.pop(stale_key, None)
    for part_index, (part_key, part_count) in enumerate(parts):
        meta[part_key] = (
            {"name": name, "province": province}
            if part_index == 0
            else {"name": name, "province": province, "pref": key}
        )
        if part_index == 0:
            meta[part_key]["pref"] = key
        counts[part_key] = part_count
    meta_serialized = json.dumps(meta, ensure_ascii=False, separators=(",", ":"))
    counts_serialized = json.dumps(counts, ensure_ascii=False, separators=(",", ":"))
    updated = (
        source[:meta_start]
        + meta_serialized
        + source[meta_end:counts_start]
        + counts_serialized
        + source[counts_end:]
    )
    path.write_text(updated, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--province", required=True)
    parser.add_argument("--part-size", type=int, default=DEFAULT_PART_SIZE)
    arguments = parser.parse_args()

    existing = read_existing_entries(arguments.key)
    scanned = read_scan_records(Path(arguments.raw))
    merged, added_count = merge_entries(existing, scanned)
    parts = write_parts(arguments.key, merged, arguments.part_size)
    update_metadata(arguments.key, arguments.name, arguments.province, parts)
    print(
        "key=%s scanned=%d existing=%d added=%d total=%d parts=%s"
        % (
            arguments.key,
            len(scanned),
            len(existing),
            added_count,
            len(merged),
            ", ".join("%s:%d" % item for item in parts),
        )
    )


if __name__ == "__main__":
    main()
