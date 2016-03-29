# 
# (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
#
# Author(s): Max Beckett
# Creation Date: 2/16/2016
# 

from datetime import date
from queue import Queue
import logging
import json
import socket
import threading
import time
import pickle

from .watchdog_handler import WatchdogHandler

def _open_socket(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    sock.bind(("0.0.0.0", port))

    return sock

class Watchdog(object):
    def __init__(self, negotiation_port):
        self._log = logging.getLogger("watchdog")
        self._log.setLevel(logging.DEBUG)

        self._lock = threading.Lock()
        self._enabled = False
        self._negotiation_port = negotiation_port
        self._socket = None
        self._workers = list()

    def start(self):
        self._log.debug("starting")
        self._enabled = True
        self.listener_thread = threading.Thread(target=self._listen)
        self.listener_thread.start()

    def stop(self):
        with self._lock:
            self._enabled = False

            self._log.debug("stopping workers")
            for worker in self._workers:
                worker.running = False

            self._log.debug("joining on workers")
            for worker in self._workers:
                if worker.is_alive():
                    worker.join()

    def _listen(self):
        try:
            self._socket = _open_socket(self._negotiation_port)

            while self._enabled:

                self._socket.listen(0)
                connection, address = self._socket.accept()
                self._log.info("Accepted connection")

                
                self._log.info("Read connection details")                
                raw_data = connection.recv(65536)
                connection_details = pickle.loads(raw_data)
                connection.close()

                new_worker = WatchdogHandler(connection_details)
                self._workers.append(new_worker)
                
                self._log.info("start watchdog for %s" % connection_details.name)
                new_worker.start()

            else:
                self.stop()
        except socket.error as msg:
            self._log.error("Something happend with the socket: %s" % msg)

