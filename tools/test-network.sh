#!/bin/sh

export ECHO="${ECHO:-echo}"

# Output is prefixed with the name of the script
myname=$(basename "$0")

# default to one round
export CHUTNEY_ROUNDS=${CHUTNEY_ROUNDS:-1}

# default to summarising unexpected warnings
export CHUTNEY_WARNINGS_IGNORE_EXPECTED=${CHUTNEY_WARNINGS_IGNORE_EXPECTED:-true}
export CHUTNEY_WARNINGS_SUMMARY=${CHUTNEY_WARNINGS_SUMMARY:-true}

# default to exiting when this script exits
export CHUTNEY_CONTROLLING_PID=${CHUTNEY_CONTROLLING_PID:-$$}

# default to allowing zero failures
export CHUTNEY_ALLOW_FAILURES=${CHUTNEY_ALLOW_FAILURES:-0}

# default to no DNS: this is a safe, working default for most users
# If a custom test expects DNS, it needs to set CHUTNEY_DNS_CONF
export CHUTNEY_DNS_CONF=${CHUTNEY_DNS_CONF:-/dev/null}

# what we say when we fail
UPDATE_YOUR_CHUTNEY="Please update your chutney using 'git pull'."

until [ -z "$1" ]
do
    case "$1" in
        # the path to the chutney directory
        --chutney-path)
            export CHUTNEY_PATH="$2"
            shift
        ;;
        --tor-path)
            # the path of a tor build directory
            # --tor-path overrides --tor and --tor-gencert
            export TOR_DIR="$2"
            shift
        ;;
        --tor)
            # the name or path of a tor binary
            export CHUTNEY_TOR="$2"
            shift
        ;;
        --tor-gencert)
            # the name or path of a tor-gencert binary
            export CHUTNEY_TOR_GENCERT="$2"
            shift
            ;;
        --debug)
            export CHUTNEY_DEBUG="yes"
            ;;
        --flavor|--flavour|--network-flavor|--network-flavour)
            export NETWORK_FLAVOUR="$2"
            shift
        ;;
        # The amount of time chutney will wait before starting to verify
        # If negative, chutney exits straight after launching the network
        --start-time)
            export CHUTNEY_START_TIME="$2"
            shift
        ;;
        # The amount of time chutney will try to verify, before failing
        # If negative, chutney exits without verifying
        --delay|--sleep|--bootstrap-time|--time|--verify-time)
            # This isn't the best name for this variable, but we kept it the
            # same for backwards compatibility
            export CHUTNEY_BOOTSTRAP_TIME="$2"
            shift
        ;;
        # The amount of time chutney will wait after successfully verifying
        # If negative, chutney exits without stopping
        --stop-time)
            export CHUTNEY_STOP_TIME="$2"
            shift
        ;;
        # If all of the CHUTNEY_*_TIME options are positive, chutney will ask
        # tor to exit when this PID exits. Set to 1 or lower to disable.
        --controlling-pid)
            export CHUTNEY_CONTROLLING_PID="$2"
            shift
        ;;
        # Environmental variables used by chutney verify performance tests
        # Send this many bytes per client connection (10 KBytes)
        --data|--data-bytes|--data-byte|--bytes|--byte)
            export CHUTNEY_DATA_BYTES="$2"
            shift
        ;;
        # Make this many simultaneous connections per client (1)
        --connections|--connection|--connection-count|--count)
            export CHUTNEY_CONNECTIONS="$2"
            shift
        ;;
        # Run this many verification rounds (1)
        --rounds)
            export CHUTNEY_ROUNDS="$2"
            shift
        ;;
        # Make each client connect to each HS (0)
        # 0 means a single client connects to each HS
        # 1 means every client connects to every HS
        --hs-multi-client|--hs-multi-clients|--hs-client|--hs-clients)
            export CHUTNEY_HS_MULTI_CLIENT="$2"
            shift
            ;;
        # The IPv4 address to bind to, defaults to 127.0.0.1
        --ipv4|--v4|-4|--ip)
            export CHUTNEY_LISTEN_ADDRESS="$2"
            shift
            ;;
        # The IPv6 address to bind to, default is not to bind to an
        # IPv6 address
        --ipv6|--v6|-6)
            export CHUTNEY_LISTEN_ADDRESS_V6="$2"
            shift
            ;;
        # The DNS server config for Tor Exits. Chutney's default is
        # /etc/resolv.conf, even if tor's compile time default is different.
        --dns-conf)
            export CHUTNEY_DNS_CONF="$2"
            shift
            ;;
        # Do not make any DNS queries. This is incompatible with external
        # controllers that use SETCONF.
        --offline)
            export CHUTNEY_DNS_CONF="/dev/null"
            ;;
        # Use tor's compile-time default for ServerDNSResolvConfFile.
        --dns-conf-default)
            export CHUTNEY_DNS_CONF=""
            ;;
        # Warning Options
        # we summarise unexpected warnings by default
        # this shows all warnings per-node
        --all-warnings)
            export CHUTNEY_WARNINGS_IGNORE_EXPECTED=false
            export CHUTNEY_WARNINGS_SUMMARY=false
            ;;
        # this doesn't run chutney, and only logs warnings
        --only-warnings)
            export CHUTNEY_WARNINGS_ONLY=true
            ;;
        # this skips warnings entirely
        --no-warnings)
            export CHUTNEY_WARNINGS_SKIP=true
            ;;
        # Expert options
        # Code Coverage Binary
        --coverage)
            export USE_COVERAGE_BINARY=true
            ;;
        # Do Nothing (but process arguments and set environmental variables)
        --dry-run)
            # process arguments, but don't call any other scripts
            export NETWORK_DRY_RUN=true
            ;;
        # The net directory, usually chutney/net
        --net-dir)
            export CHUTNEY_DATA_DIR="$2"
            shift
            ;;
        # How many failures should we allow? Defaults to 0.
        --allow-failures)
            export CHUTNEY_ALLOW_FAILURES="$2"
            shift
            ;;
        # Try not to say anything (applies only to this script)
        --quiet)
            export ECHO=true
            ;;
        # Oops
        *)
            $ECHO "$myname: Sorry, I don't know what to do with '$1'."
            $ECHO "$UPDATE_YOUR_CHUTNEY"
            # continue processing arguments during a dry run
            if [ "$NETWORK_DRY_RUN" != true ]; then
                exit 1
            fi
        ;;
    esac
    shift
