#!/usr/bin/env python3

# 
# (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
#

import argparse
import asyncio
import itertools
import logging
import os
import socket
import sys
import types
import unittest

import xmlrunner

import gi
gi.require_version('RwBaseYang', '1.0')
gi.require_version('CF', '1.0')
gi.require_version('RwDts', '1.0')
gi.require_version('RwDtsToyTaskletYang', '1.0')
gi.require_version('RwMain', '1.0')
gi.require_version('RwManifestYang', '1.0')
gi.require_version('rwlib', '1.0')
gi.require_version('RwVcsYang', '1.0')
#gi.require_version('RwCloudYang', '1.0')

import gi.repository.CF as cf
import gi.repository.RwBaseYang as rwbase
import gi.repository.RwDts as rwdts
import gi.repository.RwMain as rwmain
import gi.repository.RwManifestYang as rwmanifest
import gi.repository.rwlib as rwlib
import gi.repository.RwTypes as rwtypes
import gi.repository.RwVcsYang as rwvcs
import gi.repository.RwDtsToyTaskletYang as toyyang
import gi.repository.RwYang as RwYang
from gi.repository import ProtobufC
#from gi.repository import RwCloudYang
from gi.repository import RwcalYang as rwcalyang
import rift.auto.session
import rift.vcs.vcs

import rift.tasklets
import rift.test.dts

if sys.version_info < (3, 4, 4):
    asyncio.ensure_future = asyncio.async

