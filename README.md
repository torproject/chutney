# Chutney

This is chutney.  It doesn't do much so far.  It isn't ready for prime-time.

If it breaks, you get to keep all the pieces.

It is supposed to be a good tool for:

- Configuring a testing tor network
- Launching and monitoring a testing tor network
- Running tests on a testing tor network

Right now it only sorta does these things.

## You will need
- A supported version of Python 3
  - (we support Python versions that are still getting updates), and
- Tor binaries.

Chutney checks for Tor binaries in this order:

- If you run chutney's `tools/test-network.sh` from a tor build directory,
  (or set the environment variable `$TOR_DIR` to a tor build directory,)
  chutney will automatically detect the tor binaries, or
- If you put the location of the `tor` and `tor-gencert` binaries in the
  environment variables `$CHUTNEY_TOR` and `$CHUTNEY_TOR_GENCERT`, respectively,
  chutney will use those binaries, or
- You will need `tor` and `tor-gencert` installed somewhere in your path.

## Stuff to try

Automated Setup, Verification, and Shutdown:

``` shell
./tools/test-network.sh --flavor basic-min
./tools/test-network.sh --coverage
./tools/test-network.sh --tor-path <tor-build-directory>
./tools/test-network.sh --tor <name-or-path> --tor-gencert <name-or-path>
```
(`--tor-path` and `$TOR_DIR` override `--tor` and `--tor-gencert`.)
(The script tries hard to find `tor`.)

``` shell
./tools/test-network.sh --chutney-path <chutney-directory>
```
(The script is pretty good at finding `chutney`.)

``` shell
./tools/test-network.sh --allow-failures <N>
```

`test-network.sh` looks for some tor binaries (either in a nearby build
directory or in your `$PATH`), configures a comprehensive Tor test network,
launches it, then verifies data transmission through it, and cleans up after
itself. Relative paths are supported.

You can modify its configuration using command-line arguments, or use the
chutney environmental variables documented below:

## Verification Options

``` shell
# repeats bootstrap and verify
--allow-failures   CHUTNEY_ALLOW_FAILURES=N
# repeats verify
--rounds           CHUTNEY_ROUNDS=N
# makes multiple connections within verify
--connections      CHUTNEY_CONNECTIONS=N
```

## Timing Options

``` shell
--start-time       CHUTNEY_START_TIME=N
--min-start-time   CHUTNEY_MIN_START_TIME=N
--bootstrap-time   CHUTNEY_BOOTSTRAP_TIME=N
--stop-time        CHUTNEY_STOP_TIME=N
```

## Traffic Options

``` shell
--data             CHUTNEY_DATA_BYTES=N
--hs-multi-client  CHUTNEY_HS_MULTI_CLIENT=N
```

## Address/DNS Options

``` shell
--ipv4             CHUTNEY_LISTEN_ADDRESS=IPV4
--ipv6             CHUTNEY_LISTEN_ADDRESS_V6=IPV6

# Chutney uses /etc/resolv.conf if none of these options are set
--dns-conf         CHUTNEY_DNS_CONF=PATH
--offline          CHUTNEY_DNS_CONF=/dev/null

# Use tor's compile-time default for ServerDNSResolvConfFile
--dns-conf-default CHUTNEY_DNS_CONF=""
```

## Sandbox Options

``` shell
--sandbox          CHUTNEY_TOR_SANDBOX=N (0 or 1)
```

## Warning Options

``` shell
--all-warnings     CHUTNEY_WARNINGS_IGNORE_EXPECTED=false
                   CHUTNEY_WARNINGS_SUMMARY=false
--no-warnings      CHUTNEY_WARNINGS_SKIP=true
--only-warnings    CHUTNEY_WARNINGS_ONLY=true
--diagnostics      CHUTNEY_DIAGNOSTICS=true
--only-diagnostics CHUTNEY_DIAGNOSTICS_ONLY=true
```

## Expert Options

``` shell
--debug            CHUTNEY_DEBUG=true
--coverage         USE_COVERAGE_BINARY=true
--dry-run          NETWORK_DRY_RUN=true
--quiet            ECHO=true

--controlling-pid  CHUTNEY_CONTROLLING_PID=N
--net-dir          CHUTNEY_DATA_DIR=PATH
```
(These are advanced options: in the past, they have had long-standing bugs.)

## Standard Actions

``` shell
./chutney configure networks/basic
./chutney start networks/basic
./chutney status networks/basic
./chutney wait_for_bootstrap networks/basic
./chutney verify networks/basic
./chutney hup networks/basic
./chutney stop networks/basic
```

## Bandwidth Tests

``` shell
./chutney configure networks/basic-min
./chutney start networks/basic-min
./chutney status networks/basic-min
```

Send 100MB of data per client connection:
``` shell
CHUTNEY_DATA_BYTES=104857600 ./chutney verify networks/basic-min
./chutney stop networks/basic-min
```

If chutney sends at least `5 MB` of data, and it takes at least one second,
verify produces performance figures for:

- Single Stream Bandwidth: the speed of the slowest stream, end-to-end
- Overall tor Bandwidth: the sum of the bandwidth across each tor instance

