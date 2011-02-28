#!/usr/bin/python
#
# Copyright 2011 Nick Mathewson, Michael Stone
#
#  You may do anything with this work that copyright law would normally
#  restrict, so long as you retain the above notice(s) and this license
#  in all redistributed copies and derived works.  There is no warranty.

from __future__ import with_statement
import os
import templating
import subprocess
import sys
import re
import errno

def mkdir_p(d):
    try:
        os.makedirs(d)
    except OSError, e:
        if e.errno == errno.EEXIST:
            return
        raise

class Node:
    ########
    # Users are expected to call these:
    def __init__(self, parent=None, **kwargs):
        self._parent = parent
        self._fields = self._createEnviron(parent, kwargs)

    def getN(self, N):
        return [ Node(self) for i in xrange(N) ]

    def specialize(self, **kwargs):
        return Node(parent=self, **kwargs)

    #######
    # Users are NOT expected to call these:

    def _createTorrcFile(self, checkOnly=False):
        template = self._getTorrcTemplate()
        env = self._fields
        fn_out = templating.Template("${torrc_fname}").format(env)
        output = template.format(env)
        if checkOnly:
            return
        with open(fn_out, 'w') as f:
            f.write(output)

    def _getTorrcTemplate(self):
        env = self._fields
        template_path = env['torrc_template_path']

        t = "$${include:$torrc}"
        return templating.Template(t, includePath=template_path)

    def _getFreeVars(self):
        template = self._getTorrcTemplate()
        env = self._fields
        return template.freevars(env)

    def _createEnviron(self, parent, argdict):
        if parent:
            parentfields = parent._fields
        else:
            parentfields = self._getDefaultFields()
        return TorEnviron(parentfields, **argdict)

    def _getDefaultFields(self):
        return _BASE_FIELDS

    def _checkConfig(self, net):
        self._createTorrcFile(checkOnly=True)

    def _preConfig(self, net):
        self._makeDataDir()
        if self._fields['authority']:
            self._genAuthorityKey()
        if self._fields['relay']:
            self._genRouterKey()

    def _config(self, net):
        self._createTorrcFile()
        #self._createScripts()

    def _postConfig(self, net):
        #self.net.addNode(self)
        pass

    def _setnodenum(self, num):
        self._fields['nodenum'] = num

    def _makeDataDir(self):
        env = self._fields
        datadir = env['dir']
        mkdir_p(os.path.join(datadir, 'keys'))

    def _genAuthorityKey(self):
        env = self._fields
        datadir = env['dir']
        tor_gencert = env['tor_gencert']
        lifetime = env['auth_cert_lifetime']
        idfile   = os.path.join(datadir,'keys',"authority_identity_key")
        skfile   = os.path.join(datadir,'keys',"authority_signing_key")
        certfile = os.path.join(datadir,'keys',"authority_certificate")
        addr = "%s:%s" % (env['ip'], env['dirport'])
        passphrase = env['auth_passphrase']
        if all(os.path.exists(f) for f in [idfile, skfile, certfile]):
            return
        cmdline = [
            tor_gencert,
            '--create-identity-key',
            '--passphrase-fd', '0',
            '-i', idfile,
            '-s', skfile,
            '-c', certfile,
            '-m', str(lifetime),
            '-a', addr]
        print "Creating identity key %s for %s with %s"%(idfile,env['nick']," ".join(cmdline))
        p = subprocess.Popen(cmdline, stdin=subprocess.PIPE)
        p.communicate(passphrase+"\n")
        assert p.returncode == 0 #XXXX BAD!

    def _genRouterKey(self):
        env = self._fields
        datadir = env['dir']
        tor = env['tor']
        idfile = os.path.join(datadir,'keys',"identity_key")
        cmdline = [
            tor,
            "--quiet",
            "--list-fingerprint",
            "--orport", "1",
            "--dirserver",
                 "xyzzy 127.0.0.1:1 ffffffffffffffffffffffffffffffffffffffff",
            "--datadirectory", datadir ]
        p = subprocess.Popen(cmdline, stdout=subprocess.PIPE)
        stdout, stderr = p.communicate()
        fingerprint = "".join(stdout.split()[1:])
        assert re.match(r'^[A-F0-9]{40}$', fingerprint)
        env['fingerprint'] = fingerprint

    def _getDirServerLine(self):
        env = self._fields
        if not env['authority']:
            return ""

        datadir = env['dir']
        certfile = os.path.join(datadir,'keys',"authority_certificate")
        v3id = None
        with open(certfile, 'r') as f:
            for line in f:
                if line.startswith("fingerprint"):
                    v3id = line.split()[1].strip()
                    break

        assert v3id is not None

        return "DirServer %s v3ident=%s orport=%s %s %s:%s %s\n" %(
            env['nick'], v3id, env['orport'], env['dirserver_flags'],
            env['ip'], env['dirport'], env['fingerprint'])

