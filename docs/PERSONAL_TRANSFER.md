# Personal-account transfer preparation

Staged destination: `mehrdadxzaker/omarchy-hormuz-plugin`. Repository ID: `1412364994`.
Keep this draft unmerged until its separately approved cutover. This preparation
does not transfer anything or change live service settings, App ownership,
Apple identities, DNS, deployments, or billing.

## Prepared changes

The plugin install URL, QA source link, and pinned Hormuz package URL use the
personal owner. The Hormuz revision remains
`99b0435765c1d4a736c1cf5438216f4c5c434364`; no CLI contract, permissions,
installer behavior, or runtime evidence has been requalified by an owner change.

## Later cutover

Move Hormuz before, or with, this plugin. Merge the staged URLs once both
personal repositories exist. Existing installations should refresh their Git
source deliberately, preserving local widget settings. Validate the plugin
with Omarchy on the target system and verify the pinned Hormuz CLI before
resuming use. Current router main has changed since that pin; upgrading the
runtime is a separate compatibility task.

## Validation

`python3 -m unittest discover -s tests -q` and `bash -n scripts/install.sh`.
The tests use synthetic CLI responses; no router, model, or desktop session is
installed or reconfigured by this preparation.
