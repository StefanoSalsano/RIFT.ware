# 
# (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
#
# Author(s): Tim Mortsolf
# Creation Date: 2014/05/22
# 

cmake_minimum_required(VERSION 2.8)

set(PKG_NAME rwshell)
set(PKG_VERSION 1.0)
set(PKG_RELEASE 1)
set(PKG_LONG_NAME ${PKG_NAME}-${PKG_VERSION})

set(subdirs src plugins test)
rift_add_subdirs(SUBDIR_LIST ${subdirs})

install(FILES include/riftware/rwshell-api.h
  DESTINATION usr/include/riftware
  COMPONENT ${PKG_LONG_NAME})
