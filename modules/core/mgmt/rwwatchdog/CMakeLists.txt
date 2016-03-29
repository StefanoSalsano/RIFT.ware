# 
# (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
#
# Author(s): Max Beckett
# Creation Date: 2/16/2016
# 

include(rift_python)
include(rift_plugin)


rift_python_install_tree(
  FILES
    rift/watchdog/__init__.py
    rift/watchdog/connection_details.py
    rift/watchdog/watchdog.py
    rift/watchdog/watchdog_connector.py
    rift/watchdog/watchdog_handler.py
      PYTHON3_ONLY
  COMPONENT
    rwwatchdog
  )

set(
  WATCHDOG_BIN_FILES
    bin/rwwatchdog
  )

install(
  PROGRAMS
    ${WATCHDOG_BIN_FILES}
  DESTINATION
    usr/bin
  COMPONENT
    rwwatchdog
  )
