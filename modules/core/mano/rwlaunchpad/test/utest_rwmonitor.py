#!/usr/bin/env python3

# 
# (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
#


import argparse
import asyncio
import concurrent.futures
import logging
import os
import sys
import unittest
import uuid
import xmlrunner

import gi
gi.require_version('NsrYang', '1.0')
gi.require_version('RwcalYang', '1.0')
gi.require_version('RwmonYang', '1.0')
gi.require_version('RwVnfrYang', '1.0')
gi.require_version('RwTypes', '1.0')
gi.require_version('RwMon', '1.0')

from gi.repository import (
        NsrYang,
        RwTypes,
        RwVnfrYang,
        RwcalYang,
        RwmonYang,
        VnfrYang,
        )

from rift.tasklets.rwmonitor.core import (
        AccountAlreadyRegisteredError,
        AccountInUseError,
        InstanceConfiguration,
        Monitor,
        NfviInterface,
        NfviMetricsPluginManager,
        PluginFactory,
        PluginNotSupportedError,
        PluginUnavailableError,
        UnknownAccountError,
        VdurNfviMetrics,
        )
import rw_peas


logger = logging.getLogger(__name__)


class MockTasklet(object):
    def __init__(self, dts, log, loop, records):
        self.dts = dts
        self.log = log
        self.loop = loop
        self.records = records
        self.polling_period = 0
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=16)


def make_nsr(ns_instance_config_ref=str(uuid.uuid4())):
    nsr = NsrYang.YangData_Nsr_NsInstanceOpdata_Nsr()
    nsr.ns_instance_config_ref = ns_instance_config_ref
    return nsr

def make_vnfr(id=str(uuid.uuid4())):
    vnfr = VnfrYang.YangData_Vnfr_VnfrCatalog_Vnfr()
    vnfr.id = id
    return vnfr

def make_vdur(id=str(uuid.uuid4()), vim_id=str(uuid.uuid4())):
    vdur = VnfrYang.YangData_Vnfr_VnfrCatalog_Vnfr_Vdur()
    vdur.id = id
    vdur.vim_id = vim_id
    return vdur


