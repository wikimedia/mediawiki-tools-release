#!/usr/bin/env python3
# vim:sw=4:ts=4:et:
"""Branches and prepares a MediaWiki tarball release."""

import argparse
import sys

from mwrelease.branch import branch, gerrit_client


def get_wmf_branch(version):
    """Returns the latest mediawiki/core wmf/ branch for a given version."""

    response = gerrit_client().get('/projects/mediawiki%2Fcore/branches/')
    branches = [r['ref'][len('refs/heads/'):] for r in response
                if r['ref'].startswith('refs/heads/wmf/%s-wmf.' % version)]
    branches = sorted(branches, key=lambda b: b.split('.').pop())

    if len(branches) > 0:
        return branches.pop()
    else:
        return None


def get_rel_branch(version):
    (maj, min, _) = version.split('.')
    return 'REL%s_%s' % (maj, min)


def parse_args():
    """Parse command line arguments and return options."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument('version',
                        help='MediaWiki major/minor/patch version (e.g. 1.34.0)')

    args = parser.parse_args()

    if len(args.version.split('.')) != 3:
        print('version must include all major.minor.patch numbers')
        sys.exit(1)

    return args


if __name__ == '__main__':
    args = parse_args()

    rel_branch = get_rel_branch(args.version)
    wmf_branch = get_wmf_branch(args.version)

    if wmf_branch is None:
        print('failed to find a wmf/ branch for version %s' % args.version)
        sys.exit(2)

    # Branch WMF-deployed extensions/skins and vendor from latest wmf/* branch
    branch(branch=rel_branch,
           bundle='wmf',
           branch_point=wmf_branch)

    # Branch remaining extensions/skins from master
    branch(branch=rel_branch,
           bundle='*',
           branch_point='master')

    # Branch core from latest wmf/* branch and prepare core using the given
    # version and 'base' bundle.
    branch(branch=rel_branch,
           branch_point=wmf_branch,
           core=True,
           core_bundle='base',
           core_version=args.version)
