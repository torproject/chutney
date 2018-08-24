AuthoritativeDirectory 1
V3AuthoritativeDirectory 1
ContactInfo auth${nodenum}@test.test

# Speed up the consensus cycle as fast as it will go.
# If clock desynchronisation is an issue, increase these voting times.

# V3AuthVotingInterval and TestingV3AuthInitialVotingInterval can be:
#   10, 12, 15, 18, 20, ...
# TestingV3AuthInitialVotingInterval can also be:
#    5, 6, 8, 9
# They both need to evenly divide 24 hours.

# Testing Vote + Testing Dist must be less than Testing Interval
TestingV3AuthInitialVotingInterval 5
TestingV3AuthInitialVoteDelay 2
TestingV3AuthInitialDistDelay 2
# Vote + Dist must be less than Interval/2
V3AuthVotingInterval 10
V3AuthVoteDelay 2
V3AuthDistDelay 2
