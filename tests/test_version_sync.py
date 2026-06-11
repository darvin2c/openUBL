"""Tests for static version sync checker."""

from scripts.check_sdk_sync import check_all_versions_match


def test_all_versions_are_synchronized():
    mismatches = check_all_versions_match()
    assert mismatches == [], f"Version mismatches: {mismatches}"
