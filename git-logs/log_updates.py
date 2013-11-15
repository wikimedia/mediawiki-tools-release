#!/usr/bin/python

from subprocess import check_output
from datetime import date
import re
import sys
import getopt


def info(msg):
    print "[INFO] %s" % msg


def get_initial_commit(repodir, the_commit=None):
    if not the_commit:
        prompt = 'Enter commit number or <ENTER> for last-update: '
        the_commit = raw_input(prompt)
    if len(the_commit) == 0:
        the_commit = latest_commit(repodir)
    else:
        info('Using %s as the initial commit.' % the_commit)
    return the_commit


def latest_commit(repodir):
    info("Aquiring latest commit number...")
    cmd = ['git', 'log', '--max-count=1']
    last_log_output = check_output(cmd)
    m = re.search('commit\s+([a-z0-9]+).*', last_log_output)
    last_commit = m.group(1)
    info('Using the last commit [%s] as the initial commit.' % last_commit)
    return last_commit


def get_log_since(last_updated, repodir):
    info("Getting latest delta logs ...")
    cmd = ['git', 'log', '--no-merges', "%s.." % last_updated]
    log = check_output(cmd)
    return log


def output_change_log(f_name, change_log):
    info("Writing %s ..." % f_name)
    hLog = open(f_name, 'w')
    hLog.write(change_log)
    hLog.close()
    info("Done.")


def generate_change_log(repodir, commit=None):
    last_updated = get_initial_commit(repodir, commit)
    change_log = get_log_since(last_updated, repodir)

    f_name = 'ChangeLogs_%s.txt' % date.today().isoformat()
    output_change_log(f_name, change_log)
    return f_name


def grep_change_log_file(f_name):
    for line in open(f_name, 'r'):
        if re.findall(r"(?i)Story|(?i)Stories|(?i)Bug|(?i)Regression|(?i)QA|\
        (?i)Hygiene|(?i)Dependency", line):
            print line


if __name__ == '__main__':
    commit = None
    try:
        opts, args = getopt.getopt(sys.argv[1:], "c:")
        for opt, arg in opts:
            if opt == '-c':
                commit = arg
    except getopt.GetoptError:
        pass
    f_name = generate_change_log('.', commit)
    grep_change_log_file(f_name)
