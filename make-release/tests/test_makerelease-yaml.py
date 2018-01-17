import os
import yaml


def test_valid_syntax():
    fname = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'settings.yaml'
    )

    with open(fname) as conf:
        yaml.load(conf)
