#!/usr/bin/env python
#
# Copyright 2011 Nick Mathewson, Michael Stone
# Copyright 2013 The Tor Project
#
#  You may do anything with this work that copyright law would normally
#  restrict, so long as you retain the above notice(s) and this license
#  in all redistributed copies and derived works.  There is no warranty.

from __future__ import print_function
from __future__ import with_statement

import cgitb
import os
import signal
import subprocess
import sys
import re
import errno
import time
import shutil
import importlib

from chutney.Debug import debug_flag, debug

import chutney.Host
import chutney.Templating
import chutney.Traffic
import chutney.Util

_BASE_ENVIRON = None
_TOR_VERSIONS = None
_TORRC_OPTIONS = None
_THE_NETWORK = None

TORRC_OPTION_WARN_LIMIT = 10
torrc_option_warn_count =  0

# Get verbose tracebacks, so we can diagnose better.
cgitb.enable(format="plain")

class MissingBinaryException(Exception):
    pass

def getenv_int(envvar, default):
    """
       Return the value of the environment variable 'envar' as an integer,
       or 'default' if no such variable exists.

       Raise ValueError if the environment variable is set, but not to
       an integer.
    """
    # TODO: Use this function in more places.
    strval = os.environ.get(envvar)
    if strval is None:
        return default
    try:
        return int(strval)
    except ValueError:
        raise ValueError("Invalid value for environment variable %s: expected an integer, but got %r"%(envvar,strval))

def mkdir_p(d, mode=448):
    """Create directory 'd' and all of its parents as needed.  Unlike
       os.makedirs, does not give an error if d already exists.

       448 is the decimal representation of the octal number 0700. Since
       python2 only supports 0700 and python3 only supports 0o700, we can use
       neither.

       Note that python2 and python3 differ in how they create the
       permissions for the intermediate directories.  In python3, 'mode'
       only sets the mode for the last directory created.
    """
    try:
        os.makedirs(d, mode=mode)
    except OSError as e:
        if e.errno == errno.EEXIST:
            return
        raise

def make_datadir_subdirectory(datadir, subdir):
    """
       Create a datadirectory (if necessary) and a subdirectory of
       that datadirectory.  Ensure that both are mode 700.
    """
    mkdir_p(datadir)
    mkdir_p(os.path.join(datadir, subdir))

def get_absolute_chutney_path():
    # use the current directory as the default
    # (./chutney already sets CHUTNEY_PATH using the path to the script)
    # use tools/test-network.sh if you want chutney to try really hard to find
    # itself
    relative_chutney_path = os.environ.get('CHUTNEY_PATH', os.getcwd())
    return os.path.abspath(relative_chutney_path)

def get_absolute_net_path():
    # use the chutney path as the default
    absolute_chutney_path = get_absolute_chutney_path()
    relative_net_path = os.environ.get('CHUTNEY_DATA_DIR', 'net')
    # but what is it relative to?
    # let's check if it's in CHUTNEY_PATH first, to preserve
    # backwards-compatible behaviour
    chutney_net_path = os.path.join(absolute_chutney_path, relative_net_path)
    if os.path.isdir(chutney_net_path):
        return chutney_net_path
    # ok, it's relative to the current directory, whatever that is
    return os.path.abspath(relative_net_path)

def get_absolute_nodes_path():
    # there's no way to customise this: we really don't need more options
    return os.path.join(get_absolute_net_path(), 'nodes')

def get_new_absolute_nodes_path(now=time.time()):
    # automatically chosen to prevent path collisions, and result in an ordered
    # series of directory path names
    # should only be called by 'chutney configure', all other chutney commands
    # should use get_absolute_nodes_path()
    nodesdir = get_absolute_nodes_path()
    newdir = newdirbase = "%s.%d" % (nodesdir, now)
    # if the time is the same, fall back to a simple integer count
    # (this is very unlikely to happen unless the clock changes: it's not
    # possible to run multiple chutney networks at the same time)
    i = 0
    while os.path.exists(newdir):
        i += 1
        newdir = "%s.%d" % (newdirbase, i)
    return newdir

def _warnMissingTor(tor_path, cmdline, tor_name="tor"):
    """Log a warning that the binary tor_name can't be found at tor_path
       while running cmdline.
    """
    print(("Cannot find the {} binary at '{}' for the command line '{}'. " +
           "Set the TOR_DIR environment variable to the directory " +
           "containing {}.")
          .format(tor_name, tor_path, " ".join(cmdline), tor_name))

def run_tor(cmdline, exit_on_missing=True):
    """Run the tor command line cmdline, which must start with the path or
       name of a tor binary.

       Returns the combined stdout and stderr of the process.

       If exit_on_missing is true, warn and exit if the tor binary is missing.
       Otherwise, raise a MissingBinaryException.
    """
    if not debug_flag:
        cmdline.append("--quiet")
    try:
        stdouterr = subprocess.check_output(cmdline,
                                            stderr=subprocess.STDOUT,
                                            universal_newlines=True,
                                            bufsize=-1)
        debug(stdouterr)
    except OSError as e:
        # only catch file not found error
        if e.errno == errno.ENOENT:
            if exit_on_missing:
                _warnMissingTor(cmdline[0], cmdline)
                sys.exit(1)
            else:
                raise MissingBinaryException()
        else:
            raise
    except subprocess.CalledProcessError as e:
        # only catch file not found error
        if e.returncode == 127:
            if exit_on_missing:
                _warnMissingTor(cmdline[0], cmdline)
                sys.exit(1)
            else:
                raise MissingBinaryException()
        else:
            raise
    return stdouterr

def launch_process(cmdline, tor_name="tor", stdin=None, exit_on_missing=True):
    """Launch the command line cmdline, which must start with the path or
       name of a binary. Use tor_name as the canonical name of the binary.
       Pass stdin to the Popen constructor.

       Returns the Popen object for the launched process.
    """
    if tor_name == "tor" and not debug_flag:
        cmdline.append("--quiet")
    elif tor_name == "tor-gencert" and debug_flag:
        cmdline.append("-v")
    try:
        p = subprocess.Popen(cmdline,
                             stdin=stdin,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT,
                             universal_newlines=True,
                             bufsize=-1)
    except OSError as e:
        # only catch file not found error
        if e.errno == errno.ENOENT:
            if exit_on_missing:
                _warnMissingTor(cmdline[0], cmdline, tor_name=tor_name)
                sys.exit(1)
            else:
                raise MissingBinaryException()
        else:
            raise
    return p

