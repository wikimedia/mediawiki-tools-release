#!/usr/bin/env python2
# vim:sw=4:ts=4:et:
"""
Helper to generate a MediaWiki tarball.

If the previous version is not given, it will be derived from the next version,
and you will be prompted to confirm that the version number is correct.

If no arguments are given, a snapshot is created.
"""
from __future__ import print_function
import argparse
import glob
import logging
import os
import re
import subprocess
import sys
import time
import yaml


def parse_args():
    """Parse command line arguments and return options"""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        '--conf', dest='conffile',
        default=os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            'make-release.yaml'),
        help='specify the configuration file')

    # Positional arguments:
    parser.add_argument(
        'version', nargs='?',
        help='version you are about to release')
    parser.add_argument(
        'previousversion', nargs='?',
        help='version that came before')

    # Optional arguments:
    log_options = parser.add_mutually_exclusive_group()
    log_options.add_argument(
        '--debug', dest='log_level',
        action='store_const', const=logging.DEBUG,
        help='Print out internal processing')
    log_options.add_argument(
        '-q', '--quiet', dest='log_level',
        action='store_const', const=logging.WARNING,
        help='Only shows up warning and errors')

    parser.add_argument(
        '-y', '--yes', dest='yes', action='store_true',
        help='answer yes to any question'
    )
    parser.add_argument(
        '--no-previous', dest='no_previous', action='store_true',
        help='disable the diff with previous version'
    )
    parser.add_argument(
        '--build', dest='buildroot',
        default=os.getcwd(),
        help='where the build should happen (defaults to pwd)'
    )
    parser.add_argument(
        '--branch', dest='branch',
        default='master',
        help='which branch to use (defaults to master for snapshot)'
    )
    parser.add_argument(
        '--dont-sign', dest='sign', action='store_false',
        default=True,
        help='skip gpg signing'
    )
    parser.add_argument(
        '--tar-command', dest='tar_command',
        default='tar',
        help='path to tar, we are expecting a GNU tar. (defaults to tar)'
    )
    parser.add_argument(
        '--list-bundled', dest='list_bundled',
        action='store_true',
        help='List all bundled extensions for the given version and quit'
    )

    return parser.parse_args()


class MwVersion(object):
    """Abstract out a MediaWiki version"""

    def __init__(self, version):
        decomposed = self.decompose(version)

        self.raw = version
        self.major = decomposed.get('major', None)
        self.branch = decomposed.get('branch', None)
        self.tag = decomposed.get('tag', None)
        self.prev_version = decomposed.get('prev_version', None)
        self.prev_tag = decomposed.get('prevTag', None)

        # alpha / beta / rc ..
        self.phase = decomposed.get('phase', None)
        self.cycle = decomposed.get('cycle', None)

    @classmethod
    def new_snapshot(cls, branch='master'):
        return cls('snapshot-{}-{}'.format(
            branch, time.strftime('%Y%m%d', time.gmtime())))

    def __repr__(self):
        if self.raw is None:
            return "<MwVersion Null (snapshot?)>"

        return """
<MwVersion %s major: %s (prev: %s), tag: %s (prev: %s), branch: %s>
        """ % (
            self.raw,
            self.major, self.prev_version,
            self.tag, self.prev_tag,
            self.branch
        )

    def decompose(self, version):
        """Split a version number to branch / major

        Whenever a version is recognized, a dict is returned with keys:
            - major (ie 1.22)
            - minor
            - branch
            - tag
            - prev_version
            - prevTag

        When one or more letters are found after the minor version we consider
        it a software development phase (ex: alpha, beta, rc) with incremental
        cycles. Hence we will expose:
            - phase
            - cycle

        Default: {}
        """

        ret = {}
        if version is None:
            raise ValueError('Invalid version')
        if version.startswith('snapshot-'):
            return {
                'branch': 'master',
                'major': 'snapshot',
                'tag': 'master',
            }

        matches = re.compile(r"""
            (?P<major>(?P<major1>\d+)\.(?P<major2>\d+))
            \.
            (?P<minor>\d+)
            (?:-?
                (?P<phase>[A-Za-z]+)?\.?
                (?P<cycle>\d+)
            )?
        """, re.X).match(version)

        if matches is None:
            raise ValueError('%s is in the wrong format' % version)

        # Clear out unneed phase/cycle
        ret = dict((k, v) for k, v in matches.groupdict().iteritems()
                   if v is not None)

        ret['branch'] = 'REL%s_%s' % (
            ret['major1'],
            ret['major2'],
        )
        del ret['major1']
        del ret['major2']

        try:
            if 'phase' in ret:
                ret['tag'] = 'tags/%s.%s-%s.%s' % (
                    ret['major'],
                    ret['minor'],
                    ret.get('phase', ''),
                    ret.get('cycle', '')
                )
            else:
                ret['tag'] = 'tags/%s.%s' % (
                    ret['major'],
                    ret['minor'],
                )
        except KeyError:
            ret['tag'] = 'tags/%s.%s' % (
                ret['major'],
                ret['minor']
            )

        last = matches.group(matches.lastindex)
        if last != '' and int(last) == 0:
            ret['prev_version'] = None
            ret['prevTag'] = None
            return ret

        bits = [d for d in matches.groups('')]
        last = matches.lastindex - 3
        del bits[1]
        del bits[1]

        bits[last] = str(int(bits[last]) - 1)

        if 'phase' in ret:
            ret['prev_version'] = '%s.%s-%s.%s' % tuple(bits)
        else:
            ret['prev_version'] = '%s.%s' % (bits[0], bits[1])

        ret['prevTag'] = 'tags/' + ret['prev_version']

        return ret


