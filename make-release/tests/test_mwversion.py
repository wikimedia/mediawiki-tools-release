"""
Some basic tests for mwversion

Copyright 2013, Antoine "hashar" Musso
Copyright 2013, Wikimedia Foundation Inc.
"""

import pytest

from mwrelease import MwVersion


class FakeVersion(MwVersion):
    """Dummy wrapper around MwVersion"""
    def __init__(self, attributes):
        self.raw = None
        self.major = None
        self.branch = None
        self.tag = None
        self.prev_version = None
        self.prev_tag = None

        self.phase = None
        self.cycle = None

        self.__dict__.update(attributes)


def assert_mw_versions_equal(expected, observed):
    """Compare two object properties"""
    assert expected.__dict__ == observed.__dict__


def test_new_snapshot():
    """Make sure a new snapshot release spits out expected version info"""
    version = MwVersion.new_snapshot()
    assert version.raw.startswith('snapshot-')
    assert version.branch == 'master'
    assert version.major == 'snapshot'


def test_major_version():
    """Make sure major versions are proper"""
    observed = MwVersion('1.30.0')
    expected = FakeVersion({
        'raw': '1.30.0',
        'major': '1.30',
        'branch': 'REL1_30',
        'tag': 'tags/1.30.0',
        })
    assert_mw_versions_equal(expected, observed)


def test_minor_version():
    """Minor versions too"""
    observed = MwVersion('1.30.1')
    expected = FakeVersion({
        'raw': '1.30.1',
        'major': '1.30',
        'branch': 'REL1_30',
        'tag': 'tags/1.30.1',
        'prev_tag': 'tags/1.30.0',
        'prev_version': '1.30.0',
        })
    assert_mw_versions_equal(expected, observed)


def test_release_candidate():
    """Don't forget about release candidates"""
    observed = MwVersion('1.30.0-rc.0')
    expected = FakeVersion({
        'raw': '1.30.0-rc.0',
        'major': '1.30',
        'branch': 'REL1_30',
        'tag': 'tags/1.30.0-rc.0',
        'phase': 'rc',
        'cycle': '0',
        })
    assert_mw_versions_equal(expected, observed)


def test_release_candidate_bumps():
    """Or a second release candidate...."""
    observed = MwVersion('1.30.0-rc.0')
    expected = FakeVersion({
        'raw': '1.30.0-rc.0',
        'major': '1.30',
        'branch': 'REL1_30',
        'tag': 'tags/1.30.0-rc.0',
        'phase': 'rc',
        'cycle': '0',
        })
    assert_mw_versions_equal(expected, observed)

    observed = MwVersion('1.30.0-rc.1')
    expected = FakeVersion({
        'raw': '1.30.0-rc.1',
        'major': '1.30',
        'branch': 'REL1_30',
        'tag': 'tags/1.30.0-rc.1',
        'prev_tag': 'tags/1.30.0-rc.0',
        'prev_version': '1.30.0-rc.0',
        'phase': 'rc',
        'cycle': '1',
        })
    assert_mw_versions_equal(expected, observed)


def test_incomplete_version():
    """Bogus versions are verboten"""
    for version in ['1.30', 'bad', None]:
        with pytest.raises(ValueError):
            MwVersion(version)


def test_tag():
    """Make sure tags are right"""
    data = {
        '1.21.3': 'tags/1.21.3',
        '1.24.0': 'tags/1.24.0'
    }
    for version, tag in data.items():
        assert tag == MwVersion(version).tag
