from unittest import mock

from mwrelease import branch
import pytest


@mock.patch('mwrelease.branch.gerrit_client')
def test_delete(gerrit, capsys):
    gerrit.return_value.get.return_value = {'revision': '<revision>'}
    gerrit.return_value.put.return_value = [
        {
            'web_links': [
                {
                    'url': 'http://example.org/sometag',
                }
            ]
        }
    ]
    branch.delete_branch('test/gerrit-ping', 'wmf/1.99.0-wmf.99')

    captured = capsys.readouterr()
    assert captured.out == 'Created http://example.org/sometag\n'


@mock.patch('mwrelease.branch.gerrit_client')
def test_delete_noop_should_not_write(gerrit, capsys):
    gerrit.return_value.get.return_value = {'revision': '<revision>'}
    gerrit.return_value.put.side_effect = Exception
    gerrit.return_value.delete.side_effect = Exception
    branch.delete_branch('test/gerrit-ping', 'wmf/xx', noop=True)

    captured = capsys.readouterr()
    assert captured.out == (
        'Would create tag wmf/xx pointing to <revision>\n'
        'Would delete branch wmf/xx\n'
        )


@mock.patch('mwrelease.branch.gerrit_client')
def test_delete_tag_failure_does_not_delete_branch(gerrit, capsys):
    gerrit.return_value.get.return_value = {'revision': '<revision>'}
    gerrit.return_value.put.side_effect = Exception('<error>')
    delete = gerrit.return_value.delete

    with pytest.raises(Exception) as e:
        branch.delete_branch('test/gerrit-ping', 'wmf/xx')
    assert '<error>' == str(e.value)

    delete.assert_not_called()

    captured = capsys.readouterr()
    assert captured.out == (
            'Failed to create tag wmf/xx: <error>\n'
            'Aborting.\n'
    )
