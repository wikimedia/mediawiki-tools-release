#!/usr/bin/env python3
# Copyright © 2021 Tyler Cipriani
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
# http://www.gnu.org/copyleft/gpl.html
#
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
import re
import sys
from textwrap import dedent

from croniter import croniter
import jinja2

import deploymentcalendar.findtrain

BASE_PATH = os.path.dirname(os.path.realpath(sys.argv[0]))
DEFAULT_CONFIG = os.path.join(BASE_PATH, '..', 'deployments-calendar.json')
DAYS_OF_THE_WEEK = range(0, 7)
HOURS_OF_THE_DAY = range(0, 24)
MINUTES_OF_THE_HOUR = range(0, 60)
CRON_FMT = '{minute} {hour} * * {day}'
ROWS = []
DESC = """
deployments-calendar
====================

Module that renders the Wikitech Deployments calendar based on json input.
"""


WIKITEXT_TEMPLATES = {
    've': {
        'frontmatter': '',
        'daysep': '\n==={{{{Deployment_day|date={date}}}}}===',
        'row': dedent('''
                    {{{{Deployment calendar event card
                        |when={time}
                        |length={length}
                        |window={name}
                        |who={who}
                        |what={what}
                    }}}}
                '''),
        'sep': '',
        'endmatter': '',
    },
    'old': {
        'frontmatter': '{{#invoke:Deployment schedule|formatTable|hidedate=false|',
        'row': dedent('''
                    {{{{#invoke:Deployment schedule|row
                        |when={time}
                        |length={length}
                        |window={name}
                        |who={who}
                        |what={what}
                    }}}}
                '''),
        'sep': '|',
        'endmatter': '}}'
    }
}


class Schedule(object):
    def __init__(self, config, next_monday, fmt, schedules=None, train=None,
                 messages=None):
        self.config = config
        self.monday = next_monday
        self.fmt = fmt
        self.calendar = self.config['schedule']
        self.schedules = schedules
        self.train = train
        self.messages = messages
        self._templates = {}

        # Lets us use erb-ish formatting (since jinja2 is similar to wikitext
        # by default
        self._template_env = {
            'block_start_string': '<%',
            'block_end_string': '%>',
            'variable_start_string': '<%=',
            'variable_end_string': '%>',
            'comment_start_string': '<%#',
            'comment_end_string': '%>',
        }
        self.vars = {
            'month': next_monday.strftime('%B'),
            'day': next_monday.strftime('%d'),
            'schedules': ', '.join(schedules),
            'version': self.version()
        }

        if self.train:
            self.vars = {**self.vars, **{
                'old_train': self.train.old,
                'new_train': self.train.new,
                'train_blocker_task': self.train.blocker_task,
                'train_deployer': self.train.deployer,
                'mw_train_link': self.train.link,
                'roadmap': self.train.roadmap,
            }}
        if self.messages:
            self.vars['messages'] = '\n'.join(self.messages)
        self.update_vars()
        self.update_calendar()
        self.create_schedule_rows()

    def version(self):
        if not self.schedules:
            return 'No Train'
        return self.schedules[0].title()

    @property
    def windows(self):
        return self.config['windows']

    @property
    def frontmatter(self):
        return self.config['frontmatter'] + self.fmt['frontmatter']

    @property
    def endmatter(self):
        return self.fmt['endmatter'] + self.config['endmatter']

    def format(self, name, template, extra_vars=None):
        """
        Format templates for output
        """
        variables = self.vars
        if extra_vars:
            variables = {**variables, **extra_vars}
        loader = jinja2.DictLoader({name: template})
        output = jinja2.Environment(
            loader=loader,
            **self._template_env
        ).get_template(
            name
        ).render(**variables)
        self.vars[name] = output
        return output

    def output(self):
        """
        Print the schedule!

        Loops through every minute of every hour of every day, weeee!
        """
        lede = self.format('frontmatter', self.frontmatter)
        rows = []
        day_sep = self.fmt.get('daysep')
        for day_of_the_week in DAYS_OF_THE_WEEK:
            if day_sep:
                day = self.monday + timedelta(days=day_of_the_week - 1)
                rows.append(day_sep.format(
                    date=day.strftime('%Y-%m-%d')
                ))
            for hour_of_the_day in HOURS_OF_THE_DAY:
                for minute_of_the_hour in MINUTES_OF_THE_HOUR:
                    for item in self.calendar:
                        if not item.happens_on(day_of_the_week):
                            continue
                        if not item.happens_at(
                                hour_of_the_day,
                                minute_of_the_hour
                        ):
                            continue
                        template = item.wikitext_template(
                            timedelta(
                                days=day_of_the_week - 1,
                                hours=hour_of_the_day,
                                minutes=minute_of_the_hour
                            )
                        )
                        rows.append(
                            self.format(
                                item.name + '_wikitext',
                                template,
                                item.extra_vars
                            )
                        )
        return '{}\n{}\n{}'.format(
            lede,
            self.fmt['sep'].join(rows),
            self.format('endmatter', self.endmatter)
        )

    def update_vars(self):
        """
        Merge our vars with vars from the config
        """
        self.vars = {**self.vars, **self.config['vars']}

    def update_calendar(self):
        """
        Merge current schedule with updated schedule
        """
        for active_schedule in self.schedules:
            alt_schedule = self.config.get(
                'schedule@{}'.format(
                    active_schedule
                )
            )
            if not alt_schedule:
                raise RuntimeError('Schedule "{}" not found!'.format(
                    active_schedule
                ))
            for key, val in alt_schedule.items():
                existing_sch = self.calendar.get(key)
                if existing_sch:
                    self.calendar[key] = existing_sch + val
                else:
                    self.calendar[key] = val

    def create_schedule_rows(self):
        """
        Turns our calendar into ScheduleRow objects
        """
        rows = []
        for day, scheduled_items in self.calendar.items():
            for scheduled_item in scheduled_items:
                hour = scheduled_item['hour']
                minute = scheduled_item.get('minute', '0')
                canonical_cron = croniter.expand(
                    CRON_FMT.format(minute=minute, hour=hour, day=day)
                )[0]
                window_name = scheduled_item['name']
                window = self.windows[window_name]
                row_name = self.format(
                    window_name + '_window',
                    window['window'],
                    scheduled_item.get('vars')
                )
                row_deployer = self.format(
                    window_name + '_deployer',
                    window['deployer'],
                    scheduled_item.get('vars')
                )
                row_what = self.format(
                    window_name + '_what',
                    window['what'],
                    scheduled_item.get('vars')
                )
                rows.append(ScheduleRow(
                    name=row_name,
                    deployer=row_deployer,
                    what=row_what,
                    cron=canonical_cron,
                    fmt=self.fmt,
                    length=scheduled_item.get('length', '1'),
                    monday=self.monday,
                    extra_vars=scheduled_item.get('vars')
                ))

        self.calendar = rows


