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


echo "$myname: running Debug.py tests"

LOG_FILE=$(mktemp)
export LOG_FILE
test -n "$LOG_FILE"

unset CHUTNEY_DEBUG
export CHUTNEY_DEBUG
lib/chutney/Debug.py | tee "$LOG_FILE"
LOG_FILE_LINES=$(wc -l < "$LOG_FILE")
test "$LOG_FILE_LINES" -eq 1

LOG_FILE=$(mktemp)
export LOG_FILE
test -n "$LOG_FILE"

export CHUTNEY_DEBUG=1
lib/chutney/Debug.py | tee "$LOG_FILE"
LOG_FILE_LINES=$(wc -l < "$LOG_FILE")
test "$LOG_FILE_LINES" -eq 2

unset CHUTNEY_DEBUG
export CHUTNEY_DEBUG


echo "$myname: running Templating.py tests"

LOG_FILE=$(mktemp)
export LOG_FILE
test -n "$LOG_FILE"

lib/chutney/Templating.py torrc_templates/common.i | tee "$LOG_FILE"
grep -q owning_controller_process "$LOG_FILE"
grep -q connlimit "$LOG_FILE"
grep -q controlport "$LOG_FILE"
grep -q nick "$LOG_FILE"
grep -q authorities "$LOG_FILE"
grep -q dir "$LOG_FILE"


echo "$myname: running Traffic.py tests"

LOG_FILE=$(mktemp)
export LOG_FILE
test -n "$LOG_FILE"

# Choose an arbitrary port
PYTHONPATH=$PYTHONPATH:lib lib/chutney/Traffic.py 9999 | tee "$LOG_FILE"

# Traffic.py produces output with a single newline. But we don't want to get
# too picky about the details: allow an extra line and a few extra chars.
LOG_FILE_LINES=$(wc -l < "$LOG_FILE")
test "$LOG_FILE_LINES" -le 2
LOG_FILE_CHARS=$(wc -c < "$LOG_FILE")
test "$LOG_FILE_CHARS" -le 4


# We don't test TorNet.py: it's integration tested with tor using the
# chutney/chutney script
