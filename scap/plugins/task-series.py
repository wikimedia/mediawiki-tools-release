# This Python file uses the following encoding: utf-8

from __future__ import print_function, unicode_literals

import argparse
import datetime
import re

from calendar import Calendar
from phabricator import Phabricator
from scap import cli, log
from scap.utils import var_dump
from datetime import timedelta


ONEWEEK = timedelta(weeks=1)


def trunc(len, string, ellipsis=" …"):
    return string[0:len] + ellipsis


def action_arg(*args, **kwargs):
    kwargs['const'] = kwargs['action']
    kwargs['dest'] = 'action'
    kwargs['action'] = 'store_const'
    kwargs['metavar'] = 'ACTION'
    return cli.argument(*args, **kwargs)


# function by jfs, see https://stackoverflow.com/a/8778548/1672995
def totimestamp(dt, epoch=datetime.datetime(1970, 1, 1)):
    td = dt - epoch
    # return td.total_seconds()
    return int(
        (td.microseconds + (td.seconds + td.days * 86400) * 10**6) / 10**6
    )


def find_mondays(year, month):
    cal = Calendar()
    mondays = list()
    for week in cal.monthdays2calendar(year, month):
        for day in week:
            (monthday, weekday) = day
            if (weekday == 1 and monthday > 0):
                mondays.append(datetime.date(year=year,
                                             month=month,
                                             day=monthday))
    return mondays


phab = Phabricator(host='https://phabricator.wikimedia.org/api/')


def phab_taskid(taskid):
    if not taskid.startswith("T"):
        raise Exception("Invalid task id: %s", taskid)
    return taskid


def mediawiki_version(ver):
    """Validation our version number formats"""
    try:
        return re.match("(\\d+\\.\\d+(\\.\\d+-)?wmf\\.?\\d+)", ver).group(0)
    except Exception:
        raise argparse.ArgumentTypeError(
            "Invalid wmf version '%s' expected: #.##.#-wmf.#" % ver)


def date_str(datestr):
    formats = ['%x', '%m-%d-%Y', '%Y%m%d', '%Y-%m-%d']
    err = None
    date = None
    for format in formats:
        try:
            date = datetime.datetime.strptime(datestr, format)
        except Exception as ex:
            err = ex

    if date is None and err is not None:
        raise err

    return date


def map_transactions(obj):
    trns = []

    for key, val in obj.items():
        trns.append({
            "type": key,
            "value": val
        })
    return trns


@cli.command('blockers', subcommands=True)
class ReleaseBlockers(cli.Application):
    """
    Manage the deployment-blockers task series in phabricator.


    Command Usage:

        Create 10 release-blocker tasks, beginning with version 1.30.0-wmf.1
        on 2017-01-01:

        $ scap blockers create --count 10 --date 2017-01-01 1.30.0-wmf.1

        Show the phabricator task id for 1.32.0-wmf.5:

        $ scap blockers show --release 1.32.0-wmf.5

        List the 10 upcoming release versions and the corresponding task ids:

        $ scap blockers show --count 10

        Show the task id of the oldest open release task:

        $ scap blockers show

    """
    action = None

    def _setup_loggers(self):
        """Setup logging."""
        log.setup_loggers(self.config, self.arguments.loglevel + 10)

    def _process_arguments(self, args, extra_args):
        # print(args,extra_args)
        return args, extra_args

    @cli.argument('--count', help='Number of tasks to create, default=1',
                  metavar='NUM', default=1, type=int)
    @cli.argument('--date', help='Date of the first release,\
                  default=today\'s date', metavar='START',
                  type=date_str, default=datetime.datetime.utcnow())
    @cli.argument('release', help='Create tasks beginning with VERSION',
                  metavar='VERSION', type=mediawiki_version)
    @cli.subcommand('create')
    def blockers(self, *args):
        '''
        Create Release Blockers.
        '''
        v = self.arguments.release.split('-')
        wmfnum = int(v[-1].split('.')[-1])
        week = self.arguments.date
        weekday = week.weekday()
        if weekday:
            # ofset some days so that we always use monday of the given week:
            week -= timedelta(days=weekday)

        for n in range(wmfnum, wmfnum + self.arguments.count):
            v[-1] = 'wmf.%d' % n
            vs = "-".join(v)

            ts = totimestamp(week)
            trns = map_transactions({
                'title': "%s deployment blockers" % vs,
                'subtype': 'release',
                'projects.add': ["PHID-PROJ-fmcvjrkfvvzz3gxavs3a",
                                 "PHID-PROJ-pf35un2jsnsiriivnmeo"],
                'custom.release.version': str(vs),
                'custom.release.date': ts,
            })
            print("%s : %s, %s" % (vs, week, ts))
            var_dump(phab.maniphest.edit(transactions=trns))
            week += ONEWEEK

    @cli.argument('--count', help='Show at most this many tasks',
                  metavar='NUM', default=1, type=int)
    @cli.argument('--current', help='Show the current release branch version',
                  action='store_true')
    @cli.argument('--release', help="Show the task id for a specific version",
                  metavar='VERSION', type=mediawiki_version)
    @cli.subcommand('show')
    def show(self, *args):
        '''
        Show a list of deployment blockers tasks
        '''
        limit = self.arguments.count
        constraints = {}
        if self.arguments.current:
            limit = 1
        if self.arguments.release:
            constraints['query'] = self.arguments.release
            limit = 1

        res = phab.maniphest.search(
            queryKey="GTbIUdDaMLqV",
            constraints=constraints,
            limit=limit)

        for task in res.data:
            if self.arguments.current:
                print(task['fields']['custom.release.version'])
            elif limit > 1:
                print(
                    "T%d %s %s" %
                    (task["id"],
                     task['fields']['status']['name'],
                     task['fields']['custom.release.version']))
            else:
                print("T%d" % task["id"])
