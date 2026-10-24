"""Apply reviewed navigation evidence when maintaining the hidden collection."""
import json
import math
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
VERIFICATION_PATH = REPOSITORY_ROOT / "tools" / "data" / "hidden-collection-verification.json"
GAME_EXCEPTION_PATH = REPOSITORY_ROOT / "tools" / "data" / "tencent-game-exceptions.json"
NAVIGATION_RULE_VERSION = "navigation-v1"
LONGITUDE_LIMIT = 180
LATITUDE_LIMIT = 90
LONGITUDE_COLUMN = 1
LATITUDE_COLUMN = 2
REMOVED_STATUSES = frozenset({"regular", "invalid"})


def has_valid_coordinates(longitude, latitude):
    coordinates = (longitude, latitude)
    if not all(isinstance(coordinate, (int, float)) and not isinstance(coordinate, bool)
            and math.isfinite(coordinate) for coordinate in coordinates):
        return False
    return abs(longitude) <= LONGITUDE_LIMIT and abs(latitude) <= LATITUDE_LIMIT and coordinates != (0, 0)


def record_identifier(record):
    return str(record.get("sid") or record.get("svid") or record.get("panoid") or record.get("id") or "")


def has_verified_immobility(verification):
    return (verification.get("ruleVersion") == NAVIGATION_RULE_VERSION
        and verification.get("status") == "hidden"
        and verification.get("isValid") is True
        and verification.get("canMove") is False
        and type(verification.get("movementCount")) is int
        and verification["movementCount"] == 0)


def has_inline_immobility(record):
    return (record.get("isMobilityVerified") is True
        and record.get("verificationRule") == NAVIGATION_RULE_VERSION
        and record.get("isValid") is True
        and record.get("canMove") is False
        and type(record.get("movementCount")) is int
        and record["movementCount"] == 0)


class HiddenCollectionPolicy:
    def __init__(self, verifications, game_identifiers):
        self.verifications = verifications
        self.game_identifiers = frozenset(game_identifiers)

    def should_keep_entry(self, entry):
        identifier = str(entry[0])
        if identifier in self.game_identifiers:
            return True
        if not has_valid_coordinates(entry[LONGITUDE_COLUMN], entry[LATITUDE_COLUMN]):
            return False
        return self.verifications.get(identifier, {}).get("status") not in REMOVED_STATUSES

    def can_import_record(self, record):
        identifier = record_identifier(record)
        if not identifier or record.get("locationUnavailable"):
            return False
        if not has_valid_coordinates(record.get("lng"), record.get("lat")):
            return False
        if identifier in self.game_identifiers:
            return True
        verification = self.verifications.get(identifier)
        if verification is not None:
            return verification.get("sid") == identifier and has_verified_immobility(verification)
        return has_inline_immobility(record)


def load_policy(verification_path=VERIFICATION_PATH, game_path=GAME_EXCEPTION_PATH):
    reviewed = json.loads(Path(verification_path).read_text(encoding="utf-8"))
    exceptions = json.loads(Path(game_path).read_text(encoding="utf-8"))
    return HiddenCollectionPolicy(reviewed["records"], exceptions["panoramaIds"])
