"""
Test the tarball for basic sanity
"""
import os
import re
import subprocess
import tarfile
import pytest


def _mw_file(extract_dir, version, file=None):
    path = os.path.join(extract_dir, 'mediawiki-%s' % version)
    if file:
        path = os.path.join(path, file)
    return path


@pytest.mark.skip
class TestTarball(object):
    """Class for tarball tests. Class because we do incremental tests"""

    def test_version(self, mw_version):
        """Make sure version number isn't bogus"""
        assert re.match(r'\d\.\d+\.\d+.*',
                        mw_version) is not None, 'Bogus MediaWiki version'

    def test_tarball_exists(self, mw_tarball):
        """Make sure the tarfile exists and is indeed a tarfile"""
        assert (
            os.path.exists(mw_tarball) and tarfile.is_tarfile(mw_tarball)
        ), 'Tarfile missing or is not a tar'

    def test_tar_extraction(self, mw_tarball, mw_extract_dir, mw_version):
        """Extract the tarfile"""
        with tarfile.open(mw_tarball) as tar:
            def is_within_directory(directory, target):

                abs_directory = os.path.abspath(directory)
                abs_target = os.path.abspath(target)

                prefix = os.path.commonprefix([abs_directory, abs_target])

                return prefix == abs_directory

            def safe_extract(tar, path=".", members=None, *, numeric_owner=False):

                for member in tar.getmembers():
                    member_path = os.path.join(path, member.name)
                    if not is_within_directory(path, member_path):
                        raise Exception("Attempted Path Traversal in Tar File")

                tar.extractall(path, members, numeric_owner=numeric_owner)

            safe_extract(tar, mw_extract_dir)

        assert os.path.exists(
            _mw_file(mw_extract_dir, mw_version)), 'Bad tar extraction'

    def test_defaultsettings(self, mw_extract_dir, mw_version):
        """Make sure Defines.php exists and has MW_VERSION"""
        defines = _mw_file(mw_extract_dir, mw_version,
                           'includes/Defines.php')

        assert os.path.exists(defines), 'Defines missing!'

        with open(defines) as contents:
            # TODO: We should re-cycle the regex from branch.py and not duplicate.
            assert re.search(
                r'^define\(\s+\'MW_VERSION\',\s+\'{}\' \);'.format(mw_version),
                contents.read()) is not None, 'Bad/missing MW_VERSION'

    def test_install(self, mw_extract_dir, mw_version):
        """Make sure we can install (LocalSettings.php generated)"""
        data_dir = _mw_file(mw_extract_dir, mw_version, 'data')
        os.mkdir(data_dir)
        subprocess.check_call([
            'php',
            _mw_file(mw_extract_dir, mw_version, 'maintenance/install.php'),
            '--dbtype', 'sqlite',
            '--dbpath', data_dir,
            '--dbname', 'tmp',
            '--pass', 'releasetest',
            'TarballTestInstallation',
            'WikiSysop',
        ])

        assert os.path.exists(
            _mw_file(mw_extract_dir, mw_version, 'LocalSettings.php')
        ), 'LocalSettings.php not generated'
