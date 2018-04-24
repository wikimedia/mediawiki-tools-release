"""
Make sure settings.yaml is valid yaml
"""

import os
import yaml


def test_valid_syntax():
    """Actually check the yaml file"""
    fname = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'settings.yaml'
    )

    with open(fname) as conf:
        yaml.load(conf)
