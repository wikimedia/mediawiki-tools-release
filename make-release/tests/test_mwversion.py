#!/usr/bin/env python
#
# Copyright 2013, Antoine "hashar" Musso
# Copyright 2013, Wikimedia Foundation Inc.


import unittest

makerelease = __import__('makerelease')


class FakeVersion(makerelease.MwVersion):

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


class TestMwVersion(unittest.TestCase):

    # Helper
    def assertMwVersionEqual(self, expected, observed):
        """Compare two object properties"""
        return self.assertDictEqual(expected.__dict__, observed.__dict__)

    def test_new_snapshot(self):
        version = makerelease.MwVersion.new_snapshot()
        self.assertTrue(version.raw.startswith('snapshot-'))
        self.assertEqual(version.branch, 'master')
        self.assertEqual(version.major, 'snapshot')

    def test_major_version(self):
        observed = makerelease.MwVersion('1.22.0')
        expected = FakeVersion({
            'raw': '1.22.0',
            'major': '1.22',
            'branch': 'REL1_22',
            'tag': 'tags/1.22.0',
            })
        self.assertMwVersionEqual(expected, observed)

    def test_minor_version(self):
        observed = makerelease.MwVersion('1.22.1')
        expected = FakeVersion({
            'raw': '1.22.1',
            'major': '1.22',
            'branch': 'REL1_22',
            'tag': 'tags/1.22.1',
            'prev_tag': 'tags/1.22.0',
            'prev_version': '1.22.0',
            })
        self.assertMwVersionEqual(expected, observed)

    def test_release_candidate(self):
        observed = makerelease.MwVersion('1.22.0rc0')
        expected = FakeVersion({
            'raw': '1.22.0rc0',
            'major': '1.22',
            'branch': 'REL1_22',
            'tag': 'tags/1.22.0rc0',
            'phase': 'rc',
            'cycle': '0',
            })
        self.assertMwVersionEqual(expected, observed)

    def test_release_candidate_bumps(self):
        observed = makerelease.MwVersion('1.22.0rc0')
        expected = FakeVersion({
            'raw': '1.22.0rc0',
            'major': '1.22',
            'branch': 'REL1_22',
            'tag': 'tags/1.22.0rc0',
            'phase': 'rc',
            'cycle': '0',
            })
        self.assertMwVersionEqual(expected, observed)

        observed = makerelease.MwVersion('1.22.0rc1')
        expected = FakeVersion({
            'raw': '1.22.0rc1',
            'major': '1.22',
            'branch': 'REL1_22',
            'tag': 'tags/1.22.0rc1',
            'prev_tag': 'tags/1.22.0rc0',
            'prev_version': '1.22.0rc0',
            'phase': 'rc',
            'cycle': '1',
            })
        self.assertMwVersionEqual(expected, observed)

    def test_incomplete_version(self):
        for version in ['1.22', 'bad', None]:
            self.assertRaises(ValueError, makerelease.MwVersion, version)

    def test_special_case_1(self):
        observed = makerelease.MwVersion('1.23.0rc0')
        expected = FakeVersion({
            'raw': '1.23.0rc0',
            'major': '1.23',
            'branch': 'REL1_23',
            'tag': 'tags/1.23.0rc0',
            'phase': 'rc',
            'cycle': '0',
            })
        self.assertMwVersionEqual(expected, observed)

    def test_special_case_2(self):
        observed = makerelease.MwVersion('1.23.0-rc.1')
        expected = FakeVersion({
            'raw': '1.23.0-rc.1',
            'major': '1.23',
            'branch': 'REL1_23',
            'tag': 'tags/1.23.0-rc.1',
            'prev_tag': 'tags/1.23.0rc0',
            'prev_version': '1.23.0rc0',
            'phase': 'rc',
            'cycle': '1',
            })
        self.assertMwVersionEqual(expected, observed)

    def test_special_case_3(self):
        observed = makerelease.MwVersion('1.23.0-rc.2')
        expected = FakeVersion({
            'raw': '1.23.0-rc.2',
            'major': '1.23',
            'branch': 'REL1_23',
            'tag': 'tags/1.23.0-rc.2',
            'prev_tag': 'tags/1.23.0-rc.1',
            'prev_version': '1.23.0-rc.1',
            'phase': 'rc',
            'cycle': '2',
            })
        self.assertMwVersionEqual(expected, observed)

    def test_tag(self):
        data = {
            '1.21.3': 'tags/1.21.3',
            '1.24.0': 'tags/1.24.0'
        }
        for version, tag in data.items():
            self.assertEqual(tag, makerelease.MwVersion(version).tag)
