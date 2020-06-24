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
#                     (default: 'bridges+hs-v23')

set -o errexit
set -o nounset

# Set some default values if the variables are not already set
: "${CHUTNEY_WARNINGS_ONLY:=false}"
: "${CHUTNEY_WARNINGS_SKIP:=false}"
: "${CHUTNEY_DIAGNOSTICS_ONLY:=false}"
: "${NETWORK_DRY_RUN:=false}"
: "${USE_COVERAGE_BINARY:=false}"
: "${CHUTNEY_DIAGNOSTICS:=false}"
: "${CHUTNEY_DATA_DIR:=}"

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

CHUTNEY="$CHUTNEY_PATH/chutney"
myname=$(basename "$0")

[ -d "$CHUTNEY_PATH" ] || \
    { echo "$myname: missing chutney directory: $CHUTNEY_PATH"; exit 1; }
[ -x "$CHUTNEY" ] || \
    { echo "$myname: missing chutney: $CHUTNEY"; exit 1; }

# Set the variables for the chutney network flavour
export NETWORK_FLAVOUR=${NETWORK_FLAVOUR:-"bridges+hs-v23"}
[ -n "$1" ] && { NETWORK_FLAVOUR=$1; shift; }
export CHUTNEY_NETWORK="$CHUTNEY_PATH/networks/$NETWORK_FLAVOUR"

[ -e "$CHUTNEY_NETWORK" ] || \
    { echo "$myname: missing network file: $CHUTNEY_NETWORK"; exit 1; }

"$CHUTNEY" stop "$CHUTNEY_NETWORK"

if ! "$CHUTNEY" supported "$CHUTNEY_NETWORK"; then
    echo "%myname: network not supported."
    exit 77
fi

# Find out how many phases there are.  This will set CHUTNEY_CONFIG_PHASES
# and CHUTNEY_LAUNCH_PHASES.
if [ -z "${CHUTNEY_CONFIG_PHASES:-}" ] || [ -z "${CHUTNEY_LAUNCH_PHASES:-}" ]; then
    eval "$("$CHUTNEY" print_phases "$CHUTNEY_NETWORK" |grep =)"
fi

$ECHO "$myname: bootstrapping network: $NETWORK_FLAVOUR"
for config_idx in $(seq 1 "$CHUTNEY_CONFIG_PHASES"); do
    export CHUTNEY_CONFIG_PHASE="${config_idx}"
    "$CHUTNEY" configure "$CHUTNEY_NETWORK"
done

for launch_idx in $(seq 1 "$CHUTNEY_LAUNCH_PHASES"); do
    export CHUTNEY_LAUNCH_PHASE="${launch_idx}"
    $ECHO "======= phase ${launch_idx}"
    "$CHUTNEY" start "$CHUTNEY_NETWORK"
    sleep 3
    if ! "$CHUTNEY" status "$CHUTNEY_NETWORK"; then
	# Try to work out why the start or status command is failing
	CHUTNEY_DEBUG=1 "$CHUTNEY" start "$CHUTNEY_NETWORK"
	# Wait a little longer, just in case
	sleep 6
	CHUTNEY_DEBUG=1 "$CHUTNEY" status "$CHUTNEY_NETWORK"
    fi

    # We allow up to CHUTNEY_START_TIME for each bootstrap phase to
    # complete.
    export CHUTNEY_START_TIME=${CHUTNEY_START_TIME:-120}

    if [ "$CHUTNEY_START_TIME" -ge 0 ]; then
	$ECHO "Waiting up to $CHUTNEY_START_TIME seconds for all nodes in phase ${launch_idx} to bootstrap..."
	# We require the network to bootstrap, before we verify
	if ! "$CHUTNEY" wait_for_bootstrap "$CHUTNEY_NETWORK"; then
            "$DIAGNOSTICS"
            CHUTNEY_WARNINGS_IGNORE_EXPECTED=false \
            CHUTNEY_WARNINGS_SUMMARY=false \
            "$WARNING_COMMAND"
            "$WARNINGS"
            $ECHO "chutney boostrap phase ${launch_idx} failed (in wait_for_bootstrap)"
            exit 1
	fi
    else
	$ECHO "Chutney network launched and running. To stop the network, use:"
	$ECHO "$CHUTNEY stop $CHUTNEY_NETWORK"
	"$DIAGNOSTICS"
	"$WARNINGS"
    fi
done

exit 0