done

# If the DNS server doesn't work, tor exits may reject all exit traffic, and
# chutney may fail
if [ "$CHUTNEY_WARNINGS_ONLY" != true ]; then
    $ECHO "$myname: using CHUTNEY_DNS_CONF '$CHUTNEY_DNS_CONF'"
fi

# optional: $TOR_DIR is the tor build directory
# it's used to find the location of tor binaries
# if it's not set:
#  - set it to $BUILDDIR, or
#  - if $PWD looks like a tor build directory, set it to $PWD, or
#  - unset $TOR_DIR, and let chutney fall back to finding tor binaries in
#    $CHUTNEY_TOR and $CHUTNEY_TOR_GENCERT, or $PATH
#
# Find the Tor build dir using the src/tools dir
if [ ! -d "$TOR_DIR" ]; then
    if [ -d "$BUILDDIR/src/tools" ]; then
        # Choose the build directory
        # But only if it looks like one
        $ECHO "$myname: \$TOR_DIR not set, trying \$BUILDDIR"
        export TOR_DIR="$BUILDDIR"
    elif [ -d "$PWD/src/tools" ]; then
        # Guess the tor directory is the current directory
        # But only if it looks like one
        $ECHO "$myname: \$TOR_DIR not set, trying \$PWD"
        export TOR_DIR="$PWD"
    elif [ -d "$PWD/../tor" ] && [ -d "$PWD/../tor/src/tools" ]; then
        # Guess the tor directory is next to the current directory
        # But only if it looks like one
        $ECHO "$myname: \$TOR_DIR not set, trying \$PWD/../tor"
        export TOR_DIR="$PWD/../tor"
    else
        $ECHO "$myname: no \$TOR_DIR, chutney will use \$CHUTNEY_TOR and \$CHUTNEY_TOR_GENCERT as tor binary paths, or search \$PATH for tor binary names"
        unset TOR_DIR
    fi