class MakeRelease(object):
    """Surprisingly: do a MediaWiki release"""
    def __init__(self, ops):
        if ops.version is None:
            self.version = MwVersion.new_snapshot(ops.branch)
        else:
            self.version = MwVersion(ops.version)
        self.options = ops

        if not os.path.isfile(self.options.conffile):
            logging.error("Configuration file not found: %s",
                          self.options.conffile)
            sys.exit(1)

        self.config = None
        with open(self.options.conffile) as conf:
            self.config = yaml.load(conf)

    def get_extensions_for_version(self, version, extensions=None):
        """
        Get the list of extensions to bundle for the given
        MediaWiki core version

        :param version: A MWVersion object.
        :param extensions: Extensions that are already being included
        :type extensions: list
        :return: List of extensions to include
        """
        if extensions is None:
            extensions = []
        if 'bundles' not in self.config:
            return extensions
        bundles = self.config['bundles']
        base = set(bundles['base'])
        for release in sorted(list(bundles)):
            if release.startswith('mediawiki-') and \
                    release <= 'mediawiki-' + version.major:
                changes = bundles[release]
                if 'add' in changes:
                    for repo in changes['add']:
                        base.add(repo)
                if 'remove' in changes:
                    for repo in changes['remove']:
                        base.remove(repo)
        return sorted(extensions + list(base))

    def get_patches_for_repo(self, repo, patch_dir):
        patch_file_pattern = '*-%s.patch' % self.version.branch
        return sorted(
            glob.glob(os.path.join(patch_dir, repo, patch_file_pattern)))

    def print_bundled(self, extensions):
        """
        Print all bundled extensions and skins

        :param extensions: Extensions that are already being included
        :return: exit code
        """
        for repo in self.get_extensions_for_version(self.version, extensions):
            print(repo)
        return 0

    def main(self):
        """return value should be usable as an exit code"""

        extensions = []

        if self.options.list_bundled:
            return self.print_bundled(extensions)

        logging.info("Doing release for %s", self.version.raw)

        if self.version.branch is None:
            logging.debug("No branch, assuming '%s'. Override with --branch.",
                          self.options.branch)
            self.version.branch = self.options.branch

        # No version specified, assuming a snapshot release
        if self.options.version is None:
            self.do_release(
                version=MwVersion.new_snapshot(self.options.branch))
            return 0

        if self.options.previousversion:
            # Given the previous version on the command line
            self.do_release(
                extensions=extensions,
                version=self.version)
            return 0

        no_previous = False
        if self.version.prev_version is None:
            if not self.ask("No previous release found. Do you want to make a "
                            "release with no patch?"):
                logging.error('Please specify the correct previous release ' +
                              'on the command line')
                return 1
            else:
                no_previous = True
        if no_previous or self.options.no_previous:
            self.do_release(
                extensions=extensions,
                version=self.version)
        else:
            if not self.ask("Was %s the previous release?" %
                            self.version.prev_version):
                logging.error('Please specify the correct previous release ' +
                              'on the command line')
                return 1

            self.do_release(
                extensions=extensions,
                version=self.version)
        return 0

    def ask(self, question):
        if self.options.yes:
            return True

        while True:
            print(question + ' [y/n] ')
            response = sys.stdin.readline()
            if response:
                if response[0].lower() == 'y':
                    return True
                elif response[0].lower() == 'n':
                    return False
            print('Please type "y" for yes or "n" for no')

    def get_git(self, repo, target, git_ref):
        old_dir = os.getcwd()

        if os.path.exists(target):
            logging.info("Updating %s in %s...", repo, target)
            proc = subprocess.Popen(
                ['sh', '-c', 'cd ' + target + '; git fetch -q --all'])
        else:
            logging.info("Cloning %s into %s...", repo, target)
            repo = 'https://gerrit.wikimedia.org/r/p/mediawiki/' + repo
            proc = subprocess.Popen(['git', 'clone', '--recursive', repo, target])

        if proc.wait() != 0:
            logging.error("git clone failed, exiting")
            sys.exit(1)

        os.chdir(target)

        logging.debug("Checking out %s in %s...", git_ref, target)
        proc = subprocess.Popen(['git', 'checkout', git_ref])

        if proc.wait() != 0:
            logging.error("git checkout failed, exiting")
            sys.exit(1)

        logging.debug("Checking out submodules in %s...", target)
        proc = subprocess.Popen(['git', 'submodule', 'update', '--init',
                                 '--recursive'])

        if proc.wait() != 0:
            logging.error("git submodule update failed, exiting")
            sys.exit(1)

        os.chdir(old_dir)

    def export(self, git_ref, module, export_dir, patches=None):
        if patches:
            git_ref = self.version.branch
        self.get_git('core', os.path.join(export_dir, module), git_ref)
        self.maybe_apply_patches(export_dir, patches)

    def make_patch(self, dest_dir, patch_file_name, dir1, dir2, patch_type):
        patch_file = open(dest_dir + "/" + patch_file_name, 'w')
        args = ['diff', '-Nruw']
        if patch_type == 'i18n':
            logging.debug("Generating i18n patch file...")
            dir1 += '/languages/messages'
            dir2 += '/languages/messages'
        else:
            logging.debug("Generating normal patch file...")
            for excl in self.config['diff']['ignore']:
                args.extend(['-x', excl])

        args.extend([dir1, dir2])
        logging.debug(' '.join(args))
        diff_proc = subprocess.Popen(args, stdout=subprocess.PIPE)
        gzip_proc = subprocess.Popen(['gzip', '-9'], stdin=diff_proc.stdout,
                                     stdout=patch_file)

        diff_status = diff_proc.wait()
        gzip_status = gzip_proc.wait()

        if diff_status > 1 or gzip_status != 0:
            logging.error("diff failed, exiting")
            logging.error("diff: %s", diff_status)
            logging.error("gzip: %s", gzip_status)
            sys.exit(1)
        patch_file.close()
        logging.info('Done with making patch')
        return diff_status == 1

    def maybe_apply_patches(self, input_dir, patch_files=None):
        if not patch_files:
            return
        old_dir = os.getcwd()
        os.chdir(input_dir)
        for patch_file in patch_files:
            with open(patch_file) as patch_in:
                patch_proc = subprocess.Popen(['git', 'am', '--3way'],
                                              stdin=patch_in)
                status = patch_proc.wait()
                if status != 0:
                    logging.error("Patch failed, exiting")
                    logging.error("git: %s", status)
                    sys.exit(1)
            logging.info("Finished applying patch %s", patch_file)
        os.chdir(old_dir)

    def make_tar(self, package, input_dir, build_dir, add_args=None):
        tar = self.options.tar_command

        # Generate the .tar.gz file
        filename = package + '.tar.gz'
        out_file = open(build_dir + '/' + filename, "w")
        args = [tar, '--format=gnu', '--exclude-vcs', '-C', build_dir]
        if self.config.get('tar', {}).get('ignore', []):
            for patt in self.config['tar']['ignore']:
                args += ['--exclude', patt]
        if add_args:
            args += add_args
        args += ['-c', input_dir]
        logging.debug("Creating %s", filename)
        tar_proc = subprocess.Popen(args, stdout=subprocess.PIPE)
        gzip_proc = subprocess.Popen(['gzip', '-9'], stdin=tar_proc.stdout,
                                     stdout=out_file)

        if tar_proc.wait() != 0 or gzip_proc.wait() != 0:
            logging.error("tar/gzip failed, exiting")
            sys.exit(1)
        out_file.close()
        logging.info('%s written', filename)
        return filename

    def do_release(self, version, extensions=None):

        root_dir = self.options.buildroot

        # variables related to the version
        branch = version.branch
        tag = version.tag
        prev_version = version.prev_version
        major_ver = version.major

        if root_dir is None:
            root_dir = os.getcwd()

        if not os.path.exists(root_dir):
            logging.debug('Creating %s', root_dir)
            os.mkdir(root_dir)

        build_dir = root_dir + '/build'
        patch_dir = root_dir + '/patches'

        if not os.path.exists(build_dir):
            logging.debug('Creating build dir: %s', build_dir)
            os.mkdir(build_dir)

        os.chdir(build_dir)

        package = 'mediawiki-' + version.raw

        # Export the target
        self.export(tag, package, build_dir,
                    self.get_patches_for_repo('core', patch_dir))

        os.chdir(os.path.join(build_dir, package))
        subprocess.check_output(['composer', 'update', '--no-dev'])
        self.maybe_apply_patches(
            os.path.join(package, 'vendor'),
            self.get_patches_for_repo('vendor', patch_dir))

        ext_exclude = []
        for ext in self.get_extensions_for_version(version, extensions):
            self.maybe_apply_patches(
                os.path.join(package, ext),
                self.get_patches_for_repo(ext, patch_dir))
            ext_exclude.append("--exclude")
            ext_exclude.append(ext)

        # Generate the .tar.gz files
        out_files = []
        out_files.append(
            self.make_tar(
                package='mediawiki-core-' + version.raw,
                input_dir=package,
                build_dir=build_dir,
                add_args=ext_exclude)
        )
        out_files.append(
            self.make_tar(
                package=package,
                input_dir=package,
                build_dir=build_dir)
        )

        # Patch
        have_i18n = False
        if not self.options.no_previous and prev_version is not None:
            prev_dir = 'mediawiki-' + prev_version
            prev_mw_version = MwVersion(prev_version)
            self.export(prev_mw_version.tag,
                        prev_dir, build_dir)
            os.chdir(os.path.join(build_dir, prev_dir))
            subprocess.check_output(['composer', 'update', '--no-dev'])

            self.make_patch(
                build_dir, package + '.patch.gz', prev_dir, package, 'normal')
            out_files.append(package + '.patch.gz')
            logging.debug('%s.patch.gz written', package)
            if os.path.exists(package + '/languages/messages'):
                i18n_patch = 'mediawiki-i18n-' + version.raw + '.patch.gz'
                if (self.make_patch(
                        build_dir, i18n_patch, prev_dir, package, 'i18n')):
                    out_files.append(i18n_patch)
                    logging.info('%s written', i18n_patch)
                    have_i18n = True

        # Sign
        for file_name in out_files:
            if self.options.sign:
                try:
                    proc = subprocess.Popen([
                        'gpg', '--detach-sign', build_dir + '/' + file_name])
                except OSError as ose:
                    logging.error("gpg failed, does it exist? Skip with " +
                                  "--dont-sign.")
                    logging.error("Error %s: %s", ose.errno, ose.strerror)
                    sys.exit(1)
                if proc.wait() != 0:
                    logging.error("gpg failed, exiting")
                    sys.exit(1)

        # Write email template
        print()
        print("Full release notes:")
        url = ('https://phabricator.wikimedia.org/diffusion/MW/browse/' +
               branch + '/RELEASE-NOTES-' + major_ver)

        print(url)
        print('https://www.mediawiki.org/wiki/Release_notes/' + major_ver)
        print()
        print()
        print('*' * 70)

        server = 'https://releases.wikimedia.org/mediawiki/{}/'.format(major_ver)
        print('Download:')
        print(server + package + '.tar.gz')
        print()

        if prev_version is not None:
            if have_i18n:
                print("Patch to previous version (" + prev_version +
                      "), without interface text:")
                print(server + package + '.patch.gz')
                print("Interface text changes:")
                print(server + i18n_patch)
            else:
                print("Patch to previous version (" + prev_version + "):")
                print(server + package + '.patch.gz')
            print()

        print('GPG signatures:')
        for file_name in out_files:
            print(server + file_name + '.sig')
        print()

        print('Public keys:')
        print('https://www.mediawiki.org/keys/keys.html')
        print()

        return 0


if __name__ == '__main__':
    _OPTS = parse_args()

    if _OPTS.log_level is None:
        _OPTS.log_level = logging.INFO

    logging.basicConfig(level=_OPTS.log_level, stream=sys.stderr)
    sys.exit(MakeRelease(_OPTS).main())
