#!/usr/bin/python
#
# Copyright 2015, Antoine Musso
# Copyright 2015, Wikimedia Foundation Inc.
#
# Generate mailmap for users.mediawiki.org emails from USERINFO
#
# Take a list of name <foo@users.mediawiki.org>
# Attempt to find the foo email in USERINFO files
# Output a mailmap rule such as:
# First Last <userinfo email> <foo@users.mediawiki.org>
#
# Output can then be appended to an existing mailmap and the concatenation
# sorted with sort --ignore-case.

import os
import os.path

USERINFO_DIR = '/Users/amusso/projects/USERINFO'

info_files = [f for f in os.listdir(USERINFO_DIR)
              if not f.startswith('.')]


def parse_userinfo(user):
    try:
        with open(os.path.join(USERINFO_DIR, user)) as f:
            lines = f.readlines()
    except IOError:
        return None

    rows = [l.split(':') for l in lines if l.find(':') != -1]

    return {user:
            {row[0]: row[1].strip() for row in rows}}


userinfos = {}
for userinfo in info_files:
    userinfos.update(parse_userinfo(userinfo))

with open('users.mediawiki.org', mode='r') as f:
    users_mw_org = f.readlines()

for (name, mwemail) in [u.split(' <') for u in users_mw_org]:
    mwemail = mwemail.strip()[:-1]
    mwuser = mwemail.split('@')[0]
    if mwuser in userinfos:
        if 'email' in userinfos[mwuser]:
            uemail = userinfos[mwuser]['email']
            if uemail.find(' ') == -1:
                print("%s <%s> <%s>" % (name, userinfos[mwuser]['email'],
                                        mwemail))
