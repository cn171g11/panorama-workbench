"""Merge independently verified, immobile gap-scan panoramas into the viewer."""
import argparse
import collections
import datetime
import json
import logging
import math
import re
import shutil
from pathlib import Path

from merge_city_scan import read_assignment
from hidden_collection_rules import has_valid_coordinates, load_policy

LOGGER = logging.getLogger("merge-gap-scan")
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
COLLECTION_KEY = "hidden"
COLLECTION_NAME = "腾讯隐藏街景/时光机"
COLLECTION_MARKER = "腾讯隐藏"
GRID_RESOLUTION = 0.004
ENTRY_LENGTH = 9
TENCENT_IDENTIFIER = re.compile(r"[A-Za-z0-9]{20,32}")
CITY_PAYLOAD = re.compile(r'window\.PANO_CITY\["hidden"\]=(\[.*\]);\s*$', re.DOTALL)


def read_collection(viewer_root):
    source = (viewer_root / "hidden_pano.js").read_text(encoding="utf-8")
    match = CITY_PAYLOAD.search(source)
    if not match:
        raise ValueError("The current hidden collection payload is missing")
    return json.loads(match.group(1))


def captured_from_id(identifier):
    if len(identifier) != 23 or not identifier.isdigit():
        return ""
    try:
        captured = datetime.datetime.strptime(identifier[8:20], "%y%m%d%H%M%S")
    except ValueError:
        return ""
    return captured.strftime("%Y-%m-%d %H:%M")


def is_mappable(record):
    if record.get("locationUnavailable"):
        return False
    return has_valid_coordinates(record.get("lng"), record.get("lat"))


def build_entry(record, previous=None):
    identifier = str(record.get("sid") or record.get("svid") or record.get("panoid") or "")
    if not TENCENT_IDENTIFIER.fullmatch(identifier):
        raise ValueError(f"Invalid gap-scan identifier: {identifier}")
    entry = [identifier, record["lng"], record["lat"], record.get("roadName") or record.get("addr") or "",
        captured_from_id(identifier), str(record.get("dir") or ""), 0, 0, COLLECTION_MARKER]
    if previous:
        for column in (3, 4, 5):
            entry[column] = entry[column] or previous[column]
        entry[6:8] = previous[6:8]
    return entry


def build_grid(entries):
    cell_counts = collections.Counter(
        (math.floor(entry[1] / GRID_RESOLUTION), math.floor(entry[2] / GRID_RESOLUTION)) for entry in entries
    )
    return [[longitude_cell, latitude_cell, count] for (longitude_cell, latitude_cell), count in cell_counts.items()]


def collection_metadata():
    return {"name": COLLECTION_NAME, "province": COLLECTION_NAME, "pref": COLLECTION_KEY}


def write_collection(viewer_root, entries):
    metadata = json.dumps(collection_metadata(), ensure_ascii=False, separators=(",", ":"))
    grid = json.dumps(build_grid(entries), separators=(",", ":"))
    payload = (
        "window.PANO_META=window.PANO_META||{};window.PANO_COUNT=window.PANO_COUNT||{};"
        "window.PANO_GRID_ALL=window.PANO_GRID_ALL||{};window.PANO_CITY=window.PANO_CITY||{};"
        f'window.PANO_META["hidden"]={metadata};window.PANO_COUNT["hidden"]={len(entries)};'
        f'window.PANO_GRID_ALL["hidden"]={grid};'
        f'window.PANO_CITY["hidden"]={json.dumps(entries, ensure_ascii=False, separators=(",", ":"))};'
    )
    (viewer_root / "hidden_pano.js").write_text(payload, encoding="utf-8")


def update_metadata(viewer_root, count):
    metadata_path = viewer_root / "data_meta.js"
    source = metadata_path.read_text(encoding="utf-8")
    metadata, metadata_start, metadata_end = read_assignment(source, "PANO_META")
    counts, counts_start, counts_end = read_assignment(source, "PANO_COUNT")
    metadata[COLLECTION_KEY] = collection_metadata()
    counts[COLLECTION_KEY] = count
    updated = source[:metadata_start] + json.dumps(metadata, ensure_ascii=False, separators=(",", ":"))
    updated += source[metadata_end:counts_start] + json.dumps(counts, ensure_ascii=False, separators=(",", ":"))
    updated += source[counts_end:]
    metadata_path.write_text(updated, encoding="utf-8")


def merge_results(viewer_root, records, policy=None):
    policy = policy or load_policy()
    existing = read_collection(viewer_root)
    entries_by_id = {str(entry[0]): entry for entry in existing if policy.should_keep_entry(entry)}
    retained_existing_count = len(entries_by_id)
    mappable_ids = set()
    overlap_ids = set()
    for record in records:
        if not is_mappable(record) or not policy.can_import_record(record):
            continue
        identifier = str(record.get("sid") or record.get("svid") or record.get("panoid") or "")
        previous = entries_by_id.get(identifier)
        if previous:
            overlap_ids.add(identifier)
        entries_by_id[identifier] = build_entry(record, previous)
        mappable_ids.add(identifier)
    merged = sorted(entries_by_id.values(), key=lambda entry: str(entry[0]))
    assert all(len(entry) == ENTRY_LENGTH for entry in merged)
    assert {str(entry[0]) for entry in existing if policy.should_keep_entry(entry)}.issubset(entries_by_id)
    write_collection(viewer_root, merged)
    update_metadata(viewer_root, len(merged))
    return {"existing": len(existing), "result_records": len(records), "mappable": len(mappable_ids),
        "overlap": len(overlap_ids), "added": len(merged) - retained_existing_count, "total": len(merged),
        "removed_existing": len(existing) - retained_existing_count,
        "location_unavailable": sum(not is_mappable(record) for record in records),
        "source_types": dict(collections.Counter(record.get("sourceType", "") for record in records)),
        "accepted_ids": sorted(mappable_ids),
        "excluded_unverified_or_navigable": sum(is_mappable(record) and not policy.can_import_record(record) for record in records)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--viewer-dir", type=Path, default=REPOSITORY_ROOT / "city-viewer")
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--verification", type=Path)
    arguments = parser.parse_args()
    payload = json.loads(arguments.raw.read_text(encoding="utf-8"))
    records = payload if isinstance(payload, list) else payload["points"]
    if arguments.archive:
        if not arguments.archive.parent.is_dir():
            raise ValueError("Archive parent directory does not exist")
        shutil.copy2(arguments.raw, arguments.archive)
    policy = load_policy(arguments.verification) if arguments.verification else load_policy()
    report = merge_results(arguments.viewer_dir, records, policy)
    if report["excluded_unverified_or_navigable"] and not arguments.verification:
        LOGGER.warning("%s records were skipped because no navigation verification was supplied; "
            "pass --verification with a mobility audit before publishing this import",
            report["excluded_unverified_or_navigable"])
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
