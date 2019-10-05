#!/usr/bin/env python3
# vim:sw=4:ts=4:et:
"""Stuff about making branches and so forth."""

import argparse
import logging
import sys

from mwrelease.branch import branch


def parse_args():
    """Parse command line arguments and return options."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Positional arguments:
    parser.add_argument('branch', help='Branch we want to make')
    parser.add_argument('--branchpoint', dest='branch_point', default='master',
                        help='Where to branch from')
    parser.add_argument('--bundle', dest='bundle', default=None,
                        help='Which bundle of extensions & skins to branch')
    parser.add_argument('--core', dest='core', action='store_true',
                        help='If we branch core or not')
    parser.add_argument('--core-bundle', dest='core_bundle', default='base',
                        help='Which bundle to use for core submodules')
    parser.add_argument('--core-version', dest='core_version',
                        help='Update core version number and adds submodules')
    parser.add_argument('--no-review', dest='no_review', action='store_true',
                        help='Skip code review and push the branch.')

    return parser.parse_args()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    args = vars(parse_args())
    branch(**args)
