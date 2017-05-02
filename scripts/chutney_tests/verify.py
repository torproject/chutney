import time
import chutney


def run_test(network):
    wait_time = network._dfltEnv['bootstrap_time']
    start_time = time.time()
    end_time = start_time + wait_time
    print("Verifying data transmission: (retrying for up to %d seconds)"
          % wait_time)
    status = False
    # Keep on retrying the verify until it succeeds or times out
    while not status and time.time() < end_time:
        # TrafficTester connections time out after ~3 seconds
        # a TrafficTester times out after ~10 seconds if no data is being sent
        status = _verify_traffic(network)
        # Avoid madly spewing output if we fail immediately each time
        if not status:
            time.sleep(5)
    print("Transmission: %s" % ("Success" if status else "Failure"))
    if not status:
        print("Set CHUTNEY_DEBUG to diagnose.")
    return status


def _verify_traffic(network):
    """Verify (parts of) the network by sending traffic through it
    and verify what is received."""
    # TODO: IPv6 SOCKSPorts, SOCKSPorts with IPv6Traffic, and IPv6 Exits
    LISTEN_ADDR = network._dfltEnv['ip']
    LISTEN_PORT = 4747  # FIXME: Do better! Note the default exit policy.
    # HSs must have a HiddenServiceDir with
    # "HiddenServicePort <HS_PORT> <CHUTNEY_LISTEN_ADDRESS>:<LISTEN_PORT>"
    # TODO: Test <CHUTNEY_LISTEN_ADDRESS_V6>:<LISTEN_PORT>
    HS_PORT = 5858
    # The amount of data to send between each source-sink pair,
    # each time the source connects.
    # We create a source-sink pair for each (bridge) client to an exit,
    # and a source-sink pair for a (bridge) client to each hidden service
    DATALEN = network._dfltEnv['data_bytes']
    # Print a dot each time a sink verifies this much data
    DOTDATALEN = 5 * 1024 * 1024  # Octets.
    TIMEOUT = 3                   # Seconds.
    # Calculate the amount of random data we should use
    randomlen = _calculate_randomlen(DATALEN)
    reps = _calculate_reps(DATALEN, randomlen)
    connection_count = network._dfltEnv['connection_count']
    # sanity check
    if reps == 0:
        DATALEN = 0
    # Get the random data
    if randomlen > 0:
        # print a dot after every DOTDATALEN data is verified, rounding up
        dot_reps = _calculate_reps(DOTDATALEN, randomlen)
        # make sure we get at least one dot per transmission
        dot_reps = min(reps, dot_reps)
        with open('/dev/urandom', 'r') as randfp:
            tmpdata = randfp.read(randomlen)
    else:
        dot_reps = 0
        tmpdata = {}
    # now make the connections
    bind_to = (LISTEN_ADDR, LISTEN_PORT)
    tt = chutney.Traffic.TrafficTester(bind_to, tmpdata, TIMEOUT, reps,
                                       dot_reps)
    client_list = filter(lambda n:
                         n._env['tag'] == 'c' or n._env['tag'] == 'bc',
                         network._nodes)
    exit_list = filter(lambda n:
                       ('exit' in n._env.keys()) and n._env['exit'] == 1,
                       network._nodes)
    hs_list = filter(lambda n:
                     n._env['tag'] == 'h',
                     network._nodes)
    if len(client_list) == 0:
        print("  Unable to verify network: no client nodes available")
        return False
    if len(exit_list) == 0 and len(hs_list) == 0:
        print("  Unable to verify network: no exit/hs nodes available")
        print("  Exit nodes must be declared 'relay=1, exit=1'")
        print("  HS nodes must be declared 'tag=\"hs\"'")
        return False
    print("Connecting:")
    # the number of tor nodes in paths which will send DATALEN data
    # if a node is used in two paths, we count it twice
    # this is a lower bound, as cannabilised circuits are one node longer
    total_path_node_count = 0
    total_path_node_count += _configure_exits(tt, bind_to, tmpdata, reps,
                                              client_list, exit_list,
                                              LISTEN_ADDR, LISTEN_PORT,
                                              connection_count)
    total_path_node_count += _configure_hs(tt, tmpdata, reps, client_list,
                                           hs_list, HS_PORT, LISTEN_ADDR,
                                           LISTEN_PORT, connection_count,
                                           network._dfltEnv['hs_multi_client'])
    print("Transmitting Data:")
    start_time = time.time()
    status = tt.run()
    end_time = time.time()
    # if we fail, don't report the bandwidth
    if not status:
        return status
    # otherwise, report bandwidth used, if sufficient data was transmitted
    _report_bandwidth(DATALEN, total_path_node_count, start_time, end_time)
    return status


