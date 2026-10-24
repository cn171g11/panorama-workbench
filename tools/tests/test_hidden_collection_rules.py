"""Regression coverage for navigation evidence, zero coordinates, and game exceptions."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hidden_collection_rules import HiddenCollectionPolicy, NAVIGATION_RULE_VERSION
from merge_gap_scan import merge_results, read_collection, write_collection

CURRENT_ID = "10101012120819135641300"
OTHER_ID = "10101012120901123026900"
GAME_ID = "270130K51407070SCENE002"
LONGITUDE = 118.8
LATITUDE = 32.0
VERIFIED_HIDDEN = {"sid": CURRENT_ID, "ruleVersion": NAVIGATION_RULE_VERSION,
    "status": "hidden", "isValid": True, "canMove": False, "movementCount": 0}
VERIFIED_REGULAR = {"sid": OTHER_ID, "ruleVersion": NAVIGATION_RULE_VERSION,
    "status": "regular", "isValid": True, "canMove": True, "movementCount": 1}


def make_record(identifier, **changes):
    return {"sid": identifier, "lng": LONGITUDE, "lat": LATITUDE, "isHidden": True,
        "sourceType": "confirmed-hidden", **changes}


def make_entry(identifier, longitude=LONGITUDE, latitude=LATITUDE):
    return [identifier, longitude, latitude, "", "", "", 0, 0, "腾讯隐藏"]


class HiddenCollectionRulesTests(unittest.TestCase):
    def setUp(self):
        self.policy = HiddenCollectionPolicy({CURRENT_ID: VERIFIED_HIDDEN, OTHER_ID: VERIFIED_REGULAR}, {GAME_ID})

    def test_rejects_movable_record_despite_hidden_flags(self):
        self.assertFalse(self.policy.can_import_record(make_record(OTHER_ID)))
        self.assertFalse(self.policy.should_keep_entry(make_entry(OTHER_ID)))

    def test_accepts_reviewed_immobile_frame_despite_legacy_normal_label(self):
        self.assertTrue(self.policy.can_import_record(make_record(CURRENT_ID, sourceType="normal-in-gap")))

    def test_rejects_unverified_hidden_flag_and_zero_coordinates(self):
        unknown_policy = HiddenCollectionPolicy({}, set())
        self.assertFalse(unknown_policy.can_import_record(make_record(CURRENT_ID)))
        self.assertFalse(self.policy.can_import_record(make_record(CURRENT_ID, lng=0, lat=0)))
        self.assertFalse(self.policy.should_keep_entry(make_entry(CURRENT_ID, 0, 0)))

    def test_preserves_known_game_when_its_review_is_navigable(self):
        policy = HiddenCollectionPolicy({GAME_ID: {"status": "regular"}}, {GAME_ID})
        self.assertTrue(policy.should_keep_entry(make_entry(GAME_ID)))
        self.assertTrue(policy.can_import_record(make_record(GAME_ID)))

    def test_accepts_fresh_inline_navigation_proof(self):
        policy = HiddenCollectionPolicy({}, set())
        record = make_record(CURRENT_ID, isMobilityVerified=True, verificationRule=NAVIGATION_RULE_VERSION,
            isValid=True, canMove=False, movementCount=0)
        self.assertTrue(policy.can_import_record(record))
        self.assertFalse(policy.can_import_record({**record, "movementCount": 1}))

    def test_merge_cannot_reintroduce_removed_or_unrecognized_points(self):
        with tempfile.TemporaryDirectory() as directory:
            viewer_root = Path(directory)
            write_collection(viewer_root, [make_entry(CURRENT_ID), make_entry(OTHER_ID), make_entry(GAME_ID)])
            metadata = 'window.PANO_META={"hidden":{}};window.PANO_COUNT={"hidden":3};'
            (viewer_root / "data_meta.js").write_text(metadata, encoding="utf-8")
            records = [make_record(CURRENT_ID), make_record(OTHER_ID), make_record(GAME_ID),
                make_record("10101050141207140000000", lng=0, lat=0)]
            first_report = merge_results(viewer_root, records, self.policy)
            second_report = merge_results(viewer_root, records, self.policy)
            self.assertEqual({entry[0] for entry in read_collection(viewer_root)}, {CURRENT_ID, GAME_ID})
            self.assertEqual(first_report["accepted_ids"], [CURRENT_ID, GAME_ID])
            self.assertEqual(second_report["total"], first_report["total"])


if __name__ == "__main__":
    unittest.main()