def run_tor_gencert(cmdline, passphrase):
    """Run the tor-gencert command line cmdline, which must start with the
       path or name of a tor-gencert binary.
       Then send passphrase to the stdin of the process.

       Returns the combined stdout and stderr of the process.
    """
    p = launch_process(cmdline,
                        tor_name="tor-gencert",
                        stdin=subprocess.PIPE)
    (stdouterr, empty_stderr) = p.communicate(passphrase + "\n")
    debug(stdouterr)
    assert p.returncode == 0  # XXXX BAD!
    assert empty_stderr is None
    return stdouterr

@chutney.Util.memoized
def tor_exists(tor):
    """Return true iff this tor binary exists."""
    try:
        run_tor([tor, "--quiet", "--version"], exit_on_missing=False)
        return True
    except MissingBinaryException:
        return False

@chutney.Util.memoized
def tor_gencert_exists(gencert):
    """Return true iff this tor-gencert binary exists."""
    try:
        p = launch_process([gencert, "--help"], exit_on_missing=False)
        p.wait()
        return True
    except MissingBinaryException:
        return False

@chutney.Util.memoized
def get_tor_version(tor):
    """Return the version of the tor binary.
       Versions are cached for each unique tor path.
    """
    cmdline = [
        tor,
        "--version",
    ]
    tor_version = run_tor(cmdline)
    # clean it up a bit
    tor_version = tor_version.strip()
    tor_version = tor_version.replace("version ", "")
    tor_version = tor_version.replace(").", ")")
    # check we received a tor version, and nothing else
    assert re.match(r'^[-+.() A-Za-z0-9]+$', tor_version)

    return tor_version

@chutney.Util.memoized
def get_torrc_options(tor):
    """Return the torrc options supported by the tor binary.
       Options are cached for each unique tor path.
    """
    cmdline = [
        tor,
        "--list-torrc-options",
    ]
    opts = run_tor(cmdline)
    # check we received a list of options, and nothing else
    assert re.match(r'(^\w+$)+', opts, flags=re.MULTILINE)
    torrc_opts = opts.split()

    return torrc_opts

@chutney.Util.memoized
def get_tor_modules(tor):
    """Check the list of compile-time modules advertised by the given
       'tor' binary, and return a map from module name to a boolean
       describing whether it is supported.

       Unlisted modules are ones that Tor did not treat as compile-time
       optional modules.
    """
    cmdline = [
        tor,
        "--list-modules",
        "--quiet"
        ]
    try:
        mods = run_tor(cmdline)
    except subprocess.CalledProcessError as e:
        # Tor doesn't support --list-modules; act as if it said nothing.
        mods = ""

    supported = {}
    for line in mods.split("\n"):
        m = re.match(r'^(\S+): (yes|no)', line)
        if not m:
            continue
        supported[m.group(1)] = (m.group(2) == "yes")

    return supported

def tor_has_module(tor, modname, default=True):
    """Return true iff the given tor binary supports a given compile-time
       module.  If the module is not listed, return 'default'.
    """
    return get_tor_modules(tor).get(modname, default)

class Node(object):

    """A Node represents a Tor node or a set of Tor nodes.  It's created
       in a network configuration file.

       This class is responsible for holding the user's selected node
       configuration, and figuring out how the node needs to be
       configured and launched.
    """
    # Fields:
    # _parent
    # _env
    # _builder
    # _controller

    ########
    # Users are expected to call these:

    def __init__(self, parent=None, **kwargs):
        self._parent = parent
        self._env = self._createEnviron(parent, kwargs)
        self._builder = None
        self._controller = None

    def getN(self, N):
        return [Node(self) for _ in range(N)]

    def specialize(self, **kwargs):
        return Node(parent=self, **kwargs)

    def set_runtime(self, key, fn):
        """Specify a runtime function that gets invoked to find the
           runtime value of a key.  It should take a single argument, which
           will be an environment.
        """
        setattr(self._env, "_get_"+key, fn)

    ######
    # Chutney uses these:

    def getBuilder(self):
        """Return a NodeBuilder instance to set up this node (that is, to
           write all the files that need to be in place so that this
           node can be run by a NodeController).
        """
        if self._builder is None:
            self._builder = LocalNodeBuilder(self._env)
        return self._builder

    def getController(self):
        """Return a NodeController instance to control this node (that is,
           to start it, stop it, see if it's running, etc.)
        """
        if self._controller is None:
            self._controller = LocalNodeController(self._env)
        return self._controller

    def setNodenum(self, num):
        """Assign a value to the 'nodenum' element of this node.  Each node
           in a network gets its own nodenum.
        """
        self._env['nodenum'] = num

    #####
    # These are internal:

    def _createEnviron(self, parent, argdict):
        """Return an Environ that delegates to the parent node's Environ (if
           there is a parent node), or to the default environment.
        """
        if parent:
            parentenv = parent._env
        else:
            parentenv = self._getDefaultEnviron()
        return TorEnviron(parentenv, **argdict)

    def _getDefaultEnviron(self):
        """Return the default environment.  Any variables that we can't find
           set for any particular node, we look for here.
        """
        return _BASE_ENVIRON


class _NodeCommon(object):

    """Internal helper class for functionality shared by some NodeBuilders
       and some NodeControllers."""
    # XXXX maybe this should turn into a mixin.

    def __init__(self, env):
        self._env = env

    def expand(self, pat, includePath=(".",)):
        return chutney.Templating.Template(pat, includePath).format(self._env)

    def _getTorrcFname(self):
        """Return the name of the file where we'll be writing torrc"""
        return self.expand("${torrc_fname}")