class ScheduleRow(object):
    """
    An individual row in the Deployments calendar schedule
    """
    def __init__(self,
                 name,
                 deployer,
                 what,
                 cron,
                 monday,
                 fmt,
                 length=1,
                 extra_vars=None):
        self.name = name
        self.deployer = deployer
        self.what = what
        self.hours = cron[1]
        self.minutes = cron[0]
        self.days = cron[-1]
        self.monday = monday
        self.fmt = fmt
        self.length = length
        self.extra_vars = {}
        if extra_vars:
            self.extra_vars = extra_vars

    def happens_on(self, day_of_week):
        return day_of_week in self.days or '*' in self.days

    def happens_at(self, hour_of_day, minute_of_the_hour):
        happens_at_hour = hour_of_day in self.hours or '*' in self.hours
        happens_at_minute = minute_of_the_hour in self.minutes or '*' in self.minutes
        return happens_at_hour and happens_at_minute

    def wikitext_template(self, delta):
        utc_time = self.monday + delta
        text = self.fmt['row'].format(
            time=utc_time.strftime('%Y-%m-%d %H:%M SF'),
            length=self.length,
            name=self.name,
            who=self.deployer,
            what=self.what
        )
        return text


class WMFVersions(object):
    """
    Handles parsing WMFVersions
    """
    def __init__(self, version):
        self.version = version
        self.major = 1
        self.minor = None
        self.patch = None
        self.wmf = None
        self._parse_versions()

    def _parse_versions(self):
        """
        Major and minor train versions
        """
        match = re.match(r'1\.(\d\d)\.(\d)+-wmf\.(\d+)', self.version)
        try:
            self.minor = match.group(1)
            self.patch = match.group(2)
            self.wmf = match.group(3)
        except AttributeError:
            raise RuntimeError('Invalid version "{}"!'.format(self.version))

    def __str__(self):
        return self.version


