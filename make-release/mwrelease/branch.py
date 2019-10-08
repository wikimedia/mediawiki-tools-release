from contextlib import contextmanager
import os
import re
import shutil
import subprocess
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


def gerrit_client():
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


def git(*args, **kwargs):
    return subprocess.run(('/usr/bin/git',) + args, check=True, **kwargs)


def create_branch(repository, branch, revision):
    """Create a branch for a given repo."""

    try:
        revision = get_branchpoint(branch, repository, revision)

        print('Branching {} to {} from {}'.format(
            repository, branch, revision))
        gerrit_client().put(
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
            projects = gerrit_client().get(
                '/projects/?p=mediawiki/%s/&b=%s' % (stuff, branch))
            for proj in projects:
                depth = len(proj.split('/'))
                if projects[proj]['state'] == 'ACTIVE' and depth == 3:
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
    url = CONFIG['base_url'] + repository
    temp = tempfile.mkdtemp(prefix='mw-branching-')
    git('clone', url, temp)
    cwd = os.getcwd()
    os.chdir(temp)
    yield temp
    os.chdir(cwd)
    shutil.rmtree(temp)


WGVERSION_REGEX = re.compile(
    r'^( \$wgVersion \s+ = \s+ )  [^;]*  ( ; \s* ) $',
    re.MULTILINE | re.VERBOSE)


def do_core_work(branch, bundle, version, no_review=False):
    """Add submodules, bump $wgVersion, etc"""
    cwd = os.getcwd()

    with clone('mediawiki/core'):
        # Install Gerrit's commit-msg hook for Change-Id generation
        with open('.git/hooks/commit-msg', 'wb') as commit_msg_hook:
            commit_msg_hook.write(gerrit_client().get('/tools/hooks/commit-msg'))
        os.chmod('.git/hooks/commit-msg', 0o500)

        # Checkout a local branch from origin's
        git('checkout', '-b', branch, 'origin/%s' % branch)

        # Remove all existing submodules
        output = git('submodule', 'status', stdout=subprocess.PIPE).stdout
        existing_submodules = [line.split(' ').pop()
                               for line in output.splitlines()
                               if len(line) > 0]

        for submodule in existing_submodules:
            git('submodule', 'deinit', '-f', '--', submodule)
            git('rm', '-f', '--', submodule)

        # Read in gitignore entries so we can remove them for any added
        # submodules
        ignores = []
        with open('.gitignore', 'r') as gitignore:
            ignores = gitignore.readlines()

        # Create submodules for each ext/skin/other in the bundle
        for repo in get_bundle(bundle, branch):
            url = CONFIG['base_url'] + repo

            if repo.startswith('mediawiki/'):
                path = repo[len('mediawiki/'):]
            else:
                path = repo

            git('submodule', 'add', '--force', '--branch', branch, url, path)

            try:
                ignores.remove('/%s\n' % path)
            except ValueError:
                pass

        with open('.gitignore', 'w') as gitignore:
            for line in ignores:
                gitignore.write(line)

        with open('includes/DefaultSettings.php', 'r') as defaultsettings:
            contents = defaultsettings.read()

        with open('includes/DefaultSettings.php', 'w') as defaultsettings:
            defaultsettings.write(WGVERSION_REGEX.sub(
                r"\1'" + version + r"-rc.0'\2", contents))

        git('commit', '-a', '-m',
            'Include %s submodules and default settings' % branch)

        if no_review:
            refspec = branch
        else:
            refspec = 'HEAD:refs/for/%s' % branch

        git('push', 'origin', refspec)

    os.chdir(cwd)


def branch(branch, branch_point, bundle=None, core=False, core_bundle=None,
           core_version=None, no_review=False):
    """Performs branch creation for the given bundle and/or core."""

    if bundle:
        for repo in get_bundle(bundle, branch_point):
            create_branch(repo, branch, branch_point)

    if core:
        create_branch('mediawiki/core', branch, branch_point)
        if core_version:
            do_core_work(branch, core_bundle, core_version, no_review)