class NodeBuilder(_NodeCommon):

    """Abstract base class.  A NodeBuilder is responsible for doing all the
       one-time prep needed to set up a node in a network.
    """

    def __init__(self, env):
        _NodeCommon.__init__(self, env)

    def checkConfig(self, net):
        """Try to format our torrc; raise an exception if we can't.
        """

    def preConfig(self, net):
        """Called on all nodes before any nodes configure: generates keys as
           needed.
        """

    def config(self, net):
        """Called to configure a node: creates a torrc file for it."""

    def postConfig(self, net):
        """Called on each nodes after all nodes configure."""


    def isSupported(self, net):
        """Return true if this node appears to have everything it needs;
           false otherwise."""


class NodeController(_NodeCommon):

    """Abstract base class.  A NodeController is responsible for running a
       node on the network.
    """

    def __init__(self, env):
        _NodeCommon.__init__(self, env)

    def check(self, listRunning=True, listNonRunning=False):
        """See if this node is running, stopped, or crashed.  If it's running
           and listRunning is set, print a short statement.  If it's
           stopped and listNonRunning is set, then print a short statement.
           If it's crashed, print a statement.  Return True if the
           node is running, false otherwise.
        """

    def start(self):
        """Try to start this node; return True if we succeeded or it was
           already running, False if we failed."""

    def stop(self, sig=signal.SIGINT):
        """Try to stop this node by sending it the signal 'sig'."""


class LocalNodeBuilder(NodeBuilder):

    # Environment members used:
    # torrc -- which torrc file to use
    # torrc_template_path -- path to search for torrc files and include files
    # authority -- bool -- are we an authority?
    # bridgeauthority -- bool -- are we a bridge authority?
    # relay -- bool -- are we a relay?
    # bridge -- bool -- are we a bridge?
    # hs -- bool -- are we a hidden service?
    # nodenum -- int -- set by chutney -- which unique node index is this?
    # dir -- path -- set by chutney -- data directory for this tor
    # tor_gencert -- path to tor_gencert binary
    # tor -- path to tor binary
    # auth_cert_lifetime -- lifetime of authority certs, in months.
    # ip -- primary IP address (usually IPv4) to listen on
    # ipv6_addr -- secondary IP address (usually IPv6) to listen on
    # orport, dirport -- used on authorities, relays, and bridges. The orport
    #                    is used for both IPv4 and IPv6, if present
    # fingerprint -- used only if authority
    # dirserver_flags -- used only if authority
    # nick -- nickname of this router

    # Environment members set
    # fingerprint -- hex router key fingerprint
    # nodenum -- int -- set by chutney -- which unique node index is this?

    def __init__(self, env):
        NodeBuilder.__init__(self, env)
        self._env = env

    def _createTorrcFile(self, checkOnly=False):
        """Write the torrc file for this node, disabling any options
           that are not supported by env's tor binary using comments.
           If checkOnly, just make sure that the formatting is indeed
           possible.
        """
        global torrc_option_warn_count

        fn_out = self._getTorrcFname()
        torrc_template = self._getTorrcTemplate()
        output = torrc_template.format(self._env)
        if checkOnly:
            # XXXX Is it time-consuming to format? If so, cache here.
            return
        # now filter the options we're about to write, commenting out
        # the options that the current tor binary doesn't support
        tor = self._env['tor']
        tor_version = get_tor_version(tor)
        torrc_opts = get_torrc_options(tor)
        # check if each option is supported before writing it
        # Unsupported option values may need special handling.
        with open(fn_out, 'w') as f:
            # we need to do case-insensitive option comparison
            lower_opts = [opt.lower() for opt in torrc_opts]
            # keep ends when splitting lines, so we can write them out
            # using writelines() without messing around with "\n"s
            for line in output.splitlines(True):
                # check if the first word on the line is a supported option,
                # preserving empty lines and comment lines
                sline = line.strip()
                if (len(sline) == 0 or
                        sline[0] == '#' or
                        sline.split()[0].lower() in lower_opts):
                    pass
                else:
                    warn_msg = (("The tor binary at {} does not support " +
                                "the option in the torrc line:\n{}")
                                .format(tor, line.strip()))
                    if torrc_option_warn_count < TORRC_OPTION_WARN_LIMIT:
                        print(warn_msg)
                        torrc_option_warn_count += 1
                    else:
                        debug(warn_msg)
                    # always dump the full output to the torrc file
                    line = ("# {} version {} does not support: {}"
                            .format(tor, tor_version, line))
                f.writelines([line])

    def _getTorrcTemplate(self):
        """Return the template used to write the torrc for this node."""
        template_path = self._env['torrc_template_path']
        return chutney.Templating.Template("$${include:$torrc}",
                                           includePath=template_path)

    def _getFreeVars(self):
        """Return a set of the free variables in the torrc template for this
           node.
        """
        template = self._getTorrcTemplate()
        return template.freevars(self._env)

    def checkConfig(self, net):
        """Try to format our torrc; raise an exception if we can't.
        """
        self._createTorrcFile(checkOnly=True)

    def preConfig(self, net):
        """Called on all nodes before any nodes configure: generates keys and
           hidden service directories as needed.
        """
        self._makeDataDir()
        if self._env['authority']:
            self._genAuthorityKey()
        if self._env['relay']:
            self._genRouterKey()
        if self._env['hs']:
            self._makeHiddenServiceDir()

    def config(self, net):
        """Called to configure a node: creates a torrc file for it."""
        self._createTorrcFile()
        # self._createScripts()

    def postConfig(self, net):
        """Called on each nodes after all nodes configure."""
        # self.net.addNode(self)
        pass

    def isSupported(self, net):
        """Return true if this node appears to have everything it needs;
           false otherwise."""

        if not tor_exists(self._env['tor']):
            print("No binary found for %r"%self._env['tor'])
            return False

        if self._env['authority']:
            if not tor_has_module(self._env['tor'], "dirauth"):
                print("No dirauth support in %r"%self._env['tor'])
                return False
            if not tor_gencert_exists(self._env['tor-gencert']):
                print("No binary found for tor-gencert %r"%self._env['tor-gencrrt'])

    def _makeDataDir(self):
        """Create the data directory (with keys subdirectory) for this node.
        """
        datadir = self._env['dir']
        make_datadir_subdirectory(datadir, "keys")

    def _makeHiddenServiceDir(self):
        """Create the hidden service subdirectory for this node.

          The directory name is stored under the 'hs_directory' environment
          key. It is combined with the 'dir' data directory key to yield the
          path to the hidden service directory.
        """
        datadir = self._env['dir']
        make_datadir_subdirectory(datadir, self._env['hs_directory'])

    def _genAuthorityKey(self):
        """Generate an authority identity and signing key for this authority,
           if they do not already exist."""
        datadir = self._env['dir']
        tor_gencert = self._env['tor_gencert']
        lifetime = self._env['auth_cert_lifetime']
        idfile = os.path.join(datadir, 'keys', "authority_identity_key")
        skfile = os.path.join(datadir, 'keys', "authority_signing_key")
        certfile = os.path.join(datadir, 'keys', "authority_certificate")
        addr = self.expand("${ip}:${dirport}")
        passphrase = self._env['auth_passphrase']
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
            '-a', addr,
            ]
        # nicknames are testNNNaa[OLD], but we want them to look tidy
        print("Creating identity key for {:12} with {}"
              .format(self._env['nick'], cmdline[0]))
        debug("Identity key path '{}', command '{}'"
              .format(idfile, " ".join(cmdline)))
        run_tor_gencert(cmdline, passphrase)

    def _genRouterKey(self):
        """Generate an identity key for this router, unless we already have,
           and set up the 'fingerprint' entry in the Environ.
        """
        datadir = self._env['dir']
        tor = self._env['tor']
        torrc = self._getTorrcFname()
        cmdline = [
            tor,
            "--ignore-missing-torrc",
            "-f", torrc,
            "--list-fingerprint",
            "--orport", "1",
            "--datadirectory", datadir,
            ]
        stdouterr = run_tor(cmdline)
        fingerprint = "".join((stdouterr.rstrip().split('\n')[-1]).split()[1:])
        if not re.match(r'^[A-F0-9]{40}$', fingerprint):
            print("Error when getting fingerprint using '%r'. It output '%r'."
                  .format(" ".join(cmdline), stdouterr))
            sys.exit(1)
        self._env['fingerprint'] = fingerprint

    def _getAltAuthLines(self, hasbridgeauth=False):
        """Return a combination of AlternateDirAuthority,
        and AlternateBridgeAuthority lines for
        this Node, appropriately.  Non-authorities return ""."""
        if not self._env['authority']:
            return ""

        datadir = self._env['dir']
        certfile = os.path.join(datadir, 'keys', "authority_certificate")
        v3id = None
        with open(certfile, 'r') as f:
            for line in f:
                if line.startswith("fingerprint"):
                    v3id = line.split()[1].strip()
                    break

        assert v3id is not None

        if self._env['bridgeauthority']:
            # Bridge authorities return AlternateBridgeAuthority with
            # the 'bridge' flag set.
            options = ("AlternateBridgeAuthority",)
            self._env['dirserver_flags'] += " bridge"
        else:
            # Directory authorities return AlternateDirAuthority with
            # the 'v3ident' flag set.
            # XXXX This next line is needed for 'bridges' but breaks
            # 'basic'
            if hasbridgeauth:
                options = ("AlternateDirAuthority",)
            else:
                options = ("DirAuthority",)
            self._env['dirserver_flags'] += " v3ident=%s" % v3id

        authlines = ""
        for authopt in options:
            authlines += "%s %s orport=%s" % (
                authopt, self._env['nick'], self._env['orport'])
            # It's ok to give an authority's IPv6 address to an IPv4-only
            # client or relay: it will and must ignore it
            # and yes, the orport is the same on IPv4 and IPv6
            if self._env['ipv6_addr'] is not None:
                authlines += " ipv6=%s:%s" % (self._env['ipv6_addr'],
                                              self._env['orport'])
            authlines += " %s %s:%s %s\n" % (
                self._env['dirserver_flags'], self._env['ip'],
                self._env['dirport'], self._env['fingerprint'])
        return authlines

    def _getBridgeLines(self):
        """Return potential Bridge line for this Node. Non-bridge
        relays return "".
        """
        if not self._env['bridge']:
            return ""

        if self._env['pt_bridge']:
            port = self._env['ptport']
            transport = self._env['pt_transport']
            extra = self._env['pt_extra']
        else:
            # the orport is the same on IPv4 and IPv6
            port = self._env['orport']
            transport = ""
            extra = ""

        BRIDGE_LINE_TEMPLATE = "Bridge %s %s:%s %s %s\n"

        bridgelines = BRIDGE_LINE_TEMPLATE % (transport,
                                              self._env['ip'],
                                              port,
                                              self._env['fingerprint'],
                                              extra)
        if self._env['ipv6_addr'] is not None:
            bridgelines += BRIDGE_LINE_TEMPLATE % (transport,
                                                   self._env['ipv6_addr'],
                                                   port,
                                                   self._env['fingerprint'],
                                                   extra)
        return bridgelines


