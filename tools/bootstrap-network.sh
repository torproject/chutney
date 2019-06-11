#!/bin/sh
#
# 1. potentially stop running network
# 2. bootstrap a network from scratch as quickly as possible
# 3. tail -F all the tor log files
#
# NOTE: leaves debris around by renaming directory net/nodes
#       and creating a new net/nodes
#
# Usage:
#    tools/bootstrap-network.sh [network-flavour]
#    network-flavour: one of the files in the networks directory,
#                     (default: 'basic')
#

# Get a working chutney path
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

CHUTNEY="$CHUTNEY_PATH/chutney"
myname=$(basename "$0")

[ -d "$CHUTNEY_PATH" ] || \
    { echo "$myname: missing chutney directory: $CHUTNEY_PATH"; exit 1; }
[ -x "$CHUTNEY" ] || \
    { echo "$myname: missing chutney: $CHUTNEY"; exit 1; }

# Set the variables for the chutney network flavour
export NETWORK_FLAVOUR=${NETWORK_FLAVOUR:-"bridges+hs-v2"}
[ -n "$1" ] && { NETWORK_FLAVOUR=$1; shift; }
export CHUTNEY_NETWORK="$CHUTNEY_PATH/networks/$NETWORK_FLAVOUR"

[ -e "$CHUTNEY_NETWORK" ] || \
    { echo "$myname: missing network file: $CHUTNEY_NETWORK"; exit 1; }

"$CHUTNEY" stop "$CHUTNEY_NETWORK"

if ! "$CHUTNEY" supported "$CHUTNEY_NETWORK"; then
    echo "%myname: network not supported."
    exit 77
fi

echo "$myname: bootstrapping network: $NETWORK_FLAVOUR"
"$CHUTNEY" configure "$CHUTNEY_NETWORK"

"$CHUTNEY" start "$CHUTNEY_NETWORK"
sleep 3
if ! "$CHUTNEY" status "$CHUTNEY_NETWORK"; then
    # Try to work out why the start or status command is failing
    CHUTNEY_DEBUG=1 "$CHUTNEY" start "$CHUTNEY_NETWORK"
    # Wait a little longer, just in case
    sleep 6
    CHUTNEY_DEBUG=1 "$CHUTNEY" status "$CHUTNEY_NETWORK"
fi
