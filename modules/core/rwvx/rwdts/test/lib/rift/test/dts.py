
# 
# (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
#

import abc
import asyncio
import functools
import logging
import os
import socket
import sys
import types
import unittest

import gi
gi.require_version('CF', '1.0')
gi.require_version('RwMain', '1.0')
gi.require_version('RwManifestYang', '1.0')
gi.require_version('RwDtsToyTaskletYang', '1.0')
gi.require_version('RwcalYang', '1.0')
gi.require_version('RwVcsYang', '1.0')
gi.require_version('RwYang', '1.0')

import gi.repository.CF as cf
import gi.repository.RwMain as rwmain
import gi.repository.RwManifestYang as rwmanifest
import gi.repository.RwDtsToyTaskletYang as toyyang
import gi.repository.RwVcsYang as RwVcsYang 
import gi.repository.RwYang as RwYang 


import rift.tasklets


if sys.version_info < (3, 4, 4):
    asyncio.ensure_future = asyncio.async


class AbstractDTSTest(unittest.TestCase):
    """Provides the base components for setting up DTS related unit tests.

    The class provides 3 hooks for subclasses:
    1. configure_suite(Optional): Similar to setUpClass, configs
            related to entire suite goes here
    2. configure_test(Optional): Similar to setUp
    3. configure_schema(Mandatory): Schema of the yang module.
    4. configure_timeout(Optional): timeout for each test case, defaults to 5


    Note:  Each tests uses a list of asyncio.Events for staging through the
    test.  These are required here because we are bring up each coroutine
    ("tasklet") at the same time and are not implementing any re-try
    mechanisms.  For instance, this is used in numerous tests to make sure that
    a publisher is up and ready before the subscriber sends queries.  Such
    event lists should not be used in production software.
    """
    rwmain = None
    tinfo = None
    schema = None
    id_cnt = 0
    default_timeout = 0
    top_dir = __file__[:__file__.find('/modules/core/')]
    log_level = logging.WARN

    @classmethod
    def setUpClass(cls):
        """
        1. create a rwmain
        2. Add DTS Router and Broker tasklets. Sets a random port for the broker
        3. Triggers the configure_suite and configure_schema hooks.
        """
        sock = socket.socket()
        # Get an available port from OS and pass it on to broker.
        sock.bind(('', 0))
        port = sock.getsockname()[1]
        sock.close()
        rwmsg_broker_port = port
        os.environ['RWMSG_BROKER_PORT'] = str(rwmsg_broker_port)

        build_dir = os.path.join(cls.top_dir, '.build/modules/core/rwvx/src/core_rwvx-build')

        if 'MESSAGE_BROKER_DIR' not in os.environ:
            os.environ['MESSAGE_BROKER_DIR'] = os.path.join(build_dir, 'rwmsg/plugins/rwmsgbroker-c')

        if 'ROUTER_DIR' not in os.environ:
            os.environ['ROUTER_DIR'] = os.path.join(build_dir, 'rwdts/plugins/rwdtsrouter-c')

        msgbroker_dir = os.environ.get('MESSAGE_BROKER_DIR')
        router_dir = os.environ.get('ROUTER_DIR')

        manifest = rwmanifest.Manifest()
        manifest.init_phase.settings.rwdtsrouter.single_dtsrouter.enable = True

        cls.rwmain = rwmain.Gi.new(manifest)
        cls.tinfo = cls.rwmain.get_tasklet_info()

        # Run router in mainq. Eliminates some ill-diagnosed bootstrap races.
        os.environ['RWDTS_ROUTER_MAINQ'] = '1'
        cls.rwmain.add_tasklet(msgbroker_dir, 'rwmsgbroker-c')
        cls.rwmain.add_tasklet(router_dir, 'rwdtsrouter-c')

        cls.log = rift.tasklets.logger_from_tasklet_info(cls.tinfo)
        cls.log.setLevel(logging.DEBUG)

        fmt = logging.Formatter(
                '%(asctime)-23s %(levelname)-5s  (%(name)s@%(process)d:%(filename)s:%(lineno)d) - %(message)s')
        stderr_handler = logging.StreamHandler(stream=sys.stderr)
        stderr_handler.setFormatter(fmt)
        stderr_handler.setLevel(cls.log_level)
        logging.getLogger().addHandler(stderr_handler)

        cls.schema = cls.configure_schema()
        cls.default_timeout = cls.configure_timeout()
        cls.configure_suite(cls.rwmain)

        os.environ["PYTHONASYNCIODEBUG"] = "1"

    @abc.abstractclassmethod
    def configure_schema(cls):
        """
        Returns:
            yang schema.
        """
        raise NotImplementedError("configure_schema needs to be implemented")

    @classmethod
    def configure_timeout(cls):
        """
        Returns:
            Time limit for each test case, in seconds.
        """
        return 5

    @classmethod
    def configure_suite(cls, rwmain):
        """
        Args:
            rwmain (RwMain): Newly create rwmain instace, can be used to add
                    additional tasklets.
        """
        pass

    def setUp(self):
        """
        1. Creates an asyncio loop
        2. Triggers the hook configure_test
        """
        def scheduler_tick(self, *args):
            self.call_soon(self.stop)
            self.run_forever()

        # Init params: loop & timers
        self.loop = asyncio.new_event_loop()
        self.loop.set_debug(True)
        asyncio_logger = logging.getLogger("asyncio")
        asyncio_logger.setLevel(logging.DEBUG)

        self.loop.scheduler_tick = types.MethodType(scheduler_tick, self.loop)

        self.asyncio_timer = None
        self.stop_timer = None
        self.__class__.id_cnt += 1

        self.configure_test(self.loop, self.__class__.id_cnt)

    def configure_test(self, loop, test_id):
        """
        Args:
            loop (asyncio.BaseEventLoop): Newly created asyncio event loop.
            test_id (int): Id for tests.
        """
        pass

    def run_until(self, test_done, timeout=None):
        """
        Attach the current asyncio event loop to rwsched and then run the
        scheduler until the test_done function returns True or timeout seconds
        pass.

        Args:
            test_done (function): function which should return True once the test is
                    complete and the scheduler no longer needs to run.
            timeout (int, optional): maximum number of seconds to run the test.
        """
        timeout = timeout or self.__class__.default_timeout
        tinfo = self.__class__.tinfo

        def shutdown(*args):
            if args:
                self.log.debug('Shutting down loop due to timeout')

            if self.asyncio_timer is not None:
                tinfo.rwsched_tasklet.CFRunLoopTimerRelease(self.asyncio_timer)
                self.asyncio_timer = None

            if self.stop_timer is not None:
                tinfo.rwsched_tasklet.CFRunLoopTimerRelease(self.stop_timer)
                self.stop_timer = None

            tinfo.rwsched_instance.CFRunLoopStop()

        def tick(*args):
            self.loop.call_later(0.1, self.loop.stop)

            try:
                self.loop.run_forever()
            except KeyboardInterrupt:
                self.log.debug("Shutting down loop dur to keyboard interrupt")
                shutdown()

            if test_done():
                shutdown()

        self.asyncio_timer = tinfo.rwsched_tasklet.CFRunLoopTimer(
            cf.CFAbsoluteTimeGetCurrent(),
            0.1,
            tick,
            None)

        self.stop_timer = tinfo.rwsched_tasklet.CFRunLoopTimer(
            cf.CFAbsoluteTimeGetCurrent() + timeout,
            0,
            shutdown,
            None)

        tinfo.rwsched_tasklet.CFRunLoopAddTimer(
            tinfo.rwsched_tasklet.CFRunLoopGetCurrent(),
            self.stop_timer,
            tinfo.rwsched_instance.CFRunLoopGetMainMode())

        tinfo.rwsched_tasklet.CFRunLoopAddTimer(
            tinfo.rwsched_tasklet.CFRunLoopGetCurrent(),
            self.asyncio_timer,
            tinfo.rwsched_instance.CFRunLoopGetMainMode())

        tinfo.rwsched_instance.CFRunLoopRun()

        self.assertTrue(test_done())

    def new_tinfo(self, name):
        """
        Create a new tasklet info instance with a unique instance_id per test.
        It is up to each test to use unique names if more that one tasklet info
        instance is needed.

        @param name - name of the "tasklet"
        @return     - new tasklet info instance
        """
        # Accessing using class for consistency.
        ret = self.__class__.rwmain.new_tasklet_info(
                name,
                self.__class__.id_cnt)

        log = rift.tasklets.logger_from_tasklet_info(ret)
        log.setLevel(logging.DEBUG)

        stderr_handler = logging.StreamHandler(stream=sys.stderr)
        fmt = logging.Formatter(
                '%(asctime)-23s %(levelname)-5s  (%(name)s@%(process)d:%(filename)s:%(lineno)d) - %(message)s')
        stderr_handler.setFormatter(fmt)
        log.addHandler(stderr_handler)

        return ret


