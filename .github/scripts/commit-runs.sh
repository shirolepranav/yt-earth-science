#!/usr/bin/env bash
# Save the run folder back to the repo.
#
# The runs/ folder is the only memory this system has. Every job that changes
# it ends with this script, so the next message - which arrives in a completely
# fresh container with no knowledge of the last one - can pick up where it
# left off.
#
# Usage: bash .github/scripts/commit-runs.sh "Commit message"

set -euo pipefail

MESSAGE="${1:-Update runs}"

git config user.name  "deepearth-bot"
git config user.email "actions@github.com"

git add runs/

# Nothing changed is a perfectly normal outcome - a status query, say - and
# must not fail the job.
if git diff --cached --quiet; then
  echo "Nothing to commit."
  exit 0
fi

git commit -m "$MESSAGE"

# Another job may have pushed while this one was running (a 90-minute build is
# a long window). Rebase onto whatever landed, then push. Four attempts with a
# short backoff covers both that race and a transient network failure.
for attempt in 1 2 3 4; do
  if git pull --rebase --autostash origin "$(git rev-parse --abbrev-ref HEAD)" && git push; then
    echo "Pushed."
    exit 0
  fi
  echo "Push attempt $attempt failed; retrying in $((attempt * 2))s."
  sleep $((attempt * 2))
done

echo "Could not push the run folder after four attempts." >&2
exit 1
