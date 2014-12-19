#!/usr/bin/env python

import unittest
makerelease = __import__('make-release')


class MakeReleaseTest(unittest.TestCase):
    def test_get_tag_from_version(self):
        data = {
            '1.21.3': 'tags/1.21.3',
            '1.24.0': 'tags/1.24.0'
        }
        for version, tag in data.items():
            self.assertEqual(tag, makerelease.get_tag_from_version(version))
