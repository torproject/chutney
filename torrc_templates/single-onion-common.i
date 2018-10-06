${include:hs-common.i}

# Make this hidden service instance a Single Onion Service
HiddenServiceSingleHopMode 1
HiddenServiceNonAnonymousMode 1

# Log only the messages we need to confirm that the Single Onion server is
# making one-hop circuits, and to see any errors or major issues
# To confirm one-hop intro and rendezvous circuits, look for
# rend_service_intro_has_opened and rend_service_rendezvous_has_opened, and
# check the length of the circuit in the next line.
Log notice [rend,bug]info file ${dir}/single-onion.log

# Disable preemtive circuits, a Single Onion doesn't need them (except for
# descriptor posting).
# This stalls at bootstrap due to #17359.
#__DisablePredictedCircuits 1
# A workaround is to set:
LongLivedPorts
# This disables everything except hidden service preemptive 3-hop circuits.
# See #17360.
