#!/bin/sh
#
# Usage:
#    tools/truncate-logs.sh [node]
#
# Output:
#    for each node, truncate the logs
#
#    If the argument "node" is specified, only truncates the logs of that
#    node.
#
# Examples:
#    tools/truncate-logs.sh
#    tools/truncate-logs.sh 000a

set -o errexit
set -o nounset

# Set some default values if the variables are not already set
: "${CHUTNEY_DATA_DIR:=}"

if [ ! -d "$CHUTNEY_PATH" ] || [ ! -x "$CHUTNEY_PATH/chutney" ]; then
    # looks like a broken path: use the path to this tool instead
    TOOLS_PATH=$(dirname "$0")
    CHUTNEY_PATH=$(dirname "$TOOLS_PATH")
    export CHUTNEY_PATH
fi
if [ -d "$PWD/$CHUTNEY_PATH" ] && [ -x "$PWD/$CHUTNEY_PATH/chutney" ]; then
    # looks like a relative path: make chutney path absolute
    export CHUTNEY_PATH="$PWD/$CHUTNEY_PATH"
fi

# Get a working net path
case "$CHUTNEY_DATA_DIR" in
  /*)
    # if an absolute path, then leave as-is
    # chutney will make this directory automatically if needed
    ;;
  *)
    # if a relative path
    if [ ! -d "$CHUTNEY_DATA_DIR" ]; then
        # looks like a broken path: use the chutney path as a base
        export CHUTNEY_DATA_DIR="$CHUTNEY_PATH/net"
    fi
    if [ -d "$PWD/$CHUTNEY_DATA_DIR" ]; then
        # looks like a relative path: make chutney path absolute
        export CHUTNEY_DATA_DIR="$PWD/$CHUTNEY_DATA_DIR"
    fi
    ;;
esac

# Truncate the logs for node $1
truncate_logs() {
    echo "Truncating log: $1"
    truncate -s 0 "$1"
}

# Show the usage message for this script
usage() {
    echo "Usage: $NAME [node]"
    exit 1
}

NAME=$(basename "$0")
DEST="$CHUTNEY_DATA_DIR/nodes"
LOG_FILE=*.log

[ -d "$DEST" ] || { echo "$NAME: no logs available in '$DEST'"; exit 1; }
if [ $# -eq 0 ];
then
    for log in "$DEST"/*/$LOG_FILE;
    do
        [ -e "${log}" ] || continue
        truncate_logs "$log"
    done
elif [ $# -eq 1 ];
then
    for log in "$DEST"/$1/$LOG_FILE;
    do
        [ -e "${log}" ] || continue
        truncate_logs "$log"
    done
else
    usage
fi