@unittest.skipUnless('FORCE' in os.environ, 'Useless until DTS can actually be deallocated, RIFT-7085')
class DtsTestCase(rift.test.dts.DtsPerf):
    """
    DTS GI interface unittests

    Note:  Each tests uses a list of asyncio.Events for staging through the
    test.  These are required here because we are bring up each coroutine
    ("tasklet") at the same time and are not implementing any re-try
    mechanisms.  For instance, this is used in numerous tests to make sure that
    a publisher is up and ready before the subscriber sends queries.  Such
    event lists should not be used in production software.
    """

    def test_read_pub(self):
        """
        Verify that pub/sub are working when the publisher and subscriber are
        different Tasklets.

        The test will progress through stages defined by the events list:
            0:  Publisher registration hit on_ready()
            1:  Subscriber finished iterating through dts.query_read() results
        """
        print("{{{{{{{{{{{{{{{{{{{{STARTING - test_read_pub")
        results = []
        exp_results = [5, 9, 11, 11, 11]
        stop_seq_exp = []
        stop_seq_act = []
        confd_host="127.0.0.1"

        events = [asyncio.Event(loop=self.loop) for _ in range(2)]

        xpath = '/rw-dts-toy-tasklet:a-container'

        ret = toyyang.AContainer()
        ret.a_string = 'pub'
        os.environ['DTS_HA_TEST'] = '1'
        @asyncio.coroutine
        def sub():
            nonlocal stop_seq_exp
            nonlocal stop_seq_act

            tinfo = self.new_tinfo('sub')
            dts = rift.tasklets.DTS(tinfo, self.schema, self.loop)
            # Sleep for DTS registrations to complete
            yield from asyncio.sleep(1, loop=self.loop)

            @asyncio.coroutine
            def append_result_curr_list():
                vcs_info = rwbase.VcsInfo() 
                res_iter = yield from dts.query_read('/rw-base:vcs/rw-base:info', flags=0)
                for i in res_iter:
                    info_result = yield from i
                components = info_result.result.components.component_info
                recvd_list = {}
                for component in components:
                    recvd_list[component.instance_name] = component.rwcomponent_parent
                return  len(info_result.result.components.component_info), recvd_list

            @asyncio.coroutine
            def issue_vstart(component, parent, recover=False):
                # Issue show vcs info 
                vstart_input = rwvcs.VStartInput()
                vstart_input.component_name = component
                vstart_input.parent_instance = parent
                vstart_input.recover = recover
                query_iter = yield from dts.query_rpc( xpath="/rw-vcs:vstart",
                                                      flags=0, msg=vstart_input)
                yield from asyncio.sleep(2, loop=self.loop)

            @asyncio.coroutine
            def issue_vstop(stop_instance_name, flag=0):
                vstop_input = rwvcs.VStopInput(instance_name=stop_instance_name)
                query_iter = yield from dts.query_rpc( xpath="/rw-vcs:vstop",
                                                      flags=flag, msg=vstop_input)
                yield from asyncio.sleep(1, loop=self.loop)

            r_len, r_dict = yield from append_result_curr_list()
            old_dict = r_dict

            yield from issue_vstart('logd', 'rwdtsperf-c-vm-729');

            r_len, r_dict = yield from append_result_curr_list()
            new_inst = set(r_dict.keys()) - set(old_dict.keys())
            logd_inst = new_inst.pop()
            old_dict = r_dict
            
            #logd_tinfo = rwmain.Gi.find_taskletinfo_by_name(self.rwmain, logd_inst)
            #logd_dtsha = rift.tasklets.DTS(logd_tinfo, self.schema, self.loop)
            #logd_regh = rwdts.Api.find_reg_handle_for_xpath(logd_dtsha._dts, "D,/rwdts:dts/rwdts:member")
            #print("tinfo is {}, dtsha {} raw_regh {}\n".format(logd_tinfo, logd_dtsha, logd_regh))


            yield from issue_vstart('rwdtsperf-c-proc', 'rwdtsperf-c-vm-729');
          
            r_len, r_dict = yield from append_result_curr_list()
            new_inst = set(r_dict.keys()) - set(old_dict.keys())
            pop_inst = new_inst.pop()
            if 'rwdtsperf-c-proc' in pop_inst:
                proc_inst = pop_inst
                proc_perf_inst = new_inst.pop()
            else:
                proc_perf_inst = pop_inst
                proc_inst = new_inst.pop()
            old_dict = r_dict

            yield from issue_vstart('RW.Proc_1.uAgent', 'rwdtsperf-c-vm-729');
          
            r_len, r_dict = yield from append_result_curr_list()
            new_inst = set(r_dict.keys()) - set(old_dict.keys())
            pop_inst = new_inst.pop()
            if 'RW.Proc_1.uAgent' in pop_inst:
                proc_u_inst = pop_inst
                u_inst = new_inst.pop()
            else:
                u_inst = pop_inst
                proc_u_inst = new_inst.pop()
            old_dict = r_dict

            yield from issue_vstart('rwdtsperf-c', 'rwdtsperf-c-vm-729');

            r_len, r_dict = yield from append_result_curr_list()
            new_inst = set(r_dict.keys()) - set(old_dict.keys())
            pop_inst = new_inst.pop()
            if 'rwdtsperf-c' in pop_inst:
                perf_inst = pop_inst
                confd_inst = new_inst.pop()
            else:
                confd_inst = pop_inst
                perf_inst = new_inst.pop()
            old_dict = r_dict
            stop_seq_exp = [perf_inst, logd_inst, proc_inst, proc_perf_inst, u_inst, proc_u_inst, confd_inst, 'NOT_REMOVED', 'NOT_ADDED' ]

            #Confd 
            #mgmt_session=NetconfSession(confd_host)
            #mgmt_session.connect()

            
            yield from issue_vstop(perf_inst)

            r_len, r_dict = yield from append_result_curr_list()
            new_inst = set(old_dict.keys()) - set(r_dict.keys())
            stop_seq_act.append(new_inst.pop())
            old_dict = r_dict

            yield from issue_vstop(logd_inst)

            r_len, r_dict = yield from append_result_curr_list()
            new_inst = set(old_dict.keys()) - set(r_dict.keys())
            stop_seq_act.append(new_inst.pop())
            old_dict = r_dict

            yield from issue_vstop(proc_inst)

            r_len, r_dict = yield from append_result_curr_list()
            new_inst = set(old_dict.keys()) - set(r_dict.keys())
            pop_inst = new_inst.pop()
            if 'rwdtsperf-c-proc' in pop_inst:
                stop_seq_act.append(pop_inst)
                stop_seq_act.append(new_inst.pop())
            else:
                stop_seq_act.append(new_inst.pop())
                stop_seq_act.append(pop_inst)
            old_dict = r_dict

            yield from issue_vstop(u_inst)

            r_len, r_dict = yield from append_result_curr_list()
            new_inst = set(old_dict.keys()) - set(r_dict.keys())
            stop_seq_act.append(new_inst.pop())
            old_dict = r_dict

            yield from issue_vstop(proc_u_inst)

            r_len, r_dict = yield from append_result_curr_list()
            new_inst = set(old_dict.keys()) - set(r_dict.keys())
            stop_seq_act.append(new_inst.pop())
            old_dict = r_dict

            yield from issue_vstop(confd_inst)

            r_len, r_dict = yield from append_result_curr_list()
            new_inst = set(old_dict.keys()) - set(r_dict.keys())
            stop_seq_act.append(new_inst.pop())
            old_dict = r_dict

            yield from issue_vstart('rwdtsperf-c-proc-restart', 'rwdtsperf-c-vm-729');
          
            r_len, r_dict = yield from append_result_curr_list()
            new_inst = set(r_dict.keys()) - set(old_dict.keys())
            pop_inst = new_inst.pop()
            if 'rwdtsperf-c-proc-restart' in pop_inst:
                proc_r_inst = pop_inst
                proc_r_perf_inst = new_inst.pop()
            else:
                proc_r_perf_inst = pop_inst
                proc_r_inst = new_inst.pop()
            old_dict = r_dict

            yield from issue_vstop(proc_r_perf_inst)

            r_len, r_dict = yield from append_result_curr_list()
            new_inst = set(old_dict.keys()) - set(r_dict.keys())
            if len(new_inst) is 0:
                stop_seq_act.append('NOT_REMOVED')
            else:
                stop_seq_act.append(new_inst.pop())
            old_dict = r_dict

            yield from issue_vstart('rwdtsperf-c', proc_r_inst, True);
          
            r_len, r_dict = yield from append_result_curr_list()
            new_inst = set(r_dict.keys()) - set(old_dict.keys())
            if len(new_inst) is 0:
                stop_seq_act.append('NOT_ADDED')
            else:
                stop_seq_act.append(new_inst.pop())
            old_dict = r_dict

            events[1].set()

        asyncio.ensure_future(sub(), loop=self.loop)
        self.run_until(events[1].is_set, timeout=120)

        self.assertEqual(str(stop_seq_exp), str(stop_seq_act))
        print("}}}}}}}}}}}}}}}}}}}}DONE - test_pub")

