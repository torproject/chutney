#!/bin/sh
#
# Usage:
#    tools/diagnostics.sh [node]
#
# Output:
#    show file contents and filesystem permissions for the most recent chutney
#    network.
#
#    If the argument node is specified, show the file contents for that node,
#    otherwise, show the contents for the first node (000*).
#
#    Always show some network-wide diagnostics and authority diagnostics,
#    regardless of the chosen node.
#
# Examples:
#    tools/diagnostics.sh
#    tools/diagnostics.sh 001a

set -o errexit
set -o nounset

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

# Show the source diagnostics for $CHUTNEY_PATH and $CHUTNEY_DATA_DIR
show_source_diagnostics() {
    ## List the permissions on chutney and chutney/net
    echo "Showing permissions on '$CHUTNEY_PATH':"
    ls -al "$CHUTNEY_PATH" || \
        echo "'$CHUTNEY_PATH' ls failed"
    echo

    echo "Showing up to 10 previous nodes directories in '$CHUTNEY_DATA_DIR':"
    # We actually want to see the ls output here, not just the file names
    # shellcheck disable=SC2012
    ls -al "$CHUTNEY_DATA_DIR" | tail -10 || \
        echo "'$CHUTNEY_DATA_DIR' ls | tail failed"
    echo

    echo "Showing up to 50 nodes files, recursively:"
    ## List the link and contents of chutney/net/nodes
    ls -lR "$CHUTNEY_DATA_DIR/nodes" || \
        echo "'$CHUTNEY_DATA_DIR/nodes' ls failed"
    # shellcheck disable=SC2012
    ls -lR "$CHUTNEY_DATA_DIR/nodes/" | head -50 || \
        echo "'$CHUTNEY_DATA_DIR/nodes/' ls failed"
    echo
}

# Show the file $1, including any errors reading it
# Limit each file to 100 lines
show_file() {
    if ! test -e "$1"; then
        echo "'$1' does not exist"
        exit
    fi
    if ! test -f "$1"; then
        echo "'$1' is not a regular file"
        exit
    fi
    if ! test -r "$1"; then
        echo "'$1' is not readable"
        exit
    fi
    if ! test -s "$1"; then
        echo "'$1' is empty"
        exit
    fi

    FILE_LINES="$(grep -c "^.*$" "$1")"
    echo "'$1' contains $FILE_LINES lines:"
    # Use grep, because wc's output formatting varies
    if test "$FILE_LINES" -gt 100; then
        head -50 "$1" || echo "'$1' head failed"
        echo "..."
        tail -50 "$1" || echo "'$1' tail failed"
    else
        cat "$1" || echo "'$1' cat failed"
    fi
    echo
}

# Show the contents of all the files in the space-separated list $1
show_file_list() {
    for f in $1; do
        show_file "$f"
    done
}

# Show the contents of important files in the node directory $1
show_node_diagnostics() {
    PREV_DIR="$PWD"
    if ! cd "$1"; then
        echo "cd '$1' failed"
        return
    fi

    echo "Files for '$1':"

    ## Dump the config
    show_file torrc

    ## Dump the important directory documents
    #show_file cached-certs
    show_file cached-consensus
    show_file_list cached-descriptors*
    show_file_list cached-extrainfo*
    show_file cached-microdesc-consensus
    show_file_list cached-microdescs*
    #show_file state

    cd "$PREV_DIR" || echo "cd '$PREV_DIR' failed"
}

# Show the authority diagnostics for $CHUTNEY_DATA_DIR
show_auth_diagnostics() {
    PREV_DIR="$PWD"
    if ! cd "$CHUTNEY_DATA_DIR"; then
        echo "cd '$CHUTNEY_DATA_DIR' failed"
        return
    fi

    for d in nodes/0*a*; do
        echo "Files for authority '$d':"
        #show_file "$d/key-pinning-journal"
        #show_file "$d/router-stability"
        #show_file "$d/sr-state"
        show_file "$d/v3-status-votes"
        show_file_list "$d/unparseable-descs/"*
    done

    cd "$PREV_DIR" || echo "cd '$PREV_DIR' failed"
}

# Show the usage message for this script
usage() {
    echo "Usage: $NAME [node]"
    exit 1
}

NAME=$(basename "$0")
DEST="$CHUTNEY_DATA_DIR/nodes"

[ -d "$DEST" ] || { echo "$NAME: no nodes dir at '$DEST'"; exit 1; }
if [ $# -eq 0 ];
then
    show_source_diagnostics

    # there should only be one 000*, but if there's two, we want to see both
    echo "Files for the first authority" "$DEST"/000* ":"
    for dir in "$DEST"/000*;
    do
        show_node_diagnostics "$dir"
    done

    show_auth_diagnostics
elif [ $# -eq 1 ];
then
    show_source_diagnostics

    [ -e "$DEST/$1" ] || \
        { echo "$NAME: no node at '$DEST/$1'"; exit 1; }
    echo "Files for node $DEST/$1:"
    show_node_diagnostics "$DEST/$1"

    show_auth_diagnostics
else
    usage
fi
