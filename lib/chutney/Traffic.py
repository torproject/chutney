#!/usr/bin/env python
#
# Copyright 2013 The Tor Project
#
# You may do anything with this work that copyright law would normally
# restrict, so long as you retain the above notice(s) and this license
# in all redistributed copies and derived works.  There is no warranty.

# Do select/read/write for binding to a port, connecting to it and
# write, read what's written and verify it. You can connect over a
# SOCKS proxy (like Tor).
#
# You can create a TrafficTester and give it an IP address/host and
# port to bind to. If a Source is created and added to the
# TrafficTester, it will connect to the address/port it was given at
# instantiation and send its data. A Source can be configured to
# connect over a SOCKS proxy. When everything is set up, you can
# invoke TrafficTester.run() to start running. The TrafficTester will
# accept the incoming connection and read from it, verifying the data.
#
# For example code, see main() below.

from __future__ import print_function

import sys
import socket
import select
import struct
import errno
import time
import os

from chutney.Debug import debug_flag, debug

def socks_cmd(addr_port):
    """
    Return a SOCKS command for connecting to addr_port.

    SOCKSv4: https://en.wikipedia.org/wiki/SOCKS#Protocol
    SOCKSv5: RFC1928, RFC1929
    """
    ver = 4  # Only SOCKSv4 for now.
    cmd = 1  # Stream connection.
    user = b'\x00'
    dnsname = ''
    host, port = addr_port
    try:
        addr = socket.inet_aton(host)
    except socket.error:
        addr = b'\x00\x00\x00\x01'
        dnsname = '%s\x00' % host
    debug("Socks 4a request to %s:%d" % (host, port))
    if type(dnsname) != type(b""):
        dnsname = dnsname.encode("ascii")
    return struct.pack('!BBH', ver, cmd, port) + addr + user + dnsname


class TestSuite(object):

    """Keep a tab on how many tests are pending, how many have failed
    and how many have succeeded."""

    def __init__(self):
        self.not_done = 0
        self.successes = 0
        self.failures = 0

    def add(self):
        self.not_done += 1

    def success(self):
        self.not_done -= 1
        self.successes += 1

    def failure(self):
        self.not_done -= 1
        self.failures += 1

    def failure_count(self):
        return self.failures

    def all_done(self):
        return self.not_done == 0

    def status(self):
        return('%d/%d/%d' % (self.not_done, self.successes, self.failures))


class Peer(object):

    "Base class for Listener, Source and Sink."
    LISTENER = 1
    SOURCE = 2
    SINK = 3

    def __init__(self, ptype, tt, s=None):
        self.type = ptype
        self.tt = tt  # TrafficTester
        if s is not None:
            self.s = s
        else:
            self.s = socket.socket()
            self.s.setblocking(False)

    def fd(self):
        return self.s.fileno()

    def is_source(self):
        return self.type == self.SOURCE

    def is_sink(self):
        return self.type == self.SINK


class Listener(Peer):

    "A TCP listener, binding, listening and accepting new connections."

    def __init__(self, tt, endpoint):
        super(Listener, self).__init__(Peer.LISTENER, tt)
        self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.s.bind(endpoint)
        self.s.listen(0)

    def accept(self):
        newsock, endpoint = self.s.accept()
        debug("new client from %s:%s (fd=%d)" %
              (endpoint[0], endpoint[1], newsock.fileno()))
        self.tt.add(Sink(self.tt, newsock))


class Sink(Peer):

    "A data sink, reading from its peer and verifying the data."

    def __init__(self, tt, s):
        super(Sink, self).__init__(Peer.SINK, tt, s)
        self.inbuf = b''
        self.repetitions = self.tt.repetitions

    def on_readable(self):
        """Invoked when the socket becomes readable.
        Return 0 on finished, successful verification.
               -1 on failed verification
               >0 if more data needs to be read
        """
        return self.verify(self.tt.data)

    def verify(self, data):
        # shortcut read when we don't ever expect any data
        if self.repetitions == 0 or len(self.tt.data) == 0:
            debug("no verification required - no data")
            return 0
        inp = self.s.recv(len(data) - len(self.inbuf))
        debug("Verify: received %d bytes"% len(inp))
        if len(inp) == 0:
            debug("EOF on fd %s" % self.fd())
            return -1
        self.inbuf += inp
        debug("successfully received (bytes=%d)" % len(self.inbuf))
        while len(self.inbuf) >= len(data):
            assert(len(self.inbuf) <= len(data) or self.repetitions > 1)
            if self.inbuf[:len(data)] != data:
                debug("receive comparison failed (bytes=%d)" % len(data))
                return -1  # Failed verification.
            # if we're not debugging, print a dot every dot_repetitions reps
            elif (not debug_flag and self.tt.dot_repetitions > 0 and
                  self.repetitions % self.tt.dot_repetitions == 0):
                sys.stdout.write('.')
                sys.stdout.flush()
            # repeatedly check data against self.inbuf if required
            debug("receive comparison success (bytes=%d)" % len(data))
            self.inbuf = self.inbuf[len(data):]
            debug("receive leftover bytes (bytes=%d)" % len(self.inbuf))
            self.repetitions -= 1
            debug("receive remaining repetitions (reps=%d)" % self.repetitions)
        if self.repetitions == 0 and len(self.inbuf) == 0:
            debug("successful verification")
        # calculate the actual length of data remaining, including reps
        debug("receive remaining bytes (bytes=%d)"
              % (self.repetitions*len(data) - len(self.inbuf)))
        return self.repetitions*len(data) - len(self.inbuf)


