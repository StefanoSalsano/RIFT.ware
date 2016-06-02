
# 
# (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
#

import json
import os

import gi
gi.require_version('PnfdYang', '1.0')
gi.require_version('NsdYang', '1.0')
gi.require_version('VnfdYang', '1.0')
gi.require_version('RwYang', '1.0')
gi.require_version('VldYang', '1.0')
gi.require_version('VnffgdYang', '1.0')
from gi.repository import (
        PnfdYang,
        NsdYang,
        VnfdYang,
        RwYang,
        VldYang,
        VnffgdYang
        )


class UnknownExtensionError(Exception):
    pass


class SerializationError(Exception):
    pass


class ProtoMessageSerializer(object):
    """(De)Serializer/deserializer fo a specific protobuf message into various formats"""
    libncx_model = None

    def __init__(self, yang_ns, yang_pb_cls):
        """ Create a serializer for a specific protobuf message """
        self._yang_ns = yang_ns
        self._yang_pb_cls = yang_pb_cls

    @classmethod
    def _extension_method_map(cls):
        return {
                ".xml": cls._from_xml_file,
                ".yml": cls._from_yaml_file,
                ".yaml": cls._from_yaml_file,
                ".json": cls._from_json_file,
                }

    @classmethod
    def is_supported_file(cls, filename):
        """Returns whether a file has a supported file extension

        Arguments:
            filename - A descriptor file

        Returns:
            True if file extension is supported, False otherwise

        """
        _, extension = os.path.splitext(filename)
        extension_lc = extension.lower()

        return extension_lc in cls._extension_method_map()

    @property
    def yang_namespace(self):
        """ The Protobuf's GI namespace class (e.g. RwVnfdYang) """
        return self._yang_ns

    @property
    def yang_class(self):
        """ The Protobuf's GI class (e.g. RwVnfdYang.YangData_Vnfd_VnfdCatalog_Vnfd) """
        return self._yang_pb_cls

    @property
    def model(self):
        cls = self.__class__

        # Cache the libncx model for the serializer class
        if cls.libncx_model is None:
            cls.libncx_model = RwYang.model_create_libncx()
            cls.libncx_model.load_schema_ypbc(self.yang_namespace.get_schema())

        return cls.libncx_model

    def _from_xml_file(self, file_path):
        with open(file_path, 'r') as fp:
            xml = fp.read()

        return self.yang_class.from_xml_v2(self.model, xml)

    def _from_json_file(self, file_path):
        with open(file_path, 'r') as fp:
            json = fp.read()

        return self.yang_class.from_json(self.model, json)

    def _from_yaml_file(self, file_path):
        with open(file_path, 'r') as fp:
            yaml = fp.read()

        return self.yang_class.from_yaml(self.model, yaml)

    def to_json_string(self, pb_msg):
        """ Serialize a protobuf message into JSON

        Arguments:
            pb_msg - A GI-protobuf object of type provided into constructor

        Returns:
            A JSON string representing the protobuf message

        Raises:
            SerializationError - Message could not be
            TypeError - Incorrect protobuf type provided
        """
        if not isinstance(pb_msg, self._yang_pb_cls):
            raise TypeError("Invalid protobuf message type provided")

        try:
            json_str = pb_msg.to_json(self.model)

        except Exception as e:
            raise SerializationError(e)

        return json_str

    def from_file(self, file_path):
        """ Returns the deserialized protobuf message from file contents

        This function determines the serialization format based on file extension

        Arguments:
            file_path - The file to deserialize

        Returns:
            A GI-Proto message of type that was provided into the constructor

        Raises:
            UnknownExtensionError - File extension is not of a known serialization format
            SerializationError - File failed to be deserialized into the protobuf message
        """

        _, extension = os.path.splitext(file_path)
        extension_lc = extension.lower()
        extension_map = self._extension_method_map()

        if extension_lc not in extension_map:
            raise UnknownExtensionError("Cannot detect message format for %s extension" % extension_lc)

        try:
            msg = extension_map[extension_lc](self, file_path)
        except Exception as e:
            raise SerializationError(e)

        return msg


class VnfdSerializer(ProtoMessageSerializer):
    """ Creates a serializer for the VNFD descriptor"""
    def __init__(self):
        super().__init__(VnfdYang, VnfdYang.YangData_Vnfd_VnfdCatalog_Vnfd)


class NsdSerializer(ProtoMessageSerializer):
    """ Creates a serializer for the NSD descriptor"""
    def __init__(self):
        super().__init__(NsdYang, NsdYang.YangData_Nsd_NsdCatalog_Nsd)


class VldSerializer(ProtoMessageSerializer):
    """ Creates a serializer for the VLD descriptor"""
    def __init__(self):
        super().__init__(VldYang, VldYang.YangData_Vld_VldCatalog_Vld)


class PnfdSerializer(ProtoMessageSerializer):
    """ Creates a serializer for the PNFD descriptor"""
    def __init__(self):
        super().__init__(PnfdYang, PnfdYang.YangData_Pnfd_PnfdCatalog_Pnfd)


class VnffgdSerializer(ProtoMessageSerializer):
    """ Creates a serializer for the VNFFD descriptor"""
    def __init__(self):
        super().__init__(PnfdYang, VnffgdYang.YangData_Vnffgd_VnffgdCatalog_Vnffgd)
