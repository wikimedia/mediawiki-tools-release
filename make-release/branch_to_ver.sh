#!/bin/bash
#
# Copyright 2017, Antoine "hashar" Musso <hashar@free.fr>
# Copyright 2017, Wikimedia Foundation Inc.
#
# Convert a MediaWiki releaseable branch name to a MediaWiki version
# to be used with make-release.
#
# master is set to 99.99.99
# semver patch is always 99

set -eu

usage() {
	echo "Usage: branch_to_ver.sh <master|REL1_xx>"
}

branch_to_ver() {
	local branch=$1
	if [[ "$branch" == master ]] ; then
		echo '99.99.99'
	elif [[ $branch =~ ^REL([0-9]+)_([0-9]+)$ ]] ; then
		echo "${BASH_REMATCH[1]}.${BASH_REMATCH[2]}.99"
	fi
}

if [ "${#@}" -ne 1 ]; then
	usage >&2
	exit 1
fi

ver=$(branch_to_ver "$1")
[ -z "$ver" ] && {
	echo "Can not forge version for '$1'." >&2
	exit 1
}
echo "$ver"