class Source(Peer):

    """A data source, connecting to a TCP server, optionally over a
    SOCKS proxy, sending data."""
    NOT_CONNECTED = 0
    CONNECTING = 1
    CONNECTING_THROUGH_PROXY = 2
    CONNECTED = 5

    def __init__(self, tt, server, buf, proxy=None, repetitions=1):
        super(Source, self).__init__(Peer.SOURCE, tt)
        self.state = self.NOT_CONNECTED
        self.data = buf
        self.outbuf = b''
        self.inbuf = b''
        self.proxy = proxy
        self.repetitions = repetitions
        self._sent_no_bytes = 0
        # sanity checks
        if len(self.data) == 0:
            self.repetitions = 0
        if self.repetitions == 0:
            self.data = {}
        self.connect(server)

    def connect(self, endpoint):
        self.dest = endpoint
        self.state = self.CONNECTING
        dest = self.proxy or self.dest
        try:
            debug("socket %d connecting to %r..."%(self.fd(),dest))
            self.s.connect(dest)
        except socket.error as e:
            if e.errno != errno.EINPROGRESS:
                raise

    def on_readable(self):
        """Invoked when the socket becomes readable.
        Return -1 on failure
               >0 if more data needs to be read or written
        """
        if self.state == self.CONNECTING_THROUGH_PROXY:
            inp = self.s.recv(8 - len(self.inbuf))
            debug("-- connecting through proxy, got %d bytes"%len(inp))
            if len(inp) == 0:
                debug("EOF on fd %d"%self.fd())
                return -1
            self.inbuf += inp
            if len(self.inbuf) == 8:
                if self.inbuf[:2] == b'\x00\x5a':
                    debug("proxy handshake successful (fd=%d)" % self.fd())
                    self.state = self.CONNECTED
                    self.inbuf = b''
                    debug("successfully connected (fd=%d)" % self.fd())
                    # if we have no reps or no data, skip sending actual data
                    if self.want_to_write():
                        return 1    # Keep us around for writing.
                    else:
                        # shortcut write when we don't ever expect any data
                        debug("no connection required - no data")
                        return 0
                else:
                    debug("proxy handshake failed (0x%x)! (fd=%d)" %
                          (ord(self.inbuf[1]), self.fd()))
                    self.state = self.NOT_CONNECTED
                    return -1
            assert(8 - len(self.inbuf) > 0)
            return 8 - len(self.inbuf)
        return self.want_to_write()  # Keep us around for writing if needed

    def want_to_write(self):
        if self.state == self.CONNECTING:
            return True
        if len(self.outbuf) > 0:
            return True
        if (self.state == self.CONNECTED and
            self.repetitions > 0 and
            len(self.data) > 0):
            return True
        return False

    def on_writable(self):
        """Invoked when the socket becomes writable.
        Return 0 when done writing
               -1 on failure (like connection refused)
               >0 if more data needs to be written
        """
        if self.state == self.CONNECTING:
            if self.proxy is None:
                self.state = self.CONNECTED
                debug("successfully connected (fd=%d)" % self.fd())
            else:
                self.state = self.CONNECTING_THROUGH_PROXY
                self.outbuf = socks_cmd(self.dest)
                # we write socks_cmd() to the proxy, then read the response
                # if we get the correct response, we're CONNECTED
        if self.state == self.CONNECTED:
            # repeat self.data into self.outbuf if required
            if (len(self.outbuf) < len(self.data) and self.repetitions > 0):
                self.outbuf += self.data
                self.repetitions -= 1
                debug("adding more data to send (bytes=%d)" % len(self.data))
                debug("now have data to send (bytes=%d)" % len(self.outbuf))
                debug("send repetitions remaining (reps=%d)"
                      % self.repetitions)
        try:
            n = self.s.send(self.outbuf)
        except socket.error as e:
            if e.errno == errno.ECONNREFUSED:
                debug("connection refused (fd=%d)" % self.fd())
                return -1
            raise
        # sometimes, this debug statement prints 0
        # it should print length of the data sent
        # but the code works as long as this doesn't keep on happening
        if n > 0:
            debug("successfully sent (bytes=%d)" % n)
            self._sent_no_bytes = 0
        else:
            debug("BUG: sent no bytes (out of %d; state is %s)"% (len(self.outbuf), self.state))
            self._sent_no_bytes += 1
            # We can't retry too fast, otherwise clients burn all their HSDirs
            if self._sent_no_bytes >= 2:
                print("Sent no data %d times. Stalled." %
                      (self._sent_no_bytes))
                return -1
            time.sleep(5)
        self.outbuf = self.outbuf[n:]
        if self.state == self.CONNECTING_THROUGH_PROXY:
            return 1  # Keep us around.
        debug("bytes remaining on outbuf (bytes=%d)" % len(self.outbuf))
        # calculate the actual length of data remaining, including reps
        # When 0, we're being removed.
        debug("bytes remaining overall (bytes=%d)"
              % (self.repetitions*len(self.data) + len(self.outbuf)))
        return self.repetitions*len(self.data) + len(self.outbuf)


