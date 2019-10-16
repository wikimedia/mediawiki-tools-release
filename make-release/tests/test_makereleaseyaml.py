"""
Make sure settings.yaml is valid yaml
"""

import os
import yaml

from mwrelease.branch import get_bundle


def test_valid_syntax():
    """Actually check the yaml file"""
    fname = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'settings.yaml'
    )

    with open(fname) as conf:
        yaml.safe_load(conf)


def test_get_bundle():

    # test the global config for sanity
    base = get_bundle('base')
    assert(len(base))

    # test with a custom config to validate that include: foo works:
    conf = {
        "bundles": {
            "foo": [
                "test1"
            ],
            "bar": [
                "test2", {
                     "include": "foo"
                }
            ]
        }
    }
    foo = get_bundle("foo", conf)
    bar = get_bundle("bar", conf)
    assert(len(bar) == len(foo) + 1)
    assert("test1" in foo)
    assert("test1" in bar)
    assert("test2" in bar)
    assert(len(foo) == 1)