The overall bandwidth approximates the CPU-bound tor performance on the
current machine, assuming tor, chutney, and the OS are multithreaded, and
network performance is infinite.

## Connection Tests

``` shell
./chutney configure networks/basic-025
./chutney start networks/basic-025
./chutney status networks/basic-025
```

Make 5 simultaneous connections from each client through a random exit

``` shell
CHUTNEY_CONNECTIONS=5 ./chutney verify networks/basic-025
./chutney stop networks/basic-025
```

Run 5 sequential verification rounds

``` shell
CHUTNEY_ROUNDS=5 ./tools/test-network.sh --flavour basic
```

## HS Connection Tests

``` shell
./chutney configure networks/hs-025
./chutney start networks/hs-025
./chutney status networks/hs-025
```

Make a connection from each client to each hs Default behavior is one client
connects to each HS: 
``` shell
CHUTNEY_HS_MULTI_CLIENT=1 ./chutney verify networks/hs-025
./chutney stop networks/hs-025
```


## Bandwidth File Tests

``` shell
./tools/test-network.sh --flavour bwfile
# Warning: Can't open bandwidth file at configured location: /tmp/bwfile
# Create a bwfile with no bandwidths, that is valid for a few days
date +%s > /tmp/bwfile
./tools/test-network.sh --flavour bwfile
```

## Multiple Tests

Chutney can allow a certain number of failed tests. You can either set
`CHUTNEY_ALLOW_FAILURES` or use an `--allow-failures` command-line option to
control this. Chutney will then reattempt the test, from bootstrap through
shutdown, until either it succeeds, or until it has failed
`$CHUTNEY_ALLOW_FAILURES+1` times. The default value is zero, so the default
behavior will not change.

You can also use `CHUTNEY_ROUNDS=N` to run multiple verification rounds, or
`CHUTNEY_CONNECTIONS=N` to make multiple connections within each verification
round. Any round or connection failure will fail the current test.

## Bootstrapping the network

Chutney expects a tor network to bootstrap in these stages:

1.  All directory authorities (`DirAuths`) bootstrap to 100%.
2.  The `DirAuths` produce the first consensus.
    Usually, this consensus only contains authorities.
3.  The `DirAuths` produce a bootstrap consensus.
    This consensus has enough relays for:
      * clients and relays to bootstrap, and
      * relays to perform reachability self-tests.

    Usually, this consensus needs at least 3 nodes. This consensus is usually
    the first or second consensus. 
4.  Relays bootstrap to 100%.
5.  Relays with `AssumeReachable 1` publish their descriptors to the
    `DirAuths`.
6.  Relays perform `ORPort` reachability self-tests.
    If the consensus contains at least 1 exit, relays also perform `DirPort`
    reachability self-tests.
7.  Relays publish their descriptors to the `DirAuths`.
8.  The `DirAuths` produce a complete consensus, microdesc consensus, and
    microdescriptors. A complete consensus contains:
      * the authorities,
      * any bridge authorities, if present, and
      * all relays (including exits).
    Bridges, clients, and onion services are not included in the consensus.
9.  Bridges publish their descriptors to the Bridge Auth.
10. The Bridge Auth produces a bridge networkstatus.
11. Relays and bridges download all consensus flavours, then download
    descriptors and microdescriptors.
12. Bridge clients download the descriptors for their bridges.
13. Clients (including bridge clients, and onion services), download the
    most recent microdesc consensus, and microdescriptors.
14. Clients bootstrap to 100%.
    (Clients can bootstrap as soon as the consensus contains enough nodes,
    so this step can depend on step 3, not step 13.)
15. Onion Services publish their descriptors to Onion Service directories
    (otherwise known as hidden service directories, or `HSDirs`).

The `tools/test-network.sh` script uses the chutney `wait_for_bootstrap`
command to wait for the network to bootstrap.

`wait_for_bootstrap` waits up to `CHUTNEY_START_TIME` seconds (default: 120),
checking whether:

* the logged bootstrapped status for every node is 100% (steps 9 and 14),
  and
* directory information has been distributed throughout the network
  (steps 7-8, 11-13).

When waiting for dir info distribution, `wait_for_bootstrap` checks if:

* each relay descriptor has been posted to every authority (step 7),
* each relay is in the consensus, and the microdesc consensus, at every
  authority (step 8),
* a complete consensus and microdesc consensus has been distributed to
  relays and bridges (step 11),
* all authority and relay descriptors have been distributed to relays
  and bridges (step 11),
* all bridge descriptors have been distributed to all bridge clients
  (step 12), and
* a complete microdesc consensus has been distributed to clients
  (step 13).

`wait_for_bootstrap` does not currently check the following dir info:

