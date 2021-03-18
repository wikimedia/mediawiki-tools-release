#!/bin/bash

set -e -o pipefail

# This is a hardcoded path to the mediawiki-new-errors dashboard.
# See also:
#  - https://wikitech.wikimedia.org/wiki/Performance/Runbook/Kibana_monitoring
#  - https://wikitech.wikimedia.org/wiki/Heterogeneous_deployment/Train_deploys#Places_to_Watch_for_Breakage
DEFAULT_DASHBOARD_ID='0a9ecdc0-b6dc-11e8-9d8f-dbc23b470465'

usage () {
  cat <<DOC
USAGE

  # Check default dashboard - mediawiki-new-errors:
  ./check.sh

  # Specify a dashboard ID:
  ./check.sh $DEFAULT_DASHBOARD_ID

  # See this usage info:
  ./check.sh --help

This is a way to check status of current filters on the
mediawiki-new-errors logstash dashboard.  It's hacks all the way
down.

Prerequisites:
  jq       - sudo apt install jq
  arcanist - https://wikitech.wikimedia.org/wiki/Help:Arcanist

Once you have arcanist installed, you'll need to get a token with:

  $ arc set-config default https://phabricator.wikimedia.org/
  $ arc install-certificate

You'll need to use your LDAP password to get dashboard.json, which
_should_ be safe since this is https.

Note that this will fail if the dashboard has in excess
of 100 tasks on filters, since it doesn't handle Conduit API
pagination.  Let's try to have fewer than 100 filters.
DOC

  exit
}

curl_dashboard () {
  read -rp "LDAP username for logstash: " username
  curl --fail --user "$username" "$1" -o "$2"
}

tasks () {
  jq -r '.objects[0].attributes.kibanaSavedObjectMeta.searchSourceJSON | fromjson | .filter | .[].meta.alias' < "$1" \
    | sed 's/^T\([0-9]\+\).*/\1/' \
    | grep -E '^[0-9]+$' \
    | paste -sd ','
}

format_response () {
  jq -r '.response.data | .[] | [.id, .fields.status.value] | @tsv' | sort -u
}

if [ $# -lt 1 ]; then
  dashboard_id="$DEFAULT_DASHBOARD_ID"
elif [ "$1" = '--help' ] || [ "$1" = '-h' ]; then
  usage
else
  dashboard_id="$1"
fi
dashboard_path="https://logstash.wikimedia.org/api/kibana/dashboards/export?dashboard=$dashboard_id"
dashboard_json="$dashboard_id.json"

if ! [ -e "$dashboard_json" ]; then
  retrieve_dashboard="Y"
else
  echo "$dashboard_json"
  ls -lah "$dashboard_json"
  echo
  read -rp "Overwrite with fresh dashboard data (y/n)? " retrieve_dashboard
fi
case "$retrieve_dashboard" in
  [yY][eE][sS]|[yY])
    curl_dashboard "$dashboard_path" "$dashboard_json"
    ;;
esac

# Ask conduit for tasks with matching IDs.  This will break if there
# are more than 100 tasks with filters, since it doesn't do anything
# to handle pagination.

printf '{
  "constraints": {
    "ids": [
      %s
    ]
  }
}' "$(tasks "$dashboard_json")" | arc call-conduit -- maniphest.search | format_response
