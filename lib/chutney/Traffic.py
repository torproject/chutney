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
import struct
import errno
import time
import os

import asyncore
import asynchat

from chutney.Debug import debug_flag, debug

def addr_to_family(addr):
    for family in [socket.AF_INET, socket.AF_INET6]:
        try:
            socket.inet_pton(family, addr)
            return family
        except (socket.error, OSError):
            pass

    return socket.AF_INET

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

class Listener(asyncore.dispatcher):
    "A TCP listener, binding, listening and accepting new connections."

    def __init__(self, tt, endpoint):
        asyncore.dispatcher.__init__(self)
        self.create_socket(addr_to_family(endpoint[0]), socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind(endpoint)
        self.listen(0)
        self.tt = tt

    def handle_accept(self):
        # deprecated in python 3.2
        pair = self.accept()
        if pair is not None:
            newsock, endpoint = pair
            debug("new client from %s:%s (fd=%d)" %
                  (endpoint[0], endpoint[1], newsock.fileno()))
            handler = Sink(newsock, self.tt)

    def fileno(self):
        return self.socket.fileno()

class Sink(asynchat.async_chat):
    "A data sink, reading from its peer and verifying the data."
    def __init__(self, sock, tt):
        asynchat.async_chat.__init__(self, sock)
        self.inbuf = b""
        self.set_terminator(None)
        self.tt = tt
        self.repetitions = tt.repetitions

    def collect_incoming_data(self, inp):
        # shortcut read when we don't ever expect any data

        self.inbuf += inp
        data = self.tt.data
        debug("successfully received (bytes=%d)" % len(self.inbuf))
        while len(self.inbuf) >= len(data):
            assert(len(self.inbuf) <= len(data) or self.repetitions > 1)
            if self.inbuf[:len(data)] != data:
                debug("receive comparison failed (bytes=%d)" % len(data))
                self.tt.failure()
                self.close()
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
            self.close()
            self.tt.success()
        # calculate the actual length of data remaining, including reps
        debug("receive remaining bytes (bytes=%d)"
              % (self.repetitions*len(data) - len(self.inbuf)))

    def fileno(self):
        return self.socket.fileno()

class CloseSourceProducer:
    """Helper: when this producer is returned, a source is successful."""
    def __init__(self, source):
        self.source = source

    def more(self):
        self.source.tt.success()

class Source(asynchat.async_chat):
    """A data source, connecting to a TCP server, optionally over a
    SOCKS proxy, sending data."""
    CONNECTING = 1
    CONNECTING_THROUGH_PROXY = 2
    CONNECTED = 5

    def __init__(self, tt, server, buf, proxy=None, repetitions=1):
        asynchat.async_chat.__init__(self)
        self.data = buf
        self.outbuf = b''
        self.inbuf = b''
        self.proxy = proxy
        self.server = server
        self.repetitions = repetitions
        self._sent_no_bytes = 0
        self.tt = tt
        # sanity checks
        if len(self.data) == 0:
            self.repetitions = 0
        if self.repetitions == 0:
            self.data = b""

        self.set_terminator(None)
        dest = (self.proxy or self.server)
        self.create_socket(addr_to_family(dest[0]), socket.SOCK_STREAM)
        debug("socket %d connecting to %r..."%(self.fileno(),dest))
        self.state = self.CONNECTING
        self.connect(dest)

    def handle_connect(self):
        if self.proxy:
            self.state = self.CONNECTING_THROUGH_PROXY
            self.push(socks_cmd(self.server))
        else:
            self.state = self.CONNECTED
            self.push_output()

    def collect_incoming_data(self, data):
        self.inbuf += data
        if self.state == self.CONNECTING_THROUGH_PROXY:
            if len(self.inbuf) >= 8:
                if self.inbuf[:2] == b'\x00\x5a':
                    debug("proxy handshake successful (fd=%d)" % self.fileno())
                    self.state = self.CONNECTED
                    debug("successfully connected (fd=%d)" % self.fileno())
                    self.inbuf = self.inbuf[8:]
                    self.push_output()
                else:
                    debug("proxy handshake failed (0x%x)! (fd=%d)" %
                          (ord(self.inbuf[1]), self.fileno()))
                    self.state = self.NOT_CONNECTED
                    self.close()

    def push_output(self):
        for _ in range(self.repetitions):
            self.push_with_producer(asynchat.simple_producer(self.data))

        self.push_with_producer(CloseSourceProducer(self))
        self.close_when_done()

    def fileno(self):
        return self.socket.fileno()

class TrafficTester(object):
    """
    Hang on select.select() and dispatch to Sources and Sinks.
    Time out after self.timeout seconds.
    Keep track of successful and failed data verification using a
    TestSuite.
    Return True if all tests succeed, else False.
    """

    def __init__(self,
                 endpoint,
                 data=b"",
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
            self.data = b""
        self.dot_repetitions = dot_repetitions
        debug("listener fd=%d" % self.listener.fileno())

    def add(self, item):
        """Register a single item as a test."""
        # We used to hold on to these items for their fds, but now
        # asyncore manages them for us.

        self.tests.add()

    def success(self):
        """Declare that a single test has passed."""
        self.tests.success()

    def failure(self):
        """Declare that a single test has failed."""
        self.tests.failure()

    def run(self):
        start = now = time.time()
        end = time.time() + self.timeout
        while now < end and not self.tests.all_done():
            # run only one iteration at a time, with a nice short timeout, so we
            # can actually detect completion and timeouts.
            asyncore.loop(0.2, False, None, 1)
            now = time.time()
            debug("Test status: %s"%self.tests.status())

        if not debug_flag:
            sys.stdout.write('\n')
            sys.stdout.flush()
        debug("Done with run(); all_done == %s and failure_count == %s"
              %(self.tests.all_done(), self.tests.failure_count()))

        self.listener.close()

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
