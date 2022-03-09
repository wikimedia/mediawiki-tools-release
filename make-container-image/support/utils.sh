#!/bin/bash

# Returns true if building for train-dev environment
function train_dev {
    [ "${MW_CONFIG_BRANCH:-}" = "train-dev" ]
}

function wikiversions_basename {
    if train_dev; then
        echo wikiversions-dev
    else
        echo wikiversions
    fi
}

# Reads the realm-specific wikiversions.json file in workdir (which
# may be a docker volume or the full path of a local directory) and
# writes the unique versions to stdout.
function unique_wikiversions {
    local workdir="$1"

    docker run --rm \
           -v "$workdir:/srv/mediawiki" \
           --entrypoint /bin/cat \
           docker-registry.wikimedia.org/wikimedia-buster \
           "/srv/mediawiki/$(wikiversions_basename).json" \
        | jq -r 'values[]' | sort -u | sed -e 's/^php-//'
}
