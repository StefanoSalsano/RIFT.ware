#!/usr/bin/env python3
import os
import gi
import rift.mano.config_data.config
gi.require_version('RwNsdYang', '1.0')
gi.require_version('RwDts', '1.0')
from gi.repository import RwNsdYang, RwYang

model = RwYang.model_create_libncx()
model.load_schema_ypbc(RwNsdYang.get_schema())

for filename in os.listdir("."):
    if not filename.endswith(".yaml"):
        continue

    with open(filename) as hdl:
        yaml_str = hdl.read()

    try:
        nsd = RwNsdYang.YangData_Nsd_NsdCatalog_Nsd.from_yaml(model, yaml_str)
        print("Deserialized %s" % filename)

        config_str = rift.mano.config_data.config.ConfigPrimitiveConvertor().extract_nsd_config(nsd)
        print("config data: \n%s\n" % config_str)

    except Exception:
        print("Failed to deserialize: %s" % filename)
        raise
