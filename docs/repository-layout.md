# Repository Layout

The repository has four layers. Keeping them separate makes it easier to find a published artifact, reproduce a scan, or update a single route without touching unrelated data.

## Published Site

- `index.html`: S341 route workbench and the GitHub Pages root entry.
- `city-viewer/`: national city metadata viewer and its browser-loadable data files.
- `g101/`, `g102/`, `g103/`, `g106/`, `g312/`: route-specific viewers and metadata.
- `g212-panorama-workbench.html`: G212 route workbench.
- `lishui-panorama/`: Lishui regional workbench.
- `s341/`: S341 supporting viewer assets.

Public paths under these directories are intentionally stable. Do not rename them without adding a compatibility page or redirect.

## Research Data

- `g*-*.json`, `g*-*.geojson`: route samples and route geometry.
- `lishui-*.json`, `s341-*.json`: route-level metadata.
- `mohe/`, `erguna/`, `gaochun/`, `huma/`, `jgdaq/`, `tahe/`, `xinlin/`: regional scan manifests and boundaries.

Published manifests contain metadata only. Raw BFS state, downloaded images, tiles, and logs belong in local scan storage and are ignored by Git.

## Tools

- `tools/city-scan/`: legacy Python pipeline for regional scans and manifest generation.
- `tools/g212-scan.mjs`: G212 route sampler and metadata collector.

The tool scripts currently use local input/output paths for historical reproducibility. New scripts should accept paths through command-line arguments or environment variables and must never contain credentials.

## Documentation

- `README.md`: user-facing project overview and published entry points.
- `docs/repository-layout.md`: this structure guide.
- `docs/operations.md`: local development, scan output, and Git synchronization workflow.

## Generated Data Policy

Keep small, stable metadata required by the published site in Git. Keep raw state, logs, downloaded media, temporary files, and local exports outside Git. If a generated artifact is required by a page, document its source and regeneration command before adding it.
