# 
# (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
#
# Author(s): Sanil Puthiyandyil
# Creation Date: 03/26/2014
# 

cmake_minimum_required(VERSION 2.8)

set(PKG_NAME multivm_nsd)
set(PKG_VERSION 1.0)
set(PKG_RELEASE 1)
set(PKG_LONG_NAME ${PKG_NAME}-${PKG_VERSION})

configure_file(
  ${CMAKE_CURRENT_SOURCE_DIR}/generate_nsd_packages.sh.in
  ${CMAKE_CURRENT_BINARY_DIR}/generate_nsd_packages.sh
  ESCAPE_QUOTES @ONLY
  )

add_custom_command(
  OUTPUT
    ${CMAKE_CURRENT_BINARY_DIR}/trafgen_trafsink_multivm_nsd.tar.gz

  COMMAND
    ${CMAKE_CURRENT_BINARY_DIR}/generate_nsd_packages.sh

  DEPENDS
    ${CMAKE_CURRENT_SOURCE_DIR}/rw_multivm_nsd.py
    ${CMAKE_CURRENT_BINARY_DIR}/../multivm_vnfd/trafgen_1VM_vnfd.tar.gz
    multivm
  )

add_custom_target(multivm_nsd ALL
  DEPENDS
    multivm
    ${CMAKE_CURRENT_BINARY_DIR}/trafgen_trafsink_multivm_nsd.tar.gz
    ${CMAKE_CURRENT_SOURCE_DIR}/generate_nsd_packages.sh.in
  )

add_dependencies(multivm_nsd multivm)

install(
  FILES
    ${CMAKE_CURRENT_BINARY_DIR}/trafgen_trafsink_multivm_nsd.tar.gz
  DESTINATION
    usr/rift/mano/nsds/multivm_nsd
    COMPONENT ${PKG_LONG_NAME}
  )

rift_python_install_tree(
  COMPONENT ${PKG_LONG_NAME}
  FILES
    rift/mano/nsds/rw_multivm_nsd.py
  )
