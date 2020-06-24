#!/bin/sh

set -o errexit
set -o nounset

if ! "$CHUTNEY_PATH/tools/bootstrap-network.sh" "$NETWORK_FLAVOUR"; then
    if test "$?" = 77; then
	$ECHO "SKIP: $NETWORK_FLAVOUR not supported."
	exit 77
    fi
    "$DIAGNOSTICS"
    CHUTNEY_WARNINGS_IGNORE_EXPECTED=false CHUTNEY_WARNINGS_SUMMARY=false \
        "$WARNING_COMMAND"
    "$WARNINGS"
    $ECHO "bootstrap-network.sh failed"
    exit 1
fi

export CHUTNEY_BOOTSTRAP_TIME=${CHUTNEY_BOOTSTRAP_TIME:-60}
export CHUTNEY_STOP_TIME=${CHUTNEY_STOP_TIME:-0}

CHUTNEY="$CHUTNEY_PATH/chutney"


if [ "$CHUTNEY_BOOTSTRAP_TIME" -ge 0 ]; then
    # Chutney will try to verify for $CHUTNEY_BOOTSTRAP_TIME seconds each round
    n_rounds=0
    # Run CHUTNEY_ROUNDS verification rounds
    $ECHO "Running $CHUTNEY_ROUNDS verify rounds for this bootstrap..."
    while [ "$n_rounds" -lt "$CHUTNEY_ROUNDS" ]; do
        n_rounds=$((n_rounds+1))
        if ! "$CHUTNEY" verify "$CHUTNEY_NETWORK"; then
            "$DIAGNOSTICS"
            CHUTNEY_WARNINGS_IGNORE_EXPECTED=false \
                CHUTNEY_WARNINGS_SUMMARY=false \
                "$WARNING_COMMAND"
            "$WARNINGS"
            $ECHO "chutney verify round $n_rounds/$CHUTNEY_ROUNDS failed"
            exit 1
        fi
        $ECHO "Completed verify round $n_rounds/$CHUTNEY_ROUNDS in this bootstrap"
    done
else
    $ECHO "Chutney network ready and running. To stop the network, use:"
    $ECHO "$CHUTNEY stop $CHUTNEY_NETWORK"
    "$DIAGNOSTICS"
    "$WARNINGS"
    exit 0
fi

if [ "$CHUTNEY_STOP_TIME" -ge 0 ]; then
    if [ "$CHUTNEY_STOP_TIME" -gt 0 ]; then
        $ECHO "Waiting $CHUTNEY_STOP_TIME seconds before stopping the network..."
    fi
    sleep "$CHUTNEY_STOP_TIME"
    # work around a bug/feature in make -j2 (or more)
    # where make hangs if any child processes are still alive
    if ! "$CHUTNEY" stop "$CHUTNEY_NETWORK"; then
        "$DIAGNOSTICS"
        CHUTNEY_WARNINGS_IGNORE_EXPECTED=false CHUTNEY_WARNINGS_SUMMARY=false \
            "$WARNING_COMMAND"
        "$WARNINGS"
        $ECHO "chutney stop failed"
        exit 1
    fi
else
    $ECHO "Chutney network verified and running. To stop the network, use:"
    $ECHO "$CHUTNEY stop $CHUTNEY_NETWORK"
    "$DIAGNOSTICS"
    "$WARNINGS"
    exit 0
fi

"$DIAGNOSTICS"
"$WARNINGS"
exit 0