DEFAULTS = {
    'authority' : False,
    'relay' : False,
    'connlimit' : 60,
    'net_base_dir' : 'net',
    'tor' : 'tor',
    'auth_cert_lifetime' : 12,
    'ip' : '127.0.0.1',
    'dirserver_flags' : 'no-v2',
    'privnet_dir' : '.',
    'torrc_fname' : '${dir}/torrc',
    'orport_base' : 6000,
    'dirport_base' : 7000,
    'controlport_base' : 8000,
    'socksport_base' : 9000,
    'dirservers' : "Dirserver bleargh bad torrc file!"
}

class TorEnviron(templating.Environ):
    def __init__(self,parent=None,**kwargs):
        templating.Environ.__init__(self, parent=parent, **kwargs)

    def _get_orport(self, me):
        return me['orport_base']+me['nodenum']

    def _get_controlport(self, me):
        return me['controlport_base']+me['nodenum']

    def _get_socksport(self, me):
        return me['socksport_base']+me['nodenum']

    def _get_dirport(self, me):
        return me['dirport_base']+me['nodenum']

    def _get_dir(self, me):
        return os.path.abspath(os.path.join(me['net_base_dir'],
                                            "nodes",
                                            me['nick']))

    def _get_nick(self, me):
        return "%s-%02d"%(me['tag'], me['nodenum'])

    def _get_tor_gencert(self, me):
        return me['tor']+"-gencert"

    def _get_auth_passphrase(self, me):
        return self['nick'] # OMG TEH SECURE!

    def _get_torrc_template_path(self, me):
        return [ os.path.join(me['privnet_dir'], 'torrc_templates') ]


class Network:
    def __init__(self,defaultEnviron):
        self._nodes = []
        self._dfltEnv = defaultEnviron
        self._nextnodenum = 0

    def addNode(self, n):
        n._setnodenum(self._nextnodenum)
        self._nextnodenum += 1
        self._nodes.append(n)

    def configure(self):
        network = self
        dirserverlines = []

        for n in self._nodes:
            n._checkConfig(network)

        for n in self._nodes:
            n._preConfig(network)
            dirserverlines.append(n._getDirServerLine())

        self._dfltEnv['dirservers'] = "".join(dirserverlines)

        for n in self._nodes:
            n._config(network)

        for n in self._nodes:
            n._postConfig(network)


def ConfigureNodes(nodelist):
    network = _THE_NETWORK

    for n in nodelist:
        network.addNode(n)

def runConfigFile(f):
    global _BASE_FIELDS
    global _THE_NETWORK
    _BASE_FIELDS = TorEnviron(templating.Environ(**DEFAULTS))
    _THE_NETWORK = Network(_BASE_FIELDS)
    _GLOBALS = dict(_BASE_FIELDS= _BASE_FIELDS,
                    Node=Node,
                    ConfigureNodes=ConfigureNodes,
                    _THE_NETWORK=_THE_NETWORK)

    exec f in _GLOBALS
    network = _GLOBALS['_THE_NETWORK']

    network.configure()

if __name__ == '__main__':
    f = open(sys.argv[1])
    runConfigFile(f)


