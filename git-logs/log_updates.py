#!/usr/bin/python

from subprocess import check_output
from datetime import date
import re
import sys
import getopt

headings = ["dependencies", "stories", "bugs", "qa", "hygiene", "i18n",
            "regressions"]


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
    log = {}
    for heading in headings:
        log[heading] = []
    f = open(f_name, 'r')
    for line in f:
        if re.findall(r"(?i)Story ([0-9]*)[^:]*:", line):
            log["stories"].append(line)
        elif re.findall(r"(?i)Bug", line):
            log["bugs"].append(line)
        elif re.findall(r"(?i)QA", line):
            log["qa"].append(line)
        elif re.findall(r"(?i)Regression", line):
            log["regressions"].append(line)
        elif re.findall(r"(?i)Hygiene", line):
            log["hygiene"].append(line)
        elif re.findall(r"(?i)i18n|Localisation updates from", line):
            log["i18n"].append(line)
        elif re.findall(r"(?i)Dependency", line):
            log["dependencies"].append(line)
    f = open(f_name, 'r')
    log["raw"] = f.read()
    f.close()
    return log


def get_wiki_text(log):
    info("Generating wikitext ...")
    out = ''
    for heading in headings:
        if len(log[heading]) > 0:
            out += '== %s ==\n\n' % heading.capitalize()
            for commit in log[heading]:
                out += '* %s\n' % commit
    out += '== Raw git log ==\n\n'
    out += log["raw"]
    return out


if __name__ == '__main__':
    commit = None
    output_filename = None
    try:
        opts, args = getopt.getopt(sys.argv[1:], "c:o:")
        for opt, arg in opts:
            if opt == '-c':
                commit = arg
            elif opt == '-o':
                output_filename = arg
    except getopt.GetoptError:
        pass
    f_name = generate_change_log('.', commit)
    log = grep_change_log_file(f_name)
    wikitext = get_wiki_text(log)
    if output_filename:
        info("Saving to %s ...\n" % output_filename)
        f = open(output_filename, "w")
        f.write(wikitext)
        f.close()
    else:
        print wikitext
