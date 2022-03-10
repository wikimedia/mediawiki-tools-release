#!/usr/bin/env python3
import argparse
from datetime import datetime, timedelta, timezone
import json
import os

import requests

from dateutil import parser
from dateutil.utils import within_delta

import deploymentcalendar.relengers


def get_next_monday(start_date):
    """
    Gets the following monday after start_date

    :params start_date: either a string or a datetime
    :return: datetime
    """
    weekday = start_date.weekday()

    weeks = 1
    if weekday == 0:
        weeks = 0

    return start_date + timedelta(
        days=-weekday,
        hours=-start_date.hour,
        minutes=-start_date.minute,
        seconds=-start_date.second,
        microseconds=-start_date.microsecond,
        weeks=weeks
    )


def flatten_for_post(h, result=None, kk=None):
    """
    Since phab expects x-url-encoded form post data (meaning each
    individual list element is named). AND because, evidently, requests
    can't do this for me, I found a solution via stackoverflow.

    See also:
    <https://secure.phabricator.com/T12447>
    <https://stackoverflow.com/questions/26266664/requests-form-urlencoded-data/36411923>
    """
    if result is None:
        result = {}

    if isinstance(h, str) or isinstance(h, bool):
        result[kk] = h
    elif isinstance(h, list) or isinstance(h, tuple):
        for i, v1 in enumerate(h):
            flatten_for_post(v1, result, '%s[%d]' % (kk, i))
    elif isinstance(h, dict):
        for (k, v) in h.items():
            key = k if kk is None else "%s[%s]" % (kk, k)
            if isinstance(v, dict):
                for i, v1 in v.items():
                    flatten_for_post(v1, result, '%s[%s]' % (key, i))
            else:
                flatten_for_post(v, result, key)
    return result


class Train(object):
    """
    Object to hold information about the oncoming train
    """
    def __init__(self, task):
        self.task = task
        self.users = {}

        self.release_date = task['fields']['custom.release.date']
        self.task_id = 'T{}'.format(task['id'])
        self.primary_phid = task['fields'].get(
            'ownerPHID',
            deploymentcalendar.relengers.DEFAULT
        )
        secondaries = task['fields']['custom.train.backup']
        if secondaries:
            self.secondary_phid = secondaries[0]
        else:
            self.secondary_phid = deploymentcalendar.relengers.DEFAULT
        self.version = task['fields']['custom.release.version']
        self.task = task

    @property
    def primary(self):
        return deploymentcalendar.relengers.get(
            self.users[self.primary_phid]
        )

    @property
    def secondary(self):
        return deploymentcalendar.relengers.get(
            self.users[self.secondary_phid]
        )

    @property
    def schedule(self):
        primary_schedule = self.primary.schedule
        secondary_schedule = self.secondary.schedule
        if primary_schedule == secondary_schedule:
            return primary_schedule

        return '{}+{}'.format(primary_schedule, secondary_schedule)


class TrainFinder(object):
    """
    Logic for finding the train in phab
    """
    def __init__(self, date, phab):
        self.date = date
        self.phab = phab
        self.tasks = self._tasks()

        self.next = None
        self.last = None
        self.is_declined = False
        self._train_tasks()

    def _tasks(self):
        tasks = self.phab.query(
            'maniphest.search',
            {
                'queryKey': 'k5YunDeBIWUo',
            }
        )

        return tasks['result']['data']

    def _train_tasks(self):
        """
        Uses stored query to find oldest open train blocker task returns PHID

        This should be the current train...in theory :)
        """
        next_monday = int(self.date.timestamp())
        return_next = False

        for task in self.tasks:
            release_date = task['fields']['custom.release.date']

            # This is set after we find the *next* train
            if return_next:
                if task['fields']['status']['value'] == 'declined':
                    continue
                self.last = Train(task)
                self._populate_users(self.last)
                return

            # if release_date == next_monday:
            # If within 12 hours, close enough
            if within_delta(release_date, next_monday, 43200):
                if task['fields']['status']['value'] == 'declined':
                    self.is_declined = True
                    return
                self.next = Train(task)
                self._populate_users(self.next)
                return_next = True

    def _populate_users(self, task):
        """
        Query phab for users by phid

        :param: users - list of phids
        """
        users = self.phab.query('phid.query', {
            'phids': [task.primary_phid, task.secondary_phid]
        })

        for user in [x for x in users['result'].keys()]:
            username = users['result'][user]['name']
            phid = users['result'][user]['phid']
            task.users[phid] = username


class Phab(object):
    def __init__(self):
        self.phab_url = 'https://phabricator.wikimedia.org/api/'

        self.conduit_token = self._get_token()

    def _get_token(self):
        """
        Use the $CONDUIT_TOKEN envvar, fallback to whatever is in ~/.arcrc
        """
        token = None
        token_path = os.path.expanduser('~/.arcrc')
        if os.path.exists(token_path):
            with open(token_path) as f:
                arcrc = json.load(f)
                token = arcrc['hosts'][self.phab_url]['token']

        return os.environ.get('CONDUIT_TOKEN', token)

    def query(self, method, data):
        """
        Helper method to query phab via requests and return json
        """
        data['api.token'] = self.conduit_token
        data = flatten_for_post(data)
        r = requests.post(
            os.path.join(self.phab_url, method),
            data=data)
        r.raise_for_status()
        response = r.json()
        if response.get('error_code') is not None:
            raise Exception(
                'Phabricator API error %s: %s' % (
                    response['error_code'],
                    response['error_info'],
                )
            )
        return response


def find_train_finder(monday):
    phab = Phab()
    return TrainFinder(monday, phab)


def parse_date(date_string):
    """
    Take some date and give you the UTC version

    :params date_string: string like "Monday"
    :return: datetime
    """
    return parser.parse(date_string, ignoretz=True)


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        '-s',
        '--start-date',
        type=parse_date,
        default=datetime.now(tz=timezone.utc)
    )

    return ap.parse_args()


if __name__ == '__main__':
    args = parse_args()
    monday = get_next_monday(start_date=args.start_date)
    tf = find_train_finder(monday)

    if tf.is_declined:
        print(' '.join([
            './deployments-calendar',
            '--schedule=NoTrain',
        ]))
    else:
        primary = tf.next.primary
        secondary = tf.next.secondary

        primary = '{{ircnick|%s|%s}}' % (primary.ircnick, primary.fullname)
        secondary = '{{ircnick|%s|%s}}' % (secondary.ircnick, secondary.fullname)

        deployers = ', '.join([primary, secondary])

        print(' '.join([
            './deployments-calendar',
            '--schedule={}'.format(tf.next.schedule),
            'train --old {}'.format(tf.last.version),
            '--new {}'.format(tf.next.version),
            "--deployer='{}'".format(deployers),
            '--blocker-task={}'.format(tf.next.task_id),
        ]))
