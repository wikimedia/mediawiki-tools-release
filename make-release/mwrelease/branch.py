"""
Copyright (C) 2017-2021 by the following authors:

* Ahmon Dancy
* Chad Horohoe
* Dan Duvall
* Mukunda Modell

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

from __future__ import print_function

from contextlib import contextmanager
import os
import re
import shutil
import subprocess
import tempfile
import time

from requests.auth import HTTPBasicAuth
from requests.exceptions import HTTPError

import yaml

from pygerrit2.rest import GerritRestAPI
from pygerrit2.rest.auth import HTTPBasicAuthFromNetrc

# Setup config with local overrides
conffile = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    'settings.yaml'
)
with open(conffile) as globalconf:
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


def git(*args, **kwargs) -> subprocess.CompletedProcess:

    if "check" not in kwargs:
        kwargs["check"] = True
    if "universal_newlines" not in kwargs:
        kwargs["universal_newlines"] = True  # AKA text mode

    return subprocess.run(('/usr/bin/git',) + args, **kwargs)


def create_branch(repository, branch, revision, noop=False):
    """Create a branch for a given repo."""

    try:
        revision = get_branchpoint(branch, repository, revision)

        if noop:
            print("Would do: ", end='')

        print('Branching {} to {} from {}'.format(
            repository, branch, revision))

        if noop:
            return

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
            print('Warning: Branch %s already exists in repository %s' % (
                branch, repository))
        else:
            raise


def delete_branch(repository, branch, convert_to_tag=True, noop=False):
    """Delete a branch for a given repo."""
    if len(branch) < 1:
        raise ValueError('Invalid branch name: "%s"' % (branch))
    elif len(repository) < 1:
        raise ValueError('Invalid repo name: "%s"' % (repository))

    branch_url = '/projects/%s/branches/%s' % (
        repository.replace('/', '%2F'),
        branch.replace('/', '%2F'))

    try:
        branch_info = gerrit_client().get(branch_url)
    except HTTPError as httpe:
        if httpe.response.status_code == 404:
            print("Repo %s doesn't have a branch named %s" %
                  (repository, branch))
            return False
        else:
            raise

    if convert_to_tag:
        # Collect the commit id that the branch currently points to.
        rev = branch_info['revision']

        tag_url = '/projects/%s/tags/%s' % (
            repository.replace('/', '%2F'),
            branch.replace('/', '%2F'))

        # Create a tag that points to that commit
        message = 'archive of branch %s' % (branch)
        tag = {'message': message,
               'revision': rev}

        if noop:
            print("Would create tag %s pointing to %s" % (branch, rev))
        else:
            try:
                tag_resp = gerrit_client().put(tag_url, tag)
                print("Created %s" % tag_resp[0]['web_links'][0]['url'])
            except Exception as e:
                print("Failed to create tag %s: %s\nAborting." % (branch, e))
                raise e

    # Delete the branch.
    if noop:
        print("Would delete branch %s" % (branch))
    else:
        gerrit_client().delete(branch_url)


def get_bundle(bundle, conf=None):
    """Return the list of all/some extensions, skins, and vendor."""
    if conf is None:
        conf = CONFIG

    if bundle == '*':
        things_to_branch = []
        for stuff in ['skins', 'extensions']:
            projects = gerrit_client().get(
                '/projects/?p=mediawiki/%s/&b=master' % stuff)
            for proj in projects:
                depth = len(proj.split('/'))
                if projects[proj]['state'] == 'ACTIVE' and depth == 3:
                    things_to_branch.append(proj)
        return things_to_branch

    result = []
    for item in conf['bundles'][bundle]:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict):
            for directive, val in item.items():
                if directive == 'include':
                    include_bundle = get_bundle(val, conf)
                    result.extend(include_bundle)
                else:
                    msg = "Invalid directive %s in bundle %s" % (
                        directive,
                        bundle)
                    raise EnvironmentError(msg)

    return result


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


MWVERSION_REGEX = re.compile(
    r'^( define\( \s+ \'MW_VERSION\', \s+ ) \' [^;\']* \' ( \s+  \); \s* ) $',
    re.MULTILINE | re.VERBOSE)


def do_core_work(branch, bundle, version, no_review=False, task=None,
                 push_options=None, noop=False):
    """Add submodules, bump MW_VERSION, etc"""

    if noop:
        print("Not doing core work")
        return

    cwd = os.getcwd()

    if push_options is None:
        push_options = []

    with clone('mediawiki/core'):
        # Install Gerrit's commit-msg hook for Change-Id generation
        with open('.git/hooks/commit-msg', 'wb') as commit_msg_hook:
            commit_msg_hook.write(gerrit_client().get('/tools/hooks/commit-msg'))
        os.chmod('.git/hooks/commit-msg', 0o500)

        # Create the new branch and check it out:
        git('checkout', '-B', branch)

        # Remove all existing submodules
        output = git('submodule', '-q', 'foreach', 'echo $name', stdout=subprocess.PIPE).stdout
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

        # remove "*" from extensions/.gitignore so we can add the submodules
        with open('extensions/.gitignore', 'r+') as f:
            eignores = f.readlines()
            f.seek(0)
            f.truncate(0)
            eignores.remove('*\n')
            for line in eignores:
                f.write(line)

        # Create submodules for each ext/skin/other in the bundle
        for repo in get_bundle(bundle):
            url = CONFIG['base_url'] + repo

            if repo.startswith('mediawiki/'):
                path = repo[len('mediawiki/'):]
            else:
                path = repo

            print("Adding submodule {}".format(url))
            git('submodule', 'add', '--quiet', '--force', '--branch', branch, url, path)

            try:
                ignores.remove('/%s\n' % path)
            except ValueError:
                pass

        with open('.gitignore', 'w') as gitignore:
            for line in ignores:
                gitignore.write(line)

        with open('includes/Defines.php', 'r+') as defines:
            contents = defines.read()
            defines.seek(0)
            defines.truncate()
            defines.write(MWVERSION_REGEX.sub(
                r"\1'" + version + r"'\2", contents))

        message = 'Branch commit for %s' % branch
        if task:
            message = "%s\n\nBug: %s\n" % (message, task)

        git('commit', '-a', '-m', message)

        if no_review:
            refspec = branch
        else:
            refspec = 'HEAD:refs/for/%s' % branch

        res = git('push', 'origin', refspec,
                  *['--push-option=%s' % opt for opt in push_options],
                  stdout=subprocess.PIPE,
                  stderr=subprocess.STDOUT,
                  check=False)
        if res.returncode != 0:
            raise Exception("Command failed: {}\nOutput: {}\n".format(res.args, res.stdout))

        pattern_match = re.search(r'/c/mediawiki/core/\+/(\d+)', res.stdout)
        if pattern_match:
            change_number = pattern_match.group(1)
            wait_for_change_to_merge(change_number)

    os.chdir(cwd)


def wait_for_change_to_merge(change_number):
    # Values in seconds
    POLLING_INTERVAL = 5  # seconds
    TIMEOUT = 40*60  # 40 minutes.  The merge usually completes in about 20 minutes

    start = time.time()

    print("Waiting up to {} seconds for change {} to merge".format(TIMEOUT, change_number))

    while time.time() - start < TIMEOUT:
        detail = gerrit_client().get("/changes/{}/detail".format(change_number))
        status = detail['status']

        if status == 'MERGED':
            print("Change {} has been merged".format(change_number))
            return

        time.sleep(POLLING_INTERVAL)

    raise Exception("Change {} did not reach MERGED status within {} seconds".format(change_number, TIMEOUT))


def branch(branch, branch_point, bundle=None, core=False, core_bundle=None,
           core_version=None, no_review=False, noop=False, push_options=None,
           delete=False, task=None, skip_tag=False):
    """Performs branch creation for the given bundle and/or core."""

    if bundle:
        for repo in get_bundle(bundle):
            if delete:
                delete_branch(repo, branch, noop=noop, convert_to_tag=not skip_tag)
            else:
                create_branch(repo, branch, branch_point, noop=noop)

    if core:
        if delete:
            delete_branch('mediawiki/core', branch, noop=noop, convert_to_tag=not skip_tag)
        else:
            create_branch('mediawiki/core', branch, branch_point, noop=noop)
            if core_version:
                do_core_work(branch, core_bundle, core_version, no_review, task,
                             push_options, noop=noop)