class LocalNodeController(NodeController):

    def __init__(self, env):
        NodeController.__init__(self, env)
        self._env = env

    def getNick(self):
        """Return the nickname for this node."""
        return self._env['nick']

    def getPid(self):
        """Assuming that this node has its pidfile in ${dir}/pid, return
           the pid of the running process, or None if there is no pid in the
           file.
        """
        pidfile = os.path.join(self._env['dir'], 'pid')
        if not os.path.exists(pidfile):
            return None

        with open(pidfile, 'r') as f:
            return int(f.read())

    def isRunning(self, pid=None):
        """Return true iff this node is running.  (If 'pid' is provided, we
           assume that the pid provided is the one of this node.  Otherwise
           we call getPid().
        """
        if pid is None:
            pid = self.getPid()
        if pid is None:
            return False

        try:
            os.kill(pid, 0)  # "kill 0" == "are you there?"
        except OSError as e:
            if e.errno == errno.ESRCH:
                return False
            raise

        # okay, so the process exists.  Say "True" for now.
        # XXXX check if this is really tor!
        return True

    def check(self, listRunning=True, listNonRunning=False):
        """See if this node is running, stopped, or crashed.  If it's running
           and listRunning is set, print a short statement.  If it's
           stopped and listNonRunning is set, then print a short statement.
           If it's crashed, print a statement.  Return True if the
           node is running, false otherwise.
        """
        # XXX Split this into "check" and "print" parts.
        pid = self.getPid()
        nick = self._env['nick']
        datadir = self._env['dir']
        corefile = "core.%s" % pid
        tor_version = get_tor_version(self._env['tor'])
        if self.isRunning(pid):
            if listRunning:
                # PIDs are typically 65535 or less
                print("{:12} is running with PID {:5}: {}"
                      .format(nick, pid, tor_version))
            return True
        elif os.path.exists(os.path.join(datadir, corefile)):
            if listNonRunning:
                print("{:12} seems to have crashed, and left core file {}: {}"
                      .format(nick, corefile, tor_version))
            return False
        else:
            if listNonRunning:
                print("{:12} is stopped: {}"
                      .format(nick, tor_version))
            return False

    def hup(self):
        """Send a SIGHUP to this node, if it's running."""
        pid = self.getPid()
        nick = self._env['nick']
        if self.isRunning(pid):
            print("Sending sighup to {}".format(nick))
            os.kill(pid, signal.SIGHUP)
            return True
        else:
            print("{:12} is not running".format(nick))
            return False

    def start(self):
        """Try to start this node; return True if we succeeded or it was
           already running, False if we failed."""

        if self.isRunning():
            print("{:12} is already running".format(self._env['nick']))
            return True
        tor_path = self._env['tor']
        torrc = self._getTorrcFname()
        cmdline = [
            tor_path,
            "-f", torrc,
            ]
        p = launch_process(cmdline)
        if self.waitOnLaunch():
            # this requires that RunAsDaemon is set
            (stdouterr, empty_stderr) = p.communicate()
            debug(stdouterr)
            assert empty_stderr is None
        else:
            # this does not require RunAsDaemon to be set, but is slower.
            #
            # poll() only catches failures before the call itself
            # so let's sleep a little first
            # this does, of course, slow down process launch
            # which can require an adjustment to the voting interval
            #
            # avoid writing a newline or space when polling
            # so output comes out neatly
            sys.stdout.write('.')
            sys.stdout.flush()
            time.sleep(self._env['poll_launch_time'])
            p.poll()
        if p.returncode is not None and p.returncode != 0:
            if self._env['poll_launch_time'] is None:
                print(("Couldn't launch {:12} command '{}': " +
                       "exit {}, output '{}'")
                      .format(self._env['nick'],
                              " ".join(cmdline),
                              p.returncode,
                              stdouterr))
            else:
                print(("Couldn't poll {:12} command '{}' " +
                       "after waiting {} seconds for launch: " +
                       "exit {}").format(self._env['nick'],
                                         " ".join(cmdline),
                                         self._env['poll_launch_time'],
                                         p.returncode))
            return False
        return True

    def stop(self, sig=signal.SIGINT):
        """Try to stop this node by sending it the signal 'sig'."""
        pid = self.getPid()
        if not self.isRunning(pid):
            print("{:12} is not running".format(self._env['nick']))
            return
        os.kill(pid, sig)

    def cleanup_lockfile(self):
        lf = self._env['lockfile']
        if not self.isRunning() and os.path.exists(lf):
            debug("Removing stale lock file for {} ..."
                  .format(self._env['nick']))
            os.remove(lf)

    def waitOnLaunch(self):
        """Check whether we can wait() for the tor process to launch"""
        # TODO: is this the best place for this code?
        # RunAsDaemon default is 0
        runAsDaemon = False
        with open(self._getTorrcFname(), 'r') as f:
            for line in f.readlines():
                stline = line.strip()
                # if the line isn't all whitespace or blank
                if len(stline) > 0:
                    splline = stline.split()
                    # if the line has at least two tokens on it
                    if (len(splline) > 0 and
                            splline[0].lower() == "RunAsDaemon".lower() and
                            splline[1] == "1"):
                        # use the RunAsDaemon value from the torrc
                        # TODO: multiple values?
                        runAsDaemon = True
        if runAsDaemon:
            # we must use wait() instead of poll()
            self._env['poll_launch_time'] = None
            return True
        else:
            # we must use poll() instead of wait()
            if self._env['poll_launch_time'] is None:
                self._env['poll_launch_time'] = \
                    self._env['poll_launch_time_default']
            return False

    def getLogfile(self, info=False):
        """Return the expected path to the logfile for this instance."""
        datadir = self._env['dir']
        if info:
            logname = "info.log"
        else:
            logname = "notice.log"
        return os.path.join(datadir, logname)

    def getLastBootstrapStatus(self):
        """Look through the logs and return the last bootstrap message
           received as a 3-tuple of percentage complete, keyword
           (optional), and message.
        """
        logfname = self.getLogfile()
        if not os.path.exists(logfname):
            return (-200, "no_logfile", "There is no logfile yet.")
        percent,keyword,message=-100,"no_message","No bootstrap messages yet."
        with open(logfname, 'r') as f:
            for line in f:
                m = re.search(r'Bootstrapped (\d+)%(?: \(([^\)]*)\))?: (.*)',
                              line)
                if m:
                    percent, keyword, message = m.groups()
                    percent = int(percent)
        return (percent, keyword, message)

    def isBootstrapped(self):
        """Return true iff the logfile says that this instance is
           bootstrapped."""
        pct, _, _ = self.getLastBootstrapStatus()
        return pct == 100

