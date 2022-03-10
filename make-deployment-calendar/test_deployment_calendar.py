"""
Test deployment calendar
"""
import datetime
import time
import os
from unittest import mock

import pytest

import deploymentcalendar


def test_parse_date():
    # parse_date uses naive datetime which is not TZ aware
    expected = time.mktime(
        datetime.date(2020, 12, 1).timetuple()
        )
    dec_1 = deploymentcalendar.findtrain.parse_date('Tue 1 Dec 2020')
    assert dec_1.timestamp() == expected


def test_get_next_monday():
    # parse_date uses naive datetime which is not TZ aware
    expected = time.mktime(
        datetime.date(2020, 11, 30).timetuple()
        )
    next_monday = deploymentcalendar.findtrain.get_next_monday(
        deploymentcalendar.findtrain.parse_date('Mon 30 Nov 2020')
    )
    assert next_monday.timestamp() == expected


def test_flatten_for_post():
    """
    Flatten for post test
    """
    assert deploymentcalendar.findtrain.flatten_for_post({
        'data': {
            'api-token': 'foo',
        }}) == {'data[api-token]': 'foo'}


def test_phab_get_conduit_token():
    os.environ['CONDUIT_TOKEN'] = 'x'
    p = deploymentcalendar.findtrain.Phab()
    assert p._get_token() == 'x'


@mock.patch.dict('os.environ', clear=True)
def test_phab_query_handles_error():
    with mock.patch('deploymentcalendar.findtrain.requests') as r:
        response = r.post.return_value = mock.Mock()
        response.json.return_value = {
            'error_code': '42',
            'error_info': 'the universal response',
            }
        with pytest.raises(
            Exception,
            match='Phabricator API error 42: the universal response'
        ):
            deploymentcalendar.findtrain.Phab().query('x', {})


if __name__ == '__main__':
    pytest.main()
