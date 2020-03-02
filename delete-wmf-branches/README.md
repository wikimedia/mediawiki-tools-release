delete-wmf-branches
===================

A hacky script to delete old `wmf/` branches that accumulate from train
deploys.

See [T244368 Clean old wmf branches in Gerrit][ticket] for some background.

Usage
-----

Edit `delete-wmf-branches.sh` and replace the commented branches with your
targets to delete, then:

```sh
# cd to a _clean_ checkout of mediawiki/core - any uncommitted local state will
# be deleted:
cd /path/to/mediawiki/core

# Run the script:
bash /path/to/mediawiki/tools/release/delete-wmf-branches/delete-wmf-branches.sh
```

You can check `/tmp/delete-wmf-branches.log` for a list of the branches deleted
during a given run.

This may make several dangerous assumptions.  Exercise caution.

[ticket]: https://phabricator.wikimedia.org/T244368
