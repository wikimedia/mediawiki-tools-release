#!/usr/bin/python
# vim:sw=4:ts=4:et:

"""
Helper to generate a MediaWiki tarball.

example:
  ./make-release 1.19.0
  ./make-release  # takes a snapshot

If the previous version is not given, it will be derived from the next version,
and you will be prompted to confirm that the version number is correct. To
always answer "yes", use the --yes option.

Use --no-previous to disable the diff to previous entirely.
"""

import argparse
import hashlib
import os
import re
import subprocess
import sys
import time


def dieUsage():
    print __doc__
    sys.exit(1)


def main():
    " return value should be usable as an exit code"
    options = parse_args()

    extensions = []
    smwExtensions = [
        'SemanticMediaWiki',
        'SemanticResultFormats',
        'SemanticForms',
        'SemanticCompoundQueries',
        'SemanticInternalObjects',
        'SemanticDrilldown',
        'SemanticMaps',
        'SemanticWatchlist',
        'SemanticTasks',
        'SemanticFormsInputs',
        'SemanticImageInput',
        'Validator',
        'AdminLinks',
        'ApprovedRevs',
        'Arrays',
        'DataTransfer',
        'ExternalData',
        'HeaderTabs',
        'Maps',
        'PageSchemas',
        'ReplaceText',
        'Widgets',
    ]

    # No version specified, assuming a snapshot release
    if options.nextversion is None:
        makeRelease(
            version='snapshot-' + time.strftime('%Y%m%d', time.gmtime()),
            branch='trunk',
            dir='snapshots',
            gitRoot=options.gitroot)
        return 0

    decomposed = decomposeVersion(options.nextversion)
    if decomposed is None:
        print 'Invalid version number "%s"' % (options.nextversion)
        return 1

    version = decomposed['major']

    if options.smw:
        # Other extensions for inclusion
        for ext in smwExtensions:
            extensions.append(ext)

    if options.previousversion:
        # Given the previous version on the command line
        makeRelease(
            extensions=extensions,
            version=options.nextversion,
            prevVersion=options.previousversion,
            prevBranch=versionToBranch(options.previousversion),
            branch=decomposed['branch'],
            dir=decomposed['major'],
            gitRoot=options.gitroot)
        return 0

    if decomposed['prevVersion'] is None:
        if not ask("No previous release found. Do you want to make a release"
                   "with no patch?"):
            print('Please specify the correct previous release'
                  'on the command line')
            return 1
        else:
            noPrevious = True

    if noPrevious:
        makeRelease(
            extensions=extensions,
            version=options.nextversion,
            branch=decomposed['branch'],
            dir=decomposed['major'],
            gitRoot=options.gitroot)
    else:
        if not ask("Was %s the previous release?" % (
                   decomposed['prevVersion'])):
            print('Please specify the correct previous release'
                  'on the command line')
            return 1

        makeRelease(
            extensions=extensions,
            version=options.nextversion,
            prevVersion=decomposed['prevVersion'],
            prevBranch=decomposed['prevBranch'],
            branch=decomposed['branch'],
            dir=decomposed['major'],
            gitRoot=options.gitroot)
    return 0


def parse_args():
    """Parse command line arguments and returns options"""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Positional arguments:
    parser.add_argument(
        'nextversion', nargs='?',
        help='version you are about to release')
    parser.add_argument(
        'previousversion', nargs='?',
        help='version that came before')

    # Optional arguments:
    parser.add_argument(
        '--yes', dest='yes', action='store_true',
        help='answer yes to any question'
    )
    parser.add_argument(
        '--no-previous', dest='no-previous', action='store_true',
        help='disable the diff with previous version'
    )
    parser.add_argument(
        '--git-root', dest='gitroot',
        default='ssh://gerrit.wikimedia.org:29418/mediawiki',
        help='base git URL to fetch projects from (defaults to Gerrit)'
    )
    parser.add_argument(
        '--smw', dest='smw', action='store_true',
        help='include the SemanticMediaWiki bundle'
    )

    return parser.parse_args()


def ask(question):
    while True:
        print question + ' [y/n] ',
        response = sys.stdin.readline()
        if len(response) > 0:
            if response[0].lower() == 'y':
                return True
            elif response[0].lower() == 'n':
                return False
        print 'Please type "y" for yes or "n" for no'


def decomposeVersion(version):
    ret = {}
    m = re.compile('(\d+)\.(\d+)\.(\d+)$').match(version)
    if m is not None:
        ret['major'] = m.group(1) + "." + m.group(2)
        ret['branch'] = ('tags/' + m.group(1) + '.' + m.group(2)
                         + '.' + m.group(3))
        if int(m.group(3)) == 0:
            ret['prevVersion'] = None
        else:
            newMinor = str(int(m.group(3)) - 1)
            ret['prevVersion'] = ret['major'] + '.' + newMinor
            ret['prevBranch'] = ('tags/' + m.group(1) + '.' + m.group(2)
                                 + '.' + newMinor)
        return ret

    m = re.compile('(\d+)\.(\d+)\.(\d+)([A-Za-z]+)(\d+)$').match(version)
    if m is None:
        return None

    ret['major'] = m.group(1) + "." + m.group(2)
    ret['branch'] = ('tags/' + m.group(1) + '.' + m.group(2) + '.'
                     + m.group(3) + m.group(4) + m.group(5))
    if int(m.group(5)) == 0:
        ret['prevVersion'] = None
    else:
        newMinor = str(int(m.group(5)) - 1)
        ret['prevVersion'] = (ret['major'] + "." + m.group(3)
                              + m.group(4) + newMinor)
        ret['prevBranch'] = ('tags/' + m.group(1) + '.' + m.group(2)
                             + '.' + m.group(3) + m.group(4) + newMinor)
    return ret


