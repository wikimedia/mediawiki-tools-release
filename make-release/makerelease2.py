#!/usr/bin/env python3
"""
makerelease2.py - Generate a MediaWiki tarball

This script is "stupid" and just archives what is in Git.

Written in memory of Chad (😂).

Copyright (C) 2018-2021 Kunal Mehta <legoktm@member.fsf.org>

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
import git_archive_all
import gzip
import multiprocessing
import os
import requests
import subprocess
import sys
import tarfile
import tempfile
import zipfile

import scap_lint

# Force tarballs to be in GNU format to avoid Windows/7zip bugs (T257102)
tarfile.DEFAULT_FORMAT = tarfile.GNU_FORMAT


def call_git(args, quiet=False):
    cmd = ['git'] + args
    if quiet:
        subprocess.check_output(cmd)
    else:
        subprocess.check_call(cmd)


def is_git_tag(ref):
    """Whether the provided ref refers to a tag"""
    try:
        call_git(['rev-parse', 'refs/tags/%s' % ref], quiet=True)
        return True
    except subprocess.CalledProcessError:
        return False


def check_wg_version(ref):
    with open('includes/Defines.php') as f:
        text = f.read()
    expect = "define( 'MW_VERSION', '%s' );" % ref
    if expect not in text:
        raise RuntimeError('MW_VERSION is not set to %s' % ref)


def tarball_name(output_dir, ref, prefix='mediawiki', ext='tar.gz'):
    return os.path.abspath(os.path.join(output_dir, '%s-%s.%s' % (prefix, ref, ext)))


def archive(repo, tag, output_dir, previous=None, sign=False, upload_tar=False):
    os.chdir(repo)
    call_git(['checkout', tag])
    # Use -ff to remove deleted submodules
    call_git(['clean', '-ffdx'])
    call_git(['submodule', 'update', '--init', '--recursive'])
    call_git(['submodule', 'foreach', '--recursive', 'git clean -ffdx'])
    call_git(['submodule', 'foreach', '--recursive', 'git reset --hard'])

    is_tag = is_git_tag(tag)
    if is_tag:
        # If we're releasing a tag, verify that the
        # MediaWiki version matches exactly to the tag.
        check_wg_version(tag)
        if sign:
            try:
                call_git(['tag', '-v', tag])
            except subprocess.CalledProcessError:
                print('Error: git tag %s is not GPG signed' % tag)
                sys.exit(1)

    try:
        print('Linting PHP and JSON files for validity...')
        scap_lint.check_valid_syntax('.', procs=multiprocessing.cpu_count())
        print('Finished linting PHP and JSON files')
    except subprocess.CalledProcessError as err:
        print('Failed')

        # Output whatever was output to stderr, unless it's xargs complaining
        for line in err.stderr.decode('UTF-8').splitlines():
            if "xargs" not in line:
                print(line)
        return
    except ValueError as err:
        print('Failed')
        print(err)
        return

    # First, we create the mediawiki-core tarball
    # Explicitly ignore all extensions & skins via .gitattributes,
    # but keep the READMEs
    with open('.gitattributes', 'a') as f:
        f.write('extensions/* export-ignore\n')
        f.write('extensions/README -export-ignore\n')
        f.write('skins/* export-ignore\n')
        f.write('skins/README -export-ignore\n')
    # Note that we use a prefix of mediawiki-$tag in the tarball, but the filename
    # is mediawiki-core-$tag
    core_archiver = git_archive_all.GitArchiver(prefix='mediawiki-' + tag)

    core_only_tar = tarball_name(output_dir, tag, prefix='mediawiki-core', ext='tar.gz')
    print('Creating core tarball...')
    core_archiver.create(output_path=core_only_tar)
    print('Finished creating %s' % core_only_tar)

    core_only_zip = tarball_name(output_dir, tag, prefix='mediawiki-core', ext='zip')
    print('Creating core zip...')
    core_archiver.create(output_path=core_only_zip)
    print('Finished creating %s' % core_only_zip)

    # Reset our modifications, since we want extensions & skins in this one.
    call_git(['checkout', '.gitattributes'])

    # Now grab the rest of the extensions/skins for the full tarball
    archiver = git_archive_all.GitArchiver(prefix='mediawiki-' + tag)

    full_tar = tarball_name(output_dir, tag, ext='tar.gz')
    print('Creating core + extensions + skins tarball...')
    archiver.create(output_path=full_tar)
    print('Finished creating %s' % full_tar)

    full_zip = tarball_name(output_dir, tag, ext='zip')
    print('Creating core + extensions + skins zip...')
    archiver.create(output_path=full_zip)
    print('Finished creating %s' % full_zip)

    to_sign = [core_only_tar, core_only_zip, full_tar, full_zip]

    # TODO: Do some sanity check based on previous regressions over the tarball
    if previous:
        prev_tarball = tarball_name(output_dir, previous, ext='tar.gz')
        if not os.path.exists(prev_tarball):
            fetch_tarball(prev_tarball, previous)
        patch_paths = patch(prev_tarball, full_tar)
        to_sign.extend(patch_paths)

    if sign:
        for fname in to_sign:
            print('Signing %s:' % fname)
            print("\a")
            subprocess.check_call(['gpg', '--detach-sign', fname])

    if upload_tar:
        # Create a final tar for easy upload to the releases server
        with tarfile.open(upload_tar, 'a') as upload:
            folder = major_version(tag)
            files = to_sign
            if sign:
                files += [fname + '.sig' for fname in to_sign]
            for fname in files:
                upload.add(fname, os.path.join(folder, os.path.basename(fname)))

    # TODO: Surely there's a better way to do this
    if is_tag:
        text = """Download:
