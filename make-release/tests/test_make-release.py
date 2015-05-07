#!/usr/bin/env python2

import unittest

makerelease = __import__('make-release')


class Struct:
    def __init__(self, **entries):
        self.__dict__.update(entries)


class MakeReleaseTest(unittest.TestCase):
    def getMakeRelease(self, options):
        if 'conffile' not in options:
            options['conffile'] = '../make-release.yaml'
        return makerelease.MakeRelease(Struct(**options))

    def test_get_extensions_for_version(self):
        mr = self.getMakeRelease({'version': '1.25.0'})
        # Added in 1.25
        self.assertIn('extensions/CiteThisPage', mr.get_extensions_for_version(mr.version))

        mr = self.getMakeRelease({'version': '1.23.0'})
        # Removed in 1.23
        self.assertNotIn('extensions/SimpleAntiSpam', mr.get_extensions_for_version(mr.version))
        # But if explicitly specified, still included
        self.assertIn('extensions/SimpleAntiSpam', mr.get_extensions_for_version(
            mr.version,
            ['extensions/SimpleAntiSpam'])
        )
