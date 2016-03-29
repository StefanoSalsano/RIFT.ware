
# 
# (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
#

import os
import logging
import tempfile

from . import core

logger = logging.getLogger(__name__)

class Webserver(core.NativeProcess):
    """
    This class represents a webserver process.
    """

    def __init__(self,
            uid=None,
            name="RW.Webserver",
            ui_dir="./usr/share/rwmgmt-ui",
            confd_host="localhost",
            confd_port="8008",
            uagent_port=None,
            config_ready=True,
            recovery_action=core.RecoveryType.FAILCRITICAL.value,
            ):
        """Creates a Webserver object.

        Arguments:
            uid         - a unique identifier
            name        - the name of the process
            ui_dir      - the path to the UI resources
            confd_host  - the host that confd is on
            confd_port  - the port that confd is communicating on
            uagent_port - the port that the uAgent is communicating on
            config_ready - config readiness check enable
            recovery_action - recovery action mode

        """
        self.ui_dir = ui_dir
        self.confd_host = confd_host
        self.confd_port = confd_port
        self.uagent_port = uagent_port

        super(Webserver, self).__init__(
                uid=uid,
                name=name,
                exe="./usr/local/bin/rwmgmt-api-standalone",
                config_ready=config_ready,
                recovery_action=recovery_action,
                )

    @property
    def args(self):
        return ' '.join([
            '--ui_dir {}'.format(self.ui_dir),
            '--server localhost:{}'.format(self.uagent_port),
            '--log-level CRITICAL',
            '--confd admin:admin@{}:{}'.format(self.confd_host, self.confd_port),
            ])

class RedisCluster(core.NativeProcess):
    """
    This class represents a redis cluster process.
    """

    def __init__(self,
            uid=None,
            name="RW.RedisCluster",
            num_nodes=3,
            init_port=3152,
            config_ready=True,
            recovery_action=core.RecoveryType.FAILCRITICAL.value,
            ):
        """Creates a RedisCluster object.

        Arguments:
            name      - the name of the process
            uid       - a unique identifier
            num_nodes - the number of nodes in the cluster
            init_port - the nodes in the cluster are assigned sequential ports
                        starting at the value given by 'init_port'.
            config_ready - config readiness check enable
            recovery_action - recovery action mode

        """
        args = './usr/bin/redis_cluster.py -c -n {} -p {}'
        super(RedisCluster, self).__init__(
                uid=uid,
                name=name,
                exe='python',
                args=args.format(num_nodes, init_port),
                config_ready=config_ready,
                recovery_action=recovery_action,
                )


class RedisServer(core.NativeProcess):
    """
    This class represents a redis server process.
    """

    def __init__(self, uid=None, name="RW.RedisServer", port=None, config_ready=True, 
                 recovery_action=core.RecoveryType.FAILCRITICAL.value,
                ):
        """Creates a RedisServer object.

        Arguments:
            name - the name of the process
            uid  - a unique identifier
            port - the port to use for the server
            config_ready - config readiness check enable
            recovery_action - recovery action mode

        """
        # If the port is not specified, use the default for redis (NB: the
        # redis_cluster.py wrapper requires the init port to be specified so
        # something has to be provided).
        if port is None:
            port = '6379'

        super(RedisServer, self).__init__(
                uid=uid,
                name=name,
                exe='python',
                args= './usr/bin/redis_cluster.py -c -n 1 -p {}'.format(port),
                config_ready=config_ready,
                recovery_action=recovery_action,
                )


class UIServerLauncher(core.NativeProcess):
    """
    This class represents a UI Server Launcher.
    """

    def __init__(self, uid=None, name="RW.MC.UI", config_ready=True, 
                 recovery_action=core.RecoveryType.FAILCRITICAL.value,
                ):
        """Creates a UI Server Launcher

        Arguments:
            uid  - a unique identifier
            name - the name of the process
            config_ready - config readiness check enable
            recovery_action - recovery action mode

        """
        super(UIServerLauncher, self).__init__(
                uid=uid,
                name=name,
                exe="./usr/share/rw.ui/webapp/scripts/launch_ui.sh",
                config_ready=config_ready,
                recovery_action=recovery_action,
                )
    @property
    def args(self):
        return ' '