def async_test(f):
    """
    Runs the testcase within a coroutine using the current test cases loop.
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        self = args[0]
        if not hasattr(self, "loop"):
            raise ValueError("Could not find loop attribute in first param")

        coro = asyncio.coroutine(f)
        future = coro(*args, **kwargs)
        task = asyncio.ensure_future(future, loop=self.loop)

        self.run_until(task.done)
        if task.exception() is not None:
            self.log.error("Caught exception during test: %s", str(task.exception()))
            raise task.exception()

    return wrapper



class DTSRecoveryTest(unittest.TestCase):
    """Provides the base components for setting up DTS related unit tests.

    The class provides 3 hooks for subclasses:
    1. configure_suite(Optional): Similar to setUpClass, configs
            related to entire suite goes here
    2. configure_test(Optional): Similar to setUp
    3. configure_schema(Mandatory): Schema of the yang module.
    4. configure_timeout(Optional): timeout for each test case, defaults to 5


    Note:  Each tests uses a list of asyncio.Events for staging through the
    test.  These are required here because we are bring up each coroutine
    ("tasklet") at the same time and are not implementing any re-try
    mechanisms.  For instance, this is used in numerous tests to make sure that
    a publisher is up and ready before the subscriber sends queries.  Such
    event lists should not be used in production software.
    """
    rwmain = None
    tinfo = None
    schema = None
    id_cnt = 0
    default_timeout = 0
    top_dir = __file__[:__file__.find('/modules/core/')]
    log_level = logging.WARN

    @classmethod
    def configure_manifest(cls):
        manifest = rwmanifest.Manifest()
        manifest.bootstrap_phase = rwmanifest.BootstrapPhase.from_dict({
            'rwtrace' : {
                'enable' : 'TRUE',
                'level' : 5
            },
            'rwtasklet' : {
                'plugin_name' : 'rwinit-c',
            },
            'zookeeper' : {
                'master_ip' : '127.0.0.1' ,
                'unique_ports' : 'FALSE',
                'zake' : 'TRUE'
            },
            'rwvm' : {
                'instances' : [{
                    'component_name' : 'msgbroker'
                },
                {
                    'component_name' : 'dtsrouter'
                }]
            }
        })
        manifest.init_phase = rwmanifest.InitPhase.from_dict({
            'environment' : {
                'python_variable' : [
                    "rw_component_name = 'rwdtsperf-c-vm'",
                    "component_type = 'rwvm'",
                    "instance_id = 729"
                ],
                'component_name' : '$python(rw_component_name)',
                'component_type' : '$python(component_type)',
                'instance_id' : '$python(instance_id)'
            },
            'settings' : {
                'rwmsg' : {
                    'multi_broker' : {
                        'enable' : 'TRUE'
                    }
                },
                'rwdtsrouter' : {
                    'multi_dtsrouter' : {
                        'enable' : 'TRUE'
                    }
                },
                'rwvcs' : {
                    'collapse_each_rwvm' : 'TRUE',
                    'collapse_each_rwprocess' : 'TRUE'
                }
            }
        })
        manifest.inventory = rwmanifest.Inventory.from_dict({
           'component' : [{
              'component_name': 'rwdtsperf-c-collection',
              'component_type': 'RWCOLLECTION',
              'rwcollection': {
                  'collection_type' : 'rwcolony',
                  'event_list' : {
                      'event' : [{
                          'name' : 'onentry',
                          'action' : [{
                              'name' : 'Start rwdtsperf-c-vm',
                              'start' : {
                                  'python_variable' : [ "vm_ip_address = '127.0.0.1'" ],
                                  'component_name' : 'rwdtsperf-c-vm',
                                  'instance_id' : '729'
                              }
                          }]
                      }]
                  }
              }
           },
           {
              'component_name': 'rwdtsperf-c-vm',
              'component_type': 'RWVM',
              'rwvm': {
                  'leader' : 'TRUE',
                  'event_list' : {
                      'event' : [{
                          'name' : 'onentry',
                          'action' : [{
                              'name' : 'Start rwdtsperf-c-collection',
                              'start' : {
                                  'component_name' : 'rwdtsperf-c-collection'
                              }
                          }]
                      }]
                  }
              }
           },
           {
              'component_name': 'msgbroker',
              'component_type': 'RWTASKLET',
              'rwtasklet': {
                  'plugin_directory': 'rwmsgbroker-c',
                  'plugin_name': 'rwmsgbroker-c'
              }
           },
           {
              'component_name': 'dtsrouter',
              'component_type': 'RWTASKLET',
              'rwtasklet': {
                  'plugin_directory': 'rwdtsrouter-c',
                  'plugin_name': 'rwdtsrouter-c'
              }
           }]
        })
        return manifest

    @classmethod
    def setUpClass(cls):
        """
        1. create a rwmain
        2. Add DTS Router and Broker tasklets. Sets a random port for the broker
        3. Triggers the configure_suite and configure_schema hooks.
        """
        sock = socket.socket()
        # Get an available port from OS and pass it on to broker.
        sock.bind(('', 0))
        port = sock.getsockname()[1]
        sock.close()
        rwmsg_broker_port = port
        os.environ['RWMSG_BROKER_PORT'] = str(rwmsg_broker_port)

        build_dir = os.path.join(cls.top_dir, '.build/modules/core/rwvx/src/core_rwvx-build')

        if 'MESSAGE_BROKER_DIR' not in os.environ:
            os.environ['MESSAGE_BROKER_DIR'] = os.path.join(build_dir, 'rwmsg/plugins/rwmsgbroker-c')

        if 'ROUTER_DIR' not in os.environ:
            os.environ['ROUTER_DIR'] = os.path.join(build_dir, 'rwdts/plugins/rwdtsrouter-c')

        if 'TEST_ENVIRON' not in os.environ:
            os.environ['TEST_ENVIRON'] = '1'

        msgbroker_dir = os.environ.get('MESSAGE_BROKER_DIR')
        router_dir = os.environ.get('ROUTER_DIR')
        cls.manifest = cls.configure_manifest()
        # Run router in mainq. Eliminates some ill-diagnosed bootstrap races.
        os.environ['RWDTS_ROUTER_MAINQ'] = '1'

        cls.rwmain = rwmain.Gi.new(cls.manifest)
        cls.tinfo = cls.rwmain.get_tasklet_info()

        # Run router in mainq. Eliminates some ill-diagnosed bootstrap races.
        #cls.rwmain.add_tasklet(msgbroker_dir, 'rwmsgbroker-c')
        #cls.rwmain.add_tasklet(router_dir, 'rwdtsrouter-c')

        cls.log = rift.tasklets.logger_from_tasklet_info(cls.tinfo)
        cls.log.setLevel(logging.DEBUG)

        fmt = logging.Formatter(
                '%(asctime)-23s %(levelname)-5s  (%(name)s@%(process)d:%(filename)s:%(lineno)d) - %(message)s')
        stderr_handler = logging.StreamHandler(stream=sys.stderr)
        stderr_handler.setFormatter(fmt)
        stderr_handler.setLevel(cls.log_level)
        logging.getLogger().addHandler(stderr_handler)

        cls.schema = cls.configure_schema()
        cls.default_timeout = cls.configure_timeout()
        cls.configure_suite(cls.rwmain)

        os.environ["PYTHONASYNCIODEBUG"] = "1"

    @abc.abstractclassmethod
    def configure_schema(cls):
        """
        Returns:
            yang schema.
        """
        raise NotImplementedError("configure_schema needs to be implemented")

    @classmethod
    def configure_timeout(cls):
        """
        Returns:
            Time limit for each test case, in seconds.
        """
        return 5

    @classmethod
    def configure_suite(cls, rwmain):
        """
        Args:
            rwmain (RwMain): Newly create rwmain instace, can be used to add
                    additional tasklets.
        """
        pass

    def setUp(self):
        """
        1. Creates an asyncio loop
        2. Triggers the hook configure_test
        """
        def scheduler_tick(self, *args):
            self.call_soon(self.stop)
            self.run_forever()

        # Init params: loop & timers
        self.loop = asyncio.new_event_loop()
        self.loop.set_debug(True)
        asyncio_logger = logging.getLogger("asyncio")
        asyncio_logger.setLevel(logging.DEBUG)

        self.loop.scheduler_tick = types.MethodType(scheduler_tick, self.loop)

        self.asyncio_timer = None
        self.stop_timer = None
        self.__class__.id_cnt += 1

        self.configure_test(self.loop, self.__class__.id_cnt)

    def configure_test(self, loop, test_id):
        """
        Args:
            loop (asyncio.BaseEventLoop): Newly created asyncio event loop.
            test_id (int): Id for tests.
        """
        pass

    def run_until(self, test_done, timeout=None):
        """
        Attach the current asyncio event loop to rwsched and then run the
        scheduler until the test_done function returns True or timeout seconds
        pass.

        Args:
            test_done (function): function which should return True once the test is
                    complete and the scheduler no longer needs to run.
            timeout (int, optional): maximum number of seconds to run the test.
        """
        timeout = timeout or self.__class__.default_timeout
        tinfo = self.__class__.tinfo

        def shutdown(*args):
            if args:
                self.log.debug('Shutting down loop due to timeout')

            if self.asyncio_timer is not None:
                tinfo.rwsched_tasklet.CFRunLoopTimerRelease(self.asyncio_timer)
                self.asyncio_timer = None

            if self.stop_timer is not None:
                tinfo.rwsched_tasklet.CFRunLoopTimerRelease(self.stop_timer)
                self.stop_timer = None

            tinfo.rwsched_instance.CFRunLoopStop()

        def tick(*args):
            self.loop.call_later(0.1, self.loop.stop)

            try:
                self.loop.run_forever()
            except KeyboardInterrupt:
                self.log.debug("Shutting down loop dur to keyboard interrupt")
                shutdown()

            if test_done():
                shutdown()

        self.asyncio_timer = tinfo.rwsched_tasklet.CFRunLoopTimer(
            cf.CFAbsoluteTimeGetCurrent(),
            0.1,
            tick,
            None)

        self.stop_timer = tinfo.rwsched_tasklet.CFRunLoopTimer(
            cf.CFAbsoluteTimeGetCurrent() + timeout,
            0,
            shutdown,
            None)

        tinfo.rwsched_tasklet.CFRunLoopAddTimer(
            tinfo.rwsched_tasklet.CFRunLoopGetCurrent(),
            self.stop_timer,
            tinfo.rwsched_instance.CFRunLoopGetMainMode())

        tinfo.rwsched_tasklet.CFRunLoopAddTimer(
            tinfo.rwsched_tasklet.CFRunLoopGetCurrent(),
            self.asyncio_timer,
            tinfo.rwsched_instance.CFRunLoopGetMainMode())

        tinfo.rwsched_instance.CFRunLoopRun()

        self.assertTrue(test_done())

    def new_tinfo(self, name):
        """
        Create a new tasklet info instance with a unique instance_id per test.
        It is up to each test to use unique names if more that one tasklet info
        instance is needed.

        @param name - name of the "tasklet"
        @return     - new tasklet info instance
        """
        # Accessing using class for consistency.
        ret = self.__class__.rwmain.new_tasklet_info(
                name,
                self.__class__.id_cnt)

        log = rift.tasklets.logger_from_tasklet_info(ret)
        log.setLevel(logging.DEBUG)

        stderr_handler = logging.StreamHandler(stream=sys.stderr)
        fmt = logging.Formatter(
                '%(asctime)-23s %(levelname)-5s  (%(name)s@%(process)d:%(filename)s:%(lineno)d) - %(message)s')
        stderr_handler.setFormatter(fmt)
        log.addHandler(stderr_handler)

        return ret


def async_test(f):
    """
    Runs the testcase within a coroutine using the current test cases loop.
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        self = args[0]
        if not hasattr(self, "loop"):
            raise ValueError("Could not find loop attribute in first param")

        coro = asyncio.coroutine(f)
        future = coro(*args, **kwargs)
        task = asyncio.ensure_future(future, loop=self.loop)

        self.run_until(task.done)
        if task.exception() is not None:
            self.log.error("Caught exception during test: %s", str(task.exception()))
            raise task.exception()

    return wrapper


