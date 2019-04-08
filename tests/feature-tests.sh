#!/bin/sh

# Exit on errors
set -e
# Verbose mode
set -v

# Output is prefixed with the name of the script
myname=$(basename "$0")

echo "$myname: finding chutney directory"
TEST_DIR=$(dirname "$0")
CHUTNEY_DIR=$(dirname "$TEST_DIR")

echo "$myname: changing to chutney directory"
cd "$CHUTNEY_DIR"


echo "$myname: running chutney and test-network.sh feature tests"
echo "$myname: extra arguments: $*"


echo "$myname: doing a dry run"

tools/test-network.sh --dry-run "$@"

echo "$myname: testing warning levels"
# To avoid a combinatorial explosion of tests, we test each chutney feature
# with a different chutney network. We test the chutney networks used by tor
# for its "make test-network-all", in the order they appear in
# src/test/include.am.

tools/test-network.sh --flavour basic-min --debug "$@"
tools/test-network.sh --flavour bridges-min "$@"
# Get the warnings separately
# 0.3.4 and later: hs-v2-min
tools/test-network.sh --flavour hs-min --quiet --no-warnings "$@"
# 0.3.4 and later: hs-v2-min
tools/test-network.sh --flavour hs-min --only-warnings "$@"

echo "$myname: testing features"

# 0.3.4 and later:
#tools/test-network.sh --flavour hs-v3-min "$@"
# 0.3.4 and later: single-onion-v23
tools/test-network.sh --flavour single-onion --net-dir "$(mktemp -d)" "$@"

FIVE_MEGABYTES=$((5*1024*1024))
tools/test-network.sh --flavour bridges+ipv6-min \
                        --data "$FIVE_MEGABYTES" --connections 2 --rounds 2 \
                        --hs-multi-client 1 \
                        --start-time 130 --bootstrap-time 70 --stop-time 10 \
                        "$@"
tools/test-network.sh --flavour ipv6-exit-min \
                      --ipv4 "127.0.0.1" --ipv6 "[::1]" "$@"
# 0.3.4 and later: hs-v23-ipv6-md
tools/test-network.sh --flavour hs-ipv6 --offline "$@"
# 0.3.4 and later: single-onion-ipv6-md
tools/test-network.sh --flavour single-onion-ipv6