# XXX: document these options
DEFAULTS = {
    'authority': False,
    'bridgeauthority': False,
    'hasbridgeauth': False,
    'relay': False,
    'bridge': False,
    'pt_bridge': False,
    'pt_transport' : "",
    'pt_extra' : "",
    'hs': False,
    'hs_directory': 'hidden_service',
    'hs-hostname': None,
    'connlimit': 60,
    'net_base_dir': get_absolute_net_path(),
    'tor': os.environ.get('CHUTNEY_TOR', 'tor'),
    'tor-gencert': os.environ.get('CHUTNEY_TOR_GENCERT', None),
    'auth_cert_lifetime': 12,
    'ip': os.environ.get('CHUTNEY_LISTEN_ADDRESS', '127.0.0.1'),
    # we default to ipv6_addr None to support IPv4-only systems
    'ipv6_addr': os.environ.get('CHUTNEY_LISTEN_ADDRESS_V6', None),
    'dirserver_flags': 'no-v2',
    'chutney_dir': get_absolute_chutney_path(),
    'torrc_fname': '${dir}/torrc',
    'orport_base': 5000,
    'dirport_base': 7000,
    'controlport_base': 8000,
    'socksport_base': 9000,
    'extorport_base' : 9500,
    'ptport_base' : 9900,
    'authorities': "AlternateDirAuthority bleargh bad torrc file!",
    'bridges': "Bridge bleargh bad torrc file!",
    'core': True,
    # poll_launch_time: None means wait on launch (requires RunAsDaemon),
    # otherwise, poll after that many seconds (can be fractional/decimal)
    'poll_launch_time': None,
    # Used when poll_launch_time is None, but RunAsDaemon is not set
    # Set low so that we don't interfere with the voting interval
    'poll_launch_time_default': 0.1,
    # the number of bytes of random data we send on each connection
    'data_bytes': getenv_int('CHUTNEY_DATA_BYTES', 10 * 1024),
    # the number of times each client will connect
    'connection_count': getenv_int('CHUTNEY_CONNECTIONS', 1),
    # Do we want every client to connect to every HS, or one client
    # to connect to each HS?
    # (Clients choose an exit at random, so this doesn't apply to exits.)
    'hs_multi_client': getenv_int('CHUTNEY_HS_MULTI_CLIENT', 0),
    # How long should verify (and similar commands) wait for a successful
    # outcome? (seconds)
    # We check BOOTSTRAP_TIME for compatibility with old versions of
    # test-network.sh
    'bootstrap_time': getenv_int('CHUTNEY_BOOTSTRAP_TIME',
                                 getenv_int('BOOTSTRAP_TIME',
                                            60)),
    # the PID of the controlling script (for __OwningControllerProcess)
    'controlling_pid': getenv_int('CHUTNEY_CONTROLLING_PID', 0),
    # a DNS config file (for ServerDNSResolvConfFile)
    'dns_conf': (os.environ.get('CHUTNEY_DNS_CONF', '/etc/resolv.conf')
                        if 'CHUTNEY_DNS_CONF' in os.environ
                        else None),

    # The phase at which this instance needs to be
    # configured/launched, if we're doing multiphase
    # configuration/launch.
    'config_phase' : 1,
    'launch_phase' : 1,

    'CUR_CONFIG_PHASE': getenv_int('CHUTNEY_CONFIG_PHASE', 1),
    'CUR_LAUNCH_PHASE': getenv_int('CHUTNEY_LAUNCH_PHASE', 1),
}