class DtsTrafgenTestCase(rift.test.dts.Trafgen):
    """
    DTS GI interface unittests

    Note:  Each tests uses a list of asyncio.Events for staging through the
    test.  These are required here because we are bring up each coroutine
    ("tasklet") at the same time and are not implementing any re-try
    mechanisms.  For instance, this is used in numerous tests to make sure that
    a publisher is up and ready before the subscriber sends queries.  Such
    event lists should not be used in production software.
    """

    def trafgen(self):
        """
        Verify the trafgen setup recovery functions 
        The test will progress through stages defined by the events list:
            0:  Trafgen setup is brought up
            1:  Configuration fed by connecting through confd
            2:  Tasklet/PROC/VM restarts tested to confirm recovery is proper 
        """

        print("{{{{{{{{{{{{{{{{{{{{STARTING - trafgen recovery")
        confd_host="127.0.0.1"

        events = [asyncio.Event(loop=self.loop) for _ in range(2)]

        xpath = '/rw-dts-toy-tasklet:a-container'

        ret = toyyang.AContainer()
        ret.a_string = 'pub'
        os.environ['DTS_HA_TEST'] = '1'
        @asyncio.coroutine
        def sub():

            tinfo = self.new_tinfo('sub')
            dts = rift.tasklets.DTS(tinfo, self.schema, self.loop)
            # Sleep for DTS registrations to complete
            yield from asyncio.sleep(5, loop=self.loop)

            @asyncio.coroutine
            def issue_vstart(component, parent, recover=False):
                vstart_input = rwvcs.VStartInput()
                vstart_input.component_name = component
                vstart_input.parent_instance = parent
                vstart_input.recover = recover
                query_iter = yield from dts.query_rpc( xpath="/rw-vcs:vstart",
                                                      flags=0, msg=vstart_input)
                yield from asyncio.sleep(2, loop=self.loop)

            @asyncio.coroutine
            def issue_vstop(stop_instance_name, flag=0):
                vstop_input = rwvcs.VStopInput(instance_name=stop_instance_name)
                query_iter = yield from dts.query_rpc( xpath="/rw-vcs:vstop",
                                                      flags=flag, msg=vstop_input)
                yield from asyncio.sleep(1, loop=self.loop)

            yield from asyncio.sleep(10, loop=self.loop)

            #Confd 
            print('connecting confd')
            mgmt_session=rift.auto.session.NetconfSession(confd_host)
            mgmt_session.connect()
            print('CONNECTED CONFD')

            #logd_tinfo = rwmain.Gi.find_taskletinfo_by_name(self.rwmain, 'logd-103')
            #logd_dtsha = rift.tasklets.DTS(logd_tinfo, self.schema, self.loop)
            

            events[1].set()

        asyncio.ensure_future(sub(), loop=self.loop)
        self.run_until(events[1].is_set, timeout=120)

        print("}}}}}}}}}}}}}}}}}}}}DONE - trafgen")

