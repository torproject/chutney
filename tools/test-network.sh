#!/usr/bin/env bash

ECHO_N="/bin/echo -n"

# Output is prefixed with the name of the script
myname=$(basename "$0")

# default to summarising unexpected warnings
export CHUTNEY_WARNINGS_IGNORE_EXPECTED=${CHUTNEY_WARNINGS_IGNORE_EXPECTED:-true}
export CHUTNEY_WARNINGS_SUMMARY=${CHUTNEY_WARNINGS_SUMMARY:-true}

# what we say when we fail
UPDATE_YOUR_CHUTNEY="Please update your chutney uisng 'git pull'."

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
      # This isn't the best name for this variable, but we kept it the same
      # for backwards compatibility
      export CHUTNEY_BOOTSTRAP_TIME="$2"
      shift
    ;;
    # The amount of time chutney will wait after successfully verifying
    # If negative, chutney exits without stopping
    --stop-time)
      export CHUTNEY_STOP_TIME="$2"
      shift
    ;;
    # Environmental variables used by chutney verify performance tests
    # Send this many bytes per client connection (10 KBytes)
    --data|--data-bytes|--data-byte|--bytes|--byte)
      export CHUTNEY_DATA_BYTES="$2"
      shift
    ;;
    # Make this many connections per client (1)
    # Note: If you create 7 or more connections to a hidden service from
    # a single Tor 0.2.7 client, you'll likely get a verification failure due
    # to #15937. This is fixed in 0.2.8.
    --connections|--connection|--connection-count|--count)
      export CHUTNEY_CONNECTIONS="$2"
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
    # The IPv6 address to bind to, default is not to bind to an IPv6 address
    --ipv6|--v6|-6)
      export CHUTNEY_LISTEN_ADDRESS_V6="$2"
      shift
      ;;
    --coverage)
      export USE_COVERAGE_BINARY=true
      ;;
    --dry-run)
      # process arguments, but don't call any other scripts
      export NETWORK_DRY_RUN=true
      ;;
    # we summarise unexpected warnings by default
    # this shows all warnings per-node
    --all-warnings)
      export CHUTNEY_WARNINGS_IGNORE_EXPECTED=false
      export CHUTNEY_WARNINGS_SUMMARY=false
      ;;
    # this skips warnings entirely
    --no-warnings)
      export CHUTNEY_WARNINGS_SKIP=true
      ;;
    *)
      echo "$myname: Sorry, I don't know what to do with '$1'."
      echo "$UPDATE_YOUR_CHUTNEY"
      # continue processing arguments during a dry run
      if [ "$NETWORK_DRY_RUN" != true ]; then
          exit 2
      fi
    ;;
  esac
  shift
done

# optional: $TOR_DIR is the tor build directory
# it's used to find the location of tor binaries
# if it's not set:
#  - set it ro $BUILDDIR, or
#  - if $PWD looks like a tor build directory, set it to $PWD, or
#  - unset $TOR_DIR, and let chutney fall back to finding tor binaries in $PATH
if [ ! -d "$TOR_DIR" ]; then
    if [ -d "$BUILDDIR/src/or" -a -d "$BUILDDIR/src/tools" ]; then
        # Choose the build directory
        # But only if it looks like one
        echo "$myname: \$TOR_DIR not set, trying \$BUILDDIR"
        export TOR_DIR="$BUILDDIR"
    elif [ -d "$PWD/src/or" -a -d "$PWD/src/tools" ]; then
        # Guess the tor directory is the current directory
        # But only if it looks like one
        echo "$myname: \$TOR_DIR not set, trying \$PWD"
        export TOR_DIR="$PWD"
    elif [ -d "$PWD/../tor" -a -d "$PWD/../tor/src/or" -a \
	   -d "$PWD/../tor/src/tools" ]; then
        # Guess the tor directory is next to the current directory
        # But only if it looks like one
        echo "$myname: \$TOR_DIR not set, trying \$PWD/../tor"
        export TOR_DIR="$PWD/../tor"
    else
        echo "$myname: no \$TOR_DIR, chutney will use \$PATH for tor binaries"
        unset TOR_DIR
    fi
fi

# make TOR_DIR absolute
if [ -d "$PWD/$TOR_DIR" -a -d "$PWD/$TOR_DIR/src/or" -a \
    -d "$PWD/$TOR_DIR/src/tools" ]; then
    export TOR_DIR="$PWD/$TOR_DIR"
fi

