#!/usr/bin/env python3
# vim:sw=4:ts=4:et:
"""What repos are part of a bundle?"""

import argparse
import os

from mwrelease.branch import get_bundle


def parse_args():
    """Parse command line arguments and return options."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument('--bundle', dest='bundle', default=None,
                        help='Which bundle of extensions & skins to branch')
    parser.add_argument('--core', dest='core', action='store_true',
                        help='Include core')
    parser.add_argument('-l', '--link', dest='link', action='store_true',
                        help='Make them repo links')
    parser.add_argument('-r', '--raw', action='store_true',
                        help='Non-wiki output')
    parser.add_argument('-b', '--base-url',
                        default='https://gerrit.wikimedia.org/r',
                        help='URL for links')
    parser.add_argument('-c', '--count', action='store_true',
                        help='Show a count')

    return parser.parse_args()


def format(string, raw=False, link=None):
    if link is not None:
        string = '[{} {}]'.format(link, string)
    if not raw:
        string = '* {}'.format(string)
        return string
    if link is not None:
        return link
    return string


if __name__ == '__main__':
    args = vars(parse_args())

    repos = get_bundle(args['bundle'])

    if args['core']:
        repos.append('mediawiki/core')

    if args['count']:
        print('{} repos'.format(len(repos)))

    for repo in repos:
        link = None
        if args['link']:
            link = os.path.join(args['base_url'], repo)

        print(format(repo, args['raw'], link=link))