class DtsPerf(DTSRecoveryTest):
    """
    DTS GI interface unittests

    Note:  Each tests uses a list of asyncio.Events for staging through the
    test.  These are required here because we are bring up each coroutine
    ("tasklet") at the same time and are not implementing any re-try
    mechanisms.  For instance, this is used in numerous tests to make sure that
    a publisher is up and ready before the subscriber sends queries.  Such
    event lists should not be used in production software.
    """
    @classmethod
    def configure_schema(cls):
        return toyyang.get_schema()

    @classmethod
    def configure_manifest(cls):
        manifest = rwmanifest.Manifest()
        manifest.bootstrap_phase = rwmanifest.BootstrapPhase.from_dict({
            'rwtrace' : {
                'enable' : 'TRUE',
                'level' : 2
            },
            'log' : {
                 'enable' : 'TRUE',
                 'severity' : 2,
                 'console_severity' : 2
            },
            'rwbaseschema' : {
                'northbound_listing' : 'cli_rwfpath_schema_listing.txt'
            },
            'rwtasklet' : {
                'plugin_name' : 'rwinit-c',
            },
            'zookeeper' : {
                'master_ip' : '127.0.0.1' ,
                'unique_ports' : 'FALSE',
                'zake' : 'TRUE'
            },
            'rwvm' : {
                'instances' : [{
                    'component_name' : 'msgbroker',
                    'config_ready' : 'TRUE'
                },
                {
                    'component_name' : 'dtsrouter',
                    'config_ready' : 'TRUE'
                }]
            }
        })
        manifest.init_phase = rwmanifest.InitPhase.from_dict({
            'environment' : {
                'python_variable' : [
                    "rw_component_name = 'rwdtsperf-c-vm'",
                    "component_type = 'rwvm'",
                    "instance_id = 729"
                ],
                'component_name' : '$python(rw_component_name)',
                'component_type' : '$python(component_type)',
                'instance_id' : '$python(instance_id)'
            },
            'settings' : {
                'rwmsg' : {
                    'multi_broker' : {
                        'enable' : 'TRUE'
                    }
                },
                'rwdtsrouter' : {
                    'multi_dtsrouter' : {
                        'enable' : 'TRUE'
                    }
                },
                'rwvcs' : {
                    'collapse_each_rwvm' : 'TRUE',
                    'collapse_each_rwprocess' : 'TRUE'
                }
            }
        })
        manifest.inventory = rwmanifest.Inventory.from_dict({
           'component' : [{
              'component_name': 'rwdtsperf-c-collection',
              'component_type': 'RWCOLLECTION',
              'rwcollection': {
                  'collection_type' : 'rwcolony',
                  'event_list' : {
                      'event' : [{
                          'name' : 'onentry',
                          'action' : [{
                              'name' : 'Start rwdtsperf-c-vm',
                              'start' : {
                                  'python_variable' : [ "vm_ip_address = '127.0.0.1'" ],
                                  'component_name' : 'rwdtsperf-c-vm',
                                  'instance_id' : '729',
                                  'config_ready' : 'TRUE'
                              }
                          }]
                      }]
                  }
              }
           },
           {
              'component_name': 'rwdtsperf-c-vm',
              'component_type': 'RWVM',
              'rwvm': {
                  'leader' : 'TRUE',
                  'event_list' : {
                      'event' : [{
                          'name' : 'onentry',
                          'action' : [{
                              'name' : 'Start rwdtsperf-c-collection',
                              'start' : {
                                  'component_name' : 'rwdtsperf-c-collection',
                                  'config_ready' : 'TRUE'
                              }
                          }]
                      }]
                  }
              }
           },
           {
              'component_name': 'rwdtsperf-c-proc',
              'component_type': 'RWPROC',
              'rwproc': {
                  'tasklet': [{
                      'name': 'Start rwdtsperf-c',
                      'component_name': 'rwdtsperf-c',
                      'config_ready' : 'TRUE'
                  }]
              }
           },
           {
              'component_name': 'rwdtsperf-c-proc-restart',
              'component_type': 'RWPROC',
              'rwproc': {
                  'tasklet': [{
                      'name': 'Start rwdtsperf-c',
                      'component_name': 'rwdtsperf-c',
                      'recovery_action' : 'RESTART'
                  }]
              }
           },
           {
              'component_name': 'RW.Proc_1.uAgent',
              'component_type': 'RWPROC',
              'rwproc': {
                  'tasklet': [{
                      'python_variable' : [ "cmdargs_str = '--confd_ws confd_persist_grunt1-vm4.novalocal --confd-proto AF_INET --confd-ip 127.0.0.1'" ],
                      'name': 'Start RW.uAgent for RW.Proc_1.uAgent',
                      'component_name': 'RW.uAgent',
                      'config_ready' : 'TRUE'
                  }]
              }
           },
           {
              'component_name': 'rwdtsperf-c',
              'component_type': 'RWTASKLET',
              'rwtasklet': {
                  'plugin_directory': 'rwdtsperf-c',
                  'plugin_name': 'rwdtsperf-c'
              }
           },
           {
              'component_name': 'RW.uAgent',
              'component_type': 'RWTASKLET',
              'rwtasklet': {
                  'plugin_directory': 'rwuagent-c',
                  'plugin_name': 'rwuagent-c'
              }
           },
           {
              'component_name': 'msgbroker',
              'component_type': 'RWTASKLET',
              'rwtasklet': {
                  'plugin_directory': 'rwmsgbroker-c',
                  'plugin_name': 'rwmsgbroker-c'
              }
           },
           {
              'component_name': 'logd',
              'component_type': 'RWTASKLET',
              'rwtasklet': {
                  'plugin_directory': 'rwlogd-c',
                  'plugin_name': 'rwlogd-c'
              }
           },
           {
              'component_name': 'dtsrouter',
              'component_type': 'RWTASKLET',
              'rwtasklet': {
                  'plugin_directory': 'rwdtsrouter-c',
                  'plugin_name': 'rwdtsrouter-c'
              }
           }]
        })
        return manifest

    def tearDown(self):
        self.loop.stop()
        self.loop.close()


