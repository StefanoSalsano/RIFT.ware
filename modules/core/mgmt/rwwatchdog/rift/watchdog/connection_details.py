# 
# (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
#
# Author(s): Max Beckett
# Creation Date: 2/16/2016
# 


class ConnectionDetails():
    def __init__(self, name, mapping, port):
        self._name = name
        self._mapping = mapping
        self._port = port

    @property
    def mapping(self):
        return self._mapping

    @property
    def name(self):
        return self._name

    @property
    def port(self):
        return self._port

