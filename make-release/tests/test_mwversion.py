#!/usr/bin/env python
#
# Copyright 2013, Antoine "hashar" Musso
# Copyright 2013, Wikimedia Foundation Inc.


import unittest
makerelease = __import__('make-release')


class FakeVersion(makerelease.MwVersion):

    def __init__(self, attributes):
        self.raw = None
        self.major = None
        self.branch = None
        self.prev_version = None
        self.prev_branch = None

        self.phase = None
        self.cycle = None

        self.__dict__.update(attributes)


class TestMwVersion(unittest.TestCase):

    # Helper
    def assertMwVersionEqual(self, expected, observed):
        """Compare two object properties"""
        return self.assertDictEqual(expected.__dict__, observed.__dict__)

    def test_master(self):
        observed = makerelease.MwVersion('master')
        expected = FakeVersion({'raw': 'master'})
        self.assertMwVersionEqual(expected, observed)

    def test_major_version(self):
        observed = makerelease.MwVersion('1.22.0')
        expected = FakeVersion({
            'raw': '1.22.0',
            'major': '1.22',
            'branch': 'tags/1.22.0',
            })
        self.assertMwVersionEqual(expected, observed)

    def test_minor_version(self):
        observed = makerelease.MwVersion('1.22.1')
        expected = FakeVersion({
            'raw': '1.22.1',
            'major': '1.22',
            'branch': 'tags/1.22.1',
            'prev_branch': 'tags/1.22.0',
            'prev_version': '1.22.0',
            })
        self.assertMwVersionEqual(expected, observed)

    def test_release_candidate(self):
        observed = makerelease.MwVersion('1.22.0rc0')
        expected = FakeVersion({
            'raw': '1.22.0rc0',
            'major': '1.22',
            'branch': 'tags/1.22.0rc0',
            'phase': 'rc',
            'cycle': '0',
            })
        self.assertMwVersionEqual(expected, observed)

    def test_release_candidate_bumps(self):
        observed = makerelease.MwVersion('1.22.0rc0')
        expected = FakeVersion({
            'raw': '1.22.0rc0',
            'major': '1.22',
            'branch': 'tags/1.22.0rc0',
            'phase': 'rc',
            'cycle': '0',
            })
        self.assertMwVersionEqual(expected, observed)

        observed = makerelease.MwVersion('1.22.0rc1')
        expected = FakeVersion({
            'raw': '1.22.0rc1',
            'major': '1.22',
            'branch': 'tags/1.22.0rc1',
            'prev_branch': 'tags/1.22.0rc0',
            'prev_version': '1.22.0rc0',
            'phase': 'rc',
            'cycle': '1',
            })
        self.assertMwVersionEqual(expected, observed)

    def test_incomplete_version(self):
        observed = makerelease.MwVersion('1.22')
        expected = FakeVersion({'raw': '1.22'})
        self.assertMwVersionEqual(expected, observed)
