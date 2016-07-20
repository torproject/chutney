#! /bin/sh

ECHO_N="/bin/echo -n"

# Output is prefixed with the name of the script
myname=$(basename $0)

until [ -z "$1" ]
do
  case "$1" in
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
    --delay|--sleep|--bootstrap-time|--time)
      export CHUTNEY_BOOTSTRAP_TIME="$2"
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
    --coverage)
      export USE_COVERAGE_BINARY=true
      ;;
    --dry-run)
      # process arguments, but don't call any other scripts
      export NETWORK_DRY_RUN=true
      ;;
    *)
      echo "$myname: Sorry, I don't know what to do with '$1'."
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

# mandatory: $CHUTNEY_PATH is the path to the chutney launch script
# if it's not set:
#  - if $PWD looks like a chutney directory, set it to $PWD, or
#  - set it based on $TOR_DIR, expecting chutney to be next to tor, or
#  - fail and tell the user how to clone the chutney repository
if [ ! -d "$CHUTNEY_PATH" -o ! -x "$CHUTNEY_PATH/chutney" ]; then
    if [ -x "$PWD/chutney" ]; then
        echo "$myname: \$CHUTNEY_PATH not valid, trying \$PWD"
        export CHUTNEY_PATH="$PWD"
    elif [ -d "`dirname \"$0\"`/.." -a \
	   -x "`dirname \"$0\"`/../chutney" ]; then
        echo "$myname: \$CHUTNEY_PATH not valid, using this script's location"
        export CHUTNEY_PATH="`dirname \"$0\"`/.."
    elif [ -d "$TOR_DIR" -a -d "$TOR_DIR/../chutney" -a \
           -x "$TOR_DIR/../chutney/chutney" ]; then
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

# For picking up the right tor binaries.
# If $TOR_DIR isn't set, chutney looks for tor binaries by name or path
# using $CHUTNEY_TOR and $CHUTNEY_TOR_GENCERT, and then falls back to
# looking for tor and tor-gencert in $PATH
if [ -d "$TOR_DIR" ]; then
    tor_name=tor
    tor_gencert_name=tor-gencert
    if [ "$USE_COVERAGE_BINARY" = true ]; then
        tor_name=tor-cov
    fi
    export CHUTNEY_TOR="${TOR_DIR}/src/or/${tor_name}"
    export CHUTNEY_TOR_GENCERT="${TOR_DIR}/src/tools/${tor_gencert_name}"
fi

# Set the variables for the chutney network flavour
export NETWORK_FLAVOUR=${NETWORK_FLAVOUR:-"bridges+hs"}
export CHUTNEY_NETWORK=networks/$NETWORK_FLAVOUR

# And finish up if we're doing a dry run
if [ "$NETWORK_DRY_RUN" = true ]; then
    # we can't exit here, it breaks argument processing
    return
fi

cd "$CHUTNEY_PATH"
./tools/bootstrap-network.sh $NETWORK_FLAVOUR || exit 2

# chutney verify starts immediately, and keeps on trying for 60 seconds
CHUTNEY_BOOTSTRAP_TIME=${CHUTNEY_BOOTSTRAP_TIME:-60}
# but even the fastest tor networks take 5 seconds for their first consensus
# and then 10 seconds after that for relays to bootstrap and upload descriptors
echo "Waiting 15 seconds for a consensus containing relays to be generated..."
sleep 15
./chutney verify $CHUTNEY_NETWORK
VERIFY_EXIT_STATUS=$?
# work around a bug/feature in make -j2 (or more)
# where make hangs if any child processes are still alive
./chutney stop $CHUTNEY_NETWORK
exit $VERIFY_EXIT_STATUS