class TorEnviron(chutney.Templating.Environ):

    """Subclass of chutney.Templating.Environ to implement commonly-used
       substitutions.

       Environment fields provided:

          orport, controlport, socksport, dirport: *Port torrc option
          dir: DataDirectory torrc option
          nick: Nickname torrc option
          tor_gencert: name or path of the tor-gencert binary
          auth_passphrase: obsoleted by CookieAuthentication
          torrc_template_path: path to chutney torrc_templates directory
          hs_hostname: the hostname of the key generated by a hidden service
          owning_controller_process: the __OwningControllerProcess torrc line,
             disabled if tor should continue after the script exits
          server_dns_resolv_conf: the ServerDNSResolvConfFile torrc line,
             disabled if tor should use the default DNS conf.
             If the dns_conf file is missing, this option is also disabled:
             otherwise, exits would not work due to tor bug #21900.

       Environment fields used:
          nodenum: chutney's internal node number for the node
          tag: a short text string that represents the type of node
          orport_base, controlport_base, socksport_base, dirport_base: the
             initial port numbers used by nodenum 0. Each additional node adds
             1 to the port numbers.
          tor-gencert (note hyphen): name or path of the tor-gencert binary (if
             present)
          chutney_dir: directory of the chutney source code
          tor: name or path of the tor binary
          net_base_dir: path to the chutney net directory
          hs_directory: name of the hidden service directory
          nick: Nickname torrc option (debugging only)
          hs-hostname (note hyphen): cached hidden service hostname value
          controlling_pid: the PID of the controlling process. After this
             process exits, the child tor processes will exit
          dns_conf: the path to a DNS config file for Tor Exits. If this file
             is empty or unreadable, Tor will try 127.0.0.1:53.
    """

    def __init__(self, parent=None, **kwargs):
        chutney.Templating.Environ.__init__(self, parent=parent, **kwargs)

    def _get_orport(self, my):
        return my['orport_base'] + my['nodenum']

    def _get_controlport(self, my):
        return my['controlport_base'] + my['nodenum']

    def _get_socksport(self, my):
        return my['socksport_base'] + my['nodenum']

    def _get_dirport(self, my):
        return my['dirport_base'] + my['nodenum']

    def _get_extorport(self, my):
        return my['extorport_base'] + my['nodenum']

    def _get_ptport(self, my):
        return my['ptport_base'] + my['nodenum']

    def _get_dir(self, my):
        return os.path.abspath(os.path.join(my['net_base_dir'],
                                            "nodes",
                                            "%03d%s" % (
                                                my['nodenum'], my['tag'])))

    def _get_nick(self, my):
        return "test%03d%s" % (my['nodenum'], my['tag'])

    def _get_tor_gencert(self, my):
        return my['tor-gencert'] or '{0}-gencert'.format(my['tor'])

    def _get_auth_passphrase(self, my):
        return self['nick']  # OMG TEH SECURE!

    def _get_torrc_template_path(self, my):
        return [os.path.join(my['chutney_dir'], 'torrc_templates')]

    def _get_lockfile(self, my):
        return os.path.join(self['dir'], 'lock')

    # A hs generates its key on first run,
    # so check for it at the last possible moment,
    # but cache it in memory to avoid repeatedly reading the file
    # XXXX - this is not like the other functions in this class,
    # as it reads from a file created by the hidden service
    def _get_hs_hostname(self, my):
        if my['hs-hostname'] is None:
            datadir = my['dir']
            # a file containing a single line with the hs' .onion address
            hs_hostname_file = os.path.join(datadir, my['hs_directory'],
                                            'hostname')
            try:
                with open(hs_hostname_file, 'r') as hostnamefp:
                    hostname = hostnamefp.read()
                # the hostname file ends with a newline
                hostname = hostname.strip()
                my['hs-hostname'] = hostname
            except IOError as e:
                print("Error: hs %r error %d: %r opening hostname file '%r'" %
                      (my['nick'], e.errno, e.strerror, hs_hostname_file))
        return my['hs-hostname']

    def _get_owning_controller_process(self, my):
        cpid = my['controlling_pid']
        ocp_line = ('__OwningControllerProcess %d' % (cpid))
        # if we want to leave the network running, or controlling_pid is 1
        # (or invalid)
        if (getenv_int('CHUTNEY_START_TIME', 0) < 0 or
            getenv_int('CHUTNEY_BOOTSTRAP_TIME', 0) < 0 or
            getenv_int('CHUTNEY_STOP_TIME', 0) < 0 or
            cpid <= 1):
            return '#' + ocp_line
        else:
            return ocp_line

    # the default resolv.conf path is set at compile time
    # there's no easy way to get it out of tor, so we use the typical value
    DEFAULT_DNS_RESOLV_CONF = "/etc/resolv.conf"
    # if we can't find the specified file, use this one as a substitute
    OFFLINE_DNS_RESOLV_CONF = "/dev/null"

    def _get_server_dns_resolv_conf(self, my):
        if my['dns_conf'] == "":
            # if the user asked for tor's default
            return "#ServerDNSResolvConfFile using tor's compile-time default"
        elif my['dns_conf'] is None:
            # if there is no DNS conf file set
            debug("CHUTNEY_DNS_CONF not specified, using '{}'."
                  .format(TorEnviron.DEFAULT_DNS_RESOLV_CONF))
            dns_conf = TorEnviron.DEFAULT_DNS_RESOLV_CONF
        else:
            dns_conf = my['dns_conf']
        dns_conf = os.path.abspath(dns_conf)
        # work around Tor bug #21900, where exits fail when the DNS conf
        # file does not exist, or is a broken symlink
        # (os.path.exists returns False for broken symbolic links)
        if not os.path.exists(dns_conf):
            # Issue a warning so the user notices
            print("CHUTNEY_DNS_CONF '{}' does not exist, using '{}'."
                  .format(dns_conf, TorEnviron.OFFLINE_DNS_RESOLV_CONF))
            dns_conf = TorEnviron.OFFLINE_DNS_RESOLV_CONF
        return "ServerDNSResolvConfFile %s" % (dns_conf)