class Train(object):
    """
    Class for train information
    """
    def __init__(self, old, new, blocker_task, deployer):
        self.old = old
        self.new = new
        self.blocker_task = blocker_task
        self.deployer = deployer

    @property
    def link(self):
        return '[[mw:MediaWiki_{major}.{minor}/wmf.{wmf}|{version}]]'.format(
            major=self.new.major,
            minor=self.new.minor,
            wmf=self.new.wmf,
            version=self.new.version
        )

    @property
    def roadmap(self):
        return (
            '[[mw:MediaWiki {major}.{minor}/'
            'Roadmap#Schedule for the deployments|{major}.{minor} '
            'schedule]]').format(
                major=self.new.major, minor=self.new.minor
            )


def parse_config(config_file):
    with open(config_file) as f:
        return json.load(f)


def make_deployers(train):
    primary = train.primary
    secondary = train.secondary

    primary = '{{ircnick|%s|%s}}' % (primary.ircnick, primary.fullname)
    secondary = '{{ircnick|%s|%s}}' % (secondary.ircnick, secondary.fullname)

    return ', '.join([primary, secondary])


def get_schedule(trainfinder, config, wiki_fmt='old'):
    if trainfinder.is_declined:
        return run(
            trainfinder.date,
            config,
            schedules=['NoTrain'],
            train=None,
            wiki_fmt=wiki_fmt
        )
    else:
        deployers = make_deployers(trainfinder.next)
        old = WMFVersions(trainfinder.last.version)
        new = WMFVersions(trainfinder.next.version)

        train = Train(
            old,
            new,
            blocker_task=trainfinder.next.task_id,
            deployer=deployers
        )

        return run(
            trainfinder.date,
            config,
            schedules=[trainfinder.next.schedule],
            train=train,
            wiki_fmt=wiki_fmt
        )


def run(monday, config_file, schedules, train=None, wiki_fmt='old', msg=''):
    """
    Build the calendar
    """
    fmt = WIKITEXT_TEMPLATES[wiki_fmt]

    config = parse_config(config_file)
    schedule = Schedule(config, monday, fmt, schedules, train, msg)
    return schedule.output()


def parse_args(argv=None):
    """
    Parse arguments
    """
    ap = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=DESC
    )
    ap.add_argument(
        '-c', '--config-file', default=DEFAULT_CONFIG,
        help='config json file'
    )
    ap.add_argument(
        '-m', '--message', action='append',
        help=('Messages to print at the top of the week. '
              'Can be passed multiple times.')
    )
    sp = ap.add_subparsers()
    train = sp.add_parser('train')
    train.add_argument(
        '--old',
        help='Old train version (e.g., 1.34.0-wmf.12)',
        dest='old_train',
        metavar='<OLD TRAIN VERSION>',
        required=True
    )
    train.add_argument(
        '--new',
        dest='new_train',
        help='New train version (e.g., 1.34.0-wmf.13)',
        metavar='<NEW TRAIN VERSION>',
        required=True
    )
    train.add_argument(
        '--deployer',
        dest='train_deployer',
        help='Train deployer in wiki format (e.g., {{ircnick|thcipriani}})',
        required=True
    )
    train.add_argument(
        '--blocker-task',
        dest='train_blocker_task',
        help='Phab task number for train blocker (e.g., T1000)',
        required=True
    )
    ap.add_argument(
        '--schedule', dest='schedules', action='append',
        help='Active alternate schedules (e.g., American)'
    )
    ap.add_argument(
        '--start-date',
        default=datetime.now(tz=timezone.utc),
        type=deploymentcalendar.findtrain.parse_date,
        help='Alternative start date for calendar, defaults to next Monday'
    )
    ap.add_argument(
        '--wikitext-format',
        choices=['old', 've'],
        default='ve',
        help='Wikitext format (old or ve)'
    )
    parsed = vars(ap.parse_args(argv))
    if not parsed.get('schedules'):
        parsed['schedules'] = []

    return parsed


def main():
    """
    Run program.
    """
    args = parse_args()

    train = None
    if args.get('old_train'):
        old = WMFVersions(args.get('old_train'))
        new = WMFVersions(args.get('new_train'))
        blocker_task = args.get('train_blocker_task')
        deployer = args.get('train_deployer')
        train = Train(old, new, blocker_task, deployer)

    next_monday = deploymentcalendar.findtrain.get_next_monday(
        args['start_date']
    )

    run(
        next_monday,
        args['config_file'],
        args['schedules'],
        train=train,
        wiki_fmt=args['wikitext_format'],
        msg=args.get('message')
    )


if __name__ == '__main__':
    main()
