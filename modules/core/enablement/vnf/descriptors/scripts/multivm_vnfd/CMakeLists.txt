# 
# (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
#
# Author(s): Sanil Puthiyandyil
# Creation Date: 03/26/2014
# 

cmake_minimum_required(VERSION 2.8)

set(PKG_NAME multivm)
set(PKG_VERSION 1.0)
set(PKG_RELEASE 1)
set(PKG_LONG_NAME ${PKG_NAME}-${PKG_VERSION})

configure_file(
  ${CMAKE_CURRENT_SOURCE_DIR}/generate_packages.sh.in
  ${CMAKE_CURRENT_BINARY_DIR}/generate_packages.sh
  ESCAPE_QUOTES @ONLY
  )

add_custom_command(
  OUTPUT
    ${CMAKE_CURRENT_BINARY_DIR}/trafgen_1VM_vnfd.tar.gz
    ${CMAKE_CURRENT_BINARY_DIR}/trafgen_2VM_vnfd.tar.gz
    ${CMAKE_CURRENT_BINARY_DIR}/trafgen_3VM_vnfd.tar.gz

  COMMAND
    ${CMAKE_CURRENT_BINARY_DIR}/generate_packages.sh

  DEPENDS
    ${CMAKE_CURRENT_SOURCE_DIR}/rw_multivm_vnfd.py
  )


add_custom_target(multivm ALL
  DEPENDS
    ${CMAKE_CURRENT_BINARY_DIR}/trafgen_1VM_vnfd.tar.gz
    ${CMAKE_CURRENT_BINARY_DIR}/trafgen_2VM_vnfd.tar.gz
    ${CMAKE_CURRENT_BINARY_DIR}/trafgen_3VM_vnfd.tar.gz
    ${CMAKE_CURRENT_SOURCE_DIR}/generate_packages.sh.in
  )

install(
  FILES
    ${CMAKE_CURRENT_BINARY_DIR}/trafgen_1VM_vnfd.tar.gz
    ${CMAKE_CURRENT_BINARY_DIR}/trafgen_2VM_vnfd.tar.gz
    ${CMAKE_CURRENT_BINARY_DIR}/trafgen_3VM_vnfd.tar.gz
  DESTINATION
    usr/rift/mano/vnfds/multivm
    COMPONENT ${PKG_LONG_NAME}
  )

rift_python_install_tree(
  COMPONENT ${PKG_LONG_NAME}
  FILES
    rift/mano/vnfds/rw_multivm_vnfd.py
  )
