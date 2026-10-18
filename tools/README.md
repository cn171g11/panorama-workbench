# Tools

## `city-scan/`

Legacy Python pipeline for regional Tencent Street View metadata collection.

- `bfs.py`: resumable boundary-filtered BFS collection.
- `thumbs.py`: thumbnail download.
- `panorama_batch.py`: level-0 tile download and panorama assembly.
- `assemble.py`: manifest and panoid list generation.
- `build_viewer_data.py`: conversion to viewer data scripts.

The scripts were written for completed historical scans. They keep historical defaults for compatibility, but support local path overrides:

```powershell
$env:PANO_SCAN_BASE = 'D:\pano\mohe'
$env:PANO_SCAN_ROOT = 'D:\pano'
$env:PANO_VIEWER_DIR = 'D:\pano\viewer'
```

Before using them for a new area, verify the request throttle for the current service behavior.

## `g212-scan.mjs`

Samples G212 from OSM route geometry and Tencent metadata endpoints.

```powershell
node tools/g212-scan.mjs <key-file> [output-json] [spacing-meters] [radius-meters]
node tools/g212-scan.mjs <key-file> --route-only
```

The key file is read locally. The script logs only a short fingerprint and never prints the key value. Keep key files outside the repository.

## General Rules

1. Treat downloaded media, raw state, logs, and partial output as local artifacts.
2. Keep public metadata schemas stable because the viewers consume them directly.
3. Validate generated JSON before copying it into a published viewer directory.
4. Keep credentials in local configuration or environment variables.
