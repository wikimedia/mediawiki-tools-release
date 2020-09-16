# A hacky script to delete old wmf branches.

# For background, see: https://phabricator.wikimedia.org/T244368

# You'll want to run this from a clean checkout of mediawiki/core, as it will
# delete untracked local files.

LOGFILE="/tmp/delete-wmf-branches.log"

# Replace with your list of branches, one per line:
branches=(
# wmf/1.34.0-wmf.15
# wmf/1.34.0-wmf.16
# wmf/1.34.0-wmf.17
# ...
)

for branch in "${branches[@]}"; do
  git checkout "$branch"
  git clean -ffxd
  git submodule update --init --recursive

  # Delete branches for all submodules:
  git submodule foreach "git push origin --delete $branch || :"

  # Delete master branch:
  git push origin --delete "$branch"

  echo "completed: $branch" >> "$LOGFILE"
done

echo "See $LOGFILE for list of deleted branches."
