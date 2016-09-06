# A client that only uses IPv6 ORPorts
ClientUseIPv4 0
# Due to Tor bug #19608, microdescriptors can't be used by IPv6-only clients
UseMicrodescriptors 0

# Previous versions of Tor did not support IPv6-only operation
# But this is how it would have been configured
#ClientUseIPv6 1
#ClientPreferIPv6ORPort 1
#ReachableAddresses reject 0.0.0.0/0, accept [::]/0
