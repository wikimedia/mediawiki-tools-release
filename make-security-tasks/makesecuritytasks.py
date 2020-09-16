#!/usr/bin/env python3

from phabricator import Phabricator

phab = Phabricator(host='https://phabricator.wikimedia.org/api/', token='')

# TODO: Can we do more complex ACLs from maniphest task creation/editing?
# TODO: Set subtype?
aclSec = 'PHID-PROJ-koo4qqdng27q7r65x3cw'

# projSecTeam = 'PHID-PROJ-pdw4jlcz543opbp2drhq'
projSec = 'PHID-PROJ-dwqfaiejpr656zc6hf6o'
projMWReleasing = 'PHID-PROJ-5p3mxnq5ejf4xs7cphgl'

taskProjects = [projSec, projMWReleasing]

# TODO: Take param from script argument
version = '1.31.9/1.34.3'

res = phab.maniphest.createtask(
    title='Release MediaWiki {0}'.format(version),
    description="""Previous release work:

Tracking for activities actually pertaining to making the release of MediaWiki {0}"""
    .format(version),
    viewPolicy=aclSec,
    editPolicy=aclSec,
    projectPHIDs=taskProjects,
)
parentTaskPHID = res['phid']
print("Parent task: https://phabricator.wikimedia.org/T{0}".format(res['id']))

subTasks = [
    {
        "title": "Tracking bug for MediaWiki {0}".format(version),
        "description": """Previous work:

Tracking bug for next security release, {0}""".format(version),
    },
    {
        "title": "Write and send pre-release announcements for MediaWiki {0}".format(version),
        "description": "Previous work: ",
    },
    {
        "title": "Write and send release announcements for MediaWiki {0}".format(version),
        "description": "Previous work: ",
    },
    {
        "title": "Update onwiki release notes for {0}".format(version),
        "description":
            "The following mediawiki.org pages need updating from the RELEASE-NOTES files:",
        # TODO: URLS!
    },
    {
        "title": "Update HISTORY in master after {0}".format(version),
        "description": ("Point release RELEASE-NOTES from {0} need copying to HISTORY "
                        "in the relevant places in master".format(version)),
    },
    {
        "title": "Tag {0}".format(version),
        "description": "Create and push git tags for {0}".format(version),
    },
    {
        "title": "Obtain CVEs for {0} security releases".format(version),
        "description": "",
    },
    {
        "title": ("Write and send supplementary release announcement for "
                  "extensions and skins with security patches ({0})".format(version)),
        "description": "Previous work: ",
    },
]

subTaskPHIDS = []

for task in subTasks:
    res = phab.maniphest.createtask(
        title=task['title'],
        description=task['description'],
        viewPolicy=aclSec,
        editPolicy=aclSec,
        projectPHIDs=taskProjects,
    )
    subTaskPHIDS.append(res['phid'])

# Add trackingTaskPHID as sub tasks of parentTaskPHID
res = phab.maniphest.edit(
    transactions=[{"type": "subtasks.add", "value": subTaskPHIDS}],
    objectIdentifier=parentTaskPHID,
)

print("Done!")
