#!/bin/sh

set -o errexit
set -o nounset

# SC1117 was disabled after 0.5, because it was too pedantic
EXCLUSIONS="--exclude=SC1117"

# Output is prefixed with the name of the script
myname=$(basename "$0")

echo "$myname: finding chutney directory"
TEST_DIR=$(dirname "$0")
CHUTNEY_DIR=$(dirname "$TEST_DIR")

echo "$myname: changing to chutney directory"
cd "$CHUTNEY_DIR"


echo "$myname: running shellcheck tests with $EXCLUSIONS"

# Verbose mode
set -v

shellcheck "$EXCLUSIONS" chutney

find . -name "*.sh" -exec shellcheck "$EXCLUSIONS" {} +

find . -name "*.git-hook" -exec shellcheck "$EXCLUSIONS" {} +
