TestingTorNetwork 1
DataDirectory $dir
RunAsDaemon 1
ConnLimit $connlimit
Nickname $nick
ShutdownWaitLength 0
PidFile ${dir}/pid
Log notice file ${dir}/notice.log
${dirservers}

