#!/bin/bash

# This is a way to check status of current filters on the mediawiki-new-errors
# logstash dashboard.  It's hacks all the way down.
#
# Prerequisites:
#   jq       - sudo apt install jq
#   arcanist - https://wikitech.wikimedia.org/wiki/Help:Arcanist
#
# Once you have arcanist installed, you'll need to get a token with:
#
#   $ arc set-config default https://phabricator.wikimedia.org/
#   $ arc install-certificate
#
# Get the dashboard data with something like:
#
# curl --user "[username]" 'https://logstash.wikimedia.org/api/kibana/dashboards/export?dashboard=0a9ecdc0-b6dc-11e8-9d8f-dbc23b470465' -o dashboard_json
#
# You'll need to use your LDAP password, which _should_ be safe since this is
# https.

tasks () {
  jq -r '.objects[0].attributes.kibanaSavedObjectMeta.searchSourceJSON | fromjson | .filter | .[].meta.alias' < dashboard_json \
    | sed 's/^T\([0-9]\+\).*/\1/' \
    | grep -E '^[0-9]+$'
}

# This should almost certainly be a single request with all tasks.  Sleeps
# in-between calls to be gentle with Phab.

for task in $(tasks); do
  status=$(printf '{ "task_id": "%s" }' "$task" | arc call-conduit -- maniphest.info | jq .response.status)
  echo "$task: $status"
  sleep 5
done
