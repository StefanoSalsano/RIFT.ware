# 
# (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
#
# Author(s): Paul Laidler
# Creation Date: 09/16/2015
# 

cmake_minimum_required(VERSION 2.8)

install(
  PROGRAMS
    pingpong_longevity_systest
    pingpong_vnf_systest
    pingpong_records_systest
    pingpong_vnf_reload_systest
    pingpong_lp_standalone_systest
  DESTINATION usr/rift/systemtest/pingpong_vnf
  COMPONENT ${PKG_LONG_NAME})

install(
  PROGRAMS
    launchpad_longevity_systest
  DESTINATION usr/rift/systemtest/launchpad
  COMPONENT ${PKG_LONG_NAME})

install(
  FILES
    pytest/test_launchpad_longevity.py
    pytest/test_startstop.py
  DESTINATION usr/rift/systemtest/pytest/mission_control/launchpad
  COMPONENT ${PKG_LONG_NAME})

install(
  FILES
    pytest/conftest.py
    pytest/test_pingpong_longevity.py
    pytest/test_pingpong_vnf.py
    pytest/test_records.py
  DESTINATION usr/rift/systemtest/pytest/mission_control/pingpong_vnf
  COMPONENT ${PKG_LONG_NAME})

install(
  FILES
    racfg/pingpong_vnf_systest_cloudsim.racfg
    racfg/pingpong_vnf_systest_openstack.racfg
    racfg/pingpong_records_systest_openstack.racfg
    racfg/pingpong_vnf_reload_systest_openstack.racfg
    racfg/pingpong_lp_standalone_systest_openstack.racfg
  DESTINATION usr/rift/systemtest/pingpong_vnf
  COMPONENT ${PKG_LONG_NAME})

