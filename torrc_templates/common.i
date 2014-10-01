TestingTorNetwork 1
DataDirectory $dir
RunAsDaemon 1
ConnLimit $connlimit
Nickname $nick
ShutdownWaitLength 0
PidFile ${dir}/pid
Log notice file ${dir}/notice.log
Log info file ${dir}/info.log
ProtocolWarnings 1
SafeLogging 0
DisableDebuggerAttachment 0
${authorities}
