# 
# (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
#
# Author(s): Austin Cormier
# Creation Date: 04/22/2016
# 

rift_py3test(utest_uploader
  TEST_ARGS
  ${CMAKE_CURRENT_SOURCE_DIR}/utest_uploader.py
  )

rift_py3test(utest_serializer
  TEST_ARGS
  ${CMAKE_CURRENT_SOURCE_DIR}/utest_serializer.py
  )
