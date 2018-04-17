#!/usr/bin/env python3
# vim:sw=4:ts=4:et:
"""Stuff about making branches and so forth."""

import argparse
from contextlib import contextmanager
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile

from requests.auth import HTTPBasicAuth
from requests.exceptions import HTTPError

import yaml

from pygerrit2.rest import GerritRestAPI
from pygerrit2.rest.auth import HTTPBasicAuthFromNetrc

# Setup config with local overrides
with open('settings.yaml') as globalconf:
    CONFIG = yaml.safe_load(globalconf)
if os.path.exists('.settings.yaml'):
    with open(".settings.yaml") as localconf:
        LOCAL_CONFIG = yaml.safe_load(localconf)
        if LOCAL_CONFIG:
            CONFIG.update(LOCAL_CONFIG)


def _get_client():
    """Get the client for making requests."""
    try:
        auth = HTTPBasicAuth(CONFIG['username'], CONFIG['password'])
    except KeyError:
        # Username and password weren't provided, try falling back to .netrc
        auth = HTTPBasicAuthFromNetrc(CONFIG['base_url'])
    return GerritRestAPI(url=CONFIG['base_url'], auth=auth)


def get_branchpoint(branch, repository, default):
    """See if a repo has an overridden branchpoint"""
    try:
        return CONFIG['manual_branch_points'][branch][repository]
    except KeyError:
        return default


def create_branch(repository, branch, revision):
    """Create a branch for a given repo."""
    # If we've got a sub-submodule we care about, branch it first so we can
    # do some magic stuff
    try:
        subrepo = CONFIG['sub_submodules'][repository]
        create_branch(subrepo, branch, revision)
    except KeyError:
        # This is the normal case, actually
        pass

    try:
        revision = get_branchpoint(branch, repository, revision)

        print('Branching {} to {} from {}'.format(repository, branch, revision))
        _get_client().put(
            '/projects/%s/branches/%s' % (
                repository.replace('/', '%2F'),
                branch.replace('/', '%2F')),
            json={'revision': revision}
        )
    except HTTPError as httpe:
        # Gerrit responds 409 for edit conflicts
        # means we already have a branch
        if httpe.response.status_code == 409:
            print('Already branched!')
        else:
            raise


def get_bundle(bundle, branch):
    """Return the list of all/some extensions, skins, and vendor."""
    if bundle == '*':
        things_to_branch = []
        for stuff in ['skins', 'extensions']:
            projects = _get_client().get(
                '/projects/?p=mediawiki/%s&b=%s' % (stuff, branch))
            for proj in projects:
                if projects[proj]['state'] == 'ACTIVE':
                    things_to_branch.append(proj)
        return things_to_branch
    else:
        try:
            return CONFIG['bundles'][bundle]
        except KeyError:
            return []


@contextmanager
def clone(repository):
    """Clone a repository. Basically clone core"""
    url = CONFIG['clone_base'] + '/' + repository
    temp = tempfile.mkdtemp()
    subprocess.check_call(['/usr/bin/git', 'clone', url, temp])
    cwd = os.getcwd()
    os.chdir(temp)
    yield temp
    os.chdir(cwd)
    shutil.rmtree(temp)


WGVERSION_REGEX = re.compile(
    r'^( \$wgVersion \s+ = \s+ )  [^;]*  ( ; \s* ) $',
    re.MULTILINE | re.VERBOSE)


def do_core_work(branch, bundle, version):
    """Add submodules, bump $wgVersion, etc"""
    cwd = os.getcwd()
    with clone('core'):
        for submodule in bundle:
            url = CONFIG['clone_base'] + '/' + submodule
            subprocess.check_call(['/usr/bin/git', 'submodule', 'add',
                                   '--force', '--branch', branch, url,
                                   submodule])

        with open('includes/DefaultSettings.php', 'r') as defaultsettings:
            contents = defaultsettings.read()

        with open('includes/DefaultSettings.php', 'w') as defaultsettings:
            defaultsettings.write(WGVERSION_REGEX.sub(
                r"\1'" + version + r"'\2", contents))

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
        for repo in get_bundle(OPTIONS.bundle, OPTIONS.branch_point):
            create_branch(repo, OPTIONS.branch, OPTIONS.branch_point)

    if OPTIONS.core:
        create_branch('core', OPTIONS.branch, OPTIONS.branch_point)
        if OPTIONS.core_version:
            do_core_work(OPTIONS.branch, OPTIONS.bundle, OPTIONS.core_version)