KNOWN_REQUIREMENTS = {
    "IPV6": chutney.Host.is_ipv6_supported
}

class Network(object):
    """A network of Tor nodes, plus functions to manipulate them
    """

    def __init__(self, defaultEnviron):
        self._nodes = []
        self._requirements = []
        self._dfltEnv = defaultEnviron
        self._nextnodenum = 0

    def _addNode(self, n):
        n.setNodenum(self._nextnodenum)
        self._nextnodenum += 1
        self._nodes.append(n)

    def _addRequirement(self, requirement):
        requirement = requirement.upper()
        if requirement not in KNOWN_REQUIREMENTS:
            raise RuntimemeError(("Unrecognized requirement %r"%requirement))
        self._requirements.append(requirement)

    def move_aside_nodes_dir(self):
        """Move aside the nodes directory, if it exists and is not a link.
        Used for backwards-compatibility only: nodes is created as a link to
        a new directory with a unique name in the current implementation.
        """
        nodesdir = get_absolute_nodes_path()

        # only move the directory if it exists
        if not os.path.exists(nodesdir):
            return
        # and if it's not a link
        if os.path.islink(nodesdir):
            return

        # subtract 1 second to avoid collisions and get the correct ordering
        newdir = get_new_absolute_nodes_path(time.time() - 1)

        print("NOTE: renaming %r to %r" % (nodesdir, newdir))
        os.rename(nodesdir, newdir)

    def create_new_nodes_dir(self):
        """Create a new directory with a unique name, and symlink it to nodes
        """
        # for backwards compatibility, move aside the old nodes directory
        # (if it's not a link)
        self.move_aside_nodes_dir()

        # the unique directory we'll create
        newnodesdir = get_new_absolute_nodes_path()
        # the canonical name we'll link it to
        nodeslink = get_absolute_nodes_path()

        # this path should be unique and should not exist
        if os.path.exists(newnodesdir):
            raise RuntimeError(
                'get_new_absolute_nodes_path returned a path that exists')

        # if this path exists, it must be a link
        if os.path.exists(nodeslink) and not os.path.islink(nodeslink):
            raise RuntimeError(
                'get_absolute_nodes_path returned a path that exists and is not a link')

        # create the new, uniquely named directory, and link it to nodes
        print("NOTE: creating %r, linking to %r" % (newnodesdir, nodeslink))
        # this gets created with mode 0700, that's probably ok
        mkdir_p(newnodesdir)
        try:
            os.unlink(nodeslink)
        except OSError as e:
            # it's ok if the link doesn't exist, we're just about to make it
            if e.errno == errno.ENOENT:
                pass
            else:
                raise
        os.symlink(newnodesdir, nodeslink)

    def _checkConfig(self):
        for n in self._nodes:
            n.getBuilder().checkConfig(self)

    def supported(self):
        """Check whether this network is supported by the set of binaries
           and host information we have.
        """
        missing_any = False
        for r in self._requirements:
            if not KNOWN_REQUIREMENTS[r]():
                print(("Can't run this network: %s is missing."))
                missing_any = True
        for n in self._nodes:
            if not n.getBuilder().isSupported(self):
                missing_any = False

        if missing_any:
            sys.exit(1)

    def configure(self):
        phase = self._dfltEnv['CUR_CONFIG_PHASE']
        if phase == 1:
            self.create_new_nodes_dir()
        network = self
        altauthlines = []
        bridgelines = []
        all_builders = [ n.getBuilder() for n in self._nodes ]
        builders = [ b for b in all_builders
                     if b._env['config_phase'] == phase ]
        self._checkConfig()

        # XXX don't change node names or types or count if anything is
        # XXX running!

        for b in all_builders:
            b.preConfig(network)
            altauthlines.append(b._getAltAuthLines(
                self._dfltEnv['hasbridgeauth']))
            bridgelines.append(b._getBridgeLines())

        self._dfltEnv['authorities'] = "".join(altauthlines)
        self._dfltEnv['bridges'] = "".join(bridgelines)

        for b in builders:
            b.config(network)

        for b in builders:
            b.postConfig(network)

    def status(self):
        statuses = [n.getController().check(listNonRunning=True)
                    for n in self._nodes]
        n_ok = len([x for x in statuses if x])
        print("%d/%d nodes are running" % (n_ok, len(self._nodes)))
        return n_ok == len(self._nodes)

    def restart(self):
        self.stop()
        self.start()

    def start(self):
        # format polling correctly - avoid printing a newline
        sys.stdout.write("Starting nodes")
        sys.stdout.flush()
        rv = all([n.getController().start() for n in self._nodes
                  if n._env['launch_phase'] ==
                     self._dfltEnv['CUR_LAUNCH_PHASE']])
        # now print a newline unconditionally - this stops poll()ing
        # output from being squashed together, at the cost of a blank
        # line in wait()ing output
        print("")
        return rv

    def hup(self):
        print("Sending SIGHUP to nodes")
        return all([n.getController().hup() for n in self._nodes])

    def wait_for_bootstrap(self):
        print("Waiting for nodes to bootstrap...")
        limit = getenv_int("CHUTNEY_START_TIME", 60)
        delay = 0.5
        controllers = [n.getController() for n in self._nodes]
        elapsed = 0.0
        most_recent_status = [ None ] * len(controllers)
        while True:
            all_bootstrapped = True
            most_recent_status = [ ]
            for c in controllers:
                pct, kwd, msg = c.getLastBootstrapStatus()
                most_recent_status.append((pct, kwd, msg))
                if pct != 100:
                    all_bootstrapped = False

            if all_bootstrapped:
                print("Everything bootstrapped after %s sec"%elapsed)
                return True
            if elapsed >= limit:
                break
            time.sleep(delay)
            elapsed += delay

        print("Bootstrap failed. Node status:")
        for c, status in zip(controllers,most_recent_status):
            c.check(listRunning=False, listNonRunning=True)
            print("{}: {}".format(c.getNick(), status))

        return False

    def stop(self):
        controllers = [n.getController() for n in self._nodes]
        for sig, desc in [(signal.SIGINT, "SIGINT"),
                          (signal.SIGINT, "another SIGINT"),
                          (signal.SIGKILL, "SIGKILL")]:
            print("Sending %s to nodes" % desc)
            for c in controllers:
                if c.isRunning():
                    c.stop(sig=sig)
            print("Waiting for nodes to finish.")
            wrote_dot = False
            for n in range(15):
                time.sleep(1)
                if all(not c.isRunning() for c in controllers):
                    # make the output clearer by adding a newline
                    if wrote_dot:
                        sys.stdout.write("\n")
                        sys.stdout.flush()
                    # check for stale lock file when Tor crashes
                    for c in controllers:
                        c.cleanup_lockfile()
                    return
                sys.stdout.write(".")
                wrote_dot = True
                sys.stdout.flush()
            for c in controllers:
                c.check(listNonRunning=False)
            # make the output clearer by adding a newline
            if wrote_dot:
                sys.stdout.write("\n")
                sys.stdout.flush()