class Confd(core.NativeProcess):
    """
    This class represents a confd process.
    """

    def __init__(self, uid=None, name="RW.Confd", config_ready=True, 
                 recovery_action=core.RecoveryType.FAILCRITICAL.value,
                ):
        """Creates a Confd object.

        Arguments:
            uid  - a unique identifier
            name - the name of the process
            config_ready - config readiness check enable
            recovery_action - recovery action mode

        RIFT-8268 deprecates the direct use
        of Confd object.
        Use manifest.py to provide unique
        workspace to confd via uAgent command args
        """

        import socket
        hostname = socket.getfqdn()
        super(Confd, self).__init__(
                uid=uid,
                name=name,
                exe="./usr/bin/rw_confd",
                args="--unique confd_persist_{}".format(hostname),
                config_ready=config_ready,
                recovery_action=recovery_action,
                )

class RiftCli(core.NativeProcess):
    """
    This class represents a Rift CLI process.
    """

    def __init__(self,
              uid=None,
              name="RW.CLI",
              schema_listing="rwbase_schema_listing.txt",
              netconf_host="127.0.0.1",
              netconf_port="2022",
              config_ready=True,
              recovery_action=core.RecoveryType.FAILCRITICAL.value,
              netconf_username="admin",
              netconf_password="admin",                 
              ):
        """Creates a RiftCli object.

        Arguments:
            manifest_file - the file listing exported yang modules
            uid  - a unique identifier
            name - the name of the process
            netconf_host - IP/Host name where the Netconf server is listening
            netconf_port - Port on which Netconf server is listening
            config_ready - config readiness check enable
            recovery_action - recovery action mode
            netconf_username - the netconf username
            netconf_password - the netconf password

        """
        super(RiftCli, self).__init__(
                uid=uid,
                name=name,
                exe="./usr/bin/rwcli",
                interactive=True,
                config_ready=config_ready,
                recovery_action=recovery_action,
                )
        self.netconf_host = netconf_host
        self.netconf_port = netconf_port
        self.schema_listing = schema_listing
        self.netconf_username = netconf_username
        self.netconf_password = netconf_password

    @property
    def args(self):
        username_and_password_args = ""
        if self.netconf_username is not None:
            username_and_password_args += " --username %s " % self.netconf_username
        if self.netconf_password is not None:
            username_and_password_args += " --passwd %s " % self.netconf_password

        return ' '.join([
            '--netconf_host {}'.format(self.netconf_host),
            '--netconf_port {}'.format(self.netconf_port),
            '--schema_listing {}'.format(self.schema_listing),
            username_and_password_args,
            ])

class Watchdog(core.NativeProcess):
    """
    This class represents a Rift CLI process.
    """

    def __init__(self,
                 uid=None,
                 name="RW.Watchdog",
                 config_ready=False,
                 recovery_action=core.RecoveryType.FAILCRITICAL.value,
              ):
        """Creates a Watchdog object.

        """
        super(Watchdog, self).__init__(
                uid=uid,
                name=name,
                exe="./usr/bin/rwwatchdog",
                config_ready=config_ready,
                recovery_action=recovery_action,
                )

class CrossbarServer(core.NativeProcess):
    """
    This class represents a Crossbar process used for DTS mock.
    """

    def __init__(self, uid=None, name="RW.Crossbar", config_ready=True, 
                 recovery_action=core.RecoveryType.FAILCRITICAL.value,
                ):
        """Creates a CrossbarServer object.

        Arguments:
            uid  - a unique identifier
            name - the name of the process
            config_ready - config readiness check enable
            recovery_action - recovery action mode

        """
        super(CrossbarServer, self).__init__(
                uid=uid,
                name=name,
                exe="/usr/bin/crossbar",
                config_ready=config_ready,
                recovery_action=recovery_action,
                )

    @property
    def args(self):
        return ' '.join([
            "start", "--cbdir", "etc/crossbar/config", "--loglevel", "debug", "--logtofile",
            ])