fi

# Now find the name of the Tor app dir, which changed in Tor 0.3.5
if [ -d "$TOR_DIR" ]; then
    if [ -d "$TOR_DIR/src/app" ] && [ -d "$TOR_DIR/src/or" ]; then
        $ECHO "$myname: \$TOR_DIR has a Tor 0.3.5 or later build directory, and a Tor 0.3.4 or earlier build directory"
        $ECHO "$myname: Please remove $TOR_DIR/src/app or $TOR_DIR/src/or, or set \$CHUTNEY_TOR"
        exit 1
    elif [ -d "$TOR_DIR/src/app" ]; then
        $ECHO "$myname: \$TOR_DIR is a Tor 0.3.5 or later build directory"
        TOR_APP_DIR="$TOR_DIR/src/app"
    elif [ -d "$TOR_DIR/src/or" ]; then
        $ECHO "$myname: \$TOR_DIR is a Tor 0.3.4 or earlier build directory"
        TOR_APP_DIR="$TOR_DIR/src/or"
    else
        $ECHO "$myname: \$TOR_DIR has no src/app or src/or, looking elsewhere"
        unset TOR_DIR
    fi
fi

# make TOR_DIR and TOR_APP_DIR absolute
if [ -d "$PWD/$TOR_DIR" ] && [ -d "$PWD/$TOR_APP_DIR" ] && \
       [ -d "$PWD/$TOR_DIR/src/tools" ]; then
    export TOR_DIR="$PWD/$TOR_DIR"
    export TOR_APP_DIR="$PWD/$TOR_APP_DIR"
fi

TOOLS_DIR=$(dirname "$0")

# mandatory: $CHUTNEY_PATH is the path to the chutney launch script
# if it's not set:
#  - if $PWD looks like a chutney directory, set it to $PWD, or
#  - set it based on $TOR_DIR, expecting chutney to be next to tor, or
#  - fail and tell the user how to clone the chutney repository
if [ ! -d "$CHUTNEY_PATH" ] || [ ! -x "$CHUTNEY_PATH/chutney" ] || \
    [ ! -f "$CHUTNEY_PATH/chutney" ]; then
    if [ -x "$PWD/chutney" ] && [ -f "$PWD/chutney" ]; then
        $ECHO "$myname: \$CHUTNEY_PATH not valid, trying \$PWD"
        export CHUTNEY_PATH="$PWD"
    elif [ -d "$TOOLS_DIR/.." ] && \
         [ -x "$TOOLS_DIR)/../chutney" ] && \
         [ -f "$TOOLS_DIR/../chutney" ]; then
        $ECHO "$myname: \$CHUTNEY_PATH not valid, using this script's location"
        export CHUTNEY_PATH="$TOOLS_DIR/.."
    elif [ -d "$TOR_DIR" ] && \
	 [ -d "$TOR_DIR/../chutney" ] && \
         [ -x "$TOR_DIR/../chutney/chutney" ] && \
	 [ -f "$TOR_DIR/../chutney/chutney" ]; then
        $ECHO "$myname: \$CHUTNEY_PATH not valid, trying \$TOR_DIR/../chutney"
        export CHUTNEY_PATH="$TOR_DIR/../chutney"
    else
        # TODO: work out how to package and install chutney,
        # so users can find it in $PATH
        $ECHO "$myname: missing 'chutney' in \$CHUTNEY_PATH ($CHUTNEY_PATH)"
        $ECHO "$myname: Get chutney: git clone https://git.torproject.org/chutney.git"
        $ECHO "$myname: Set \$CHUTNEY_PATH to a non-standard location: export CHUTNEY_PATH=\`pwd\`/chutney"
        unset CHUTNEY_PATH
        exit 1
    fi
fi

