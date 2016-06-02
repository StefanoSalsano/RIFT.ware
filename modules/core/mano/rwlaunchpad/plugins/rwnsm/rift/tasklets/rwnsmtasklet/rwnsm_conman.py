
# 
# (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
#

import asyncio
import time
import ncclient
import ncclient.asyncio_manager
import re

import gi
gi.require_version('RwYang', '1.0')
gi.require_version('RwNsmYang', '1.0')
gi.require_version('RwDts', '1.0')
gi.require_version('RwTypes', '1.0')
gi.require_version('RwConmanYang', '1.0')
from gi.repository import (
    RwYang,
    RwNsmYang as nsmY,
    NsrYang as nsrY,
    RwDts as rwdts,
    RwTypes,
    RwConmanYang as conmanY
)

import rift.tasklets

class ROConfigManager(object):
    def __init__(self, log, loop, dts, parent):
        self._log = log
        self._loop = loop
        self._dts = dts
        self.nsm = parent
        self._log.debug("Initialized ROConfigManager")

    def is_ready(self):
        return True

    @property
    def cm_state_xpath(self):
        return ("/rw-conman:cm-state/rw-conman:cm-nsr")

    @asyncio.coroutine
    def update_ns_cfg_state(self, cm_nsr):
        try:
            if (cm_nsr is None or 'cm_vnfr' not in cm_nsr):
                return

            # Fill in new state to all vnfrs
            gen = (vnfr for vnfr in cm_nsr['cm_vnfr'] if vnfr['id'] in self.nsm._vnfrs)
            for vnfr in gen:
                vnfrid = vnfr['id']
                # Need a consistent derivable way of checking state (hard coded for now)
                if ((vnfr['state'] == 'ready' and
                     self.nsm._vnfrs[vnfrid].is_configured() is False) or
                     vnfr['state'] == 'ready_no_cfg') :
                    yield from self.nsm._vnfrs[vnfrid].set_config_status(nsrY.ConfigStates.CONFIGURED)

        except Exception as e:
            self._log.error("Failed to process cm-state(nsr) e=%s", str(e))
                
    @asyncio.coroutine
    def register(self):
        """ Register for cm-state changes """
        
        @asyncio.coroutine
        def on_prepare(xact_info, query_action, ks_path, msg):
            """ cm-state changed """

            #print("###>>> cm-state change ({}), msg_dict = {}".format(query_action, msg_dict))
            self._log.debug("Received cm-state on_prepare (%s:%s:%s)",
                            query_action,
                            ks_path,
                            msg)

            if (query_action == rwdts.QueryAction.UPDATE or
                query_action == rwdts.QueryAction.CREATE):
                # Update Each NSR/VNFR state
                msg_dict = msg.as_dict()
                yield from self.update_ns_cfg_state(msg_dict)
            elif query_action == rwdts.QueryAction.DELETE:
                self._log.debug("DELETE action in on_prepare for cm-state, ignoring")
            else:
                raise NotImplementedError(
                    "%s on cm-state is not supported",
                    query_action)

            xact_info.respond_xpath(rwdts.XactRspCode.ACK)

        try:
            handler = rift.tasklets.DTS.RegistrationHandler(on_prepare=on_prepare)
            self.dts_reg_hdl = yield from self._dts.register(self.cm_state_xpath,
                                                             flags=rwdts.Flag.SUBSCRIBER,
                                                             handler=handler)
        except Exception as e:
            self._log.error("Failed to register for cm-state changes as %s", str(e))
            