* microdescriptors (steps 8, 11, and 13, chutney ticket #33407),
* bridge descriptors at the bridge authority (steps 9-10,
  tor ticket #33582, chutney ticket #33428), and
* onion services have published their descriptors to the HSDirs (step 15,
  chutney ticket #33609).

After bootstrapping and dir info distribution, `wait_for_bootstrap` waits
until the network has been running for at least `CHUTNEY_MIN_START_TIME`
seconds (default 0 seconds for `tor` > 0.3.5., 65 seconds for `tor` <= 0.3.5.),
to compensate for microdesc download issues in older tor versions.

In addition, `wait_for_bootstrap` also waits an extra:

- 10 seconds for clients to download microdescs, and
- 30 seconds for onion services to upload their descriptors.

We expect that these delays will be removed, once the relevant checks are
implemented in chutney.

If the `CHUTNEY_START_TIME` has elapsed, and some nodes have not bootstrapped,
or there are some nodes missing from the consensus, `wait_for_bootstrap` dumps
the bootstrap statuses, and exits with a failure.

## Verifying the network

Commands like `chutney verify` start immediately, and keep trying for
`CHUTNEY_BOOTSTRAP_TIME` seconds (default: 60). If it hasn't been
successful after that time, it fails. If `CHUTNEY_BOOTSTRAP_TIME` is negative,
the script leaves the network running, and exits after `CHUTNEY_START_TIME`
(without verifying).

## Shutting down the network

The `tools/test-network.sh` script waits `CHUTNEY_STOP_TIME` seconds
after verifying, then exits (default: immediately). If `CHUTNEY_STOP_TIME` is
negative, the script leaves the network running, and exits after verifying.

If none of these options are negative, `test-network.sh` tells the tor
processes to exit after it exits, using `CHUTNEY_CONTROLLING_PID`. To disable
this functionality, set `CHUTNEY_CONTROLLING_PID` to 1 or less.

## Changing the network address

Chutney defaults to binding to `localhost`. To change the IPv4 bind address,
set the `CHUTNEY_LISTEN_ADDRESS` environment variable. Similarly, change
`CHUTNEY_LISTEN_ADDRESS_V6` for IPv6: it defaults to "no IPv6 address".
Setting it to some interface's IP address allows us to make the simulated
Tor network available on the network.

IPv6 support for both Tor and Chutney is a work in progress. Currently,
chutney verifies IPv6 client, bridge client (?), hidden service, and exit
connections. It does not use IPv6 `SOCKSPorts` or `HiddenServicePorts`.

## Using DNS

Chutney verify uses IP addresses by default. It does not need to look up
any hostnames. We recommend that chutney users disable DNS using `--offline`
or `CHUTNEY_DNS_CONF=/dev/null`, because any DNS failures causes tests to
fail. Chutney's DNS queries also produce external traffic in a predictable
pattern.

If you want to use a hostname with `CHUTNEY_LISTEN_ADDRESS[_V6]`, or you want
to run tests that use DNS, set `CHUTNEY_DNS_CONF` to the path to a file in
`resolv.conf` format. Chutney's default of `/etc/resolv.conf` should be fine for
most UNIX-based operating systems. If your tor is compiled with a different
default, use `--dns-resolv-conf-default` or `CHUTNEY_DNS_CONF=""`.

When the `CHUTNEY_DNS_CONF` file does not exist, or is a broken symlink,
`chutney` uses `/dev/null` instead. This is a workaround for bugs in Tor's
use of `eventdns`. For example, macOS deletes the `resolv.conf` file when it
thinks the network is down: this can make tor exits reject all traffic,
even if a working DNS server is running on 127.0.0.1:53.

When tor has no working name servers (including `--offline` mode), it can
crash on `SETCONF`. (Chutney does not use `SETCONF`, but some external tor
controllers do.) To avoid this crash, set `CHUTNEY_DNS_CONF` to a file
containing a working name server address. For your convenience, chutney
provides a local `resolv.conf` file containing IPv4, IPv6, and `localhost`.
Use `--dns-conf resolv.conf` (relative paths work).

## The Tor sandbox

Chutney can run with the Tor seccomp sandbox enabled. But if Tor's sandbox
is broken on your local version of glibc, you can set `CHUTNEY_TOR_SANDBOX=0`
to disable the sandbox. If `CHUTNEY_TOR_SANDBOX` is unset, Sandbox defaults
to 1 on Linux, and 0 on other platforms.

## The configuration files

`networks/basic` holds the configuration for the network you're configuring
above. It refers to some torrc template files in `torrc_templates/`.

Chutney uses a templating system to produce torrc files from the templates.
These torrc files can be modified using various chutney options.

## The working files

Chutney sticks its working files, including all generated torrc files,
data directories, log files, etc, in `./net/`.  Each tor instance gets a
subdirectory of `net/nodes`.

You can override the directory `./net` with the `CHUTNEY_DATA_DIR`
environment variable.

## Test scripts

The test scripts are stored in the `scripts/chutney_tests` directory. These
Python files must define a `run_test(network)` function. Files starting with
an underscore ("_") are ignored.

Test scripts can be run using the following syntax:

``` shell
./chutney <script-name> networks/<network-name>
```

The `chutney verify` command is implemented using a test script.

Test scripts in the test directory with the same name as standard commands
are run instead of that standard command. This allows expert users to replace
the standard chutney commands with modified versions.
