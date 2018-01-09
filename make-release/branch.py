#!/usr/bin/python3
# vim:sw=4:ts=4:et:
"""Stuff about making branches and so forth."""

import argparse
import logging
import os
import subprocess
import sys
import tempfile

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

        print('Branching {} to {} from {}'.format(repository, branch, revision))
        _get_client().put(
            '/projects/%s/branches/%s' % (
                repository.replace('/', '%2F'),
                branch.replace('/', '%2F')),
            data='{"revision":"%s"}' % revision
        )
    except HTTPError as httpe:
        # Gerrit responds 409 for edit conflicts
        # means we already have a branch
        if httpe.response.status_code == 409:
            print('Already branched!')
        else:
            raise


def get_bundle(bundle):
    """Return the list of all/some extensions, skins, and vendor."""
    if bundle == '*':
        things_to_branch = []
        for stuff in ['skins', 'extensions']:
            projects = _get_client().get('/projects/?p=mediawiki/%s' % stuff)
            for proj in projects:
                if projects[proj]['state'] == 'ACTIVE':
                    things_to_branch.append(proj)
        return things_to_branch
    else:
        try:
            return CONFIG['bundles'][bundle]
        except KeyError:
            return []


def do_core_work(branch, bundle, version):
    cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as temp:
        subprocess.check_call(['/usr/bin/git', 'clone', '-b', branch,
                              CONFIG['clone_base'] + '/core', temp])
        os.chdir(temp)
        for submodule in bundle:
            url = CONFIG['clone_base'] + '/' + submodule
            subprocess.check_call(['/usr/bin/git', 'submodule', 'add',
                                   '--force', '--branch', branch, url,
                                   submodule])
        # something with defaultsettings
        subprocess.check_call(['/usr/bin/git', 'commit', '-a', '-m',
                               'Creating new %s branch' % branch])
        subprocess.check_call(['/usr/bin/git', 'push', 'origin',
                               'HEAD:refs/for/%s' % branch])
    os.chdir(cwd)


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
    parser.add_argument(
        '--core-version',
        dest='core_version',
        help='If set, core will be given submodules with the bundle, plus this version number')

    return parser.parse_args()


if __name__ == '__main__':
    OPTIONS = parse_args()
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)

    if OPTIONS.bundle:
        for repo in get_bundle(OPTIONS.bundle):
            create_branch(repo, OPTIONS.branch, OPTIONS.branch_point)

    if OPTIONS.core:
        create_branch('core', OPTIONS.branch, OPTIONS.branch_point)
        if OPTIONS.core_version:
            do_core_work(OPTIONS.branch, OPTIONS.bundle, OPTIONS.core_version)
