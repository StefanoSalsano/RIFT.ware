# Creation Date: 2016/1/12
# RIFT_IO_STANDARD_CMAKE_COPYRIGHT_HEADER(END)

cmake_minimum_required(VERSION 2.8)


rift_python_install_tree(
  FILES
    rift/mano/cloud/__init__.py
    rift/mano/cloud/accounts.py
    rift/mano/cloud/config.py
    rift/mano/cloud/operdata.py
    rift/mano/config_agent/operdata.py
    rift/mano/config_agent/__init__.py
    rift/mano/config_agent/config.py
    rift/mano/config_data/__init__.py
    rift/mano/config_data/config.py
    rift/mano/tosca_translator/__init__.py
    rift/mano/tosca_translator/translator_logging.conf
    rift/mano/tosca_translator/compare_desc.py
    rift/mano/tosca_translator/shell.py
    rift/mano/tosca_translator/rwmano/tosca_translator.py
    rift/mano/tosca_translator/rwmano/translate_inputs.py
    rift/mano/tosca_translator/rwmano/__init__.py
    rift/mano/tosca_translator/rwmano/translate_outputs.py
    rift/mano/tosca_translator/rwmano/translate_node_templates.py
    rift/mano/tosca_translator/rwmano/syntax/mano_parameter.py
    rift/mano/tosca_translator/rwmano/syntax/mano_resource.py
    rift/mano/tosca_translator/rwmano/syntax/__init__.py
    rift/mano/tosca_translator/rwmano/syntax/mano_template.py
    rift/mano/tosca_translator/rwmano/syntax/mano_output.py
    rift/mano/tosca_translator/rwmano/tosca/tosca_nfv_vnf.py
    rift/mano/tosca_translator/rwmano/tosca/__init__.py
    rift/mano/tosca_translator/rwmano/tosca/tosca_config_primitives.py
    rift/mano/tosca_translator/rwmano/tosca/tosca_network_port.py
    rift/mano/tosca_translator/rwmano/tosca/tosca_network_network.py
    rift/mano/tosca_translator/rwmano/tosca/tosca_compute.py
    rift/mano/tosca_translator/rwmano/tosca/tosca_scaling_group.py
    rift/mano/tosca_translator/common/__init__.py
    rift/mano/tosca_translator/common/utils.py
    rift/mano/tosca_translator/common/exception.py
    rift/mano/tosca_translator/custom/__init__.py
    rift/mano/tosca_translator/custom/rwmano/__init__.py
    rift/mano/tosca_translator/conf/translator.conf
    rift/mano/tosca_translator/conf/__init__.py
    rift/mano/tosca_translator/conf/config.py
  COMPONENT ${PKG_LONG_NAME}
  PYTHON3_ONLY
  )

##
# Include the subdirs
##
set(subdirs
  rift/mano/tosca_translator/test
  )

rift_add_subdirs(SUBDIR_LIST ${subdirs})