class Trafgen(DTSRecoveryTest):
    """
    DTS GI interface unittests

    Note:  Each tests uses a list of asyncio.Events for staging through the
    test.  These are required here because we are bring up each coroutine
    ("tasklet") at the same time and are not implementing any re-try
    mechanisms.  For instance, this is used in numerous tests to make sure that
    a publisher is up and ready before the subscriber sends queries.  Such
    event lists should not be used in production software.
    """
    @classmethod
    def configure_schema(cls):
        schema = RwYang.Model.load_and_merge_schema(
                     RwVcsYang.get_schema(),
                     'librwcal_yang_gen.so', 
                     'Rwcal')
        return schema


    @classmethod
    def configure_manifest(cls):
        manifest = rwmanifest.Manifest()
        manifest.bootstrap_phase = rwmanifest.BootstrapPhase.from_dict({
            'rwtrace' : {
                'enable' : 'TRUE',
                'level' : 5
            },
            'log' : {
                 'enable' : 'TRUE',
                 'severity' : 5,
                 'console_severity' : 5
            },
            'rwbaseschema' : {
                'northbound_listing' : 'cli_rwfpath_schema_listing.txt'
            },
            'rwtasklet' : {
                'plugin_name' : 'rwinit-c',
            },
            'zookeeper' : {
                'master_ip' : '127.0.0.1' ,
                'unique_ports' : 'FALSE',
                'zake' : 'TRUE'
            },
            'rwvm' : {
                'instances' : [{
                    'component_name' : 'msgbroker',
                    'config_ready' : 'TRUE'
                },
                {
                    'component_name' : 'dtsrouter',
                    'config_ready' : 'TRUE'
                }]
            },
            'serf': {
                'start': 'TRUE'
            },
#           'rwsecurity': {
#               'use_ssl': 'TRUE',
#               'cert': '/net/mahi/localdisk/kelayath/ws/rift/etc/ssl/current.cert',
#               'key': '/net/mahi/localdisk/kelayath/ws/rift/etc/ssl/current.key'
#           }
        })
        manifest.init_phase = rwmanifest.InitPhase.from_dict({
            'environment' : {
                'python_variable' : [
                    "rw_component_name = 'RW_VM_MASTER'",
                    "component_type = 'rwvm'",
                    "instance_id = 9"
                ],
                'component_name' : '$python(rw_component_name)',
                'component_type' : '$python(component_type)',
                'instance_id' : '$python(instance_id)'
            },
            'settings' : {
                'rwmsg' : {
                    'multi_broker' : {
                        'enable' : 'TRUE'
                    }
                },
                'rwdtsrouter' : {
                    'multi_dtsrouter' : {
                        'enable' : 'TRUE'
                    }
                },
                'rwvcs' : {
                    'collapse_each_rwvm' : 'TRUE',
                    'collapse_each_rwprocess' : 'TRUE'
                }
            }
        })
        manifest.inventory = rwmanifest.Inventory.from_dict({
           'component' : [{
               'component_name': 'rw.colony',
               'component_type': 'RWCOLLECTION',
               'rwcollection': {
                   'collection_type': 'rwcolony',
                   'event_list': {
                       "event": [{
                           'name': 'onentry',
                           'action': [
                               {
                                   'name': 'Start trafgen for rw.colony',
                                   'start': {
                                       'component_name': 'trafgen',
                                       'instance_id': '7',
                                       'config_ready': 'TRUE'
                                   }
                               },
                               {
                                   "name": "Start trafsink for rw.colony",
                                   "start": {
                                       "component_name": "trafsink",
                                       "instance_id": "8",
                                       "config_ready": "TRUE"
                                   }
                               },
                               {
                                   "name": "Start RW_VM_MASTER for rw.colony",
                                   "start": {
                                       "python_variable": [ "vm_ip_address = '127.0.0.1'" ],
                                       "component_name": "RW_VM_MASTER",
                                       "instance_id": "9",
                                       "config_ready": "TRUE"
                                   }
                               }
                           ]
                       }]
                   }
               }
           },


           {
               "component_name": "trafgen",
               "component_type": "RWCOLLECTION",
               "rwcollection": {
                   "collection_type": "rwcluster",
                   "event_list": {
                       "event": [{
                           "name": "onentry",
                           "action": [
                               {
                                   "name": "Start RW.VM.TG.LEAD for trafgen",
                                   "start": {
                                       "python_variable": [ "vm_ip_address = '127.0.0.2'" ],
                                       "component_name": "RW.VM.TG.LEAD",
                                       "instance_id": "10",
                                       "config_ready": "TRUE"
                                   }
                               } 
                              ,{
                                   "name": "Start RW.VM.trafgen for trafgen",
                                   "start": {
                                       "python_variable": [ "vm_ip_address = '127.0.0.3'" ],
                                       "component_name": "RW.VM.trafgen",
                                       "instance_id": "11",
                                       "config_ready": "TRUE"
                                   }
                               }
                           ]
                       }]
                   }
               }
           },

           {
               "component_name": "RW.VM.TG.LEAD",
               "component_type": "RWVM",
               "rwvm": {
                   "leader": "TRUE",
                   "event_list": {
                       "event": [{
                           "name": "onentry",
                           "action": [
                               {
                                   "name": "Start the RW.Proc_4.Fpath~58003",
                                   "start": {
                                       "component_name": "RW.Proc_4.Fpath~58003",
                                       "config_ready": "TRUE"
                                   }
                               },
                               {
                                   "name": "Start the RW.Proc_5.NcMgr",
                                   "start": {
                                       "component_name": "RW.Proc_5.NcMgr",
                                       "config_ready": "TRUE"
                                   }
                               },
                               {
                                   "name": "Start the RW.Proc_6.FpCtrl",
                                   "start": {
                                       "component_name": "RW.Proc_6.FpCtrl",
                                       "config_ready": "TRUE"
                                   }
                               },
                               {
                                   "name": "Start the RW.Proc_7.IfMgr",
                                   "start": {
                                       "component_name": "RW.Proc_7.IfMgr",
                                       "config_ready": "TRUE"
                                   }
                               }
                           ]
                       }]
                   }
               }
           },


           {
               "component_name": "RW.Proc_4.Fpath~58003",
               "component_type": "RWPROC",
               "rwproc": {
                   "run_as": "root",
                   "tasklet": [{
                       "name": "Start RW.Fpath for RW.Proc_4.Fpath~58003",
                       "component_name": "RW.Fpath",
                       "instance_id": 1,
                       "config_ready": "TRUE",
                       "python_variable": [
                           "colony_name = 'trafgen'",
                           "colony_id = 7",
                           "port_map = 'vfap/1/1|eth_sim:name=fabric1|vfap'",
                           "cmdargs_str = ''"
                       ]
                   }]
               }
           },

           {
               "component_name": "RW.Fpath",
               "component_type": "RWTASKLET",
               "rwtasklet": {
                   "plugin_directory": "./usr/lib/rift/plugins/rwfpath-c",
                   "plugin_name": "rwfpath-c"
               }
           },


           {
               "component_name": "RW.Proc_5.NcMgr",
               "component_type": "RWPROC",
               "rwproc": {
                   "run_as": "root",
                   "tasklet": [{
                       "name": "Start RW.NcMgr for RW.Proc_5.NcMgr",
                       "component_name": "RW.NcMgr",
                       "config_ready": "TRUE",
                       "python_variable": [
                           "cmdargs_str = ''",
                           "colony_name = 'trafgen'",
                           "colony_id = 7"
                       ]
                   }]
               }
           },
           {
               "component_name": "RW.NcMgr",
               "component_type": "RWTASKLET",
               "rwtasklet": {
                   "plugin_directory": "./usr/lib/rift/plugins/rwncmgr-c",
                   "plugin_name": "rwncmgr-c"
               }
           },


           {
               "component_name": "RW.Proc_6.FpCtrl",
               "component_type": "RWPROC",
               "rwproc": {
                   "tasklet": [
                       {
                           "name": "Start RW.FpCtrl for RW.Proc_6.FpCtrl",
                           "component_name": "RW.FpCtrl",
                           "config_ready": "TRUE",
                           "python_variable": [
                               "cmdargs_str = ''",
                               "colony_name = 'trafgen'",
                               "colony_id = 7"
                           ]
                       },
                       {
                           "name": "Start RW.NNLatencyTasklet for RW.Proc_6.FpCtrl",
                           "component_name": "RW.NNLatencyTasklet",
                           "config_ready": "TRUE"
                       },
                       {
                           "name": "Start RW.SfMgr for RW.Proc_6.FpCtrl",
                           "component_name": "RW.SfMgr",
                           "config_ready": "TRUE"
                       },
                       {
                           "name": "Start RW.SffMgr for RW.Proc_6.FpCtrl",
                           "component_name": "RW.SffMgr",
                           "config_ready": "TRUE"
                       }
                   ]
               }
           },

           {
               "component_name": "RW.FpCtrl",
               "component_type": "RWTASKLET",
               "rwtasklet": {
                   "plugin_directory": "./usr/lib/rift/plugins/rwfpctrl-c",
                   "plugin_name": "rwfpctrl-c"
               }
           },
           {
               "component_name": "RW.NNLatencyTasklet",
               "component_type": "RWTASKLET",
               "rwtasklet": {
                   "plugin_directory": "./usr/lib/rift/plugins/rwnnlatencytasklet",
                   "plugin_name": "rwnnlatencytasklet"
               }
           },
           {
               "component_name": "RW.SfMgr",
               "component_type": "RWTASKLET",
               "rwtasklet": {
                   "plugin_directory": "./usr/lib/rift/plugins/sfmgr",
                   "plugin_name": "rwsfmgr"
               }
           },
           {
               "component_name": "RW.SffMgr",
               "component_type": "RWTASKLET",
               "rwtasklet": {
                   "plugin_directory": "./usr/lib/rift/plugins/sffmgr",
                   "plugin_name": "rwsffmgr"
               }
           },
           {
               "component_name": "RW.Proc_7.IfMgr",
               "component_type": "RWPROC",
               "rwproc": {
                   "tasklet": [{
                       "name": "Start RW.IfMgr for RW.Proc_7.IfMgr",
                       "component_name": "RW.IfMgr",
                       "config_ready": "TRUE",
                       "python_variable": [
                           "cmdargs_str = ''",
                           "colony_name = 'trafgen'",
                           "colony_id = 7"
                       ]
                   }]
               }
           },
           {
               "component_name": "RW.IfMgr",
               "component_type": "RWTASKLET",
               "rwtasklet": {
                   "plugin_directory": "./usr/lib/rift/plugins/rwifmgr-c",
                   "plugin_name": "rwifmgr-c"
               }
           },
           {
               "component_name": "RW.VM.trafgen",
               "component_type": "RWVM",
               "rwvm": {
                   "event_list": {
                       "event": [{
                           "name": "onentry",
                           "action": [{
                               "name": "Start the RW.Proc_8.Fpath~94220",
                               "start": {
                                   "component_name": "RW.Proc_8.Fpath~94220",
                                   "config_ready": "TRUE"
                               }
                           }]
                       }]
                   }
               }
           },

           {
               "component_name": "RW.Proc_8.Fpath~94220",
               "component_type": "RWPROC",
               "rwproc": {
                   "run_as": "root",
                   "tasklet": [{
                       "name": "Start RW.Fpath for RW.Proc_8.Fpath~94220",
                       "component_name": "RW.Fpath",
                       "instance_id": 2,
                       "config_ready": "TRUE",
                       "python_variable": [
                           "colony_name = 'trafgen'",
                           "colony_id = 7",
                           "port_map = 'vfap/2/1|eth_sim:name=fabric1|vfap,trafgen/2/1|eth_sim:name=trafgenport|external'",
                           "cmdargs_str = ''"
                       ]
                   }]
               }
           },

           {
               "component_name": "trafsink",
               "component_type": "RWCOLLECTION",
               "rwcollection": {
                   "collection_type": "rwcluster",
                   "event_list": {
                       "event": [{
                           "name": "onentry",
                           "action": [
                               {
                                   "name": "Start RW.VM.APP.LEAD for trafsink",
                                   "start": {
                                       "python_variable": [ "vm_ip_address = '127.0.0.4'" ],
                                       "component_name": "RW.VM.APP.LEAD",
                                       "instance_id": "12",
                                       "config_ready": "TRUE"
                                   }
                               },
                               {
                                   "name": "Start RW.VM.loadbal for trafsink",
                                   "start": {
                                       "python_variable": [ "vm_ip_address = '127.0.0.5'" ],
                                       "component_name": "RW.VM.loadbal",
                                       "instance_id": "13",
                                       "config_ready": "TRUE"
                                   }
                               },
                               {
                                   "name": "Start RW.VM.trafsink for trafsink",
                                   "start": {
                                       "python_variable": [ "vm_ip_address = '127.0.0.6'" ],
                                       "component_name": "RW.VM.trafsink",
                                       "instance_id": "14",
                                       "config_ready": "TRUE"
                                   }
                               }
                           ]
                       }]
                   }
               }
           },
           {
               "component_name": "RW.VM.APP.LEAD",
               "component_type": "RWVM",
               "rwvm": {
                   "leader": "TRUE",
                   "event_list": {
                       "event": [{
                           "name": "onentry",
                           "action": [
                               {
                                   "name": "Start the RW.Proc_9.Fpath~15567",
                                   "start": {
                                       "component_name": "RW.Proc_9.Fpath~15567",
                                       "config_ready": "TRUE"
                                   }
                               },
                               {
                                   "name": "Start the RW.Proc_10.NcMgr",
                                   "start": {
                                       "component_name": "RW.Proc_10.NcMgr",
                                       "config_ready": "TRUE"
                                   }
                               },
                               {
                                   "name": "Start the RW.Proc_11.FpCtrl",
                                   "start": {
                                       "component_name": "RW.Proc_11.FpCtrl",
                                       "config_ready": "TRUE"
                                   }
                               },
                               {
                                   "name": "Start the RW.Proc_12.IfMgr",
                                   "start": {
                                       "component_name": "RW.Proc_12.IfMgr",
                                       "config_ready": "TRUE"
                                   }
                               }
                           ]
                       }]
                   }
               }
           },

           {
               "component_name": "RW.Proc_9.Fpath~15567",
               "component_type": "RWPROC",
               "rwproc": {
                   "run_as": "root",
                   "tasklet": [{
                       "name": "Start RW.Fpath for RW.Proc_9.Fpath~15567",
                       "component_name": "RW.Fpath",
                       "instance_id": 3,
                       "config_ready": "TRUE",
                       "python_variable": [
                           "colony_name = 'trafsink'",
                           "colony_id = 8",
                           "port_map = 'vfap/3/1|eth_sim:name=fabric1|vfap'",
                           "cmdargs_str = ''"
                       ]
                   }]
               }
           },
           {
               "component_name": "RW.Proc_10.NcMgr",
               "component_type": "RWPROC",
               "rwproc": {
                   "run_as": "root",
                   "tasklet": [{
                       "name": "Start RW.NcMgr for RW.Proc_10.NcMgr",
                       "component_name": "RW.NcMgr",
                       "config_ready": "TRUE",
                       "python_variable": [
                           "cmdargs_str = ''",
                           "colony_name = 'trafsink'",
                           "colony_id = 8"
                       ]
                   }]
               }
           },


                {
                    "component_name": "RW.Proc_11.FpCtrl",
                    "component_type": "RWPROC",
                    "rwproc": {
                        "tasklet": [
                            {
                                "name": "Start RW.FpCtrl for RW.Proc_11.FpCtrl",
                                "component_name": "RW.FpCtrl",
                                "config_ready": "TRUE",
                                "python_variable": [
                                    "cmdargs_str = ''",
                                    "colony_name = 'trafsink'",
                                    "colony_id = 8"
                                ]
                            },
                            {
                                "name": "Start RW.NNLatencyTasklet for RW.Proc_11.FpCtrl",
                                "component_name": "RW.NNLatencyTasklet",
                                "config_ready": "TRUE"
                            },
                            {
                                "name": "Start RW.SfMgr for RW.Proc_11.FpCtrl",
                                "component_name": "RW.SfMgr",
                                "config_ready": "TRUE"
                            },
                            {
                                "name": "Start RW.SffMgr for RW.Proc_11.FpCtrl",
                                "component_name": "RW.SffMgr",
                                "config_ready": "TRUE"
                            }
                        ]
                    }
                },

                {
                    "component_name": "RW.Proc_12.IfMgr",
                    "component_type": "RWPROC",
                    "rwproc": {
                        "tasklet": [{
                            "name": "Start RW.IfMgr for RW.Proc_12.IfMgr",
                            "component_name": "RW.IfMgr",
                            "config_ready": "TRUE",
                            "python_variable": [
                                "cmdargs_str = ''",
                                "colony_name = 'trafsink'",
                                "colony_id = 8"
                            ]
                        }]
                    }
                },
                {
                    "component_name": "RW.VM.loadbal",
                    "component_type": "RWVM",
                    "rwvm": {
                        "event_list": {
                            "event": [{
                                "name": "onentry",
                                "action": [{
                                    "name": "Start the RW.Proc_13.Fpath~30102",
                                    "start": {
                                        "component_name": "RW.Proc_13.Fpath~30102",
                                        "config_ready": "TRUE"
                                    }
                                }]
                            }]
                        }
                    }
                },

                {
                    "component_name": "RW.Proc_13.Fpath~30102",
                    "component_type": "RWPROC",
                    "rwproc": {
                        "run_as": "root",
                        "tasklet": [{
                            "name": "Start RW.Fpath for RW.Proc_13.Fpath~30102",
                            "component_name": "RW.Fpath",
                            "instance_id": 4,
                            "config_ready": "TRUE",
                            "python_variable": [
                                "colony_name = 'trafsink'",
                                "colony_id = 8",
                                "port_map = 'vfap/4/1|eth_sim:name=fabric1|vfap,trafsink/4/1|eth_sim:name=lbport1|external,trafsink/4/2|eth_sim:name=lbport2|external'",
                                "cmdargs_str = ''"
                            ]
                        }]
                    }
                },
                {
                    "component_name": "RW.VM.trafsink",
                    "component_type": "RWVM",
                    "rwvm": {
                        "event_list": {
                            "event": [{
                                "name": "onentry",
                                "action": [{
                                    "name": "Start the RW.Proc_14.Fpath~27537",
                                    "start": {
                                        "component_name": "RW.Proc_14.Fpath~27537",
                                        "config_ready": "TRUE"
                                    }
                                }]
                            }]
                        }
                    }
                },

                {
                    "component_name": "RW.Proc_14.Fpath~27537",
                    "component_type": "RWPROC",
                    "rwproc": {
                        "run_as": "root",
                        "tasklet": [{
                            "name": "Start RW.Fpath for RW.Proc_14.Fpath~27537",
                            "component_name": "RW.Fpath",
                            "instance_id": 5,
                            "config_ready": "TRUE",
                            "python_variable": [
                                "colony_name = 'trafsink'",
                                "colony_id = 8",
                                "port_map = 'vfap/5/1|eth_sim:name=fabric1|vfap,trafsink/5/1|eth_sim:name=trafsinkport|external'",
                                "cmdargs_str = ''"
                            ]
                        }]
                    }
                },

                {
                    "component_name": "RW_VM_MASTER",
                    "component_type": "RWVM",
                    "rwvm": {
                        "leader": "TRUE",
                        "event_list": {
                            "event": [{
                                "name": "onentry",
                                "action": [
                                    {
                                        "name": "Start the rw.colony",
                                        "start": {
                                            "component_name": "rw.colony",
                                            "config_ready": "TRUE"
                                        }
                                    },
                                    {
                                        "name": "Start the RW.Proc_1.uAgent",
                                        "start": {
                                            "component_name": "RW.Proc_1.uAgent",
                                            "config_ready": "TRUE"
                                        }
                                    },
#                                   {
#                                       "name": "Start the RW.CLI",
#                                       "start": {
#                                           "component_name": "RW.CLI",
#                                           "config_ready": "TRUE"
#                                       }
#                                   },
                                    {
                                        "name": "Start the RW.Proc_2.Restconf",
                                        "start": {
                                            "component_name": "RW.Proc_2.Restconf",
                                            "config_ready": "TRUE"
                                        }
                                    },
                                    {
                                        "name": "Start the RW.Proc_3.RestPortForward",
                                        "start": {
                                            "component_name": "RW.Proc_3.RestPortForward",
                                            "config_ready": "TRUE"
                                        }
                                    },
                                    {
                                        "name": "Start the RW.MC.UI",
                                        "start": {
                                            "component_name": "RW.MC.UI",
                                            "config_ready": "TRUE"
                                        }
                                    },
                                    {
                                        "name": "Start the logd",
                                        "start": {
                                            "component_name": "logd",
                                            "recovery_action": "RESTART",
                                            "config_ready": "TRUE"
                                        }
                                    }
                                ]
                            }]
                        }
                    }
                },


                {
                    "component_name": "RW.Proc_1.uAgent",
                    "component_type": "RWPROC",
                    "rwproc": {
                        "tasklet": [{
                            "name": "Start RW.uAgent for RW.Proc_1.uAgent",
                            "component_name": "RW.uAgent",
                            "config_ready": "TRUE",
                            "python_variable": [ "cmdargs_str = '--confd_ws confd_persist_grunt1-vm4.novalocal --confd-proto AF_INET --confd-ip 127.0.0.1'" ]
                        }]
                    }
                },
                {
                    "component_name": "RW.uAgent",
                    "component_type": "RWTASKLET",
                    "rwtasklet": {
                        "plugin_directory": "./usr/lib/rift/plugins/rwuagent-c",
                        "plugin_name": "rwuagent-c"
                    }
                },
#               {
#                   "component_name": "RW.CLI",
#                   "component_type": "PROC",
#                   "native_proc": {
#                       "exe_path": "./usr/bin/rwcli",
#                       "args": "--netconf_host 127.0.0.1 --netconf_port 2022 --schema_listing cli_rwfpath_schema_listing.txt",
#                   }
#               },

                {
                    "component_name": "RW.Proc_2.Restconf",
                    "component_type": "RWPROC",
                    "rwproc": {
                        "tasklet": [{
                            "name": "Start RW.Restconf for RW.Proc_2.Restconf",
                            "component_name": "RW.Restconf",
                            "config_ready": "TRUE"
                        }]
                    }
                },
                {
                    "component_name": "RW.Restconf",
                    "component_type": "RWTASKLET",
                    "rwtasklet": {
                        "plugin_directory": "./usr/lib/rift/plugins/restconf",
                        "plugin_name": "restconf"
                    }
                },
#               {
#                   "component_name": "RW.Proc_3.RestPortForward",
#                   "component_type": "RWPROC",
#                   "rwproc": {
#                       "tasklet": [{
#                           "name": "Start RW.RestPortForward for RW.Proc_3.RestPortForward",
#                           "component_name": "RW.RestPortForward",
#                           "config_ready": "TRUE"
#                       }]
#                   }
#               },


#               {
#                   "component_name": "RW.RestPortForward",
#                   "component_type": "RWTASKLET",
#                   "rwtasklet": {
#                       "plugin_directory": "./usr/lib/rift/plugins/restportforward",
#                       "plugin_name": "restportforward"
#                   }
#               },
                {
                    "component_name": "RW.MC.UI",
                    "component_type": "PROC",
                    "native_proc": {
                        "exe_path": "./usr/share/rw.ui/webapp/scripts/launch_ui.sh",
                    }
                },
                {
                    "component_name": "logd",
                    "component_type": "RWTASKLET",
                    "rwtasklet": {
                        "plugin_directory": "./usr/lib/rift/plugins/rwlogd-c",
                        "plugin_name": "rwlogd-c"
                    }
                },
                {
                    "component_name": "msgbroker",
                    "component_type": "RWTASKLET",
                    "rwtasklet": {
                        "plugin_directory": "./usr/lib/rift/plugins/rwmsgbroker-c",
                        "plugin_name": "rwmsgbroker-c"
                    }
                },


                {
                    "component_name": "dtsrouter",
                    "component_type": "RWTASKLET",
                    "rwtasklet": {
                        "plugin_directory": "./usr/lib/rift/plugins/rwdtsrouter-c",
                        "plugin_name": "rwdtsrouter-c"
                    }
                }
            ]
      })
        return manifest


    def tearDown(self):
        self.loop.stop()
        self.loop.close()

