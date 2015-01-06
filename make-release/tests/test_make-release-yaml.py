#!/usr/bin/env python

import os
import unittest
import yaml


class MakeReleaseYamlTest(unittest.TestCase):
    fname = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'make-release.yaml'
    )

    def test_valid_syntax(self):
        with open(self.fname) as f:
            yaml.load(f)

        # No exception raised
        self.assertTrue(True)