def versionToBranch(version):
    return 'tags/' + version


def hashfile(fileName, algorithm):
    f = open(fileName, 'r')
    hash = hashlib.new(algorithm)
    while True:
        buf = f.read(16384)
        if buf == '':
            break
        hash.update(buf)
    f.close()
    return hash.hexdigest()


def getGit(repo, dir, label):
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


def patchExport(patch, dir, gitRoot):
    os.chdir(dir)
    print "Applying patch " . patch

    # git fetch the reference from Gerrit and cherry-pick it
    proc = subprocess.Popen(['git', 'fetch', gitRoot + '/core', patch,
                             '&&', 'git', 'cherry-pick', 'FETCH_HEAD'])

    if proc.wait() != 0:
        print "git patch failed, exiting"
        sys.exit(1)

    os.chdir('..')
    print "Done"


def export(tag, dir, gitRoot):
    getGit(gitRoot + '/core.git', dir, "core")

    os.chdir(dir)

    if tag != 'trunk':
        print "Checking out %s..." % (tag)
        proc = subprocess.Popen(['git', 'checkout', tag])

        if proc.wait() != 0:
            print "git checkout failed, exiting"
            sys.exit(1)

    os.chdir('..')
    print "Done"


def exportExtension(branch, extension, dir, gitRoot):
    getGit(gitRoot + '/extensions/' + extension + '.git',
           dir + '/extensions/' + extension, extension)
    print "Done"


def makePatch(patchFileName, dir1, dir2, type):
    patchFile = open(patchFileName, 'w')
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

    return extensions


def makeTarFile(package, file, dir, rootDir, argAdd=[]):
    # Generate the .tar.gz file
    outFile = open(dir + '/' + file + '.tar.gz', 'w')
    args = ['tar', '--format=gnu', '--exclude-vcs',
            '--exclude-from', rootDir + '/tarignore']
    args += argAdd
    args += ['-c', package]
    print ' '.join(args)
    exit
    tarProc = subprocess.Popen(args, stdout=subprocess.PIPE)
    gzipProc = subprocess.Popen(['gzip', '-9'], stdin=tarProc.stdout,
                                stdout=outFile)

    if tarProc.wait() != 0 or gzipProc.wait() != 0:
        print "tar/gzip failed, exiting"
        sys.exit(1)
    outFile.close()
    targz = file + '.tar.gz'
    print targz + ' written'
    return targz


def makeRelease(version, branch, dir, gitRoot, prevVersion=None,
                prevBranch=None, extensions=[]):
    if not os.path.exists('build'):
        os.mkdir('build')
    if not os.path.exists('uploads'):
        os.mkdir('uploads')
    rootDir = os.getcwd()
    os.chdir('build')

    if not os.path.exists(dir):
        os.mkdir(dir)

    package = 'mediawiki-' + version

    # Export the target
    export(branch, package, gitRoot)

    patchRevisions = []
    for patch in patchRevisions:
        patchExport(patch, package, gitRoot)

    extExclude = []
    for ext in getVersionExtensions(version, extensions):
        exportExtension(branch, ext, package, gitRoot)
        extExclude.append("--exclude")
        extExclude.append("extensions/" + ext)

    # Generate the .tar.gz files
    outFiles = []
    outFiles.append(makeTarFile(package, 'mediawiki-core-' + version, dir,
                                rootDir, extExclude))
    outFiles.append(makeTarFile(package, package, dir, rootDir))

    # Patch
    if prevVersion is not None:
        prevDir = 'mediawiki-' + prevVersion
        export(prevBranch, prevDir, gitRoot)

        for ext in getVersionExtensions(prevVersion, extensions):
            exportExtension(branch, ext, prevDir, gitRoot)

        makePatch(dir + '/' + package + '.patch.gz',
                  prevDir, package, 'normal')
        outFiles.append(package + '.patch.gz')
        print package + '.patch.gz written'
        haveI18n = False
        if os.path.exists(package + '/languages/messages'):
            i18nPatch = 'mediawiki-i18n-' + version + '.patch.gz'
            if (makePatch(dir + '/' + i18nPatch, prevDir, package, 'i18n')):
                outFiles.append(i18nPatch)
                print i18nPatch + ' written'
                haveI18n = True

    # Sign
    uploadFiles = []
    for fileName in outFiles:
        proc = subprocess.Popen(['gpg', '--detach-sign', dir + '/' + fileName])
        if proc.wait() != 0:
            print "gpg failed, exiting"
            sys.exit(1)
        uploadFiles.append(dir + '/' + fileName)
        uploadFiles.append(dir + '/' + fileName + '.sig')

    # Generate upload tarball
    args = ['tar', 'cf', '../uploads/upload-' + version + '.tar']
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
    sys.exist(main())
