# 
# (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
#
# Author(s): Anil Gunturu
# Creation Date: 03/26/2014
# 

cmake_minimum_required(VERSION 2.8)

configure_file(
  ${CMAKE_CURRENT_SOURCE_DIR}/generate_packages.sh.in
  ${CMAKE_CURRENT_BINARY_DIR}/generate_packages.sh
  ESCAPE_QUOTES @ONLY
  )

set(PACKAGE_OUTPUT
  ${CMAKE_CURRENT_BINARY_DIR}/ping_pong_nsd.tar.gz
  ${CMAKE_CURRENT_BINARY_DIR}/ping_vnfd.tar.gz
  ${CMAKE_CURRENT_BINARY_DIR}/pong_vnfd.tar.gz
  ${CMAKE_CURRENT_BINARY_DIR}/ping_vnfd_with_image.tar.gz
  ${CMAKE_CURRENT_BINARY_DIR}/pong_vnfd_with_image.tar.gz
  ${CMAKE_CURRENT_BINARY_DIR}/ping_pong_nsd_with_epa.tar.gz
  ${CMAKE_CURRENT_BINARY_DIR}/ping_vnfd_with_epa.tar.gz
  ${CMAKE_CURRENT_BINARY_DIR}/pong_vnfd_with_epa.tar.gz)

add_custom_command(
    OUTPUT ${PACKAGE_OUTPUT}
    COMMAND ${CMAKE_CURRENT_BINARY_DIR}/generate_packages.sh
    DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/ping_pong_nsd.py
  )

add_custom_target(ping_pong_pkg_gen ALL
    DEPENDS ${PACKAGE_OUTPUT}
    mano_yang
  )

install(
    FILES ${PACKAGE_OUTPUT}
    DESTINATION
      usr/rift/mano/examples/ping_pong_ns
      COMPONENT ${PKG_LONG_NAME}
    )

rift_python_install_tree(
  COMPONENT ${PKG_LONG_NAME}
  FILES
    rift/mano/examples/ping_pong_nsd.py
  )