class TestNfviInterface(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.get_event_loop()

        self.account = RwcalYang.CloudAccount(
                name='test-cloud-account',
                account_type="mock",
                )

        # Define the VDUR to avoid division by zero
        self.vdur = make_vdur()
        self.vdur.vm_flavor.vcpu_count = 4
        self.vdur.vm_flavor.memory_mb = 100
        self.vdur.vm_flavor.storage_gb = 2
        self.vdur.vim_id = 'test-vim-id'

        self.plugin_manager = NfviMetricsPluginManager(logger)
        self.plugin_manager.register(self.account, "mock")

        self.metrics_manager = NfviInterface(
                self.loop,
                logger,
                self.plugin_manager,
                )

    def test_add_remove_vdur(self):
        """
        This test simply tests that a VDUR is correctly registered and
        unregistered from an NfviInterface.
        """
        # Register with the manager
        self.metrics_manager.register_vdur(self.account, self.vdur)
        self.assertIn(self.vdur.id, self.metrics_manager._metrics)

        # Unregister from the manager
        self.metrics_manager.unregister_vdur(self.vdur.id)
        self.assertNotIn(self.vdur.id, self.metrics_manager._metrics)


class TestVdurNfviMetrics(unittest.TestCase):
    def setUp(self):
        # Reduce the sample interval so that test run quickly
        VdurNfviMetrics.SAMPLE_INTERVAL = 0.1

        # Create a mock plugin to define the metrics retrieved. The plugin will
        # return a VCPU utilization of 0.5.
        class MockPlugin(object):
            def __init__(self):
                self.metrics = RwmonYang.NfviMetrics()

            def nfvi_metrics(self, account, vim_id):
                self.metrics.vcpu.utilization = 0.5
                return self.metrics

        self.loop = asyncio.get_event_loop()

        self.account = RwcalYang.CloudAccount(
                name='test-cloud-account',
                account_type="mock",
                )

        # Define the VDUR to avoid division by zero
        vdur = make_vdur()
        vdur.vm_flavor.vcpu_count = 4
        vdur.vm_flavor.memory_mb = 100
        vdur.vm_flavor.storage_gb = 2
        vdur.vim_id = 'test-vim-id'

        # Instantiate the mock plugin
        self.plugins = NfviMetricsPluginManager(logger)
        self.plugins.register(self.account, "mock")

        self.plugin = self.plugins.plugin(self.account.name)
        self.plugin.set_impl(MockPlugin())

        self.manager = NfviInterface(self.loop, logger, self.plugins)
        self.metrics = VdurNfviMetrics(
                self.manager,
                self.account,
                self.plugin,
                vdur,
                )

    def test_retrieval(self):
        metrics_a = None
        metrics_b = None

        # Define a coroutine that can be added to the asyncio event loop
        @asyncio.coroutine
        def update():
            # Output from the metrics calls with be written to these nonlocal
            # variables
            nonlocal metrics_a
            nonlocal metrics_b

            # This first call will return the current metrics values and
            # schedule a request to the NFVI to retrieve metrics from the data
            # source. All metrics will be zero at this point.
            metrics_a = self.metrics.retrieve()

            # Wait for the scheduled update to take effect
            yield from asyncio.sleep(0.2, loop=self.loop)

            # Retrieve the updated metrics
            metrics_b = self.metrics.retrieve()

        self.loop.run_until_complete(update())

        # Check that the metrics returned indicate that the plugin was queried
        # and returned the appropriate value, i.e. 0.5 utilization
        self.assertEqual(0.0, metrics_a.vcpu.utilization)
        self.assertEqual(0.5, metrics_b.vcpu.utilization)


class TestNfviMetricsPluginManager(unittest.TestCase):
    def setUp(self):
        self.plugins = NfviMetricsPluginManager(logger)
        self.account = RwcalYang.CloudAccount(
                name='test-cloud-account',
                account_type="mock",
                )

    def test_mock_plugin(self):
        # Register an account name with a mock plugin. If successful, the
        # plugin manager should return a non-None object.
        self.plugins.register(self.account, 'mock')
        self.assertIsNotNone(self.plugins.plugin(self.account.name))

        # Now unregister the cloud account
        self.plugins.unregister(self.account.name)

        # Trying to retrieve a plugin for a cloud account that has not been
        # registered with the manager is expected to raise an exception.
        with self.assertRaises(KeyError):
            self.plugins.plugin(self.account.name)

    def test_multiple_registration(self):
        self.plugins.register(self.account, 'mock')

        # Attempting to register the account with another type of plugin will
        # also cause an exception to be raised.
        with self.assertRaises(AccountAlreadyRegisteredError):
            self.plugins.register(self.account, 'mock')

        # Attempting to register the account with 'openstack' again with cause
        # an exception to be raised.
        with self.assertRaises(AccountAlreadyRegisteredError):
            self.plugins.register(self.account, 'openstack')

    def test_unsupported_plugin(self):
        # If an attempt is made to register a cloud account with an unknown
        # type of plugin, a PluginNotSupportedError should be raised.
        with self.assertRaises(PluginNotSupportedError):
            self.plugins.register(self.account, 'unsupported-plugin')

    def test_anavailable_plugin(self):
        # Create a factory that always raises PluginUnavailableError
        class UnavailablePluginFactory(PluginFactory):
            PLUGIN_NAME = "unavailable-plugin"

            def create(self, cloud_account):
                raise PluginUnavailableError()

        # Register the factory
        self.plugins.register_plugin_factory(UnavailablePluginFactory())

        # Ensure that the correct exception propagates when the cloud account
        # is registered.
        with self.assertRaises(PluginUnavailableError):
            self.plugins.register(self.account, "unavailable-plugin")


class TestMonitor(unittest.TestCase):
    """
    The Monitor class is the implementation that is called by the
    MonitorTasklet. It provides the unified interface for controlling and
    querying the monitoring functionality.
    """

    def setUp(self):
        # Reduce the sample interval so that test run quickly
        VdurNfviMetrics.SAMPLE_INTERVAL = 0.1

        self.loop = asyncio.get_event_loop()
        self.config = InstanceConfiguration()
        self.monitor = Monitor(self.loop, logger, self.config)

        self.account = RwcalYang.CloudAccount(
                name='test-cloud-account',
                account_type="mock",
                )

    def test_instance_config(self):
        """
        Configuration data for an instance is pass to the Monitor when it is
        created. The data is passed in the InstanceConfiguration object. This
        object is typically shared between the tasklet and the monitor, and
        provides a way for the tasklet to update the configuration of the
        monitor.
        """
        self.assertTrue(hasattr(self.monitor._config, "polling_period"))
        self.assertTrue(hasattr(self.monitor._config, "min_cache_lifetime"))
        self.assertTrue(hasattr(self.monitor._config, "max_polling_frequency"))

    def test_monitor_cloud_accounts(self):
        """
        This test checks the cloud accounts are correctly added and deleted,
        and that the correct exceptions are raised on duplicate adds or
        deletes.

        """
        # Add the cloud account to the monitor
        self.monitor.add_cloud_account(self.account)
        self.assertIn(self.account.name, self.monitor._cloud_accounts)

        # Add the cloud account to the monitor again
        with self.assertRaises(AccountAlreadyRegisteredError):
            self.monitor.add_cloud_account(self.account)

        # Delete the cloud account
        self.monitor.remove_cloud_account(self.account.name)
        self.assertNotIn(self.account.name, self.monitor._cloud_accounts)

        # Delete the cloud account again
        with self.assertRaises(UnknownAccountError):
            self.monitor.remove_cloud_account(self.account.name)

    def test_monitor_cloud_accounts_illegal_removal(self):
        """
        A cloud account may not be removed while there are plugins or records
        that are associated with it. Attempting to delete such a cloud account
        will raise an exception.
        """
        # Add the cloud account to the monitor
        self.monitor.add_cloud_account(self.account)

        # Create a VNFR associated with the cloud account
        vnfr = RwVnfrYang.YangData_Vnfr_VnfrCatalog_Vnfr()
        vnfr.cloud_account = self.account.name
        vnfr.id = 'test-vnfr-id'

        # Add a VDUR to the VNFR
        vdur = vnfr.vdur.add()
        vdur.vim_id = 'test-vim-id-1'
        vdur.id = 'test-vdur-id-1'

        # Now add the VNFR to the monitor
        self.monitor.add_vnfr(vnfr)

        # Check that the monitor contains the VNFR, VDUR, and metrics
        self.assertTrue(self.monitor.is_registered_vdur(vdur.id))
        self.assertTrue(self.monitor.is_registered_vnfr(vnfr.id))
        self.assertEqual(1, len(self.monitor.metrics))

        # Deleting the cloud account now should raise an exception because the
        # VNFR and VDUR are associated with the cloud account.
        with self.assertRaises(AccountInUseError):
            self.monitor.remove_cloud_account(self.account.name)

        # Now remove the VNFR from the monitor
        self.monitor.remove_vnfr(vnfr.id)
        self.assertFalse(self.monitor.is_registered_vdur(vdur.id))
        self.assertFalse(self.monitor.is_registered_vnfr(vnfr.id))
        self.assertEqual(0, len(self.monitor.metrics))

        # Safely delete the cloud account
        self.monitor.remove_cloud_account(self.account.name)

    def test_vdur_registration(self):
        """
        When a VDUR is registered with the Monitor it is registered with the
        VdurNfviMetricsManager. Thus it is assigned a plugin that can be used
        to retrieve the NFVI metrics associated with the VDU.
        """
        # Define the VDUR to be registered
        vdur = VnfrYang.YangData_Vnfr_VnfrCatalog_Vnfr_Vdur()
        vdur.vm_flavor.vcpu_count = 4
        vdur.vm_flavor.memory_mb = 100
        vdur.vm_flavor.storage_gb = 2
        vdur.vim_id = 'test-vim-id'
        vdur.id = 'test-vdur-id'

        # Before registering the VDUR, the cloud account needs to be added to
        # the monitor.
        self.monitor.add_cloud_account(self.account)

        # Register the VDUR with the monitor
        self.monitor.add_vdur(self.account, vdur)
        self.assertTrue(self.monitor.is_registered_vdur(vdur.id))

        # Unregister the VDUR
        self.monitor.remove_vdur(vdur.id)
        self.assertFalse(self.monitor.is_registered_vdur(vdur.id))

    def test_vnfr_add_update_delete(self):
        """
        When a VNFR is added to the Monitor a record is created of the
        relationship between the VNFR and any VDURs that it contains. Each VDUR
        is then registered with the VdurNfviMetricsManager. A VNFR can also be
        updated so that it contains more of less VDURs. Any VDURs that are
        added to the VNFR are registered with the NdurNfviMetricsManager, and
        any that are removed are unregistered. When a VNFR is deleted, all of
        the VDURs contained in the VNFR are unregistered.
        """
        # Define the VDUR to be registered
        vdur = RwVnfrYang.YangData_Vnfr_VnfrCatalog_Vnfr_Vdur()
        vdur.vim_id = 'test-vim-id-1'
        vdur.id = 'test-vdur-id-1'

        vnfr = RwVnfrYang.YangData_Vnfr_VnfrCatalog_Vnfr()
        vnfr.cloud_account = self.account.name
        vnfr.id = 'test-vnfr-id'

        vnfr.vdur.append(vdur)

        self.monitor.add_cloud_account(self.account)

        # Add the VNFR to the monitor. This will also register VDURs contained
        # in the VNFR with the monitor.
        self.monitor.add_vnfr(vnfr)
        self.assertTrue(self.monitor.is_registered_vdur('test-vdur-id-1'))

        # Add another VDUR to the VNFR and update the monitor. Both VDURs
        # should now be registered
        vdur = RwVnfrYang.YangData_Vnfr_VnfrCatalog_Vnfr_Vdur()
        vdur.vim_id = 'test-vim-id-2'
        vdur.id = 'test-vdur-id-2'

        vnfr.vdur.append(vdur)

        self.monitor.update_vnfr(vnfr)
        self.assertTrue(self.monitor.is_registered_vdur('test-vdur-id-1'))
        self.assertTrue(self.monitor.is_registered_vdur('test-vdur-id-2'))

        # Delete the VNFR from the monitor. This should remove the VNFR and all
        # of the associated VDURs from the monitor.
        self.monitor.remove_vnfr(vnfr.id)
        self.assertFalse(self.monitor.is_registered_vnfr('test-vnfr-id'))
        self.assertFalse(self.monitor.is_registered_vdur('test-vdur-id-1'))
        self.assertFalse(self.monitor.is_registered_vdur('test-vdur-id-2'))

        with self.assertRaises(KeyError):
            self.monitor.retrieve_nfvi_metrics('test-vdur-id-1')

        with self.assertRaises(KeyError):
            self.monitor.retrieve_nfvi_metrics('test-vdur-id-2')

    def test_complete(self):
        """
        This test simulates the addition of a VNFR to the Monitor (along with
        updates), and retrieves NFVI metrics from the VDUR. The VNFR is then
        deleted, which should result in a cleanup of all the data in the
        Monitor.
        """
        # Create the VNFR
        vnfr = RwVnfrYang.YangData_Vnfr_VnfrCatalog_Vnfr()
        vnfr.cloud_account = self.account.name
        vnfr.id = 'test-vnfr-id'

        # Create 2 VDURs
        vdur = vnfr.vdur.add()
        vdur.id = 'test-vdur-id-1'
        vdur.vim_id = 'test-vim-id-1'
        vdur.vm_flavor.vcpu_count = 4
        vdur.vm_flavor.memory_mb = 100
        vdur.vm_flavor.storage_gb = 2

        vdur = vnfr.vdur.add()
        vdur.id = 'test-vdur-id-2'
        vdur.vim_id = 'test-vim-id-2'
        vdur.vm_flavor.vcpu_count = 4
        vdur.vm_flavor.memory_mb = 100
        vdur.vm_flavor.storage_gb = 2

        class MockPlugin(object):
            def __init__(self):
                self._metrics = dict()
                self._metrics['test-vim-id-1'] = RwmonYang.NfviMetrics()
                self._metrics['test-vim-id-2'] = RwmonYang.NfviMetrics()

            def nfvi_metrics(self, account, vim_id):
                metrics = self._metrics[vim_id]

                if vim_id == 'test-vim-id-1':
                    metrics.memory.used += 1000
                else:
                    metrics.memory.used += 2000

                return metrics

        class MockFactory(PluginFactory):
            PLUGIN_NAME = "mock"

            def create(self, cloud_account):
                plugin = rw_peas.PeasPlugin("rwmon_mock", 'RwMon-1.0')
                impl = plugin.get_interface("Monitoring")
                impl.set_impl(MockPlugin())
                return impl

        # Modify the mock plugin factory
        self.monitor._nfvi_plugins._factories["mock"] = MockFactory()

        # Add the cloud account the monitor
        self.monitor.add_cloud_account(self.account)

        # Add the VNFR to the monitor.
        self.monitor.add_vnfr(vnfr)

        @asyncio.coroutine
        def process():
            # call #1 (time = 0.00s)
            # The metrics for these VDURs have not been populated yet so a
            # default metrics object (all zeros) is returned, and a request is
            # scheduled with the data source to retrieve the metrics.
            metrics1 = self.monitor.retrieve_nfvi_metrics('test-vdur-id-1')
            metrics2 = self.monitor.retrieve_nfvi_metrics('test-vdur-id-2')

            self.assertEqual(0, metrics1.memory.used)
            self.assertEqual(0, metrics2.memory.used)

            yield from asyncio.sleep(0.05, loop=self.loop)

            # call #2 (time = 0.05s)
            # The metrics have been populated with data from the data source
            # due to the request made during call #1.
            metrics1 = self.monitor.retrieve_nfvi_metrics('test-vdur-id-1')
            metrics2 = self.monitor.retrieve_nfvi_metrics('test-vdur-id-2')

            self.assertEqual(1000, metrics1.memory.used)
            self.assertEqual(2000, metrics2.memory.used)

            yield from asyncio.sleep(0.45, loop=self.loop)

            # call #3 (time = 0.50s)
            # This call exceeds 0.1s (the sample interval of the plugin)
            # from when the data was retrieved. The cached metrics are
            # immediately returned, but a request is made to the data source to
            # refresh these metrics.
            metrics1 = self.monitor.retrieve_nfvi_metrics('test-vdur-id-1')
            metrics2 = self.monitor.retrieve_nfvi_metrics('test-vdur-id-2')

            self.assertEqual(1000, metrics1.memory.used)
            self.assertEqual(2000, metrics2.memory.used)

            yield from asyncio.sleep(0.5, loop=self.loop)

            # call #4 (time = 1.00s)
            # The metrics retrieved differ from those in call #3 because the
            # cached metrics have been updated.
            metrics1 = self.monitor.retrieve_nfvi_metrics('test-vdur-id-1')
            metrics2 = self.monitor.retrieve_nfvi_metrics('test-vdur-id-2')

            self.assertEqual(2000, metrics1.memory.used)
            self.assertEqual(4000, metrics2.memory.used)

        @asyncio.coroutine
        def timeout(coro, duration):
            yield from asyncio.wait_for(coro, timeout=duration)

        self.loop.run_until_complete(timeout(process(), 2))


def main(argv=sys.argv[1:]):
    logging.basicConfig(format='TEST %(message)s')

    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--verbose', action='store_true')

    args = parser.parse_args(argv)

    # Set the global logging level
    logging.getLogger().setLevel(logging.DEBUG if args.verbose else logging.ERROR)

    # Set the logger in this test to use a null handler
    logger.addHandler(logging.NullHandler())

    # The unittest framework requires a program name, so use the name of this
    # file instead (we do not want to have to pass a fake program name to main
    # when this is called from the interpreter).
    unittest.main(argv=[__file__] + argv,
            testRunner=xmlrunner.XMLTestRunner(
                output=os.environ["RIFT_MODULE_TEST"]))

if __name__ == '__main__':
    main()
