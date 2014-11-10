#!/usr/bin/env python

from subprocess import check_output
from datetime import date
import re
import sys
import getopt
import os

DEPENDENCY_URL = '//gerrit.wikimedia.org/r/#q,%s,n,z'
STORY_URL = '//wikimedia.mingle.thoughtworks.com/projects/mobile/cards/%s'
BUG_URL = '//bugzilla.wikimedia.org/show_bug.cgi?id=%s'
headings = ["dependencies", "stories", "bugs", "qa", "hygiene", "i18n",
            "regressions", "other"]
DEBUG = False


def info(msg):
    if DEBUG:
        print "[INFO] %s" % msg


def get_commit_range(repodir, commit=None):
    if not commit:
        prompt = 'Enter commit number or <ENTER> for last-update: '
        commit = raw_input(prompt)
    if len(commit) == 0:
        commit = latest_commit(repodir)
    else:
        info('Using %s as the initial commit.' % commit)
    if len(commit.split('..')) < 2:
        commit = '%s..' % commit
    return commit


def latest_commit(repodir):
    info("Aquiring latest commit number...")
    cmd = ['git', 'log', '--max-count=1', '--no-merges']
    last_log_output = check_output(cmd)
    m = re.search('commit\s+([a-z0-9]+).*', last_log_output)
    last_commit = m.group(1)
    info('Using the last commit [%s] as the initial commit.' % last_commit)
    return last_commit


def get_log_from_range(commit_range):
    info("Getting latest delta logs ...")
    cmd = ['git', 'log', '--no-merges', "%s" % commit_range]
    log = check_output(cmd)
    return log


def output_change_log(f_name, change_log):
    info("Writing %s ..." % f_name)
    hLog = open(f_name, 'w')
    hLog.write(change_log)
    hLog.close()
    info("Done.")


def generate_change_log(repodir, commit=None):
    commit_range = get_commit_range(repodir, commit)
    change_log = get_log_from_range(commit_range)

    f_name = 'ChangeLogs_%s.txt' % date.today().isoformat()
    output_change_log(f_name, change_log)
    return f_name


def grep_change_log_file(f_name):
    log = {}
    for heading in headings:
        log[heading] = []
    f = open(f_name, 'r')
    commits = f.read().split('\ncommit')
    f.close()

    for commit in commits:
        grep_commit(log, '\ncommit'+commit)
    f = open(f_name, 'r')
    log["raw"] = f.read()
    f.close()
    return log


def grep_commit(log, commit):
    ignored_lines = 0
    lines = commit.split('\n')
    commit_lines = len(lines)
    # split the entire commit into multiple lines
    # as it may match different buckets
    for line in lines:
        line = line.strip()
        if re.findall(r"(?i)Story ([0-9]*)[^:]*:", line):
            matches = re.findall(r"(?i)Story ([0-9]*)[^:]*:", line)
            if len(matches) == 1:
                url = STORY_URL % matches[0]
                line = '[%s %s]' % (url, line.strip())
            log["stories"].append(line)
        elif re.findall(r"(?i)Bug:", line):
            matches = re.findall(r"(?i)Bug: ([0-9]*)", line)
            if len(matches) == 1:
                url = BUG_URL % matches[0]
                line = '[%s %s]\n' % (url, line.strip())
            line = '%s\n' % line.strip()
            line += '<pre>%s</pre>\n' % commit
            log["bugs"].append(line)
        elif re.findall(r"(?i)QA", line):
            log["qa"].append(line)
        elif re.findall(r"(?i)Regression", line):
            log["regressions"].append(line)
        elif re.findall(r"(?i)Hygiene", line):
            log["hygiene"].append(line)
        elif re.findall(r"(?i)i18n|Localisation updates from", line):
            line = '%s\n' % line.strip()
            line += '<pre>%s</pre>\n' % commit
            log["i18n"].append(line)
        elif re.findall(r"(?i)Dependency", line):
            matches = re.findall(r"(?i)Dependency: (.*)", line)
            if len(matches) == 1:
                url = DEPENDENCY_URL % matches[0]
                line = '[%s %s]' % (url, line.strip())
            log["dependencies"].append(line)
        else:
            ignored_lines += 1
    # If all the lines were ignored it didn't go into a bucket
    if commit_lines == ignored_lines:
        log["other"].append('<pre>%s</pre>\n' % commit)
    return log


def get_wiki_text(log):
    info("Generating wikitext ...")
    out = ''
    for heading in headings:
        changes = len(log[heading])
        if changes > 0:
            out += '== %s (%s) ==\n\n' % (heading.capitalize(), changes)
            for commit in log[heading]:
                if '<pre>' not in commit:
                    out += '* %s\n' % commit
                else:
                    out += commit
    out += '== Raw git log ==\n\n'
    out += '<pre>%s</pre>' % log["raw"]
    return out


if __name__ == '__main__':
    commit = None
    output_filename = None
    try:
        opts, args = getopt.getopt(sys.argv[1:], "c:o:v")
        for opt, arg in opts:
            if opt == '-c':
                commit = arg
            elif opt == '-o':
                output_filename = arg
            elif opt == '-v':
                DEBUG = True
    except getopt.GetoptError:
        pass
    f_name = generate_change_log('.', commit)
    log = grep_change_log_file(f_name)
    # cleanup, remove changelog file
    # @TODO is there any reason to keep this around?
    # perhaps make this a tmpfile
    info("Deleting %s..." % f_name)
    os.remove(f_name)
    info("Done.")
    wikitext = get_wiki_text(log)
    if output_filename:
        info("Saving to %s ...\n" % output_filename)
        f = open(output_filename, "w")
        f.write(wikitext)
        f.close()
    else:
        print wikitext
