#!/bin/sh

# Exit on errors
set -e
# Verbose mode
set -v


# Output is prefixed with the name of the script
myname=$(basename "$0")

echo "$myname: finding chutney directory"
TEST_DIR=$(dirname "$0")
CHUTNEY_DIR=$(dirname "$TEST_DIR")

echo "$myname: changing to chutney directory"
cd "$CHUTNEY_DIR"


echo "$myname: running shellcheck tests"

shellcheck chutney
find . -name "*.sh" -exec shellcheck {} +
