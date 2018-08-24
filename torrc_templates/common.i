TestingTorNetwork 1

## Rapid Bootstrap Testing Options ##
# These typically launch a working minimal Tor network in ~20s
# These parameters make tor networks bootstrap fast,
# but can cause consensus instability and network unreliability
# (Some are also bad for security.)
AssumeReachable 1
# We need at least 3 descriptors to build circuits.
# In a 3 relay network, 0.67 > 2/3, so we try hard to get 3 descriptors.
# In larger networks, 0.67 > 2/N, so we try hard to get >=3 descriptors.
PathsNeededToBuildCircuits 0.67
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
