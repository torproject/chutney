#!/bin/sh
#
# Usage:
#    tools/warnings.sh [node]
# Output: for each node outputs its warnings and the number of times that
# warning has ocurred. If the argument node is specified, it only shows
# the warnings of that node.
# Examples: tools/warnings.sh
#           tools/warnings.sh 000a
# Environmental variables:
# CHUTNEY_WARNINGS_IGNORE_EXPECTED: set to "true" to filter expected warnings
# CHUTNEY_WARNINGS_SUMMARY: set to "true" to merge warnings from all instances

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
if [ ! -d "$CHUTNEY_DATA_DIR" ]; then
    # looks like a broken path: use the chutney path as a base
    export CHUTNEY_DATA_DIR="$CHUTNEY_PATH/net"
fi
if [ -d "$PWD/$CHUTNEY_DATA_DIR" ]; then
    # looks like a relative path: make chutney path absolute
    export CHUTNEY_DATA_DIR="$PWD/$CHUTNEY_DATA_DIR"
fi

show_warnings() {
    # Work out the file and filter settings
    LOGS=$(mktemp)
    if [ "$CHUTNEY_WARNINGS_SUMMARY" = true ]; then
        cat "$1"/*/"$LOG_FILE" > "$LOGS"
    else
        cat "$1/$LOG_FILE" > "$LOGS"
    fi
    FILTERED_LOGS=$(mktemp)
    if [ "$CHUTNEY_WARNINGS_IGNORE_EXPECTED" = true ] && \
           [ -e "$IGNORE_FILE" ]; then
        grep -v -f "$IGNORE_FILE" "$LOGS" | $SED_E "$FILTER" > "$FILTERED_LOGS"
    else
        $SED_E "$FILTER" "$LOGS" > "$FILTERED_LOGS"
        IGNORE_FILE=
    fi
    # Silence any messages if we are in summary mode, and there are no warnings
    # must be kept in sync with the filter commands below
    if [ "$CHUTNEY_WARNINGS_SUMMARY" = true ] && \
       [ "$(wc -c < "$FILTERED_LOGS")" -eq 0 ]; \
       then
        ECHO_Q="true"
        ECHO_A="true"
     else
        # if there is output, always echo the detail message
        ECHO_A="echo"
    fi
    # Give context to the warnings we're about to display
    if [ "$CHUTNEY_WARNINGS_SUMMARY" = true ]; then
        $ECHO_Q "${GREEN}Summary: $(basename "$1")${NC}"
    else
        $ECHO_Q "${GREEN}Node: $(basename "$1")${NC}"
    fi
    if [ "$CHUTNEY_WARNINGS_IGNORE_EXPECTED" = true ] && \
       [ -e "$IGNORE_FILE" ]; then
        PERMANENT_DIR=$(readlink -n "$1" || echo "$1")
        $ECHO_A "${GREEN}Detail: chutney/tools/warnings.sh $PERMANENT_DIR${NC}"
    fi
    # Display the warnings, after filtering and counting occurrences
    # must be kept in sync with the filter commands above
    sort "$FILTERED_LOGS" | uniq -c | \
    sed -e 's/^\s*//' -e "s/ *\([0-9][0-9]*\) *\(.*\)/${YELLOW}Warning:${NC} \2${YELLOW} Number: \1${NC}/"
    if [ "$CHUTNEY_WARNINGS_SUMMARY" != true ]; then
        $ECHO_Q ""
    fi
}

usage() {
    echo "Usage: $NAME [node]"
    exit 1
}

# Don't colour in log files
if [ -t 1 ]; then
    NC=$(tput sgr0)
    YELLOW=$(tput setaf 3)
    GREEN=$(tput setaf 2)
fi

NAME=$(basename "$0")
DEST="$CHUTNEY_DATA_DIR/nodes"
LOG_FILE=info.log
# ignore warnings we expect to get every time chutney runs
CHUTNEY_WARNINGS_IGNORE_EXPECTED=${CHUTNEY_WARNINGS_IGNORE_EXPECTED:-0}
# don't put spaces in CHUTNEY_PATH or IGNORE_FILE
IGNORE_FILE="$CHUTNEY_PATH/tools/ignore.warnings"
# merge all log files into one before counting entries
CHUTNEY_WARNINGS_SUMMARY=${CHUTNEY_WARNINGS_SUMMARY:-0}
SED_E='sed -n -E'
# Label errs as "Warning:", they're infrequent enough it doesn't matter
FILTER='s/^.*\[(warn|err)\]//p'
# use the --quiet setting from test-network.sh, if available
ECHO_Q=${ECHO:-"echo"}

[ -d "$DEST" ] || { echo "$NAME: no logs available"; exit 1; }
if [ $# -eq 0 ];
then
    if [ "$CHUTNEY_WARNINGS_SUMMARY" = true ]; then
        show_warnings "$DEST"
        exit 0
    fi
    for dir in "$DEST"/*;
    do
        [ -e "${dir}/$LOG_FILE" ] || continue
        show_warnings "$dir"
    done
elif [ $# -eq 1 ];
then
    [ -e "$DEST/$1/$LOG_FILE" ] || \
        { echo "$NAME: no log available"; exit 1; }
    show_warnings "$DEST/$1"
else
    usage
fi
