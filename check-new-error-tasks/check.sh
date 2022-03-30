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

This is a way to check status of current filters on a logstash
dashboard, usually mediawiki-new-errors or its client-side equivalent.
It's hacks all the way down.

Prerequisites:
  jq       - sudo apt install jq
  arcanist - https://wikitech.wikimedia.org/wiki/Help:Arcanist

Once you have arcanist installed, you'll need to get a token with:

  $ arc set-config default https://phabricator.wikimedia.org/
  $ arc install-certificate

You'll need to use your LDAP password to get the dashboard data, which
_should_ be safe since this is https.

Note that this will fail if the dashboard has in excess of 100 tasks
on filters, since it doesn't handle Conduit API pagination.  Let's try
to have fewer than 100 filters.

Filters are assumed to have custom labels referencing Phabricator
tasks. For example:

  T269750 - PegTokenizer: UTF-8 errors
DOC

  exit
}

# Extracts a JSON blob of dashboard info as a saved object from the
# opensearch API.
#
# https://opensearch.org/docs/latest/troubleshoot/index/
# https://www.elastic.co/guide/en/kibana/current/saved-objects-api-export.html
curl_dashboard () {
  read -rp "LDAP username for logstash: " username

  tempfile="$(mktemp errorcheck.XXXXX)"
  trap "rm -f $tempfile" EXIT

  curl --silent --show-error --fail \
    --user "$username" \
    -o "$tempfile" \
    -X POST https://logstash.wikimedia.org/api/saved_objects/_export \
    -H 'osd-xsrf: true' \
    -H 'Content-Type: application/json' \
    -d '{
          "objects": [
            {
              "type": "dashboard",
              "id": "'"$1"'"
            }
          ]
        }'

  mv "$tempfile" "$2"
}

# Extracts a list of tasks from the dashboard JSON blob.
tasks () {
  # Returned data is http://ndjson.org/ - one record per line.
  head -1 "$1" \
    | jq -r '.attributes.kibanaSavedObjectMeta.searchSourceJSON | fromjson | .filter | .[].meta.alias' \
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
    curl_dashboard "$dashboard_id" "$dashboard_json"
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
