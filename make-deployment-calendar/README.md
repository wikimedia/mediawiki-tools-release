# README for make-deployments-calendar

## Modify the deployment calendar

The deployment calendar is generated from the data in `deployment-calendar.yaml`.
The `windows` key defines metadata about the windows: name, deployers, descriptions.
The `schedules` key schedules `windows` throughout the week. The keys in schedules
are train schedules (whether the train conductor is American or European means
that the windows move around slightly). The default `schedule` key is for events
that are unaffected by the train; i.e., they will always happen at a scheduled
time.

## Scripts

Scripts are all meant to be run from within this directory as they assume
the `.py` files in this directory are in your python path.

* `make-deployments-calendar` is a script that will dump the wikitext for the
  next week's deployment calendar to stdout
* `is-there-a-train-in-two-weeks` is a script that will exit 1 if the train
  was declined in two weeks
* `update-wikis` updates the "Deployments" page on wikitech with the new
  deployment calendar and archives the previous week's calendar.

## Setup

You need to setup a [pywikibot user](toolforge) and [oauth](oauth) that
user to create an edit pages on Wikitech.

Additionally to find a train, this script requires a Phabricator conduit
token. It can be installed using [Arcanist](arcanist) or may be set by using
the `CONDUIT_TOKEN` environment variable.

toolforge: <https://wikitech.wikimedia.org/wiki/Help:Toolforge/Pywikibot#Using_the_shared_Pywikibot_files_(recommended_setup)>
oauth: <https://www.mediawiki.org/wiki/OAuth/Owner-only_consumers>
arcanist: <https://www.mediawiki.org/wiki/Phabricator/Arcanist>

Running tests sets up a local virtualenv.

## Tests

There aren't a lot of tests, to run the tests that exist:

```
$ make test
```