# mandatory: $CHUTNEY_PATH is the path to the chutney launch script
# if it's not set:
#  - if $PWD looks like a chutney directory, set it to $PWD, or
#  - set it based on $TOR_DIR, expecting chutney to be next to tor, or
#  - fail and tell the user how to clone the chutney repository
if [ ! -d "$CHUTNEY_PATH" -o ! -x "$CHUTNEY_PATH/chutney" -o \
     ! -f "$CHUTNEY_PATH/chutney" ]; then
    if [ -x "$PWD/chutney" -a -f "$PWD/chutney" ]; then
        echo "$myname: \$CHUTNEY_PATH not valid, trying \$PWD"
        export CHUTNEY_PATH="$PWD"
    elif [ -d "`dirname \"$0\"`/.." -a \
	   -x "`dirname \"$0\"`/../chutney" -a \
	   -f "`dirname \"$0\"`/../chutney" ]; then
        echo "$myname: \$CHUTNEY_PATH not valid, using this script's location"
        export CHUTNEY_PATH="`dirname \"$0\"`/.."
    elif [ -d "$TOR_DIR" -a -d "$TOR_DIR/../chutney" -a \
           -x "$TOR_DIR/../chutney/chutney" -a \
	   -f "$TOR_DIR/../chutney/chutney" ]; then
        echo "$myname: \$CHUTNEY_PATH not valid, trying \$TOR_DIR/../chutney"
        export CHUTNEY_PATH="$TOR_DIR/../chutney"
    else
        # TODO: work out how to package and install chutney,
        # so users can find it in $PATH
        echo "$myname: missing 'chutney' in \$CHUTNEY_PATH ($CHUTNEY_PATH)"
        echo "$myname: Get chutney: git clone https://git.torproject.org/\
chutney.git"
        echo "$myname: Set \$CHUTNEY_PATH to a non-standard location: export \
CHUTNEY_PATH=\`pwd\`/chutney"
        unset CHUTNEY_PATH
        exit 1
    fi
fi

# make chutney path absolute
if [ -d "$PWD/$CHUTNEY_PATH" -a -x "$PWD/$CHUTNEY_PATH/chutney" ]; then
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
    # TOR_DIR is absolute, so these are absolute paths
    export CHUTNEY_TOR="${TOR_DIR}/src/or/${tor_name}"
    export CHUTNEY_TOR_GENCERT="${TOR_DIR}/src/tools/${tor_gencert_name}"
else
    # these are binary names, they will be searched for in $PATH
    export CHUTNEY_TOR="${tor_name}"
    export CHUTNEY_TOR_GENCERT="${tor_gencert_name}"
fi

# Set the variables for the chutney network flavour
export NETWORK_FLAVOUR=${NETWORK_FLAVOUR:-"bridges+hs"}
export CHUTNEY_NETWORK="$CHUTNEY_PATH/networks/$NETWORK_FLAVOUR"

# And finish up if we're doing a dry run
if [ "$NETWORK_DRY_RUN" = true ]; then
    # we can't exit here, it breaks argument processing
    # this only works in bash: return semantics are shell-specific
    return 2>/dev/null || exit
fi

"$CHUTNEY_PATH/tools/bootstrap-network.sh" "$NETWORK_FLAVOUR" || exit 2

# chutney starts verifying after 20 seconds, keeps on trying for 60 seconds,
# and then stops immediately (by default)
# Even the fastest chutney networks take 5-10 seconds for their first consensus
# and then 10 seconds after that for relays to bootstrap and upload descriptors
export CHUTNEY_START_TIME=${CHUTNEY_START_TIME:-20}
export CHUTNEY_BOOTSTRAP_TIME=${CHUTNEY_BOOTSTRAP_TIME:-60}
export CHUTNEY_STOP_TIME=${CHUTNEY_STOP_TIME:-0}

CHUTNEY="$CHUTNEY_PATH/chutney"
if [ "$CHUTNEY_WARNINGS_SKIP" = true ]; then
  WARNINGS=true
else
  WARNINGS="$CHUTNEY_PATH/tools/warnings.sh"
fi

if [ "$CHUTNEY_START_TIME" -ge 0 ]; then
  echo "Waiting ${CHUTNEY_START_TIME} seconds for a consensus containing relays to be generated..."
  sleep "$CHUTNEY_START_TIME"
else
  echo "Chutney network launched and running. To stop the network, use:"
  echo "$CHUTNEY stop $CHUTNEY_NETWORK"
  "$WARNINGS"
  exit 0
fi

if [ "$CHUTNEY_BOOTSTRAP_TIME" -ge 0 ]; then
  # Chutney will try to verify for $CHUTNEY_BOOTSTRAP_TIME seconds
  "$CHUTNEY" verify "$CHUTNEY_NETWORK"
  VERIFY_EXIT_STATUS="$?"
else
  echo "Chutney network ready and running. To stop the network, use:"
  echo "$CHUTNEY" stop "$CHUTNEY_NETWORK"
  "$WARNINGS"
  exit 0
fi

if [ "$CHUTNEY_STOP_TIME" -ge 0 ]; then
  if [ "$CHUTNEY_STOP_TIME" -gt 0 ]; then
    echo "Waiting ${CHUTNEY_STOP_TIME} seconds before stopping the network..."
  fi
  sleep "$CHUTNEY_STOP_TIME"
  # work around a bug/feature in make -j2 (or more)
  # where make hangs if any child processes are still alive
  "$CHUTNEY" stop "$CHUTNEY_NETWORK"
  "$WARNINGS"
  exit "$VERIFY_EXIT_STATUS"
else
  echo "Chutney network verified and running. To stop the network, use:"
  echo "$CHUTNEY stop $CHUTNEY_NETWORK"
  "$WARNINGS"
  exit 0
fi
