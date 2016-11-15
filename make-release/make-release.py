#!/usr/bin/env python
# vim:sw=4:ts=4:et:
from __future__ import print_function
"""
Helper to generate a MediaWiki tarball.

If the previous version is not given, it will be derived from the next version,
and you will be prompted to confirm that the version number is correct.

If no arguments are given, a snapshot is created.
"""

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
        '--smw', dest='smw', action='store_true',
        help='include the SemanticMediaWiki bundle'
    )
    parser.add_argument(
        '--git-root', dest='gitroot',
        default='https://gerrit.wikimedia.org/r/p/mediawiki',
        help='base git URL to fetch projects from (defaults to Gerrit)'
    )
    parser.add_argument(
        '--git-root-ext', dest='gitrootext',
        default=None,
        help='base git URL to fetch extensions from (defaults to git-root)'
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
        '--offline', dest='offline',
        default=False, action='store_true',
        help='Do not perform actions (e.g. git pull) that require the network'
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
        decomposed = self.decomposeVersion(version)

        self.raw = version
        self.major = decomposed.get('major', None)
        self.branch = decomposed.get('branch', None)
        self.tag = decomposed.get('tag', None)
        self.prev_version = decomposed.get('prevVersion', None)
        self.prev_tag = decomposed.get('prevTag', None)

        # alpha / beta / rc ..
        self.phase = decomposed.get('phase', None)
        self.cycle = decomposed.get('cycle', None)

    @classmethod
    def new_snapshot(cls):
        return cls('snapshot-' + time.strftime('%Y%m%d', time.gmtime()))

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

    def decomposeVersion(self, version):
        """Split a version number to branch / major

        Whenever a version is recognized, a dict is returned with keys:
            - major (ie 1.22)
            - minor
            - branch
            - tag
            - prevVersion
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

        m = re.compile(r"""
            (?P<major>(?P<major1>\d+)\.(?P<major2>\d+))
            \.
            (?P<minor>\d+)
            (?:-?
                (?P<phase>[A-Za-z]+)?\.?
                (?P<cycle>\d+)
            )?
        """, re.X).match(version)

        if m is None:
            raise ValueError('%s is in the wrong format' % version)

        # Clear out unneed phase/cycle
        ret = dict((k, v) for k, v in m.groupdict().iteritems()
                   if v is not None)

        ret['branch'] = 'REL%s_%s' % (
            ret['major1'],
            ret['major2'],
        )
        del ret['major1']
        del ret['major2']

        try:
            # Special case for when we switched to semantic versioning
            if(ret['major'] <= '1.22' or
               (ret['major'] == '1.23' and
                ret['minor'] == '0' and
                (ret['phase'] == 'rc' and
                 ret['cycle'] == '0'))):
                ret['tag'] = 'tags/%s.%s%s%s' % (
                    ret['major'],
                    ret['minor'],
                    ret.get('phase', ''),
                    ret.get('cycle', '')
                )
            elif('phase' in ret):
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

        last = m.group(m.lastindex)
        if last != '' and int(last) == 0:
            ret['prevVersion'] = None
            ret['prevTag'] = None
            return ret

        bits = [d for d in m.groups('')]
        last = m.lastindex - 3
        del bits[1]
        del bits[1]

        bits[last] = str(int(bits[last]) - 1)

        if(bits[0] <= '1.22' or
           (bits[0] == '1.23' and
            bits[1] == '0' and
            (bits[2] == 'rc' and
             bits[3] == '0'))):
            ret['prevVersion'] = '%s.%s%s%s' % tuple(bits)
        elif 'phase' in ret:
            ret['prevVersion'] = '%s.%s-%s.%s' % tuple(bits)
        else:
            ret['prevVersion'] = '%s.%s' % (bits[0], bits[1])

        ret['prevTag'] = 'tags/' + ret['prevVersion']

        return ret


class MakeRelease(object):
    """Surprisingly: do a MediaWiki release"""

    options = None
    version = None  # MwVersion object
    config = None

    def __init__(self, options):
        if options.version is None:
            self.version = MwVersion.new_snapshot()
        else:
            self.version = MwVersion(options.version)
        self.options = options

        if not os.path.isfile(self.options.conffile):
            logging.error("Configuration file not found: %s",
                          self.options.conffile)
            sys.exit(1)

        with open(self.options.conffile) as f:
            self.config = yaml.load(f)

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

    def get_patches_for_repo(self, repo, patchDir):
        patch_file_pattern = '*-%s.patch' % self.version.branch
        return sorted(
            glob.glob(os.path.join(patchDir, repo, patch_file_pattern)))

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
        bundles = self.config.get('bundles', {})

        if options.smw:
            if 'smw' not in bundles:
                raise Exception("No SMW extensions given.")

            # Other extensions for inclusion
            extensions.extend(bundles['smw'])
        if options.list_bundled:
            return self.print_bundled(extensions)

        logging.info("Doing release for %s", self.version.raw)

        if self.version.branch is None:
            logging.debug("No branch, assuming '%s'. Override with --branch.",
                          options.branch)
            self.version.branch = options.branch

        # No version specified, assuming a snapshot release
        if options.version is None:
            self.makeRelease(
                version=MwVersion.new_snapshot(),
                dir='snapshots')
            return 0

        if options.previousversion:
            # Given the previous version on the command line
            self.makeRelease(
                extensions=extensions,
                version=self.version,
                dir=self.version.major)
            return 0

        noPrevious = False
        if self.version.prev_version is None:
            if not self.ask("No previous release found. Do you want to make a "
                            "release with no patch?"):
                logging.error('Please specify the correct previous release ' +
                              'on the command line')
                return 1
            else:
                noPrevious = True
        if noPrevious or options.no_previous:
            self.makeRelease(
                extensions=extensions,
                version=self.version,
                dir=self.version.major)
        else:
            if not self.ask("Was %s the previous release?" %
                            self.version.prev_version):
                logging.error('Please specify the correct previous release ' +
                              'on the command line')
                return 1

            self.makeRelease(
                extensions=extensions,
                version=self.version,
                dir=options.buildroot)
        return 0

    def ask(self, question):
        if self.options.yes:
            return True

        while True:
            print(question + ' [y/n] ')
            response = sys.stdin.readline()
            if len(response) > 0:
                if response[0].lower() == 'y':
                    return True
                elif response[0].lower() == 'n':
                    return False
            print('Please type "y" for yes or "n" for no')

    def getGit(self, repo, dir, label, gitRef):
        oldDir = os.getcwd()
        if os.path.exists(repo):
            logging.debug("Updating local %s", repo)
            proc = subprocess.Popen(['git', 'remote', 'update'],
                                    cwd=repo)
            if proc.wait() != 0:
                logging.error("Could not update local repository %s", repo)
                sys.exit(1)

        if not self.options.offline:
            if os.path.exists(dir):
                logging.debug("Updating %s in %s...", label, dir)
                proc = subprocess.Popen(
                    ['sh', '-c', 'cd ' + dir + '; git fetch -q --all'])
            else:
                logging.info("Cloning %s into %s...", label, dir)
                proc = subprocess.Popen(['git', 'clone', repo, dir])

            if proc.wait() != 0:
                logging.error("git clone failed, exiting")
                sys.exit(1)

        os.chdir(dir)

        if gitRef != 'master':
            logging.debug("Checking out %s in %s...", gitRef, dir)
            proc = subprocess.Popen(['git', 'checkout', gitRef])

            if proc.wait() != 0:
                logging.error("git checkout failed, exiting")
                sys.exit(1)

        os.chdir(oldDir)

    def export(self, gitRef, module, exportDir, patches=[]):

        gitRoot = self.options.gitroot

        dir = exportDir + '/' + module
        if patches:
            gitRef = self.version.branch
        self.getGit(gitRoot + '/core', dir, "core", gitRef)
        for patch in patches:
            self.applyPatch(patch, dir)
        # 1.25+ has composer dependencies and needs mediawiki/vendor.
        if self.version.major >= '1.25' or self.version.major == 'snapshot':
            self.getGit(gitRoot + '/vendor', dir + '/vendor',
                        'vendor', self.version.branch)

        logging.info('Done with exporting core')

    def exportExtension(self, branch, extension, dir, patches=[]):
        gitroot = self.options.gitroot
        if self.options.gitrootext:
            gitroot = self.options.gitrootext

        self.getGit(gitroot + '/' + extension,
                    dir + '/' + extension, extension, branch)
        for patch in patches:
            self.applyPatch(patch, dir + '/' + extension)
        logging.info('Done with exporting %s', extension)

    def makePatch(self, destDir, patchFileName, dir1, dir2, type):
        patchFile = open(destDir + "/" + patchFileName, 'w')
        args = ['diff', '-Nruw']
        if type == 'i18n':
            logging.debug("Generating i18n patch file...")
            dir1 += '/languages/messages'
            dir2 += '/languages/messages'
        else:
            logging.debug("Generating normal patch file...")
            for excl in self.config['diff']['ignore']:
                args.extend(['-x', excl])

        args.extend([dir1, dir2])
        logging.debug(' '.join(args))
        diffProc = subprocess.Popen(args, stdout=subprocess.PIPE)
        gzipProc = subprocess.Popen(['gzip', '-9'], stdin=diffProc.stdout,
                                    stdout=patchFile)

        diffStatus = diffProc.wait()
        gzipStatus = gzipProc.wait()

        if diffStatus > 1 or gzipStatus != 0:
            logging.error("diff failed, exiting")
            logging.error("diff: %s", diffStatus)
            logging.error("gzip: %s", gzipStatus)
            sys.exit(1)
        patchFile.close()
        logging.info('Done with making patch')
        return diffStatus == 1

    def applyPatch(self, patchFile, targetDir):
        oldDir = os.getcwd()
        os.chdir(targetDir)
        with open(patchFile) as patchIn:
            patchProc = subprocess.Popen(['git', 'am', '--signoff', '--3way'],
                                         stdin=patchIn)
            status = patchProc.wait()
            if status != 0:
                logging.error("Patch failed, exiting")
                logging.error("git: %s", status)
                sys.exit(1)
        logging.info("Finished applying patch %s", patchFile)
        os.chdir(oldDir)

    def makeTarFile(self, package, targetDir, dir, argAdd=[]):
        tar = self.options.tar_command

        # Generate the .tar.gz file
        filename = package + '.tar.gz'
        outFile = open(dir + '/' + filename, "w")
        args = [tar, '--format=gnu', '--exclude-vcs', '-C', dir]
        if self.config.get('tar', {}).get('ignore', []):
            for patt in self.config['tar']['ignore']:
                args += ['--exclude', patt]
        args += argAdd
        args += ['-c', targetDir]
        logging.debug("Creating %s", filename)
        tarProc = subprocess.Popen(args, stdout=subprocess.PIPE)
        gzipProc = subprocess.Popen(['gzip', '-9'], stdin=tarProc.stdout,
                                    stdout=outFile)

        if tarProc.wait() != 0 or gzipProc.wait() != 0:
            logging.error("tar/gzip failed, exiting")
            sys.exit(1)
        outFile.close()
        logging.info('%s written', filename)
        return filename

    def makeRelease(self, version, dir, extensions=[]):

        rootDir = self.options.buildroot

        # variables related to the version
        branch = self.version.branch
        tag = self.version.tag
        prevVersion = self.version.prev_version

        if rootDir is None:
            rootDir = os.getcwd()

        if not os.path.exists(rootDir):
            logging.debug('Creating %s', rootDir)
            os.mkdir(rootDir)

        buildDir = rootDir + '/build'
        uploadDir = rootDir + '/uploads'
        patchDir = rootDir + '/patches'

        if not os.path.exists(buildDir):
            logging.debug('Creating build dir: %s', buildDir)
            os.mkdir(buildDir)
        if not os.path.exists(uploadDir):
            logging.debug('Creating uploads dir: %s', uploadDir)
            os.mkdir(uploadDir)
        if not os.path.exists(patchDir):
            logging.debug('Creating patch directory: %s', patchDir)
            os.mkdir(patchDir)

        os.chdir(buildDir)

        if not os.path.exists(dir):
            os.mkdir(dir)

        package = 'mediawiki-' + version.raw

        # Export the target
        patches = self.get_patches_for_repo('core', patchDir)
        self.export(tag, package, buildDir, patches)

        extExclude = []
        for ext in self.get_extensions_for_version(version, extensions):
            patches = self.get_patches_for_repo(ext, patchDir)
            self.exportExtension(branch, ext, package, patches)
            extExclude.append("--exclude")
            extExclude.append(ext)

        # Generate the .tar.gz files
        outFiles = []
        outFiles.append(
            self.makeTarFile(
                package='mediawiki-core-' + version.raw,
                targetDir=package,
                dir=buildDir,
                argAdd=extExclude)
        )
        outFiles.append(
            self.makeTarFile(
                package=package,
                targetDir=package,
                dir=buildDir)
        )

        # Patch
        haveI18n = False
        if not self.options.no_previous and prevVersion is not None:
            prevDir = 'mediawiki-' + prevVersion
            prev_mw_version = MwVersion(prevVersion)
            self.export(prev_mw_version.tag,
                        prevDir, buildDir)

            for ext in self.get_extensions_for_version(MwVersion(prevVersion),
                                                       extensions):
                self.exportExtension(branch, ext, prevDir)

            self.makePatch(
                buildDir, package + '.patch.gz', prevDir, package, 'normal')
            outFiles.append(package + '.patch.gz')
            logging.debug('%s.patch.gz written', package)
            if os.path.exists(package + '/languages/messages'):
                i18nPatch = 'mediawiki-i18n-' + version.raw + '.patch.gz'
                if (self.makePatch(
                        buildDir, i18nPatch, prevDir, package, 'i18n')):
                    outFiles.append(i18nPatch)
                    logging.info('%s written', i18nPatch)
                    haveI18n = True

        # Sign
        uploadFiles = []
        for fileName in outFiles:
            if options.sign:
                try:
                    proc = subprocess.Popen([
                        'gpg', '--detach-sign', buildDir + '/' + fileName])
                except OSError as e:
                    logging.error("gpg failed, does it exist? Skip with " +
                                  "--dont-sign.")
                    logging.error("Error %s: %s", e.errno, e.strerror)
                    sys.exit(1)
                if proc.wait() != 0:
                    logging.error("gpg failed, exiting")
                    sys.exit(1)
                uploadFiles.append(fileName + '.sig')
            uploadFiles.append(fileName)

        # Generate upload tarball
        tar = self.options.tar_command
        args = [tar, '-C', buildDir,
                '-cf', uploadDir + '/upload-' + version.raw + '.tar']
        args.extend(uploadFiles)
        proc = subprocess.Popen(args)
        if proc.wait() != 0:
            logging.error("Failed to generate upload.tar")
            return 1

        # Write email template
        print()
        print("Full release notes:")
        url = ('https://phabricator.wikimedia.org/diffusion/MW/browse/' +
               branch + '/RELEASE-NOTES-' + dir)

        print(url)
        print('https://www.mediawiki.org/wiki/Release_notes/' + dir)
        print()
        print()
        print('*' * 70)

        releaseServer = 'https://releases.wikimedia.org/mediawiki/'
        print('Download:')
        print(releaseServer + dir + '/' + package + '.tar.gz')
        print()

        if prevVersion is not None:
            if haveI18n:
                print("Patch to previous version (" + prevVersion +
                      "), without interface text:")
                print(releaseServer + dir + '/' + package + '.patch.gz')
                print("Interface text changes:")
                print(releaseServer + dir + '/' + i18nPatch)
            else:
                print("Patch to previous version (" + prevVersion + "):")
                print(releaseServer + dir + '/' + package + '.patch.gz')
            print()

        print('GPG signatures:')
        for fileName in outFiles:
            print(releaseServer + dir + '/' + fileName + '.sig')
        print()

        print('Public keys:')
        print('https://www.mediawiki.org/keys/keys.html')
        print()

        os.chdir('..')
        return 0


if __name__ == '__main__':
    options = parse_args()

    if options.log_level is None:
        options.log_level = logging.INFO

    logging.basicConfig(level=options.log_level, stream=sys.stderr)
    app = MakeRelease(options)
    sys.exit(app.main())
