"""Remove reviewed navigable and invalid records from the active hidden collection."""
import argparse
import collections
import json
import logging
from pathlib import Path

from hidden_collection_rules import load_policy
from merge_gap_scan import read_collection, update_metadata, write_collection

LOGGER = logging.getLogger("hidden-collection-cleanup")
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def cleanup_report(entries, policy):
    kept = [entry for entry in entries if policy.should_keep_entry(entry)]
    removed = [entry for entry in entries if not policy.should_keep_entry(entry)]
    reasons = collections.Counter(policy.verifications.get(str(entry[0]), {}).get("status", "invalid") for entry in removed)
    return kept, {"before": len(entries), "total": len(kept), "removed": len(removed),
        "removed_by_status": dict(reasons), "removed_ids": [str(entry[0]) for entry in removed],
        "game_exceptions_preserved": sum(str(entry[0]) in policy.game_identifiers for entry in kept)}


def purge_collection(viewer_root, policy, should_write):
    entries = read_collection(viewer_root)
    kept, report = cleanup_report(entries, policy)
    LOGGER.info("cleanup before=%s kept=%s removed=%s", report["before"], report["total"], report["removed"])
    if should_write:
        write_collection(viewer_root, kept)
        update_metadata(viewer_root, len(kept))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--viewer-dir", type=Path, default=REPOSITORY_ROOT / "city-viewer")
    parser.add_argument("--verification", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    policy = load_policy(arguments.verification) if arguments.verification else load_policy()
    report = purge_collection(arguments.viewer_dir, policy, not arguments.dry_run)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
