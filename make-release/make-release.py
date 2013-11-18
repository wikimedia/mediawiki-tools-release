#!/usr/bin/python
# vim:sw=4:ts=4:et:

"""
Helper to generate a MediaWiki tarball.

If the previous version is not given, it will be derived from the next version,
and you will be prompted to confirm that the version number is correct.

If no arguments are given, a snapshot is created.
"""

import argparse
import logging
import os
import re
import subprocess
import sys
import time
import yaml

config = {}


def getVersionExtensions(version, extensions=[]):
    coreExtensions = [
        'ConfirmEdit',
        'Gadgets',
        'Nuke',
        'ParserFunctions',
        'PdfHandler',
        'Renameuser',
        'SpamBlacklist',
        'Vector',
        'WikiEditor',
    ]
    newExtensions = [
        'Cite',
        'ImageMap',
        'Interwiki',
        'TitleBlacklist',
        'SpamBlacklist',
        'Poem',
        'InputBox',
        'LocalisationUpdate',
        'SyntaxHighlight_GeSHi',
        'SimpleAntiSpam',
    ]
    oldCoreExtensions = [
        'ConfirmEdit',
        'Gadgets',
        'Nuke',
        'ParserFunctions',
        'Renameuser',
        'Vector',
        'WikiEditor',
    ]

    # Export extensions for inclusion
    if version > '1.21':
        extensions += coreExtensions + newExtensions
    elif version > '1.20':
        extensions += coreExtensions
    elif version > '1.17':
        extensions += oldCoreExtensions

    if version > '1.22':
        extensions.remove('Vector')

    # Return uniq elements (order not preserved)
    return list(set(extensions))


def versionToBranch(version):
    return 'tags/' + version


def read_config(conffile=None):
    if conffile is None:
        conffile = 'make-release.yaml'

    if not os.path.isfile(conffile):
        print "Configuration file not found: %s" % conffile
        sys.exit(1)

    return yaml.load(open(conffile))


def parse_args():
    """Parse command line arguments and return options"""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument('--conf', help='specify the configuration file')

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
        default='ssh://gerrit.wikimedia.org:29418/mediawiki',
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
        '--destDir', dest='destDir',
        default='/usr/local/share/make-release',
        help='where the tarignore (and other files necessary to '
        'create a tarball) files are stored.  (defaults to '
        '/usr/local/share/make-release)'
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

    return parser.parse_args()


class MwVersion(object):
    "Abstract out a MediaWiki version"

    def __init__(self, version):
        decomposed = self.decomposeVersion(version)

        self.raw = version
        self.major = decomposed.get('major', None)
        self.branch = decomposed.get('branch', None)
        self.prev_version = decomposed.get('prevVersion', None)
        self.prev_branch = decomposed.get('prevBranch', None)

        # alpha / beta / rc ..
        self.phase = decomposed.get('phase', None)
        self.cycle = decomposed.get('cycle', None)

    def __repr__(self):
        if self.raw is None:
            return "<MwVersion Null (snapshot?)>"

        return "<MwVersion %s major: %s (prev: %s), branch: %s (prev: %s)>" % (
            self.raw,
            self.major, self.prev_version,
            self.branch, self.prev_branch)

    def decomposeVersion(self, version):
        '''Split a version number to branch / major

        Whenever a version is recognized, a dict is returned with keys:
            - major (ie 1.22)
            - minor
            - branch
            - prevVersion
            - prevBranch

        When one or more letters are found after the minor version we consider
        it a software development phase (ex: alpha, beta, rc) with incremental
        cycles. Hence we will expose:
            - phase
            - cycle

        Default: {}
        '''

        ret = {}
        if version is None:
            return ret

        m = re.compile(r"""
            (?P<major>\d+\.\d+)
            \.
            (?P<minor>\d+)
            (?:
                (?P<phase>[A-Za-z]+)
                (?P<cycle>\d+)
            )?
        """, re.X).match(version)

        if m is None:
            return ret

        # Clear out unneed phase/cycle
        ret = dict((k, v) for k, v in m.groupdict().iteritems()
                   if v is not None)

        ret['branch'] = 'tags/%s.%s%s%s' % (
            ret['major'],
            ret['minor'],
            ret.get('phase', ''),
            ret.get('cycle', '')
        )

        last = m.group(m.lastindex)
        if int(last) == 0:
            ret['prevVersion'] = None
            return ret

        bits = [d if d is not None else '' for d in m.groups()]
        bits[m.lastindex - 1] = str(int(bits[m.lastindex - 1]) - 1)

        ret['prevVersion'] = '%s.%s%s%s' % tuple(bits)
        ret['prevBranch'] = 'tags/' + ret['prevVersion']

        return ret