# make chutney path absolute
if [ -d "$PWD/$CHUTNEY_PATH" ] && [ -x "$PWD/$CHUTNEY_PATH/chutney" ]; then
    export CHUTNEY_PATH="$PWD/$CHUTNEY_PATH"
fi

# For picking up the right tor binaries
# Choose coverage binaries, if selected
tor_name=tor
tor_gencert_name=tor-gencert
if [ "$USE_COVERAGE_BINARY" = true ]; then
    tor_name=tor-cov
fi
# If $TOR_DIR isn't set, chutney looks for tor binaries by name or path
# using $CHUTNEY_TOR and $CHUTNEY_TOR_GENCERT, and then falls back to
# looking for tor and tor-gencert in $PATH
if [ -d "$TOR_DIR" ]; then
    $ECHO "$myname: Setting \$CHUTNEY_TOR and \$CHUTNEY_TOR_GENCERT based on TOR_DIR: '$TOR_DIR'"
    # TOR_DIR is absolute, so these are absolute paths
    export CHUTNEY_TOR="$TOR_APP_DIR/$tor_name"
    export CHUTNEY_TOR_GENCERT="$TOR_DIR/src/tools/$tor_gencert_name"
else
    if [ -x "$CHUTNEY_TOR" ]; then
        $ECHO "$myname: Assuming \$CHUTNEY_TOR is a path to a binary"
    elif [ -n "$CHUTNEY_TOR" ]; then
        $ECHO "$myname: Assuming \$CHUTNEY_TOR is a binary name in \$PATH"
    else
        $ECHO "$myname: Setting \$CHUTNEY_TOR to the standard binary name in \$PATH"
        export CHUTNEY_TOR="$tor_name"
    fi
    if [ -x "$CHUTNEY_TOR_GENCERT" ]; then
        $ECHO "$myname: Assuming \$CHUTNEY_TOR_GENCERT is a path to a binary"
    elif [ -n "$CHUTNEY_TOR_GENCERT" ]; then
        $ECHO "$myname: Assuming \$CHUTNEY_TOR_GENCERT is a binary name in \$PATH"
    else
        $ECHO "$myname: Setting \$CHUTNEY_TOR_GENCERT to the standard binary name in \$PATH"
        export CHUTNEY_TOR_GENCERT="$tor_gencert_name"
    fi
fi
$ECHO "$myname: Using \$CHUTNEY_TOR: '$CHUTNEY_TOR' and \$CHUTNEY_TOR_GENCERT: '$CHUTNEY_TOR_GENCERT'"

# Set the variables for the chutney network flavour
export NETWORK_FLAVOUR=${NETWORK_FLAVOUR:-"bridges+hs-v2"}
export CHUTNEY_NETWORK="$CHUTNEY_PATH/networks/$NETWORK_FLAVOUR"

export WARNING_COMMAND="$CHUTNEY_PATH/tools/warnings.sh"
if [ "$CHUTNEY_WARNINGS_SKIP" = true ]; then
    export WARNINGS=true
else
    export WARNINGS="$WARNING_COMMAND"
fi

# And finish up if we're doing a dry run
if [ "$NETWORK_DRY_RUN" = true ] || [ "$CHUTNEY_WARNINGS_ONLY" = true ]; then
    if [ "$CHUTNEY_WARNINGS_ONLY" = true ]; then
        "$WARNINGS"
    fi
    $ECHO "Finished dry run"
    # This breaks sourcing this script: that is intentional, as the previous
    # behaviour only worked with bash as /bin/sh
    exit 0
fi

n_attempts=0
max_attempts=$((CHUTNEY_ALLOW_FAILURES+1))

while [ "$n_attempts" -lt "$max_attempts" ]; do
    n_attempts=$((n_attempts+1))
    $ECHO "==== Running tests: attempt $n_attempts/$max_attempts"
    if "$CHUTNEY_PATH/tools/test-network-impl.sh"; then
	$ECHO "==== Chutney succeeded after $n_attempts attempt(s)."
	exit 0
    fi
    if test "$?" = 77; then
	exit 77
    fi
done

$ECHO "Chutney failed $n_attempts times; we may have a problem here."
exit 1
