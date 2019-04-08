#!/bin/sh
#
# Usage:
#    tools/hsaddress.sh [hs_node]
# Output: for each HS outputs its onion address. If the argument node is
#    specified, it only shows the onion address of that node.
# Examples: tools/hsaddress.sh
#           tools/hsaddress.sh 025h

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

NAME=$(basename "$0")
DEST="$CHUTNEY_DATA_DIR/nodes"
TARGET=hidden_service/hostname

usage() {
    echo "Usage: $NAME [hs_node]"
    exit 1
}

show_address() {
    cat "$1"
}

[ -d "$DEST" ] || { echo "$NAME: no nodes available"; exit 1; }
if [ $# -eq 0 ];
then
    # support hOLD
    for dir in "$DEST"/*h*;
    do
        FILE="${dir}/$TARGET"
        [ -e "$FILE" ] || continue
        echo "Node $(basename "$dir"): " | tr -d "\n"
        show_address "$FILE"
    done
elif [ $# -eq 1 ];
then
    [ -d "$DEST/$1" ] || { echo "$NAME: $1 not found"; exit 1; }
    # we don't check the name of the HS directory, because tags vary
    FILE="$DEST/$1/$TARGET"
    [ -e "$FILE" ] || { echo "$NAME: $FILE not found"; exit 1; }
    show_address "$FILE"
else
    usage
fi