def Require(feature):
    network = _THE_NETWORK
    network._addRequirement(feature)

def ConfigureNodes(nodelist):
    network = _THE_NETWORK

    for n in nodelist:
        network._addNode(n)
        if n._env['bridgeauthority']:
            network._dfltEnv['hasbridgeauth'] = True

def getTests():
    tests = []
    chutney_path = get_absolute_chutney_path()
    if len(chutney_path) > 0 and chutney_path[-1] != '/':
        chutney_path += "/"
    for x in os.listdir(chutney_path + "scripts/chutney_tests/"):
        if not x.startswith("_") and os.path.splitext(x)[1] == ".py":
            tests.append(os.path.splitext(x)[0])
    return tests


def usage(network):
    return "\n".join(["Usage: chutney {command/test} {networkfile}",
                      "Known commands are: %s" % (
                          " ".join(x for x in dir(network)
                                   if not x.startswith("_"))),
                      "Known tests are: %s" % (
                          " ".join(getTests()))
                      ])


def exit_on_error(err_msg):
    print("Error: {0}\n".format(err_msg))
    print(usage(_THE_NETWORK))
    sys.exit(1)


def runConfigFile(verb, data):
    _GLOBALS = dict(_BASE_ENVIRON=_BASE_ENVIRON,
                    Node=Node,
                    Require=Require,
                    ConfigureNodes=ConfigureNodes,
                    _THE_NETWORK=_THE_NETWORK,
                    torrc_option_warn_count=0,
                    TORRC_OPTION_WARN_LIMIT=10)

    exec(data, _GLOBALS)
    network = _GLOBALS['_THE_NETWORK']

    # let's check if the verb is a valid test and run it
    if verb in getTests():
        test_module = importlib.import_module("chutney_tests.{}".format(verb))
        try:
            run_test = test_module.run_test
        except AttributeError as e:
            print("Error running test {!r}: {}".format(verb, e))
            return False
        return run_test(network)

    # tell the user we don't know what their verb meant
    if not hasattr(network, verb):
        print(usage(network))
        print("Error: I don't know how to %s." % verb)
        return

    return getattr(network, verb)()


def parseArgs():
    if len(sys.argv) < 3:
        exit_on_error("Not enough arguments given.")
    if not os.path.isfile(sys.argv[2]):
        exit_on_error("Cannot find networkfile: {0}.".format(sys.argv[2]))
    return {'network_cfg': sys.argv[2], 'action': sys.argv[1]}


def main():
    global _BASE_ENVIRON
    global _THE_NETWORK
    _BASE_ENVIRON = TorEnviron(chutney.Templating.Environ(**DEFAULTS))
    _THE_NETWORK = Network(_BASE_ENVIRON)

    args = parseArgs()
    f = open(args['network_cfg'])
    result = runConfigFile(args['action'], f.read())
    if result is False:
        return -1
    return 0

if __name__ == '__main__':
    sys.exit(main())