class TrafficTester():

    """
    Hang on select.select() and dispatch to Sources and Sinks.
    Time out after self.timeout seconds.
    Keep track of successful and failed data verification using a
    TestSuite.
    Return True if all tests succeed, else False.
    """

    def __init__(self,
                 endpoint,
                 data={},
                 timeout=3,
                 repetitions=1,
                 dot_repetitions=0):
        self.listener = Listener(self, endpoint)
        self.pending_close = []
        self.timeout = timeout
        self.tests = TestSuite()
        self.data = data
        self.repetitions = repetitions
        # sanity checks
        if len(self.data) == 0:
            self.repetitions = 0
        if self.repetitions == 0:
            self.data = {}
        self.dot_repetitions = dot_repetitions
        debug("listener fd=%d" % self.listener.fd())
        self.peers = {}  # fd:Peer

    def sinks(self):
        return self.get_by_ptype(Peer.SINK)

    def sources(self):
        return self.get_by_ptype(Peer.SOURCE)

    def get_by_ptype(self, ptype):
        return list(filter(lambda p: p.type == ptype, self.peers.values()))

    def add(self, peer):
        self.peers[peer.fd()] = peer
        if peer.is_source():
            self.tests.add()

    def remove(self, peer):
        self.peers.pop(peer.fd())
        self.pending_close.append(peer.s)

    def run(self):
        while not self.tests.all_done() and self.timeout > 0:
            rset = [self.listener.fd()] + list(self.peers)
            wset = [p.fd() for p in
                    filter(lambda x: x.want_to_write(), self.sources())]
            # debug("rset %s wset %s" % (rset, wset))
            sets = select.select(rset, wset, [], 1)
            if all(len(s) == 0 for s in sets):
                debug("Decrementing timeout.")
                self.timeout -= 1
                continue

            for fd in sets[0]:  # readable fd's
                if fd == self.listener.fd():
                    self.listener.accept()
                    continue
                p = self.peers[fd]
                n = p.on_readable()
                debug("On read, fd %d for %s said %d"%(fd, p, n))
                if n > 0:
                    # debug("need %d more octets from fd %d" % (n, fd))
                    pass
                elif n == 0:  # Success.
                    self.tests.success()
                    self.remove(p)
                else:       # Failure.
                    debug("Got a failure reading fd %d for %s" % (fd,p))
                    self.tests.failure()
                    if p.is_sink():
                        print("verification failed!")
                    self.remove(p)

            for fd in sets[1]:  # writable fd's
                p = self.peers.get(fd)
                if p is not None:  # Might have been removed above.
                    n = p.on_writable()
                    debug("On write, fd %d said %d"%(fd, n))
                    if n == 0:
                        self.remove(p)
                    elif n < 0:
                        debug("Got a failure writing fd %d for %s" % (fd,p))
                        self.tests.failure()
                        self.remove(p)

        for fd in self.peers:
            peer = self.peers[fd]
            debug("peer fd=%d never pending close, never read or wrote" % fd)
            self.pending_close.append(peer.s)
        self.listener.s.close()
        for s in self.pending_close:
            s.close()
        if not debug_flag:
            sys.stdout.write('\n')
            sys.stdout.flush()
        debug("Done with run(); all_done == %s and failure_count == %s"
              %(self.tests.all_done(), self.tests.failure_count()))
        return self.tests.all_done() and self.tests.failure_count() == 0


def main():
    """Test the TrafficTester by sending and receiving some data."""
    DATA = b"a foo is a bar" * 1000
    bind_to = ('localhost', int(sys.argv[1]))

    tt = TrafficTester(bind_to, DATA)
    # Don't use a proxy for self-testing, so that we avoid tor entirely
    tt.add(Source(tt, bind_to, DATA))
    success = tt.run()

    if success:
        return 0
    return 255

if __name__ == '__main__':
    sys.exit(main())
