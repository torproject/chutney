#!/usr/bin/env bash
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

if [ ! -d "$CHUTNEY_PATH" -o ! -x "$CHUTNEY_PATH/chutney" ]; then
    # looks like a broken path: use the path to this tool instead
    TOOLS_PATH=`dirname "$0"`
    export CHUTNEY_PATH=`dirname "$TOOLS_PATH"`
fi
if [ -d "$PWD/$CHUTNEY_PATH" -a -x "$PWD/$CHUTNEY_PATH/chutney" ]; then
    # looks like a relative path: make chutney path absolute
    export CHUTNEY_PATH="$PWD/$CHUTNEY_PATH"
fi

VOTING_OFFSET=6
CHUTNEY="$CHUTNEY_PATH/chutney"
myname=$(basename "$0")

[ -d "$CHUTNEY_PATH" ] || \
    { echo "$myname: missing chutney directory: $CHUTNEY_PATH"; exit 1; }
[ -x "$CHUTNEY" ] || \
    { echo "$myname: missing chutney: $CHUTNEY"; exit 1; }
flavour=basic; [ -n "$1" ] && { flavour=$1; shift; }

export CHUTNEY_NETWORK="$CHUTNEY_PATH/networks/$NETWORK_FLAVOUR"

[ -e "$CHUTNEY_NETWORK" ] || \
  { echo "$myname: missing network file: $CHUTNEY_NETWORK"; exit 1; }

# Chutney must be launched at $CHUTNEY_PATH, at least until #21521 is fixed
cd "$CHUTNEY_PATH"

"$CHUTNEY" stop "$CHUTNEY_NETWORK"

echo "$myname: bootstrapping network: $flavour"
"$CHUTNEY" configure "$CHUTNEY_NETWORK"

# TODO: Make 'chutney configure' take an optional offset argument and
# use the templating system in Chutney to set this instead of editing
# files like this.
offset=$(expr \( $(date +%s) + $VOTING_OFFSET \) % 300)
CONFOPT="TestingV3AuthVotingStartOffset"
for file in "$CHUTNEY_PATH"/net/nodes/*a/torrc ; do
    sed -i.bak -e "s/^${CONFOPT}.*$/${CONFOPT} $offset/1" $file
done

"$CHUTNEY" start "$CHUTNEY_NETWORK"
sleep 1
"$CHUTNEY" status "$CHUTNEY_NETWORK"
#echo "tail -F net/nodes/*/notice.log"