https://releases.wikimedia.org/mediawiki/{short}/mediawiki-{tag}.tar.gz
https://releases.wikimedia.org/mediawiki/{short}/mediawiki-{tag}.zip

Download without bundled extensions:
https://releases.wikimedia.org/mediawiki/{short}/mediawiki-core-{tag}.tar.gz
https://releases.wikimedia.org/mediawiki/{short}/mediawiki-core-{tag}.zip"""

        if previous:
            text += """

Patch to previous version ({previous}):
https://releases.wikimedia.org/mediawiki/{short}/mediawiki-{tag}.patch.gz
https://releases.wikimedia.org/mediawiki/{short}/mediawiki-{tag}.patch.zip"""

        text += """

GPG signatures:
https://releases.wikimedia.org/mediawiki/{short}/mediawiki-core-{tag}.tar.gz.sig
https://releases.wikimedia.org/mediawiki/{short}/mediawiki-core-{tag}.zip.sig
https://releases.wikimedia.org/mediawiki/{short}/mediawiki-{tag}.tar.gz.sig
https://releases.wikimedia.org/mediawiki/{short}/mediawiki-{tag}.zip.sig"""

        if previous:
            text += """
https://releases.wikimedia.org/mediawiki/{short}/mediawiki-{tag}.patch.gz.sig
https://releases.wikimedia.org/mediawiki/{short}/mediawiki-{tag}.patch.zip.sig"""
        text += """

Public keys:
https://www.mediawiki.org/keys/keys.html"""

        text = text.strip().format(tag=tag, short=major_version(tag), previous=previous)
        print('*' * 70)
        print(text)


def major_version(version):
    return '.'.join(version.split('.')[:2])


def fetch_tarball(fname, version):
    url = 'https://releases.wikimedia.org/mediawiki/%s/mediawiki-%s.tar.gz' \
          % (major_version(version), version)
    r = requests.get(url, stream=True)
    with open(fname, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024):
            f.write(chunk)
    # TODO: Should we do GPG verification for integrity?
    print('Downloaded %s' % url)


def _extract(tarball, tmpdir=None):
    """Extracts a tarball and returns the temporary directory"""
    if tmpdir is None:
        tmpdir = tempfile.TemporaryDirectory(prefix='mw')
    os.chdir(tmpdir.name)
    subprocess.check_call(['tar', '-xzf', tarball])
    return tmpdir


def patch(first, second):
    tmpdir = tempfile.TemporaryDirectory(prefix='mw-patch')
    os.chdir(tmpdir.name)
    _extract(first, tmpdir)
    _extract(second, tmpdir)

    def fname(x):
        return os.path.basename(x).replace('.tar.gz', '')
    try:
        output = subprocess.check_output(['diff', '-Nru', fname(first), fname(second)])
        # TODO: if exception wasn't thrown, that means there was no diff. That should be
        # impossible.
    except subprocess.CalledProcessError as e:
        output = e.stdout

    gz_patch_path = second.replace('.tar.gz', '.patch.gz')
    with gzip.open(gz_patch_path, 'wb') as f:
        f.write(output)
    print('Wrote gz patch to %s' % gz_patch_path)

    zip_patch_path = second.replace('.tar.gz', '.patch.zip')
    with zipfile.ZipFile(zip_patch_path, mode='w') as f:
        f.writestr(os.path.basename(second.replace('.tar.gz', '.patch')), output)
    print('Wrote zip patch to %s' % zip_patch_path)

    return [gz_patch_path, zip_patch_path]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('repository', help='Path to the MediaWiki git repository')
    parser.add_argument('tag', help='Git tag (or branch) to archive')
    parser.add_argument('--previous', help='Previous tarball to create a patch against')
    parser.add_argument('--sign', help='Sign the generated contents with GPG',
                        action='store_true')
    parser.add_argument('--output_dir', help='Location to put tarballs, relative to current '
                                             'directory',
                        default=os.getcwd())
    parser.add_argument('--upload-tar', help='Tarfile to put generated tarballs into')
    args = parser.parse_args()
    archive(args.repository, args.tag, args.output_dir, args.previous, sign=args.sign,
            upload_tar=args.upload_tar)


if __name__ == '__main__':
    main()