class MakeRelease(object):
    "Surprisingly: do a MediaWiki release"

    options = None
    version = None  # MwVersion object

    def __init__(self, options):
        self.version = MwVersion(options.version)
        self.options = options

    def main(self):
        " return value should be usable as an exit code"

        global config  # yeah globals are evil. We know.
        config = read_config(options.conf)

        # TODO we should validate the YAML configuration file

        extensions = []
        bundles = config.get('bundles')
        smwExtensions = bundles.get('smw')

        print "Doing release for %s" % self.version

        if self.version.branch is None:
            print "No branch, assuming '%s'. Override with --branch." % (
                  options.branch)
            self.version.branch = options.branch

        # No version specified, assuming a snapshot release
        if options.version is None:
            self.makeRelease(
                version='snapshot-' + time.strftime('%Y%m%d', time.gmtime()),
                dir='snapshots')
            return 0

        if options.smw:
            # Other extensions for inclusion
            for ext in smwExtensions:
                extensions.append(ext)

        if options.previousversion:
            # Given the previous version on the command line
            self.makeRelease(
                extensions=extensions,
                version=options.version,
                dir=self.version.major)
            return 0

        noPrevious = False
        if self.version.prev_version is None:
            if not self.ask("No previous release found. Do you want to make a "
                            "release with no patch?"):
                print('Please specify the correct previous release '
                      'on the command line')
                return 1
            else:
                noPrevious = True

        if noPrevious:
            self.makeRelease(
                extensions=extensions,
                version=options.version,
                dir=self.version.major)
        else:
            if not self.ask("Was %s the previous release?" %
                            self.version.prev_version):
                print('Please specify the correct previous release '
                      'on the command line')
                return 1

            self.makeRelease(
                extensions=extensions,
                version=options.version,
                dir=options.buildroot)
        return 0

    def ask(self, question):
        if self.options.yes:
            return True

        while True:
            print question + ' [y/n] ',
            response = sys.stdin.readline()
            if len(response) > 0:
                if response[0].lower() == 'y':
                    return True
                elif response[0].lower() == 'n':
                    return False
            print 'Please type "y" for yes or "n" for no'

    def getGit(self, repo, dir, label):
        if os.path.exists(repo):
            print "Updating local %s" % repo
            proc = subprocess.Popen(['git', 'remote', 'update'],
                                    cwd=repo)
            if proc.wait() != 0:
                print "Could not update local repository %s" % repo
                sys.exit(1)

        if (os.path.exists(dir)):
            print "Updating " + label + " in " + dir + "..."
            proc = subprocess.Popen(
                ['sh', '-c', 'cd ' + dir + '; git fetch -q --all'])
        else:
            print "Cloning " + label + " into " + dir + "..."
            proc = subprocess.Popen(['git', 'clone', '-q', repo, dir])

        if proc.wait() != 0:
            print "git clone failed, exiting"
            sys.exit(1)

    def patchExport(self, patch, dir):

        gitRoot = self.options.gitroot

        os.chdir(dir)
        print "Applying patch %s" % patch

        # git fetch the reference from Gerrit and cherry-pick it
        proc = subprocess.Popen(['git', 'fetch', gitRoot + '/core', patch,
                                 '&&', 'git', 'cherry-pick', 'FETCH_HEAD'])

        if proc.wait() != 0:
            print "git patch failed, exiting"
            sys.exit(1)

        os.chdir('..')
        print "Done"

    def export(self, tag, module, exportDir):

        gitRoot = self.options.gitroot

        dir = exportDir + '/' + module
        self.getGit(gitRoot + '/core', dir, "core")

        os.chdir(dir)

        if tag != 'trunk':
            print "Checking out %s..." % (tag)
            proc = subprocess.Popen(['git', 'checkout', tag])

            if proc.wait() != 0:
                print "git checkout failed, exiting"
                sys.exit(1)

        os.chdir('..')
        print "Done"

    def exportExtension(self, branch, extension, dir):
        gitroot = self.options.gitroot
        if self.options.gitrootext:
            gitroot = self.options.gitrootext

        self.getGit(gitroot + '/extensions/' + extension,
                    dir + '/extensions/' + extension, extension)
        print "Done"

    def makePatch(self, destDir, patchFileName, dir1, dir2, type):
        patchFile = open(destDir + "/" + patchFileName, 'w')
        args = ['diff', '-Nruw']
        if type == 'i18n':
            print "Generating i18n patch file..."
            dir1 += '/languages/messages'
            dir2 += '/languages/messages'
        else:
            print "Generating normal patch file..."
            excludedExtensions = [
                'messages',
                '*.png',
                '*.jpg',
                '*.xcf',
                '*.gif',
                '*.svg',
                '*.tiff',
                '*.zip',
                '*.xmp',
                '.git*',
            ]
            for ext in excludedExtensions:
                args.extend(['-x', ext])

        args.extend([dir1, dir2])
        print ' '.join(args)
        diffProc = subprocess.Popen(args, stdout=subprocess.PIPE)
        gzipProc = subprocess.Popen(['gzip', '-9'], stdin=diffProc.stdout,
                                    stdout=patchFile)

        diffStatus = diffProc.wait()
        gzipStatus = gzipProc.wait()

        if diffStatus > 1 or gzipStatus != 0:
            print "diff failed, exiting"
            print "diff: " + str(diffStatus)
            print "gzip: " + str(gzipStatus)
            sys.exit(1)
        patchFile.close()
        print "Done"
        return diffStatus == 1

    def makeTarFile(self, package, targetDir, dir, argAdd=[]):
        tar = self.options.tar_command

        tarignore = self.options.destDir + '/tarignore'
        if not os.path.isfile(tarignore):
            "Tarignore %s not found, IGNORING." % tarignore
            tarignore = None

        # Generate the .tar.gz file
        filename = package + '.tar.gz'
        outFile = open(dir + '/' + filename, "w")
        args = [tar, '--format=gnu', '--exclude-vcs', '-C', dir]
        if tarignore:
            args += ['--exclude-from', tarignore]
        args += argAdd
        args += ['-c', targetDir]
        print "Creating " + filename
        tarProc = subprocess.Popen(args, stdout=subprocess.PIPE)
        gzipProc = subprocess.Popen(['gzip', '-9'], stdin=tarProc.stdout,
                                    stdout=outFile)

        if tarProc.wait() != 0 or gzipProc.wait() != 0:
            print "tar/gzip failed, exiting"
            sys.exit(1)
        outFile.close()
        print filename + ' written'
        return filename

    def makeRelease(self, version, dir, extensions=[]):

        rootDir = self.options.buildroot

        # variables related to the version
        branch = self.version.branch
        #prevBranch = self.version.prev_branch
        prevVersion = self.version.prev_version

        if rootDir is None:
            rootDir = os.getcwd()

        if not os.path.exists(rootDir):
            print 'Creating ' + rootDir
            os.mkdir(rootDir)

        buildDir = rootDir + '/build'
        uploadDir = rootDir + '/uploads'

        if not os.path.exists(buildDir):
            print 'Creating build dir: ' + buildDir
            os.mkdir(buildDir)
        if not os.path.exists(uploadDir):
            print 'Creating uploads dir: ' + uploadDir
            os.mkdir(uploadDir)

        os.chdir(buildDir)

        if not os.path.exists(dir):
            os.mkdir(dir)

        package = 'mediawiki-' + version

        # Export the target
        self.export(branch, package, buildDir)

        patchRevisions = []
        for patch in patchRevisions:
            self.patchExport(patch, package)

        extExclude = []
        for ext in getVersionExtensions(version, extensions):
            self.exportExtension(branch, ext, package)
            extExclude.append("--exclude")
            extExclude.append("extensions/" + ext)

        # Generate the .tar.gz files
        outFiles = []
        outFiles.append(
            self.makeTarFile(
                package='mediawiki-core-' + version,
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
        if prevVersion is not None:
            prevDir = 'mediawiki-' + prevVersion
            self.export(versionToBranch(prevVersion),
                        prevDir, buildDir)

            for ext in getVersionExtensions(prevVersion, extensions):
                self.exportExtension(branch, ext, prevDir)

            self.makePatch(
                buildDir, package + '.patch.gz', prevDir, package, 'normal')
            outFiles.append(package + '.patch.gz')
            print package + '.patch.gz written'
            haveI18n = False
            if os.path.exists(package + '/languages/messages'):
                i18nPatch = 'mediawiki-i18n-' + version + '.patch.gz'
                if (self.makePatch(
                        buildDir, i18nPatch, prevDir, package, 'i18n')):
                    outFiles.append(i18nPatch)
                    print i18nPatch + ' written'
                    haveI18n = True

        # Sign
        uploadFiles = []
        for fileName in outFiles:
            if options.sign:
                try:
                    proc = subprocess.Popen([
                        'gpg', '--detach-sign', buildDir + '/' + fileName])
                except OSError, e:
                    print "gpg failed, does it exist? Skip with --dont-sign."
                    print "Error %s: %s" % (e.errno, e.strerror)
                    sys.exit(1)
                if proc.wait() != 0:
                    print "gpg failed, exiting"
                    sys.exit(1)
                uploadFiles.append(fileName + '.sig')
            uploadFiles.append(fileName)

        # Generate upload tarball
        tar = self.options.tar_command
        args = [tar, '-C', buildDir,
                '-cf', uploadDir + '/upload-' + version + '.tar']
        args.extend(uploadFiles)
        proc = subprocess.Popen(args)
        if proc.wait() != 0:
            print "Failed to generate upload.tar"
            return 1

        # Write email template
        print
        print "Full release notes:"
        url = ('https://git.wikimedia.org/blob/mediawiki%2Fcore.git/'
               + branch + '/RELEASE-NOTES')
        if dir > '1.17':
            url += '-' + dir

        print url
        print 'https://www.mediawiki.org/wiki/Release_notes/' + dir
        print
        print
        print '*' * 70

        print 'Download:'
        print ('http://download.wikimedia.org/mediawiki/'
               + dir + '/' + package + '.tar.gz')
        print

        if prevVersion is not None:
            if haveI18n:
                print ("Patch to previous version (" + prevVersion
                       + "), without interface text:")
                print ('http://download.wikimedia.org/mediawiki/'
                       + dir + '/' + package + '.patch.gz')
                print "Interface text changes:"
                print ('http://download.wikimedia.org/mediawiki/'
                       + dir + '/' + i18nPatch)
            else:
                print "Patch to previous version (" + prevVersion + "):"
                print ('http://download.wikimedia.org/mediawiki/'
                       + dir + '/' + package + '.patch.gz')
            print

        print 'GPG signatures:'
        for fileName in outFiles:
            print ('http://download.wikimedia.org/mediawiki/'
                   + dir + '/' + fileName + '.sig')
        print

        print 'Public keys:'
        print 'https://www.mediawiki.org/keys/keys.html'
        print

        os.chdir('..')
        return 0

if __name__ == '__main__':
    options = parse_args()

    if options.log_level is None:
        options.log_level = logging.INFO

    logging.basicConfig(level=options.log_level, stream=sys.stderr)
    app = MakeRelease(options)
    sys.exit(app.main())
