#!/usr/bin/python
"""OpenClass network module"""

import os
import Queue
import socket
import traceback
import struct
import SocketServer
import sys
import time
import thread
import ssl
from threading import Thread

# constants
LISTENPORT = 40000
MCASTPORT = 40001
BCASTPORT = 40002

MCASTADDR="224.51.105.104"
BCASTADDR="255.255.255.255"

DATAGRAM_SIZE=65000

DEBUG=False

# {{{ BcastSender
class BcastSender(Thread):
    """Sends broadcast requests"""
    def __init__(self, port, data):
        Thread.__init__(self)
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('', 0))
        self.actions = Queue.Queue()
        self.data = data

    def stop():
        """Stops sending"""
        self.actions.put()

    def run(self):
        """Starts threading loop"""
        print "Running!"
        while 1:
            # TODO: add timers to exit when required
            try:
                if not self.actions.empty():
                    # exiting
                    return
                if DEBUG:
                    self.gui.log(_("Sending broadcasting message.."))
                self.sock.sendto(self.data, ('255.255.255.255', self.port))
                time.sleep(1)
            except:
                self.gui.log("Error sending broadcast message: %s" % sys.exc_value)
                traceback.print_exc()
                time.sleep(1)
# }}}

# {{{ McastListener
class McastListener(Thread):
    """Multicast listening thread"""
    def __init__(self):
        Thread.__init__(self)
        self.actions = Queue.Queue()
        self.messages = []
        self.lock = thread.allocate_lock()

    def get_log(self):
        """Returns the execution log"""
        self.lock.acquire()
        msgs = "\n".join(self.messages)
        return "# received msgs: %d msg_size: %d\n%s" % (len(self.messages), DATAGRAM_SIZE, msgs)
        self.lock.release()

    def stop(self):
        """Stops the execution"""
        self.actions.put(1)

    def run(self):
        """Keep listening for multicasting messages"""
        # Configura o socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('', MCASTPORT))
        # configura para multicast
        mreq = struct.pack("4sl", socket.inet_aton(MCASTADDR), socket.INADDR_ANY)
        s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        # configura timeout para 1 segundo
        s.settimeout(1)
        # configura o mecanismo de captura de tempo
        if get_os() == "Windows":
            timefunc = time.clock
        else:
            timefunc = time.time
        last_ts = None
        while 1:
            if not self.actions.empty():
                print "Finishing multicast capture"
                s.setsockopt(socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP, mreq)
                s.close()
                return
            try:
                data = s.recv(DATAGRAM_SIZE + 1024)
                count = struct.unpack("<I", data[:struct.calcsize("<I")])[0]
                self.lock.acquire()
                curtime = timefunc()
                walltime = time.time()
                if not last_ts:
                    last_ts = curtime
                    timediff = 0
                else:
                    timediff = curtime - last_ts
                    last_ts = curtime
                self.messages.append("%d %f %f %f" % (count, timediff, curtime, walltime))
                self.lock.release()
            except socket.timeout:
                #print "Timeout!"
                pass
            except:
                print "Exception!"
                traceback.print_exc()
# }}}

# {{{ BcastListener
class BcastListener(Thread):
    """Broadcast listening thread"""
    def __init__(self, port=BCASTPORT, datagram_size=DATAGRAM_SIZE):
        Thread.__init__(self)
        self.port = port
        self.datagram_size = datagram_size
        self.actions = Queue.Queue()
        self.messages = Queue.Queue()
        self.lock = thread.allocate_lock()

    def get_log(self):
        """Returns one of received messages"""
        if not self.messages.empty():
            return self.messages.get()
        else:
            return None

    def stop(self):
        """Stops the execution"""
        self.actions.put(1)

    def run(self):
        """Keep listening for broadcasting messages"""
        # Configura o socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('', self.port))
        # configura timeout para 1 segundo
        s.settimeout(1)
        # configura o mecanismo de captura de tempo
        while 1:
            if not self.actions.empty():
                print "Finishing broadcast capture"
                s.close()
                return
            try:
                data = s.recv(self.datagram_size)
                print "Received %s" % data
                self.messages.put(data)
            except socket.timeout:
                #print "Timeout!"
                pass
            except:
                print "Exception!"
                traceback.print_exc()
# }}}

# {{{ TcpClient
class TcpClient:
    """TCP Client"""
    def __init__(self, addr, port, use_ssl=False):
        """Initializes a TCP connection"""
        self.addr = addr
        self.port = port
        self.use_ssl = use_ssl
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if use_ssl:
            self.sock = ssl.wrap_socket(self.sock)

    def connect(self, timeout=None, retries=1):
        """Attempts to connect"""
        while retries > 0:
            try:
                self.sock.connect((self.addr, self.port))
                if timeout:
                    s.settimeout(timeout)
                return True
            except:
                traceback.print_exc()
                continue
        # Unable to establish a connection
        return False

    def close(self, msg=None):
        """Closes a connection"""
        if msg:
            self.sock.send(msg)
        self.sock.close()

    def send(self, msg):
        """Sends a message"""
        self.sock.write(msg)

    def recv(self, msg_size):
        """Receives a message"""
        try:
            data = self.sock.read(msg_size)
            return data
        except:
            traceback.print_exc()
            return None
# }}}

class ReusableSocketServer(SocketServer.TCPServer):
    # TODO: allow address reuse
    allow_reuse_address = True

