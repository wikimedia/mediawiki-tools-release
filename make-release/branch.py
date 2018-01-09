#!/usr/bin/env python3
# vim:sw=4:ts=4:et:
"""Stuff about making branches and so forth."""

import argparse
import logging
import sys

from requests.auth import HTTPDigestAuth
from requests.exceptions import HTTPError

import yaml

from pygerrit.rest import GerritRestAPI

with open("make-release.yaml") as conf:
    CONFIG = yaml.safe_load(conf)


def _get_client():
    """Get the client for making requests."""
    return GerritRestAPI(
        url=CONFIG['base_url'],
        auth=HTTPDigestAuth(CONFIG['username'], CONFIG['password']))


def create_branch(repository, branch, revision):
    """Create a branch for a given repo."""
    try:
        try:
            revision = CONFIG['manual_branch_points'][branch][repository]
        except KeyError:
            pass

        _get_client().put(
            '/projects/%s/branches/%s' % (
                repository.replace('/', '%2F'),
                branch.replace('/', '%2F')),
            data='{"revision":"%s"}' % revision
        )
    except HTTPError as httpe:
        # Gerrit responds 409 for edit conflicts
        # means we already have a branch
        if httpe.response.status_code != 409:
            raise


def branch_everything(branch, branch_point, bundle=None):
    """Branch stuff."""
    if bundle == '*':
        repos_to_branch = get_star_bundle()

    for repo in repos_to_branch:
        print('Branching %s to %s from %s' % (
            repo, branch, branch_point))
        create_branch(repo, branch, branch_point)


def get_star_bundle():
    """Return the list of all extensions, skins, and vendor."""
    things_to_branch = []
    for stuff in ['skins', 'extensions']:
        projects = _get_client().get('/projects/?p=mediawiki/%s' % stuff)
        for proj in projects:
            if projects[proj]['state'] == 'ACTIVE':
                things_to_branch.append(proj)
    return things_to_branch


def parse_args():
    """Parse command line arguments and return options."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Positional arguments:
    parser.add_argument('branch', nargs='?', help='Branch we want to make')
    parser.add_argument('--branchpoint', dest='branch_point', default='HEAD',
                        help='Where to branch from')
    parser.add_argument('--core', dest='core', action='store_true',
                        help='If we branch core or not')
    parser.add_argument('--bundle', dest='bundle', default=None,
                        help='What bundle of extensions & skins to branch')

    return parser.parse_args()


if __name__ == '__main__':
    OPTIONS = parse_args()
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)

    if OPTIONS.core:
        create_branch('core', OPTIONS.branch, OPTIONS.branch_point)
    if OPTIONS.bundle:
        branch_everything(OPTIONS.branch, OPTIONS.branch_point, OPTIONS.bundle)
