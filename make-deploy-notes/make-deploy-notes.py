#!/usr/bin/env python3
"""
make-deploy-notes.py
====================

Create a wiki-formatted changelog using gitiles and the make-wmf-branch
config.json.
"""

import argparse
import json
import os
import re

import requests

GITILES_URL = 'https://gerrit.wikimedia.org/r/plugins/gitiles'

# Messages we don't want to see in the git log
SKIP_MESSAGES = [
    'Localisation updates from',
    # Fix for escaping fail leaving a commit summary of $COMMITMSG
    'COMMITMSG',
    'Add (\.gitreview( and )?)?\.gitignore',
    # Branching commit; set $wgVersion, defaultbranch, add submodules
    'Creating new WMF',
    'Updating development dependencies',
    # git submodule autobumps
    'Updated mediawiki\/core',
]


def version_parser(ver):
    """
    Validate our version number formats.
    """
    try:
        return re.match(r"(1\.\d\d\.\d+-wmf\.\d+|master)", ver).group(0)
    except re.error:
        raise argparse.ArgumentTypeError(
            "Branch '%s' does not match required format" % ver)


def gitiles_changelog_url(old_branch, new_branch, repo):
    """
    Create url for valid git log
    """
    return '{}/{}/+log/{}..{}?format=JSON&no-merges'.format(
            GITILES_URL,
            repo,
            old_branch,
            new_branch
        )


def patch_url(change):
    """
    Create patch url for gitiles
    """
    return '{{git|%s}}' % change[:8]


def git_log(old, new, repo):
    """
    Fetches and loads the json git log from gitiles
    """
    r = requests.get(gitiles_changelog_url(old, new, repo))
    r.raise_for_status()
    log_json = r.text
    # remove )]}' since because gerrit.
    return json.loads(log_json[4:])


def maybe_task(message):
    """
    Tries to dig a task id out of a commit
    """
    task = ''
    for line in message.splitlines():
        if not line.startswith('Bug: '):
            continue

        task += ' ({{phabricator|%s}})' % line[len('Bug: '):]

    return task


def valid_change(message):
    """
    validates a change based on a commit
    """
    for skip_message in SKIP_MESSAGES:
        if re.search(skip_message, message):
            return False

    return True


def format_changes(old, new, repo):
    """
    format all valid changes
    """
    valid_changes = []

    changes = git_log(old, new, repo)

    for change in changes['log']:
        if not valid_change(change['message']):
            continue

        link = patch_url(change['commit'].strip())
        committer = change['committer']['name'].strip()
        message = change['message'].splitlines()[0].strip()

        formatted_change = '* {} - <nowiki>{}</nowiki>{} by {}'.format(
            link, message, maybe_task(change['message']), committer)

        valid_changes.append(formatted_change)

    return '\n'.join(valid_changes)


def print_formatted_changes(old, new, extension, display_name=None):
    """
    Print our changes if there are any, otherwise output a message
    """
    if not display_name:
        display_name = os.path.basename(extension)

    changes = format_changes(old, new, extension)
    if changes:
        print(changes)
    else:
        print('No changes for {}'.format(display_name))


def parse_args():
    """
    Parse arguments
    """
    ap = argparse.ArgumentParser()
    ap.add_argument(
        'oldbranch',
        metavar='OLD BRANCH',
        type=version_parser,
        help='Old branch (e.g., 1.31.0-wmf.23)'
    )
    ap.add_argument(
        'newbranch',
        metavar='NEW BRANCH',
        type=version_parser,
        help='New branch (e.g., 1.31.0-wmf.24)'
    )
    branches = vars(ap.parse_args())
    return (
        os.path.join('wmf', branches['oldbranch']),
        os.path.join('wmf', branches['newbranch'])
    )


def main():
    old, new = parse_args()

    base_path = os.path.dirname(os.path.realpath(__file__))
    branch_config_file = os.path.join(
        base_path, '..', 'make-wmf-branch', 'config.json')

    with open(branch_config_file) as f:
        branch_config = json.load(f)

    extensions = list(
        map(
            lambda x: os.path.join('mediawiki', x),
            branch_config['extensions']
        )
    )

    print("== Core changes ==")
    print_formatted_changes(old, new, 'mediawiki/core')
    print("=== Vendor ===")
    print_formatted_changes(old, new, 'mediawiki/vendor')

    printed_skins = False

    print("== Extensions ==")
    for extension in extensions:
        extension_name = os.path.basename(extension)

        # We already did vendor
        if 'vendor' == extension_name:
            continue

        # Print a skin header at the start of the skins
        if 'skins' in extension and not printed_skins:
            printed_skins = True
            print('== Skins ==')

        print('=== {} ==='.format(extension_name))
        print_formatted_changes(old, new, extension, display_name=extension_name)


if __name__ == '__main__':
    main()
