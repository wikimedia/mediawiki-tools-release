"""
Test deployment calendar
"""
import os

import pytest

import deploymentcalendar

from datetime import datetime, timezone


def test_parse_date():
    dec_1 = deploymentcalendar.findtrain.parse_date('Tue 1 Dec 2020')
    assert  dec_1.timestamp() == 1606806000


def test_get_next_monday():
    nov_30 = 1606719600
    next_monday = deploymentcalendar.findtrain.get_next_monday(
        deploymentcalendar.findtrain.parse_date('Mon 30 Nov 2020')
    )
    assert next_monday.timestamp() == nov_30


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