class MissionCTestCase(rift.test.dts.MissionControl):
    """
    DTS GI interface unittests

    Note:  Each tests uses a list of asyncio.Events for staging through the
    test.  These are required here because we are bring up each coroutine
    ("tasklet") at the same time and are not implementing any re-try
    mechanisms.  For instance, this is used in numerous tests to make sure that
    a publisher is up and ready before the subscriber sends queries.  Such
    event lists should not be used in production software.
    """
    def mission_control(self):
        """
        Verify the mission_control setup functions
        The test will progress through stages defined by the events list:
            0:  mission_control setup is brought up
            1:  Configuration fed by connecting through confd
            2:  Tasklet/PROC/VM restarts tested to confirm recovery is proper
        """

        print("{{{{{{{{{{{{{{{{{{{{STARTING - mano recovery test")
        confd_host="127.0.0.1"

        events = [asyncio.Event(loop=self.loop) for _ in range(2)]


        @asyncio.coroutine
        def sub():

            tinfo = self.new_tinfo('sub')
            dts = rift.tasklets.DTS(tinfo, self.schema, self.loop)

            # Sleep for DTS registrations to complete
            yield from asyncio.sleep(240, loop=self.loop)

            #Confd
            print('connecting confd')
            mgmt_session=rift.auto.session.NetconfSession(confd_host)
            mgmt_session.connect()
            print('CONNECTED CONFD')

            #logd_tinfo = rwmain.Gi.find_taskletinfo_by_name(self.rwmain, 'logd-103')
            #logd_dtsha = rift.tasklets.DTS(logd_tinfo, self.schema, self.loop)

            events[1].set()

        asyncio.ensure_future(sub(), loop=self.loop)
        self.run_until(events[1].is_set, timeout=360)

class LaunchPadTest(rift.test.dts.LaunchPad):
    """
    DTS GI interface unittests

    Note:  Each tests uses a list of asyncio.Events for staging through the
    test.  These are required here because we are bring up each coroutine
    ("tasklet") at the same time and are not implementing any re-try
    mechanisms.  For instance, this is used in numerous tests to make sure that
    a publisher is up and ready before the subscriber sends queries.  Such
    event lists should not be used in production software.
    """
    def test_launch_pad(self):
        """
        Verify the launchpad setup functions
        The test will progress through stages defined by the events list:
            0:  mission_control setup is brought up
            2:  Tasklet/PROC/VM restarts tested to confirm recovery is proper
        """

        print("{{{{{{{{{{{{{{{{{{{{STARTING - mano recovery test")
        confd_host="127.0.0.1"

        events = [asyncio.Event(loop=self.loop) for _ in range(2)]

        @asyncio.coroutine
        def sub():

            tinfo = self.new_tinfo('sub')
            dts = rift.tasklets.DTS(tinfo, self.schema, self.loop)

            # Sleep for DTS registrations to complete
            print('.........................................................')
            print('........SLEEPING 80 seconds for system to come up........')
            yield from asyncio.sleep(80, loop=self.loop)
            print('........RESUMING........')

            @asyncio.coroutine
            def confd_cloud_acct():
                print('connecting confd')
                mgmt_session=rift.auto.session.NetconfSession(confd_host)
                mgmt_session.connect()
                print('CONNECTED CONFD. sleep 30s')
                yield from asyncio.sleep(10, loop=self.loop)
                print('waiting until system started')
                rift.vcs.vcs.wait_until_system_started(mgmt_session)
            
                cloud_account = RwCloudYang.CloudAccountConfig()
                cloud_account.name = "riftuser1"
                cloud_account.account_type = "openstack"
                cloud_account.openstack.key = 'pluto'
                cloud_account.openstack.secret = 'mypasswd'
                cloud_account.openstack.auth_url = 'http://10.95.4.2:5000/v3/'
                cloud_account.openstack.tenant = 'demo'
                cloud_account.openstack.mgmt_network = 'private'
                cloud_proxy = mgmt_session.proxy(RwCloudYang)
                print('configuring cloud account')
                cloud_proxy.merge_config("/rw-cloud:cloud-account", cloud_account)
                print('CONFIGURED cloud account')

            @asyncio.coroutine
            def dts_cloud_acct():
                msg = rwcalyang.CloudAccount()
                msg.name          = 'mock_account'
                msg.account_type  = "mock"
                msg.mock.username = "mock_user"
                account_xpath = "C,/rw-cloud:cloud-account"
                account = RwCloudYang.CloudAccountConfig()
                account.from_pbuf(msg.to_pbuf())
                account.name = msg.name
                yield from dts.query_create(account_xpath,
                      rwdts.Flag.ADVISE|rwdts.Flag.TRACE,msg)

            @asyncio.coroutine
            def issue_vstop(component,inst,flag=0):
                vstop_input = rwvcs.VStopInput(instance_name=component+'-'+(str(inst))) 
                query_iter = yield from dts.query_rpc( xpath="/rw-vcs:vstop",
                                    flags=flag, msg=vstop_input)
                yield from asyncio.sleep(1, loop=self.loop)


            @asyncio.coroutine
            def inventory():
                vcs_info = rwbase.VcsInfo()
                res_iter = yield from dts.query_read('/rw-base:vcs/rw-base:info', flags=0)
                for i in res_iter:
                    info_result = yield from i
                components = info_result.result.components.component_info
                recvd_list = {}
                for component in components:
                    recvd_list[component.component_name] = (component.instance_id, component.rwcomponent_parent, component.component_type)
                return recvd_list

            @asyncio.coroutine
            def issue_vstart(component, parent, recover=False):
                vstart_input = rwvcs.VStartInput()
                vstart_input.component_name = component
                vstart_input.parent_instance = parent
                vstart_input.recover = recover
                query_iter = yield from dts.query_rpc( xpath="/rw-vcs:vstart",
                                                      flags=0, msg=vstart_input)
                yield from asyncio.sleep(1, loop=self.loop)

            @asyncio.coroutine
            def issue_start_stop(comp_inventory, component_type):
