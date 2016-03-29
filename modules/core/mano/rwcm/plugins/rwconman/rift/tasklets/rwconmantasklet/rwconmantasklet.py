
# 
# (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
#

'''
This file - ConfigManagerTasklet()
|
+--|--> ConfigurationManager()
        |
        +--> rwconman_config.py - ConfigManagerConfig()
        |    |
        |    +--> ConfigManagerNSR()
        |
        +--> rwconman_events.py - ConfigManagerEvents()
             |
             +--> ConfigManagerROif()

'''

import asyncio
import logging
import os

import gi
gi.require_version('RwDts', '1.0')
gi.require_version('RwConmanYang', '1.0')


from gi.repository import (
    RwDts as rwdts,
    RwConmanYang as conmanY,
)

import rift.tasklets

from . import rwconman_config as Config
from . import rwconman_events as Event

class ConfigurationManager(object):
    def __init__(self, log, loop, dts):
        self._log            = log
        self._loop           = loop
        self._dts            = dts
        self.cfg_sleep       = True
        self.cfg_dir         = os.path.join(os.environ["RIFT_INSTALL"], "etc/conman")
        self._config         = Config.ConfigManagerConfig(self._dts, self._log, self._loop, self)
        self._event          = Event.ConfigManagerEvents(self._dts, self._log, self._loop, self)
        self.pending_cfg     = []

    @asyncio.coroutine
    def update_vnf_state(self, vnf_cfg, state):
        nsr_obj = vnf_cfg['nsr_obj']
        yield from nsr_obj.update_vnf_cm_state(vnf_cfg['vnfr'], state)

    @asyncio.coroutine
    def update_ns_state(self, nsr_obj, state):
        yield from nsr_obj.update_ns_cm_state(state)
        
    @asyncio.coroutine
    def register(self):
        yield from self._config.register()
        self._event.register()

        @asyncio.coroutine
        def configuration_handler():
            while True:
                #self._log.debug("Pending Configuration  = %s", self.pending_cfg)
                if self.pending_cfg:
                    # pending_cfg is nsr_obj list
                    nsr_obj = self.pending_cfg[0]
                    if nsr_obj.being_deleted is False:
                        vnf_cfg_list = nsr_obj.vnf_cfg_list
                        while True:
                            if vnf_cfg_list:
                                vnf_cfg = vnf_cfg_list[0]
                                self._log.info("Applying Pending Configuration for NS/VNF = %s/%s", nsr_obj.nsr_name, vnf_cfg)
                                try:
                                    done = yield from self._event.apply_vnf_config(vnf_cfg)
                                    if done:
                                        vnf_cfg_list.remove(vnf_cfg)
                                    else:
                                        # Do not update nsr state, since config failed for at least one VNF
                                        nsr_obj = None
                                        break
                                except Exception as e:
                                    yield from self.update_vnf_state(vnf_cfg, conmanY.RecordState.CFG_FAILED)
                                    self._log.info("Failed(%s) to Apply Pending Configuration for VNF = %s, will retry", e, vnf_cfg)
                                    # Do not update nsr state, since config failed for at least one VNF
                                    nsr_obj = None
                                    # Do not attempt the next VNF config, there might be dependancies (hence config order)
                                    break
                            else:
                                # Done iterating thru each VNF in this NS
                                break
                                
                    if nsr_obj is not None:
                        yield from self.update_ns_state(nsr_obj, conmanY.RecordState.READY)
                        # Now delete this NS from pending
                        self.pending_cfg.pop(0)

                yield from asyncio.sleep(1, loop=self._loop)
        asyncio.ensure_future(configuration_handler(), loop=self._loop)

class ConfigManagerTasklet(rift.tasklets.Tasklet):
    def __init__(self, *args, **kwargs):
        super(ConfigManagerTasklet, self).__init__(*args, **kwargs)
        self._dts = None
        self._con_man = None

    def start(self):
        super(ConfigManagerTasklet, self).start()
        self.log.setLevel(logging.DEBUG)
        self.log.info("Starting ConfigManagerTasklet")

        self.log.debug("Registering with dts")

        self._dts = rift.tasklets.DTS(self.tasklet_info,
                                      conmanY.get_schema(),
                                      self.loop,
                                      self.on_dts_state_change)

        self.log.debug("Created DTS Api GI Object: %s", self._dts)

    def on_instance_started(self):
        self.log.debug("Got instance started callback")

    @asyncio.coroutine
    def init(self):
        self._log.info("Initializing the Service Orchestrator tasklet")
        self._con_man = ConfigurationManager(self.log,
                                             self.loop,
                                             self._dts)
        yield from self._con_man.register()

    @asyncio.coroutine
    def run(self):
        pass

    @asyncio.coroutine
    def on_dts_state_change(self, state):
        """Take action according to current dts state to transition
        application into the corresponding application state

        Arguments
            state - current dts state
        """
        switch = {
            rwdts.State.INIT: rwdts.State.REGN_COMPLETE,
            rwdts.State.CONFIG: rwdts.State.RUN,
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
        if next_state is not None:
            self._dts.handle.set_state(next_state)
