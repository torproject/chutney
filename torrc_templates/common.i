TestingTorNetwork 1

## Comprehensive Bootstrap Testing Options ##
# These typically launch a working minimal Tor network in 25s-30s,
# and a working HS Tor network in 40-45s.
# See authority.tmpl for a partial explanation
#AssumeReachable 0
#Default PathsNeededToBuildCircuits 0.6
#Disable TestingDirAuthVoteExit
#Disable TestingDirAuthVoteHSDir
#Default V3AuthNIntervalsValid 3

## Rapid Bootstrap Testing Options ##
# These typically launch a working minimal Tor network in 6s-10s
# These parameters make tor networks bootstrap fast,
# but can cause consensus instability and network unreliability
# (Some are also bad for security.)
AssumeReachable 1
PathsNeededToBuildCircuits 0.25
TestingDirAuthVoteExit *
TestingDirAuthVoteHSDir *
V3AuthNIntervalsValid 2

## Always On Testing Options ##
# We enable TestingDirAuthVoteGuard to avoid Guard stability requirements
TestingDirAuthVoteGuard *
# We set TestingMinExitFlagThreshold to 0 to avoid Exit bandwidth requirements
TestingMinExitFlagThreshold 0
# VoteOnHidServDirectoriesV2 needs to be set for HSDirs to get the HSDir flag
#Default VoteOnHidServDirectoriesV2 1

## Options that we always want to test ##
Sandbox 1

DataDirectory $dir
RunAsDaemon 1
ConnLimit $connlimit
Nickname $nick
# Let tor close connections gracefully before exiting
ShutdownWaitLength 2
DisableDebuggerAttachment 0

ControlPort $controlport
# Use ControlSocket rather than ControlPort unix: to support older tors
ControlSocket ${dir}/control
CookieAuthentication 1
PidFile ${dir}/pid
# Ask all child tor processes to exit when chutney's test-network.sh exits
# (if the CHUTNEY_*_TIME options leave the network running, this option is
# disabled)
${owning_controller_process}

Log notice file ${dir}/notice.log
Log info file ${dir}/info.log
# Turn this off to save space
#Log debug file ${dir}/debug.log
ProtocolWarnings 1
SafeLogging 0
LogTimeGranularity 1

${authorities}
