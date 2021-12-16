#!/usr/bin/env python3
"""
This script makes deploying security patches easier and more automated.
Applies the patch in the repo, sync the file, log in IRC, copies to /srv/patches
and commit it to local git repo.

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
import argparse
import getpass
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime

parser = argparse.ArgumentParser()
parser.add_argument('patch')
parser.add_argument('repo')
parser.add_argument('--branch')
parser.add_argument('--run', action="store_true")
args = parser.parse_args()


def run(command, cwd=None):
    print(datetime.fromtimestamp(time.time()), 'CWD: ' + str(cwd), '---', command)
    if not args.run:
        return ''
    res = subprocess.run(command, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, shell=True, cwd=cwd,
                         universal_newlines=True)
    print(res.stdout)
    if res.returncode:
        sys.exit('Non zero exit status')
    return res.stdout


def get_tickets_from_content(content):
    commit_msg = re.split('\ndiff --git.*', content)[0]
    return re.findall(r'\nBug: (T\d+)', commit_msg)


def get_most_common_path(file_paths):
    common = []
    if not file_paths:
        return ''
    file_paths = [i.split('/') for i in file_paths
                  if not i.startswith('tests/')]
    if len(file_paths) == 1:
        return '/'.join(file_paths[0])
    while True:
        for i in range(len(file_paths[0])):
            first_value = file_paths[0][i]
            for file_path in file_paths:
                try:
                    new_value = file_path[i]
                except IndexError:
                    return '/'.join(common)
                if new_value != first_value:
                    return '/'.join(common)
            common.append(first_value)


def get_sync_path_from_content(content):
    files = []
    for case in re.findall(r'\ndiff --git a/(.+?) b/(.+?)\s', content):
        if case[0] == case[1]:
            files.append(case[0])
        else:
            if 'dev/null' in case[0] or 'dev/null' in case[1]:
                continue
            files.append(case[0])
            files.append(case[1])
    if len(files) == 1:
        return files[0]
    return get_most_common_path(files)


def fix_subject_line(patch):
    subject_needs_fixing = False
    with open(patch, 'r') as f:
        content = f.read()
        subjectline = content.split('\nSubject: [PATCH] ')[1].split('\n')[0]
        if subjectline.startswith('[SECURITY] '):
            subjectline = 'SECURITY: ' + subjectline[len('[SECURITY] '):]
            subject_needs_fixing = True
        elif 'SECURITY' not in subjectline:
            subjectline = 'SECURITY: ' + subjectline
            subject_needs_fixing = True

    if subject_needs_fixing:
        with open(patch, 'w') as f:
            og_subjectline = content.split('\nSubject: [PATCH] ')[1].split('\n')[0]
            f.write(
                content.replace(
                    '\nSubject: [PATCH] ' + og_subjectline + '\n',
                    '\nSubject: [PATCH] ' + subjectline + '\n',
                )
            )


def handle_branch(branch, repo, patch):
    repo_path = os.path.join('/srv/mediawiki-staging/', branch)
    if repo != 'core':
        repo_path = os.path.join(repo_path, repo)
    fix_subject_line(patch)
    with open(patch, 'r') as f:
        content = f.read()
        patch_path = os.path.realpath(f.name)
    tickets = get_tickets_from_content(content)
    sync_path = get_sync_path_from_content(content)
    if not tickets:
        sys.exit('No ticket has been found, exiting')
    res = run('git apply --check ' + patch_path, repo_path)
    if res:
        print('Patch failed, trying 3way')
        run('git apply --check --3way ' + patch_path, repo_path)
        response = input('Does it look good? [y or yes]: ')
        if response.lower() not in ['y', 'yes']:
            sys.exit('patch failed to apply, exiting')

    run('git am --3way ' + patch_path, repo_path)
    run('scap sync-file {} --no-log-message'.format(os.path.join(repo_path, sync_path)),
        '/srv/mediawiki-staging')

    comment = ''
    if tickets:
        comment = ' for ' + ' '.join(tickets)
    user = getpass.getuser()
    run('dologmsg !log {}: Deployed security patch'.format(user) + comment)
    patches_repo_path = os.path.join('/srv/patches/', branch.replace('php-', ''), repo)
    if run('git diff', patches_repo_path):
        sys.exit('dirty git in /srv/patches, exiting')
    run('mkdir -p ' + patches_repo_path)
    current_patches = []
    for files in os.listdir(patches_repo_path):
        if os.path.isfile(os.path.join(patches_repo_path, files)):
            current_patches.append(files)

    current_patches = sorted(current_patches)
    if not current_patches:
        num_patch = 1
    else:
        num_patch = int(current_patches[-1].split('-')[0]) + 1

    num_patch = str(num_patch).zfill(2)
    run('cp {} {}/{}-{}.patch'.format(patch_path, patches_repo_path, num_patch, tickets[0]))
    run('git add {}-{}.patch'.format(num_patch, tickets[0]), patches_repo_path)
    run('git commit -m "Add patch for {} on branch {}"'.format(
        tickets[0], branch.replace('php-', '')), patches_repo_path)


if args.branch:
    branch = args.branch
    if not branch.startswith('php-'):
        branch = 'php-' + branch
    branches = [branch]
else:
    with open('/srv/mediawiki-staging/wikiversions.json', 'r') as f:
        versions_json = json.load(f)
        branches = set(versions_json.values())

for branch in branches:
    handle_branch(branch, args.repo, args.patch)