#               critical_components = {'msgbroker', 'dtsrouter'}
                critical_components = {'msgbroker', 'dtsrouter', 'RW.uAgent'}
                for component in comp_inventory:
                  if ((comp_inventory[component])[2] == component_type):
                      inst = (comp_inventory[component])[0]
                      parent = (comp_inventory[component])[1]
                      if (component in critical_components):
                          print(component, 'Marked as CRITICAL - Not restarting')
                      else:
                          print('Stopping ', component_type,component)
                          yield from issue_vstop(component,inst)
                          print('Starting ',component_type,component)
                          yield from issue_vstart(component, parent, recover=True)

            yield from asyncio.sleep(20, loop=self.loop)
            comp_inventory = yield from inventory()
            yield from issue_start_stop(comp_inventory, 'RWTASKLET')
#           yield from issue_start_stop(comp_inventory, 'RWPROC')

            yield from asyncio.sleep(20, loop=self.loop)
            restarted_inventory = yield from inventory()
            for comp in comp_inventory:
                self.assertEqual(str(comp_inventory[comp]), str(restarted_inventory[comp])) 

            events[1].set()

        asyncio.ensure_future(sub(), loop=self.loop)
        self.run_until(events[1].is_set, timeout=360)


def main():
    top_dir = __file__[:__file__.find('/modules/core/')]
    build_dir = os.path.join(top_dir, '.build/modules/core/rwvx/src/core_rwvx-build')
    install_dir = os.environ.get('INSTALLDIR', '')

    if 'DTS_TEST_PUB_DIR' not in os.environ:
        os.environ['DTS_TEST_PUB_DIR'] = os.path.join(build_dir, 'rwdts/plugins/dtstestpub')

    if 'RIFT_NO_SUDO_REAPER' not in os.environ:
        os.environ['RIFT_NO_SUDO_REAPER'] = '1'

    if 'MESSAGE_BROKER_DIR' not in os.environ:
        os.environ['MESSAGE_BROKER_DIR'] = os.path.join(build_dir, 'rwmsg/plugins/rwmsgbroker-c')

    if 'ROUTER_DIR' not in os.environ:
        os.environ['ROUTER_DIR'] = os.path.join(build_dir, 'rwdts/plugins/rwdtsrouter-c')

    if 'RW_VAR_RIFT' not in os.environ:
        os.environ['RW_VAR_RIFT'] = '1'
    
    if 'INSTALLDIR' in os.environ:
        os.chdir(os.environ.get('INSTALLDIR')) 

    if 'RWMSG_BROKER_SHUNT' not in os.environ:
        os.environ['RWMSG_BROKER_SHUNT'] = '1'

#   if 'RW_MANIFEST' not in os.environ:
#       os.environ['RW_MANIFEST'] = os.path.join(install_dir, 'lptestmanifest.xml')

    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--verbose', action='store_true')
    args, _ = parser.parse_known_args()

    DtsTestCase.log_level = logging.DEBUG if args.verbose else logging.WARN

    runner = xmlrunner.XMLTestRunner(output=os.environ["RIFT_MODULE_TEST"])
    unittest.main(testRunner=runner)

if __name__ == '__main__':
    main()

# vim: sw=4