# In order to performance test a tor network, we need to transmit
# several hundred megabytes of data or more. Passing around this
# much data in Python has its own performance impacts, so we provide
# a smaller amount of random data instead, and repeat it to DATALEN
def _calculate_randomlen(datalen):
    MAX_RANDOMLEN = 128 * 1024   # Octets.
    if datalen > MAX_RANDOMLEN:
        return MAX_RANDOMLEN
    else:
        return datalen


def _calculate_reps(datalen, replen):
    # sanity checks
    if datalen == 0 or replen == 0:
        return 0
    # effectively rounds datalen up to the nearest replen
    if replen < datalen:
        return (datalen + replen - 1) / replen
    else:
        return 1


# if there are any exits, each client / bridge client transmits
# via 4 nodes (including the client) to an arbitrary exit
# Each client binds directly to <CHUTNEY_LISTEN_ADDRESS>:LISTEN_PORT
# via an Exit relay
def _configure_exits(tt, bind_to, tmpdata, reps, client_list, exit_list,
                     LISTEN_ADDR, LISTEN_PORT, connection_count):
    CLIENT_EXIT_PATH_NODES = 4
    exit_path_node_count = 0
    if len(exit_list) > 0:
        exit_path_node_count += (len(client_list) *
                                 CLIENT_EXIT_PATH_NODES *
                                 connection_count)
        for op in client_list:
            print("  Exit to %s:%d via client %s:%s"
                  % (LISTEN_ADDR, LISTEN_PORT,
                     'localhost', op._env['socksport']))
            for _ in range(connection_count):
                proxy = ('localhost', int(op._env['socksport']))
                tt.add(chutney.Traffic.Source(tt, bind_to, tmpdata, proxy,
                                              reps))
    return exit_path_node_count


# The HS redirects .onion connections made to hs_hostname:HS_PORT
# to the Traffic Tester's CHUTNEY_LISTEN_ADDRESS:LISTEN_PORT
# an arbitrary client / bridge client transmits via 8 nodes
# (including the client and hs) to each hidden service
# Instead of binding directly to LISTEN_PORT via an Exit relay,
# we bind to hs_hostname:HS_PORT via a hidden service connection
def _configure_hs(tt, tmpdata, reps, client_list, hs_list, HS_PORT,
                  LISTEN_ADDR, LISTEN_PORT, connection_count, hs_multi_client):
    CLIENT_HS_PATH_NODES = 8
    hs_path_node_count = (len(hs_list) * CLIENT_HS_PATH_NODES *
                          connection_count)
    # Each client in hs_client_list connects to each hs
    if hs_multi_client:
        hs_client_list = client_list
        hs_path_node_count *= len(client_list)
    else:
        # only use the first client in the list
        hs_client_list = client_list[:1]
    # Setup the connections from each client in hs_client_list to each hs
    for hs in hs_list:
        hs_bind_to = (hs._env['hs_hostname'], HS_PORT)
        for client in hs_client_list:
            print("  HS to %s:%d (%s:%d) via client %s:%s"
                  % (hs._env['hs_hostname'], HS_PORT,
                     LISTEN_ADDR, LISTEN_PORT,
                     'localhost', client._env['socksport']))
            for _ in range(connection_count):
                proxy = ('localhost', int(client._env['socksport']))
                tt.add(chutney.Traffic.Source(tt, hs_bind_to, tmpdata,
                                              proxy, reps))
    return hs_path_node_count


# calculate the single stream bandwidth and overall tor bandwidth
# the single stream bandwidth is the bandwidth of the
# slowest stream of all the simultaneously transmitted streams
# the overall bandwidth estimates the simultaneous bandwidth between
# all tor nodes over all simultaneous streams, assuming:
# * minimum path lengths (no cannibalized circuits)
# * unlimited network bandwidth (that is, localhost)
# * tor performance is CPU-limited
# This be used to estimate the bandwidth capacity of a CPU-bound
# tor relay running on this machine
def _report_bandwidth(data_length, total_path_node_count, start_time,
                      end_time):
    # otherwise, if we sent at least 5 MB cumulative total, and
    # it took us at least a second to send, report bandwidth
    MIN_BWDATA = 5 * 1024 * 1024  # Octets.
    MIN_ELAPSED_TIME = 1.0        # Seconds.
    cumulative_data_sent = total_path_node_count * data_length
    elapsed_time = end_time - start_time
    if (cumulative_data_sent >= MIN_BWDATA and
            elapsed_time >= MIN_ELAPSED_TIME):
        # Report megabytes per second
        BWDIVISOR = 1024*1024
        single_stream_bandwidth = (data_length / elapsed_time / BWDIVISOR)
        overall_bandwidth = (cumulative_data_sent / elapsed_time /
                             BWDIVISOR)
        print("Single Stream Bandwidth: %.2f MBytes/s"
              % single_stream_bandwidth)
        print("Overall tor Bandwidth: %.2f MBytes/s"
              % overall_bandwidth)
