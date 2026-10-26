"""Download DataV GeoAtlas prefecture boundaries into a local cache.

Usage:
    python tools/fetch_prefecture_boundaries.py --out <cache-dir>

The cache is not committed: boundaries are only needed when re-splitting hidden
collections by prefecture. Coordinates are GCJ-02, matching the panorama data.
"""
import argparse
import json
import subprocess
from pathlib import Path

BASE = "https://geo.datav.aliyun.com/areas_v3/bound/%s_full.json"
SKIP = {"710000", "810000", "820000"}


def fetch(url, target):
    subprocess.run(["curl", "-fsL", "--max-time", "90", "--noproxy", "*", url, "-o", str(target)], check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    country = args.out / "country.json"
    if not country.is_file():
        fetch(BASE % "100000", country)
    data = json.loads(country.read_text(encoding="utf-8"))
    codes = [str(f["properties"]["adcode"]) for f in data["features"]
             if f["properties"].get("level") == "province" and str(f["properties"]["adcode"]) not in SKIP]

    downloaded = []
    for code in codes:
        target = args.out / ("%s.json" % code)
        if target.is_file() and target.stat().st_size > 1000:
            continue
        try:
            fetch(BASE % code, target)
            downloaded.append(code)
        except subprocess.CalledProcessError:
            print(json.dumps({"warning": "download failed", "adcode": code}))
    print(json.dumps({"provinces": len(codes), "downloaded": downloaded, "cache": str(args.out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
