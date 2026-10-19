"""Build city-viewer/hidden_pano.js from the merged Tencent hidden-pano list.

The viewer keeps generated city data in per-key files. Hidden panoramas are
kept in one dedicated key so they stay discoverable without being merged into
scanned city files.
"""
import json
import math
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = REPOSITORY_ROOT / "tools" / "data" / "tencent-hidden-merged-318.json"
OUTPUT_PATH = REPOSITORY_ROOT / "city-viewer" / "hidden_pano.js"
HIDDEN_KEY = "hidden"
GRID_RESOLUTION = 0.004


def format_captured(date_code: str) -> str:
    if len(date_code) == 6 and date_code.isdigit():
        return f"20{date_code[0:2]}-{date_code[2:4]}-{date_code[4:6]}"
    return ""


def format_direction(direction) -> object:
    try:
        return int(float(direction))
    except (TypeError, ValueError):
        return ""


def choose_road_name(record: dict) -> str:
    name = (record.get("name") or "").strip()
    if name:
        return name
    return "景区道路" if record.get("type") == "park" else ""


def build_entry(record: dict) -> list:
    panorama_id = str(record["id"])
    return [
        panorama_id,
        float(record["lng"]),
        float(record["lat"]),
        choose_road_name(record),
        format_captured(str(record.get("date_code") or "")),
        format_direction(record.get("direction")),
        0,
        0,
        "腾讯隐藏",
    ]


def build_grid_cells(records: list) -> list:
    cell_counts = {}
    for record in records:
        cell_x = math.floor(float(record["lng"]) / GRID_RESOLUTION)
        cell_y = math.floor(float(record["lat"]) / GRID_RESOLUTION)
        cell_key = (cell_x, cell_y)
        cell_counts[cell_key] = cell_counts.get(cell_key, 0) + 1
    return [[cell_x, cell_y, count] for (cell_x, cell_y), count in cell_counts.items()]


def write_payload(records: list) -> None:
    entries = [build_entry(record) for record in records]
    grid_cells = build_grid_cells(records)
    payload = (
        "window.PANO_META=window.PANO_META||{};"
        "window.PANO_COUNT=window.PANO_COUNT||{};"
        "window.PANO_GRID_ALL=window.PANO_GRID_ALL||{};"
        "window.PANO_CITY=window.PANO_CITY||{};"
        "window.PANO_META[%s]={name:'腾讯隐藏街景',province:'腾讯隐藏',pref:%s};"
        "window.PANO_COUNT[%s]=%d;"
        "window.PANO_GRID_ALL[%s]=%s;"
        "window.PANO_CITY[%s]=%s;"
        % (
            json.dumps(HIDDEN_KEY),
            json.dumps(HIDDEN_KEY),
            json.dumps(HIDDEN_KEY),
            len(entries),
            json.dumps(HIDDEN_KEY),
            json.dumps(grid_cells, ensure_ascii=False, separators=(",", ":")),
            json.dumps(HIDDEN_KEY),
            json.dumps(entries, ensure_ascii=False, separators=(",", ":")),
        )
    )
    OUTPUT_PATH.write_text(payload, encoding="utf-8")


def main() -> None:
    records = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    unique_records = {str(record["id"]): record for record in records}
    write_payload(list(unique_records.values()))
    print(f"hidden points: {len(unique_records)} -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