class MissionControl(DTSRecoveryTest):
    """
    DTS GI interface unittests

    Note:  Each tests uses a list of asyncio.Events for staging through the
    test.  These are required here because we are bring up each coroutine
    ("tasklet") at the same time and are not implementing any re-try
    mechanisms.  For instance, this is used in numerous tests to make sure that
    a publisher is up and ready before the subscriber sends queries.  Such
    event lists should not be used in production software.
    """
    @classmethod
    def configure_schema(cls):
        schema = RwYang.Model.load_and_merge_schema(
                     RwVcsYang.get_schema(),
                     'librwcal_yang_gen.so', 
                     'Rwcal')
        return schema


    @classmethod
    def configure_manifest(cls):
        manifest = rwmanifest.Manifest()
        manifest.bootstrap_phase = rwmanifest.BootstrapPhase.from_dict({
            "rwbaseschema": {
                "northbound_listing": "cli_rwmc_schema_listing.txt"
            }, 
            "rwtasklet": {
                "plugin_name": "rwinit-c"
            }, 
            "rwtrace": {
                "enable": "TRUE", 
                "level": 5, 
            }, 
            "log": {
                "enable": "TRUE", 
                "severity": 6, 
                "bootstrap_time": 30, 
                "console_severity": 5
            }, 
            "zookeeper": {
                "master_ip": "127.0.0.1", 
                "unique_ports": "FALSE", 
                "zake": "TRUE"
            }, 
            "serf": {
                "start": "TRUE"
            }, 
            "rwvm": {
                "instances": [
                    {
                        "component_name": "msgbroker", 
                        "config_ready": "TRUE"
                    }, 
                    {
                        "component_name": "dtsrouter", 
                        "config_ready": "TRUE"
                    }
                ]
            }, 
            "rwsecurity": {
                "use_ssl": "TRUE", 
                "cert": "/net/mahi/localdisk/kelayath/ws/coreha/etc/ssl/current.cert", 
                "key": "/net/mahi/localdisk/kelayath/ws/coreha/etc/ssl/current.key"
            }
        }) 
        manifest.init_phase = rwmanifest.InitPhase.from_dict({
            "environment": {
                "python_variable": [
                    "vm_ip_address = '127.0.0.1'",
                    "rw_component_name = 'vm-mission-control'",
                    "instance_id = 2",
                    "component_type = 'rwvm'",
                ], 
                "component_name": "$python(rw_component_name)", 
                "instance_id": "$python(instance_id)", 
                "component_type": "$python(rw_component_type)"
            }, 
            "settings": {
                "rwmsg": {
                    "multi_broker": {
                        "enable": "TRUE"
                    }
                }, 
                "rwdtsrouter": {
                    "multi_dtsrouter": {
                        "enable": "TRUE"
                    }
                }, 
                "rwvcs": {
                    "collapse_each_rwvm": "TRUE", 
                    "collapse_each_rwprocess": "TRUE"
                }
            }
        }) 
        manifest.inventory = rwmanifest.Inventory.from_dict({
            "component": [
                {
                    "component_name": "rw.colony", 
                    "component_type": "RWCOLLECTION", 
                    "rwcollection": {
                        "collection_type": "rwcolony", 
                        "event_list": {
                            "event": [{
                                "name": "onentry", 
                                "action": [{
                                    "name": "Start vm-mission-control for rw.colony", 
                                    "start": {
                                        "python_variable": ["vm_ip_address = '127.0.0.1'"], 
                                        "component_name": "vm-mission-control", 
                                        "instance_id": "2", 
                                        "config_ready": "TRUE"
                                    }
                                }]
                            }]
                        }
                    }
                }, 
                {
                    "component_name": "vm-mission-control", 
                    "component_type": "RWVM", 
                    "rwvm": {
                        "leader": "TRUE", 
                        "event_list": {
                            "event": [{
                                "name": "onentry", 
                                "action": [
                                    {
                                        "name": "Start the rw.colony", 
                                        "start": {
                                            "component_name": "rw.colony", 
                                            "config_ready": "TRUE"
                                        }
                                    }, 
#                                   {
#                                       "name": "Start the RW.CLI", 
#                                       "start": {
#                                           "component_name": "RW.CLI", 
#                                           "config_ready": "TRUE"
#                                       }
#                                   }, 
                                    {
                                        "name": "Start the RW.Proc_1.Restconf", 
                                        "start": {
                                            "component_name": "RW.Proc_1.Restconf", 
                                            "config_ready": "TRUE"
                                        }
                                    }, 
                                    {
                                        "name": "Start the RW.Proc_2.RestPortForward", 
                                        "start": {
                                            "component_name": "RW.Proc_2.RestPortForward", 
                                            "config_ready": "TRUE"
                                        }
                                    }, 
                                    {
                                        "name": "Start the RW.Proc_3.CalProxy", 
                                        "start": {
                                            "component_name": "RW.Proc_3.CalProxy", 
                                            "config_ready": "TRUE"
                                        }
                                    }, 
                                    {
                                        "name": "Start the RW.Proc_4.mission-control", 
                                        "start": {
                                            "component_name": "RW.Proc_4.mission-control", 
                                            "config_ready": "TRUE"
                                        }
                                    }, 
                                    {
                                        "name": "Start the RW.MC.UI", 
                                        "start": {
                                            "component_name": "RW.MC.UI", 
                                            "config_ready": "TRUE"
                                        }
                                    }, 
                                    {
                                        "name": "Start the RW.uAgent", 
                                        "start": {
                                            "python_variable": ["cmdargs_str = '--confd_ws confd_persist_grunt1-vm4.novalocal --confd-proto AF_INET --confd-ip 127.0.0.1'"],
                                            "component_name": "RW.uAgent", 
                                            "config_ready": "TRUE"
                                        }
                                    }, 
                                    {
                                        "name": "Start the logd", 
                                        "start": {
                                            "component_name": "logd", 
                                            "config_ready": "TRUE"
                                        }
                                    }
                                ]
                            }]
                        }
                    }
                }, 
#               {
#                   "component_name": "RW.CLI", 
#                   "component_type": "PROC", 
#                   "native_proc": {
#                       "exe_path": "./usr/bin/rwcli", 
#                       "args": "--netconf_host 127.0.0.1 --netconf_port 2022 --schema_listing cli_rwmc_schema_listing.txt", 
#                   }
#               }, 
                {
                    "component_name": "RW.Proc_1.Restconf", 
                    "component_type": "RWPROC", 
                    "rwproc": {
                        "tasklet": [{
                            "name": "Start RW.Restconf for RW.Proc_1.Restconf", 
                            "component_name": "RW.Restconf", 
                            "config_ready": "TRUE"
                        }]
                    }
                }, 
                {
                    "component_name": "RW.Restconf", 
                    "component_type": "RWTASKLET", 
                    "rwtasklet": {
                        "plugin_directory": "./usr/lib/rift/plugins/restconf", 
                        "plugin_name": "restconf"
                    }
                }, 
                {
                    "component_name": "RW.Proc_2.RestPortForward", 
                    "component_type": "RWPROC", 
                    "rwproc": {
                        "tasklet": [{
                            "name": "Start RW.RestPortForward for RW.Proc_2.RestPortForward", 
                            "component_name": "RW.RestPortForward", 
                            "config_ready": "TRUE"
                        }]
                    }
                }, 
                {
                    "component_name": "RW.RestPortForward", 
                    "component_type": "RWTASKLET", 
                    "rwtasklet": {
                        "plugin_directory": "./usr/lib/rift/plugins/restportforward", 
                        "plugin_name": "restportforward"
                    }
                }, 
                {
                    "component_name": "RW.Proc_3.CalProxy", 
                    "component_type": "RWPROC", 
                    "rwproc": {
                        "tasklet": [{
                            "name": "Start RW.CalProxy for RW.Proc_3.CalProxy", 
                            "component_name": "RW.CalProxy", 
                            "config_ready": "TRUE"
                        }]
                    }
                }, 
                {
                    "component_name": "RW.CalProxy", 
                    "component_type": "RWTASKLET", 
                    "rwtasklet": {
                        "plugin_directory": "./usr/lib/rift/plugins/rwcalproxytasklet", 
                        "plugin_name": "rwcalproxytasklet"
                    }
                }, 
                {
                    "component_name": "RW.Proc_4.mission-control", 
                    "component_type": "RWPROC", 
                    "rwproc": {
                        "tasklet": [{
                            "name": "Start mission-control for RW.Proc_4.mission-control", 
                            "component_name": "mission-control", 
                            "config_ready": "TRUE"
                        }]
                    }
                }, 
                {
                    "component_name": "mission-control", 
                    "component_type": "RWTASKLET", 
                    "rwtasklet": {
                        "plugin_directory": "./usr/lib/rift/plugins/rwmctasklet", 
                        "plugin_name": "rwmctasklet"
                    }
                }, 
                {
                    "component_name": "RW.MC.UI", 
                    "component_type": "PROC", 
                    "native_proc": {
                        "exe_path": "./usr/share/rw.ui/webapp/scripts/launch_ui.sh", 
                    }
                }, 
                {
                    "component_name": "RW.uAgent", 
                    "component_type": "RWTASKLET", 
                    "rwtasklet": {
                        "plugin_directory": "./usr/lib/rift/plugins/rwuagent-c", 
                        "plugin_name": "rwuagent-c"
                    }
                }, 
                {
                    "component_name": "logd", 
                    "component_type": "RWTASKLET", 
                    "rwtasklet": {
                        "plugin_directory": "./usr/lib/rift/plugins/rwlogd-c", 
                        "plugin_name": "rwlogd-c"
                    }
                }, 
                {
                    "component_name": "msgbroker", 
                    "component_type": "RWTASKLET", 
                    "rwtasklet": {
                        "plugin_directory": "./usr/lib/rift/plugins/rwmsgbroker-c", 
                        "plugin_name": "rwmsgbroker-c"
                    }
                }, 
                {
                    "component_name": "dtsrouter", 
                    "component_type": "RWTASKLET", 
                    "rwtasklet": {
                        "plugin_directory": "./usr/lib/rift/plugins/rwdtsrouter-c", 
                        "plugin_name": "rwdtsrouter-c"
                    }
                }
            ]
        })
        return manifest

    def tearDown(self):
        self.loop.stop()
        self.loop.close()

