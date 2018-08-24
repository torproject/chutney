AuthoritativeDirectory 1
V3AuthoritativeDirectory 1
ContactInfo auth${nodenum}@test.test

# Speed up the consensus cycle as fast as it will go
# Voting Interval can be:
#   10, 12, 15, 18, 20, 24, 25, 30, 36, 40, 45, 50, 60, ...
# Testing Initial Voting Interval can be:
#    5,  6,  8,  9, or any of the possible values for Voting Interval,
# as they both need to evenly divide 30 minutes.
# If clock desynchronisation is an issue, use an interval of at least:
#   18 * drift in seconds, to allow for a clock slop factor
TestingV3AuthInitialVotingInterval 5
V3AuthVotingInterval 10
# VoteDelay + DistDelay must be less than VotingInterval
TestingV3AuthInitialVoteDelay 2
V3AuthVoteDelay 2
TestingV3AuthInitialDistDelay 2
V3AuthDistDelay 2
