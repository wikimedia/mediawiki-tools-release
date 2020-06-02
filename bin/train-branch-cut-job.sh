#!/bin/bash
set -eu

#find out the newest wmf/* branch version
VERSION=$(git ls-remote --heads https://gerrit.wikimedia.org/r/mediawiki/core refs/heads/wmf/*|awk '{print $2}' | sort --version-sort --reverse|head -1|cut -d'/' -f4)
WMF_VERSION=${VERSION##*.}
(( WMF_VERSION++ ))
MAJOR_VERSION="${VERSION%.*}"
VERSION="${MAJOR_VERSION}.${WMF_VERSION}"


if [[ -z "$VERSION" ]]; then
  echo "please provide a VERSION!"
  exit 1
else
  echo "Branching mediawiki version $VERSION"
fi

export HOME="$(dirname "$netrc_file")"
ln -s "$netrc_file" "$HOME/.netrc"

set -x

# Ensure we can make a commit
export GIT_AUTHOR_NAME=trainbranchbot
export GIT_AUTHOR_EMAIL=trainbranchbot@releases-jenkins.wikimedia.org
export GIT_COMMITTER_NAME=$GIT_AUTHOR_NAME
export GIT_COMMITTER_EMAIL=$GIT_AUTHOR_EMAIL

# Remove previous attempts to branch
rm /tmp/mw-branching-* -rf

cd make-release

# SSH_AUTH_SOCK=1 necessary due to check in branch.py
SSH_AUTH_SOCK=1 ./branch.py --core --core-bundle wmf_core --bundle wmf_branch --branchpoint HEAD --core-version "$VERSION"  "wmf/${VERSION}"

