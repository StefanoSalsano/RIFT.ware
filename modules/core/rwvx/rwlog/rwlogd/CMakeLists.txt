# 
# (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
#
# Author(s): Anil Gunturu
# Creation Date: 8/29/2013
# 

cmake_minimum_required(VERSION 2.8)

##
# Include the subdirs
##
set(subdirs
  sinkapi
  plugins/proto
  plugins/rwlogd-c
  plugins/yang
  src
  test
  bin
  )
rift_add_subdirs(SUBDIR_LIST ${subdirs})
