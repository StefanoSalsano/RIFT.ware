# 
# (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
#
# Author(s): Max Beckett
# Creation Date: 2/16/2016
# 

import asyncio
import logging
import socket
import pickle
import enum

from .connection_details import ConnectionDetails

class WatchdogConnector():
    def __init__(self, log, name, mapping, asyncio_loop):
        self._log = log
        self._name = name
        self._mapping = mapping
        self._connected = False
        self._asyncio_loop = asyncio_loop

    @property
    def connected(self):
        return self._connected

    @asyncio.coroutine
    def connect(self):
        self._log.debug("construct socket")

        control_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        counter = 10
        while counter > 0:
            try:    
                self._log.debug("Trying to connect....")

                control_sock.connect(("0.0.0.0", 60999))
                control_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self._log.debug("Socket connected")

                break
            except socket.error as err:
                self._log.debug("Can't connect to watchdog: %s " % str(err))

                yield from asyncio.sleep(1, loop=self._asyncio_loop)
                counter -= 1

        if counter <= 0:
            self._log.debug("Failed to connect to watchdog")
            return
        
        data_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        data_sock.bind(('0.0.0.0', 0))
        address, port = data_sock.getsockname()

        data_sock.listen(1)        
        data_sock.settimeout(5)
        connection_details = ConnectionDetails(self._name, self._mapping, port)
    
        raw_data = pickle.dumps(connection_details)
        control_sock.send(raw_data)
        control_sock.close()
    
        try:
            connection, address = data_sock.accept()
        except socket.timeout:
            self._log.debug("failed to connect to watchdog")
            return 

        self._connection = connection
        self._socket = data_sock
        
        self._connected = True

    def write(self, raw_message):
        if not self._connected:
            return

        if isinstance(raw_message, enum.Enum):
            message = str(raw_message.value).encode("utf-8")
        else:
            message = str(raw_message).encode("utf-8")
        try:
            self._connection.send(message)
            self._connection.send(b'\n')
        except socket.error:
            self._connected = False
            self._socket.close()
