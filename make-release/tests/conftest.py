"""
Various fixtures for the tarball release test
"""

import os
import shutil
import pytest


# Hooks
def pytest_addoption(parser):
    """Get our tarball version to test"""
    parser.addoption('--mw-version', action='store', default=None,
                     help='What MediaWiki tarball version to test')


def pytest_collection_modifyitems(config, items):
    """Skip tests that require the tarball"""
    if config.getoption('--mw-version'):
        return
    for item in items:
        if 'tarball_test' in item.keywords:
            item.add_marker(pytest.mark.skip(
                reason='Need --mw-version option to run'))


def pytest_runtest_makereport(item, call):
    """Report failures due to incremental nature"""
    if 'tarball_test' in item.keywords:
        if call.excinfo is not None:
            item.parent._previousfailed = item


def pytest_runtest_setup(item):
    """Fail tests due to incremental nature"""
    if 'tarball_test' in item.keywords:
        previousfailed = getattr(item.parent, '_previousfailed', None)
        if previousfailed is not None:
            pytest.xfail('previous test failed (%s)' % previousfailed.name)


# Fixtures
@pytest.fixture
def mw_version(request):
    """Return the MW version we'll test"""
    return request.config.getoption('--mw-version')


@pytest.fixture
def mw_tarball(request):
    """Return the MW tarball we'll test"""
    return os.path.join(
        os.path.dirname(__file__), '..', 'build',
        'mediawiki-%s.tar.gz' % request.config.getoption('--mw-version'))


@pytest.fixture(scope='session')
def mw_extract_dir(tmpdir_factory):
    """Static temporary directory for tar extraction"""
    temp = str(tmpdir_factory.mktemp('mediawiki'))
    yield temp
    shutil.rmtree(temp)
