# 
# (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
#
# Author(s): Max Beckett
# Creation Date: 2/16/2016
# 

from datetime import date
from queue import Queue
import logging

import socket
import threading
import time


class WatchdogHandler(threading.Thread):
    def __init__(self, connection_details):
        super(WatchdogHandler, self).__init__()

        self._name = connection_details.name
        self._mapping = connection_details.mapping
        self._port = connection_details.port

        self._fp = None
        self._log = logging.getLogger(self._name)
        self._running = True
        self._lock = threading.Lock()
        
    @property
    def running(self):
        with self._lock:
            return self._running

    @running.setter
    def running(self, value):
        with self._lock:
            self._running = value

    def run(self):
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.connect(("0.0.0.0", self._port))
            self._socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self._socket.settimeout(1)
        except socket.error as err:
            self._log.error("quitting: %s" % err)
        
        while self.running:
                
            try:
                data = self._socket.recv(1024)
            except socket.timeout:
                continue
            except socket.error as msg:
                self._log.error("error with connection read: %s" % msg)
                self.running = False
                quit()
                continue

            str_data = data.decode("utf-8").strip()

            if str_data == '':
                continue

            values = str_data.split("\n")

            for v in values:

                message = self._mapping.get(v, "Unknown token: %s" % v)
                self._log.debug("%s", message)


