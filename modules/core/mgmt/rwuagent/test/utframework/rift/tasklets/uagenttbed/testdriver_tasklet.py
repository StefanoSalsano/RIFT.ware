"""
# 
# (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
#

@file testdriver_tasklet.py
@date 16/03/2016
"""

import logging
import collections
import time
import asyncio
import gi

import rift.tasklets
import rift.tasklets.dts
import gi.repository.RwTypes as rwtypes


gi.require_version('RwDts', '1.0')
gi.require_version('UtCompositeYang', '1.0')
gi.require_version('RwAgentTestbedYang', '1.0')
gi.require_version('RwMgmtagtYang', '1.0')

from gi.repository import UtCompositeYang, RwAgentTestbedYang, RwMgmtagtYang
from gi.repository import RwDts as rwdts

from . import testbed_tests as TestBedTests

TESTS = [ TestBedTests.TestEditConf, 
          TestBedTests.TestLargeBinaryBlob, 
          TestBedTests.TestPBRequest,
          TestBedTests.TestNotification
        ]

class TaskletState(object):
    """
    Different states of the tasklet.
    """
    STARTING, RUNNING, FINISHED = ("starting", "running", "finished")

class TestDriverTasklet(rift.tasklets.Tasklet):
   """
   The test driver tasklet that executes all the testcases
   """
   def start(self):
       """
       Entry point for the tasklet
       """
       self.log.setLevel(logging.INFO)
       super().start()
   
       self._dts = rift.tasklets.DTS(self.tasklet_info,
                                     UtCompositeYang.get_schema(),
                                     self._loop,
                                     self.on_dts_state_change) 

       # Set the instance id
       self.instance_name = self.tasklet_info.instance_name
       self.instance_id = int(self.instance_name.rsplit('-', 1)[1])
       self.log.debug("Starting TestDriverTasklet Name: {}, Id: {}".format(
                      self.instance_name,
                      self.instance_id))

       self.state = TaskletState.STARTING

   def stop(self):
       """
       Exit point for the tasklet
       """
       super().stop()

   @asyncio.coroutine
   def on_dts_state_change(self, state):
       """
       Take action according to current dts state to transition
       application into the corresponding application state
       """
    
       switch = {
            rwdts.State.CONFIG: rwdts.State.INIT,
            rwdts.State.INIT: rwdts.State.REGN_COMPLETE,
            rwdts.State.REGN_COMPLETE: rwdts.State.RUN,
        }

       handlers = {
            rwdts.State.INIT: self.init,
            rwdts.State.RUN: self.run,
        }

        # Transition application to next state
       handler = handlers.get(state, None)
       if handler is not None:
           yield from handler()

        # Transition dts to next state
       next_state = switch.get(state, None)
       self.log.info("DTS transition from {} -> {}".format(state, next_state))

       if next_state is not None:
           self._dts.handle.set_state(next_state)

   @asyncio.coroutine
   def init(self):
       """
       Initialize application. During this state transition all DTS
       registrations and subscriptions required by application
       should be started.
       """
  
       self._nc_session = TestBedTests.TBNetconfSession(self.log, self.loop)
       self._nc_proxy = TestBedTests.TBNetconfProxy(self._nc_session, UtCompositeYang, self.log)
       self._test_objects = []

       for cls in TESTS:
           obj = cls(self._dts, self.log, self._nc_proxy)
           yield from obj.dts_self_register()
           self._test_objects.append(obj)

       @asyncio.coroutine
       def run_all_tests(xact_info, action, ks_path, msg):
           ro = RwAgentTestbedYang.AgentTestsOp()
           ro.total_tests = len(self._test_objects)
           
           for test in self._test_objects:
               result = yield from test.run_test()
               if result is True:
                  self._log.info("Test {} passed".format(test.name))
                  ro.passed_count += 1
               else:
                  self._log.error("Test {} failed".format(test.name))
                  ro.failed_count += 1
                  ro.failed_tests.append(test.name)
                  if msg.continue_on_failure is False:
                     break

           xpath = "O,/rw-agent-testbed:agent-tests"
           xact_info.respond_xpath(rwdts.XactRspCode.ACK, xpath, ro)
          
       # Register for all test-cases
       yield from self._dts.register(
                  xpath="I,/rw-agent-testbed:agent-tests/rw-agent-testbed:all",
                  flags=rwdts.Flag.PUBLISHER,
                  handler=rift.tasklets.DTS.RegistrationHandler(on_prepare=run_all_tests))
       
   def run(self):
       """
       """
       yield from self._dts.ready.wait()