class LaunchPad(DTSRecoveryTest):
    """
    DTS GI interface unittests

    Note:  Each tests uses a list of asyncio.Events for staging through the
    test.  These are required here because we are bring up each coroutine
    ("tasklet") at the same time and are not implementing any re-try
    mechanisms.  For instance, this is used in numerous tests to make sure that
    a publisher is up and ready before the subscriber sends queries.  Such
    event lists should not be used in production software.
    """
    @classmethod
    def configure_schema(cls):
        schema =  RwYang.Model.load_and_merge_schema(RwVcsYang.get_schema(), 'librwcal_yang_gen.so', 'Rwcal')
        cls.model = RwYang.Model.create_libncx()
        cls.model.load_schema_ypbc(schema)
        with open('lptestmanifest.xml', 'w') as f:
           f.write(str(cls.manifest.to_xml_v2(cls.model, 1)))
        f.close()
        return schema


    @classmethod
    def configure_manifest(cls):
        manifest = rwmanifest.Manifest()
        manifest.bootstrap_phase = rwmanifest.BootstrapPhase.from_dict({
            "rwbaseschema": {
                "northbound_listing": "cli_rwmc_schema_listing.txt"
            }, 
            "rwtasklet": {
                "plugin_name": "rwinit-c"
            }, 
            "rwtrace": {
                "enable": "TRUE", 
                "level": 5, 
            }, 
            "log": {
                "enable": "TRUE", 
                "severity": 4, 
                "bootstrap_time": 30, 
                "console_severity": 4
            }, 
            "zookeeper": {
                "master_ip": "127.0.0.1", 
                "unique_ports": "FALSE", 
                "zake": "TRUE"
            }, 
            "serf": {
                "start": "TRUE"
            }, 
            "rwvm": {
                "instances": [
                    {
                        "component_name": "msgbroker", 
                        "config_ready": "TRUE"
                    }, 
                    {
                        "component_name": "dtsrouter", 
                        "config_ready": "TRUE"
                    }
                ]
            }, 
#           "rwsecurity": {
#               "use_ssl": "TRUE", 
#               "cert": "/net/mahi/localdisk/kelayath/ws/coreha/etc/ssl/current.cert", 
#               "key": "/net/mahi/localdisk/kelayath/ws/coreha/etc/ssl/current.key"
#           }
        }) 
        manifest.init_phase = rwmanifest.InitPhase.from_dict({
            "environment": {
                "python_variable": [
                    "vm_ip_address = '127.0.0.1'",
                    "rw_component_name = 'vm-launchpad'",
                    "instance_id = 1",
                    "component_type = 'rwvm'",
                ], 
                "component_name": "$python(rw_component_name)", 
                "instance_id": "$python(instance_id)", 
                "component_type": "$python(rw_component_type)"
            }, 
            "settings": {
                "rwmsg": {
                    "multi_broker": {
                        "enable": "TRUE"
                    }
                }, 
                "rwdtsrouter": {
                    "multi_dtsrouter": {
                        "enable": "TRUE"
                    }
                }, 
                "rwvcs": {
                    "collapse_each_rwvm": True, 
                    "collapse_each_rwprocess": True 
                }
            }
        }) 
        manifest.inventory = rwmanifest.Inventory.from_dict({
            "component": [
                {
                    "component_name": "master", 
                    "component_type": "RWCOLLECTION", 
                    "rwcollection": {
                        "collection_type": "rwcolony", 
                        "event_list": {
                            "event": [{
                                "name": "onentry", 
                                "action": [{
                                    "name": "Start vm-launchpad for master", 
                                    "start": {
                                        "python_variable": ["vm_ip_address = '127.0.0.1'"], 
                                        "component_name": "vm-launchpad", 
                                        "instance_id": "1", 
                                        "config_ready": "TRUE"
                                    }
                                }]
                            }]
                        }
                    }
                }, 
                {
                    "component_name": "vm-launchpad", 
                    "component_type": "RWVM", 
                    "rwvm": {
                        "leader": "TRUE", 
                        "event_list": {
                            "event": [{
                                "name": "onentry", 
                                "action": [
                                    {
                                        "name": "Start the master", 
                                        "start": {
                                            "component_name": "master", 
                                            "recovery_action": "RESTART",
                                            "config_ready": "TRUE"
                                        }
                                    }, 
#                                   {
#                                       "name": "Start the RW.CLI", 
#                                       "start": {
#                                           "component_name": "RW.CLI", 
#                                           "recovery_action": "RESTART",
#                                           "config_ready": "TRUE"
#                                       }
#                                   }, 
                                    {
                                        "name": "Start the RW.Proc_1.Restconf", 
                                        "start": {
                                            "component_name": "RW.Proc_1.Restconf", 
                                            "recovery_action": "RESTART",
                                            "config_ready": "TRUE"
                                        }
                                    }, 
                                    {
                                        "name": "Start the RW.Proc_2.RestPortForward", 
                                        "start": {
                                            "component_name": "RW.Proc_2.RestPortForward", 
                                            "recovery_action": "RESTART",
                                            "config_ready": "TRUE"
                                        }
                                    }, 
                                    {
                                        "name": "Start the RW.Proc_3.CalProxy", 
                                        "start": {
                                            "component_name": "RW.Proc_3.CalProxy", 
                                            "recovery_action": "RESTART",
                                            "config_ready": "TRUE"
                                        }
                                    }, 
                                    {
                                        "name": "Start the RW.Proc_4.nfvi-metrics-monitor", 
                                        "start": {
                                            "component_name": "RW.Proc_4.nfvi-metrics-monitor", 
                                            "recovery_action": "RESTART",
                                            "config_ready": "TRUE"
                                        }
                                    }, 
                                    {
                                        "name": "Start the RW.Proc_5.network-services-manager", 
                                        "start": {
                                            "component_name": "RW.Proc_5.network-services-manager", 
                                            "recovery_action": "RESTART",
                                            "config_ready": "TRUE"
                                        }
                                    }, 
                                    {
                                        "name": "Start the RW.Proc_6.virtual-network-function-manager", 
                                        "start": {
                                            "component_name": "RW.Proc_6.virtual-network-function-manager", 
                                            "recovery_action": "RESTART",
                                            "config_ready": "TRUE"
                                        }
                                    }, 
                                    {
                                        "name": "Start the RW.Proc_7.virtual-network-service", 
                                        "start": {
                                            "component_name": "RW.Proc_7.virtual-network-service", 
                                            "recovery_action": "RESTART",
                                            "config_ready": "TRUE"
                                        }
                                    }, 
                                    {
                                        "name": "Start the RW.Proc_8.nfvi-metrics-monitor", 
                                        "start": {
                                            "component_name": "RW.Proc_8.nfvi-metrics-monitor", 
                                            "recovery_action": "RESTART",
                                            "config_ready": "TRUE"
                                        }
                                    }, 
                                    {
                                        "name": "Start the RW.MC.UI", 
                                        "start": {
                                            "component_name": "RW.MC.UI", 
                                            "recovery_action": "RESTART",
                                            "config_ready": "TRUE"
                                        }
                                    }, 
                                    {
                                        "name": "Start the RW.COMPOSER.UI", 
                                        "start": {
                                            "component_name": "RW.COMPOSER.UI", 
                                            "config_ready": "TRUE"
                                        }
                                    }, 
                                    {
                                        "name": "Start the RW.Proc_10.launchpad", 
                                        "start": {
                                            "component_name": "RW.Proc_10.launchpad", 
                                            "recovery_action": "RESTART",
                                            "config_ready": "TRUE"
                                        }
                                    }, 
                                    {
                                        "name": "Start the RW.Proc_11.Resource-Manager", 
                                        "start": {
                                            "component_name": "RW.Proc_11.Resource-Manager", 
                                            "recovery_action": "RESTART",
                                            "config_ready": "TRUE"
                                        }
                                    }, 
                                    {
                                        "name": "Start the RW.uAgent", 
                                        "start": {
                                            "python_variable": ["cmdargs_str = '--confd_ws confd_persist_grunt1-vm4.novalocal --confd-proto AF_INET --confd-ip 127.0.0.1'"], 
                                            "component_name": "RW.uAgent", 
                                            "recovery_action": "RESTART",
                                            "config_ready": "TRUE"
                                        }
                                    }, 
                                    {
                                        "name": "Start the logd", 
                                        "start": {
                                            "component_name": "logd", 
                                            "recovery_action": "RESTART",
                                            "config_ready": "TRUE"
                                        }
                                    }
                                ]
                            }]
                        }
                    }
                }, 
#               {
#                   "component_name": "RW.CLI", 
#                   "component_type": "PROC", 
#                   "native_proc": {
#                       "exe_path": "./usr/bin/rwcli", 
#                       "args": "--netconf_host 127.0.0.1 --netconf_port 2022 --schema_listing cli_rwmc_schema_listing.txt", 
#                   }
#               }, 
                {
                    "component_name": "RW.Proc_1.Restconf", 
                    "component_type": "RWPROC", 
                    "rwproc": {
                        "tasklet": [{
                            "name": "Start RW.Restconf for RW.Proc_1.Restconf", 
                            "component_name": "RW.Restconf", 
                            "recovery_action": "RESTART",
                            "config_ready": "TRUE"
                        }]
                    }
                }, 
                {
                    "component_name": "RW.Restconf", 
                    "component_type": "RWTASKLET", 
                    "rwtasklet": {
                        "plugin_directory": "./usr/lib/rift/plugins/restconf", 
                        "plugin_name": "restconf"
                    }
                }, 
                {
                    "component_name": "RW.Proc_2.RestPortForward", 
                    "component_type": "RWPROC", 
                    "rwproc": {
                        "tasklet": [{
                            "name": "Start RW.RestPortForward for RW.Proc_2.RestPortForward", 
                            "component_name": "RW.RestPortForward", 
                            "recovery_action": "RESTART",
                            "config_ready": "TRUE"
                        }]
                    }
                }, 
                {
                    "component_name": "RW.RestPortForward", 
                    "component_type": "RWTASKLET", 
                    "rwtasklet": {
                        "plugin_directory": "./usr/lib/rift/plugins/restportforward", 
                        "plugin_name": "restportforward"
                    }
                }, 
                {
                    "component_name": "RW.Proc_3.CalProxy", 
                    "component_type": "RWPROC", 
                    "rwproc": {
                        "tasklet": [{
                            "name": "Start RW.CalProxy for RW.Proc_3.CalProxy", 
                            "component_name": "RW.CalProxy", 
                            "recovery_action": "RESTART",
                            "config_ready": "TRUE"
                        }]
                    }
                }, 
                {
                    "component_name": "RW.CalProxy", 
                    "component_type": "RWTASKLET", 
                    "rwtasklet": {
                        "plugin_directory": "./usr/lib/rift/plugins/rwcalproxytasklet", 
                        "plugin_name": "rwcalproxytasklet"
                    }
                }, 
                {
                    "component_name": "RW.Proc_4.nfvi-metrics-monitor", 
                    "component_type": "RWPROC", 
                    "rwproc": {
                        "tasklet": [{
                            "name": "Start nfvi-metrics-monitor for RW.Proc_4.nfvi-metrics-monitor", 
                            "component_name": "nfvi-metrics-monitor", 
                            "recovery_action": "RESTART",
                            "config_ready": "TRUE"
                        }]
                    }
                }, 
                {
                    "component_name": "nfvi-metrics-monitor", 
                    "component_type": "RWTASKLET", 
                    "rwtasklet": {
                        "plugin_directory": "./usr/lib/rift/plugins/rwmonitor", 
                        "plugin_name": "rwmonitor"
                    }
                }, 
                {
                    "component_name": "RW.Proc_5.network-services-manager", 
                    "component_type": "RWPROC", 
                    "rwproc": {
                        "tasklet": [{
                            "name": "Start network-services-manager for RW.Proc_5.network-services-manager", 
                            "component_name": "network-services-manager", 
                            "recovery_action": "RESTART",
                            "config_ready": "TRUE"
                        }]
                    }
                }, 
                {
                    "component_name": "network-services-manager", 
                    "component_type": "RWTASKLET", 
                    "rwtasklet": {
                        "plugin_directory": "./usr/lib/rift/plugins/rwnsmtasklet", 
                        "plugin_name": "rwnsmtasklet"
                    }
                }, 
                {
                    "component_name": "RW.Proc_6.virtual-network-function-manager", 
                    "component_type": "RWPROC", 
                    "rwproc": {
                        "tasklet": [{
                            "name": "Start virtual-network-function-manager for RW.Proc_6.virtual-network-function-manager", 
                            "component_name": "virtual-network-function-manager", 
                            "recovery_action": "RESTART",
                            "config_ready": "TRUE"
                        }]
                    }
                }, 
                {
                    "component_name": "virtual-network-function-manager", 
                    "component_type": "RWTASKLET", 
                    "rwtasklet": {
                        "plugin_directory": "./usr/lib/rift/plugins/rwvnfmtasklet", 
                        "plugin_name": "rwvnfmtasklet"
                    }
                }, 
                {
                    "component_name": "RW.Proc_7.virtual-network-service", 
                    "component_type": "RWPROC", 
                    "rwproc": {
                        "tasklet": [{
                            "name": "Start virtual-network-service for RW.Proc_7.virtual-network-service", 
                            "component_name": "virtual-network-service", 
                            "recovery_action": "RESTART",
                            "config_ready": "TRUE"
                        }]
                    }
                }, 
                {
                    "component_name": "virtual-network-service", 
                    "component_type": "RWTASKLET", 
                    "rwtasklet": {
                        "plugin_directory": "./usr/lib/rift/plugins/rwvnstasklet", 
                        "plugin_name": "rwvnstasklet"
                    }
                }, 
                {
                    "component_name": "RW.Proc_8.nfvi-metrics-monitor", 
                    "component_type": "RWPROC", 
                    "rwproc": {
                        "tasklet": [{
                            "name": "Start nfvi-metrics-monitor for RW.Proc_8.nfvi-metrics-monitor", 
                            "component_name": "nfvi-metrics-monitor", 
                            "recovery_action": "RESTART",
                            "config_ready": "TRUE"
                        }]
                    }
                }, 
                {
                    "component_name": "RW.MC.UI", 
                    "component_type": "PROC", 
                    "native_proc": {
                        "exe_path": "./usr/share/rw.ui/webapp/scripts/launch_ui.sh", 
                    }
                }, 
                {
                    "component_name": "RW.COMPOSER.UI", 
                    "component_type": "PROC", 
                    "native_proc": {
                        "exe_path": "./usr/share/composer/scripts/launch_composer.sh", 
                    }
                }, 
                {
                    "component_name": "RW.Proc_9.Configuration-Manager", 
                    "component_type": "RWPROC", 
                    "rwproc": {
                        "tasklet": [{
                            "name": "Start Configuration-Manager for RW.Proc_9.Configuration-Manager", 
                            "component_name": "Configuration-Manager", 
                            "recovery_action": "RESTART",
                            "config_ready": "TRUE"
                        }]
                    }
                }, 
                {
                    "component_name": "Configuration-Manager", 
                    "component_type": "RWTASKLET", 
                    "rwtasklet": {
                        "plugin_directory": "./usr/lib/rift/plugins/rwconmantasklet", 
                        "plugin_name": "rwconmantasklet"
                    }
                }, 
                {
                    "component_name": "RW.Proc_10.launchpad", 
                    "component_type": "RWPROC", 
                    "rwproc": {
                        "tasklet": [{
                            "name": "Start launchpad for RW.Proc_10.launchpad", 
                            "component_name": "launchpad", 
                            "recovery_action": "RESTART",
                            "config_ready": "TRUE"
                        }]
                    }
                }, 
                {
                    "component_name": "launchpad", 
                    "component_type": "RWTASKLET", 
                    "rwtasklet": {
                        "plugin_directory": "./usr/lib/rift/plugins/rwlaunchpad", 
                        "plugin_name": "rwlaunchpad"
                    }
                }, 
                {
                    "component_name": "RW.Proc_11.Resource-Manager", 
                    "component_type": "RWPROC", 
                    "rwproc": {
                        "tasklet": [{
                            "name": "Start Resource-Manager for RW.Proc_11.Resource-Manager", 
                            "component_name": "Resource-Manager", 
                            "recovery_action": "RESTART",
                            "config_ready": "TRUE"
                        }]
                    }
                }, 
                {
                    "component_name": "Resource-Manager", 
                    "component_type": "RWTASKLET", 
                    "rwtasklet": {
                        "plugin_directory": "./usr/lib/rift/plugins/rwresmgrtasklet", 
                        "plugin_name": "rwresmgrtasklet"
                    }
                }, 
                {
                    "component_name": "RW.uAgent", 
                    "component_type": "RWTASKLET", 
                    "rwtasklet": {
                        "plugin_directory": "./usr/lib/rift/plugins/rwuagent-c", 
                        "plugin_name": "rwuagent-c"
                    }
                }, 
                {
                    "component_name": "logd", 
                    "component_type": "RWTASKLET", 
                    "rwtasklet": {
                        "plugin_directory": "./usr/lib/rift/plugins/rwlogd-c", 
                        "plugin_name": "rwlogd-c"
                    }
                }, 
                {
                    "component_name": "msgbroker", 
                    "component_type": "RWTASKLET", 
                    "rwtasklet": {
                        "plugin_directory": "./usr/lib/rift/plugins/rwmsgbroker-c", 
                        "plugin_name": "rwmsgbroker-c"
                    }
                }, 
                {
                    "component_name": "dtsrouter", 
                    "component_type": "RWTASKLET", 
                    "rwtasklet": {
                        "plugin_directory": "./usr/lib/rift/plugins/rwdtsrouter-c", 
                        "plugin_name": "rwdtsrouter-c"
                    }
                }
            ]
        })
        return manifest

    def tearDown(self):
        self.loop.stop()
        self.loop.close()

