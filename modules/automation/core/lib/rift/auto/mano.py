"""
# 
# (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
#

@file mano.py
@author Varun Prasad (varun.prasad@riftio.com)
@date 19/01/2016

"""

import collections
import contextlib
import logging
import os
import subprocess
import time
import uuid

from gi.repository import RwcalYang, RwTypes
import rw_peas
import rwlogger


logger = logging.getLogger()


class TimeoutError(Exception):
    '''Thrown if object does not reach the desired state within the timeout'''
    pass


class ValidationError(Exception):
    '''Thrown if success of the bootstrap process is not verified'''
    pass


class OpenstackCleanup(object):
    """
    A convenience class on top of cal interface to provide cleanup
    functions.
    """
    DEFAULT_FLAVORS = ['m1.tiny', 'm1.small', 'm1.medium', 'm1.large', 'm1.xlarge']
    DEFAULT_IMAGES = ['rwimage']
    DEFAULT_NETWORKS =["public", "private"]

    def __init__(self, account, dry_run=False):
        """
        Args:
            account (RwcalYang.CloudAccount): Accound details
            dry_run (bool, optional): If enable, only log statements are
                    printed.
        """
        self.account = account
        self.cal = self._get_cal_interface()
        self.dry_run = dry_run

    def _get_cal_interface(self):
        """Get an instance of the rw.cal interface

        Load an instance of the rw.cal plugin via libpeas
        and returns the interface to that plugin instance

        Returns:
            rw.cal interface to created rw.cal instance
        """
        plugin = rw_peas.PeasPlugin('rwcal_openstack', 'RwCal-1.0')
        engine, info, extension = plugin()
        cal = plugin.get_interface("Cloud")
        rwloggerctx = rwlogger.RwLog.Ctx.new("Cal-Log")
        rc = cal.init(rwloggerctx)
        assert rc == RwTypes.RwStatus.SUCCESS

        return cal

    def delete_vms(self, skip_list=None):
        """Delete all the VM in the tenant.

        Args:
            skip_list (list, optional): A list of VM names. Skips the
                    VMs present in the list
        """
        skip_list = skip_list or []
        rc, vdulist = self.cal.get_vdu_list(self.account)
        for vduinfo in vdulist.vdu_info_list:
            if vduinfo.name not in skip_list:
                logger.info("Deleting VM: {}".format(vduinfo.name))
                if self.dry_run:
                    continue
                self.cal.delete_vdu(self.account, vduinfo.vdu_id)

    def delete_networks(self, skip_list=None):
        """Delete all the networks.

        Args:
            skip_list (list, optional): A list of Network names. Skips the
                    networks present in the list
        """
        skip_list = skip_list or []
        rc, rsp = self.cal.get_virtual_link_list(self.account)

        for vlink in rsp.virtual_link_info_list:
            if vlink.name not in skip_list:
                logger.info("Deleting Network: {}".format(vlink.name))
                if self.dry_run:
                    continue
                self.cal.delete_virtual_link(
                        self.account,
                        vlink.virtual_link_id)

    def delete_ports_on_default_network(self, skip_list=None):
        """Delete all the ports on the mgmt_network, except the ones
        that are active.

        The ports that are active are identified using the presence of
        VM ID.

        Args:
            skip_list (list, optional): A list of port names. Skips the
                    ports present in the list
        """
        skip_list = skip_list or []
        rc, rsp = self.cal.get_port_list(self.account)

        for port in rsp.portinfo_list:
            if port.port_name not in skip_list and len(port.vm_id) == 0:
                logger.info("Deleting Port: {}".format(port.port_name))
                if self.dry_run:
                    continue
                self.cal.delete_port(self.account, port.port_id)

    def delete_flavors(self, skip_list=None):
        """Delete all the flavors.

        Args:
            skip_list (list, optional): A list of flavor names. Skips the
                    flavors present in the list
        """
        skip_list = skip_list or []
        rc, rsp = self.cal.get_flavor_list(self.account)
        for flavor in rsp.flavorinfo_list:
            if flavor.name not in skip_list:
                logger.info("Deleting Flavor: {}".format(flavor.name))
                if self.dry_run:
                    continue
                self.cal.delete_flavor(self.account, flavor.id)

    def delete_images(self, skip_list=None):
        """Delete all the images.

        Args:
            skip_list (list, optional): A list of image names. Skips the
                    images present in the list
        """
        skip_list = skip_list or []
        rc, rsp = self.cal.get_image_list(self.account)

        for image in rsp.imageinfo_list:
            if image.name not in skip_list:
                logger.info("Deleting Image: {}".format(image.name))
                if self.dry_run:
                    continue
                self.cal.delete_image(self.account, image.id)


class OpenstackManoSetup(object):
    """Provide a single entry point for setting up an openstack controller
    with launchpad and mission_control.

    Usage:
        mano = OpenstackManoSetup(account)
        with mano.setup() as (mc, launchpad, slaves):
            <SYS CMD>
    """
    _DEFAULT_IMG = RwcalYang.ImageInfoItem.from_dict({
            'name': 'rift.auto.image',
            'location': os.path.join(os.getenv("RIFT_ROOT"), "images/rift-ui-lab-latest.qcow2"),
            'disk_format': 'qcow2',
            'container_format': 'bare'})

    _DEFAULT_FLAVOR = RwcalYang.FlavorInfoItem.from_dict({
            'name': 'rift.auto.flavor.{}'.format(str(uuid.uuid4())),
            'vm_flavor': {
                'memory_mb': 8192,  # 8 GB
                'vcpu_count': 4,
                'storage_gb': 40,  # 40 GB
            }
        })

    _MISSION_CONTROL_NAME = "rift_auto_mission_control"
    _LAUNCHPAD_NAME = "rift_auto_launchpad"

    def __init__(self, account, site=None, image=None, flavor=None, use_existing=False, lp_standalone=False):
        """
        Args:
            account (RwcalYang.CloudAccount): Account details
            site (str, optional): If specified as "blr", enable_lab CMD
                is called with -s option.
            image (RwcalYang.ImageInfoItem, optional): If specified the image
                is created usin the config.
            flavor (RwcalYang.FlavorInfoItem, optional): If specified the
                flavor config is used to create all resources.
            use_exiting(bool, optional): If set no new instance are created,
                looks for exiting ones.
            lp_standalone (bool, optional): If set only Lp instance will be
                created
        """
        self.account = account
        self.cal = self._get_cal_interface()
        self._site = site
        self.image = image or self._DEFAULT_IMG
        self.flavor = flavor or self._DEFAULT_FLAVOR
        self._use_existing = use_existing
        self._lp_standalone = lp_standalone

    @property
    def master_name(self):
        """Returns the Master resource's name based on the standalone mode
        """
        return self._LAUNCHPAD_NAME if self._lp_standalone else self._MISSION_CONTROL_NAME

    def _get_cal_interface(self):
        """Get an instance of the rw.cal interface

        Load an instance of the rw.cal plugin via libpeas
        and returns the interface to that plugin instance

        Returns:
            rw.cal interface to created rw.cal instance
        """
        plugin = rw_peas.PeasPlugin('rwcal_openstack', 'RwCal-1.0')
        engine, info, extension = plugin()
        cal = plugin.get_interface("Cloud")
        rwloggerctx = rwlogger.RwLog.Ctx.new("Cal-Log")
        rc = cal.init(rwloggerctx)
        assert rc == RwTypes.RwStatus.SUCCESS

        return cal

    def create_image(self):
        """Creates an image using the config provided.

        Raises:
            TimeoutError: If the image does not reach a valid state
            ValidationError: If the image upload failed.

        Returns:
            str: image_id
        """
        def wait_for_image_state(account, image_id, state, timeout=300):
            state = state.lower()
            current_state = 'unknown'

            while current_state != state:
                rc, image_info = self.cal.get_image(account, image_id)
                current_state = image_info.state.lower()

                if current_state in ['failed']:
                   raise ValidationError('Image [{}] entered failed state while waiting for state [{}]'.format(image_id, state))

                if current_state != state:
                    time.sleep(1)

            if current_state != state:
                logger.error('Image still in state [{}] after [{}] seconds'.format(current_state, timeout))
                raise TimeoutError('Image [{}] failed to reach state [{}] within timeout [{}]'.format(image_id, state, timeout))

            return image_info

        logger.debug("Uploading VM Image")
        rc, image_id = self.cal.create_image(self.account, self.image)
        assert rc == RwTypes.RwStatus.SUCCESS
        image_info = wait_for_image_state(self.account, image_id, 'active')

        return image_id

    def create_flavor(self):
        """Creates a flavor in the openstack instance.

        Returns:
            str: flavor id
        """
        logger.debug("Creating VM Flavor")
        rc, flavor_id = self.cal.create_flavor(self.account, self.flavor)
        assert rc == RwTypes.RwStatus.SUCCESS

        return flavor_id

    def _wait_for_vdu_state(self, vdu_id, state, timeout=300):
        """Wait till the VM enter an 'active' state.

        Args:
            vdu_id (str): ID of the VM
            state (str): expected state
            timeout (int, optional): defaults to 300

        Raises:
            TimeoutError: If the VM does not reach a valid state
            ValidationError: If VM reaches a failed state.

        Returns:
            vdu_info(RwcalYang.VDUInfoParams)
        """
        state = state.lower()
        current_state = 'unknown'
        while current_state != state:
            rc, vdu_info = self.cal.get_vdu(self.account, vdu_id)

            assert rc == RwTypes.RwStatus.SUCCESS
            current_state = vdu_info.state.lower()

            if current_state in ['failed']:
               raise ValidationError('VM [{}] entered failed state while waiting for state [{}]'.format(vdu_id, state))

            if current_state != state:
                time.sleep(1)

        if current_state != state:
            raise TimeoutError('VM [{}] failed to reach state [{}] within timeout [{}]'.format(vdu_id, state, timeout))

        return vdu_info

    def create_master_resource(self, name):
        """Creates the master resource instance.

        Returns:
            VduInfo: vdu_info of master resource
        """
        vdu_id = str(uuid.uuid4())
        userdata = """#cloud-config

    runcmd:
     - /usr/rift/scripts/cloud/enable_lab {site}
    """

        site = ""
        if self._site == "blr":
            site = "-s blr"
        userdata = userdata.format(site=site)

        vdu_info = RwcalYang.VDUInitParams.from_dict({
            'name': name,
            'node_id': vdu_id,
            'flavor_id': str(self.flavor_id),
            'image_id': self.image_id,
            'allocate_public_address': False,
            'vdu_init': {
                'userdata': userdata}
        })

        logger.debug("Creating Master VM")
        rc, vdu_id = self.cal.create_vdu(self.account, vdu_info)

        assert rc == RwTypes.RwStatus.SUCCESS

        vdu_info = self._wait_for_vdu_state(vdu_id, 'active')
        logger.debug("Master VM Active!")

        return VduInfo(vdu_info)

    def create_slave_resource(self, vdu_name, master_vm):
        """Create a slave resource with salt config pointing to master's IP.

        Args:
            vdu_name (str): Name of the VDU
            master_vm (VduInfo): VduInfo instance for Master Vm

        Returns:
            VduInfo(VduInfo): VduInfo of the newly created slave resource.

        """
        vdu_id = str(uuid.uuid4())

        site = ""
        if self._site == "blr":
            site = "-s blr"

        vdu_userdata = """#cloud-config

    salt_minion:
      conf:
        master: {mgmt_ip}
        id: {vdu_id}
        acceptance_wait_time: 1
        recon_default: 100
        recon_max: 1000
        recon_randomize: False
        log_level: debug

    runcmd:
     - echo Sleeping for 5 seconds and attempting to start minion
     - sleep 5
     - /bin/systemctl start salt-minion.service

    runcmd:
     - /usr/rift/scripts/cloud/enable_lab {site}
    """.format(mgmt_ip=master_vm.vdu_info.management_ip,
               vdu_id=vdu_id,
               site=site)

        vdu_info = RwcalYang.VDUInitParams.from_dict({
            'name': vdu_name,
            'node_id': vdu_id,
            'flavor_id': str(self.flavor_id),
            'image_id': self.image_id,
            'allocate_public_address': False,
            'vdu_init': {'userdata': vdu_userdata},
        })

        logger.debug("Creating vdu resource {}".format(vdu_name))
        rc, vdu_id = self.cal.create_vdu(self.account, vdu_info)

        vdu_info = self._wait_for_vdu_state(vdu_id, 'active')
        logger.debug("Slave VM {} active".format(vdu_name))

        return VduInfo(vdu_info)

    def _wait_till_resources_ready(self, resources, timeout):
        """A convenience method to check if all resource are ready (ssh'able &
            cloud-init is done running.)

        Args:
            resources (list): A list of all resources to be checked.
            timeout (int): Timeout in seconds

        Raises:
            ValidationError: If all the resources are not ready within the
            timeout duration.

        """
        start = time.time()
        elapsed = 0
        while resources and elapsed < timeout:
            resource = resources.popleft()
            if not resource.is_ready():
                resources.append(resource)

            time.sleep(5)
            elapsed = time.time() - start

        if resources:
            raise ValidationError("Failed to verify all VM resources started")

    def _get_vdu(self, name):
        """Finds and returns the VM from the list of VMs present in the tenant.

        Args:
            name (str): Name of the VM

        Returns:
            VduInfo: VduInfo instance of the VM.
        """
        rc, vdulist = self.cal.get_vdu_list(self.account)
        for vduinfo in vdulist.vdu_info_list:
            if vduinfo.name == name:
                return VduInfo(vduinfo)

        return None

    @contextlib.contextmanager
    def setup(self, slave_resources=0, timeout=900, cleanup_clbk=None):
        """
        Args:
            slave_resources (int, optional): Number of additional slave resource
                to be created.
            timeout (int, optional): timeout in seconds
            cleanup_clbk (callable, optional): Callback to perform any teardown
                operations.
                Signature: cleanup_clbk(account)
                    account(RwcalYang.CloudAccount): Account details

        Yields:
            A tuple of VduInfo- Master, Slaves.
        """
        try:
            if self._use_existing:
                yield self._get_vdu(self._MISSION_CONTROL_NAME), \
                      [self._get_vdu(self._LAUNCHPAD_NAME)] \

            else:
                self.image_id = self.create_image()
                self.flavor_id = self.create_flavor()

                master = self.create_master_resource(self.master_name)
                resources = collections.deque([master])

                slave_names = ['rift_auto_resource_{}'.format(index) 
                        for index in range(slave_resources)]

                if not self._lp_standalone:
                    slave_names.insert(0, self._LAUNCHPAD_NAME)

                slaves = []
                for slave_name in slave_names:
                    slave = self.create_slave_resource(slave_name, master)
                    slaves.append(slave)

                resources.extend(slaves)

                self._wait_till_resources_ready(resources, timeout=timeout)

                yield master, slaves

        finally:
            if cleanup_clbk is not None:
                cleanup_clbk(self.account)


class VduInfo(object):
    """
    A wrapper on the vdu_info with some additional utilities.
    """
    def __init__(self, vdu_info):
        """
        Args:
            vdu_info (RwcalYang.VDUInfoParams): Vdu info
        """
        self.vdu_info = vdu_info
        self._ip = vdu_info.management_ip
        self._is_accessible = False

    @property
    def id(self):
        """Node ID of the VM in openstack
        """
        return self.vdu_info.vdu_id

    @property
    def ip(self):
        """IP address of the VM
        """
        return self._ip

    @property
    def is_accessible(self):
        """Check if the machine is ssh'able.
        """
        if self._is_accessible:
            return self._is_accessible

        check_host_cmd = 'ssh -q -o BatchMode=yes -o StrictHostKeyChecking=no -- {ip} ls > /dev/null'
        rc = subprocess.call(check_host_cmd.format(ip=self._ip), shell=True)
        logger.info("Checking if {} is accessible".format(self._ip))

        if rc != 0:
            return False

        self._is_accessible = True
        return self._is_accessible

    def is_ready(self):
        """Checks if the cloud-init script is done running.

        Checks if the boot-finished file is present.

        Returns:
            bool: True if present.
        """
        if not self.is_accessible:
            return False

        is_ready_cmd = 'ssh -q -o BatchMode=yes -o StrictHostKeyChecking=no -- {ip} stat /var/lib/cloud/instance/boot-finished > /dev/null'
        rc = subprocess.call(is_ready_cmd.format(ip=self._ip), shell=True)

        logger.info("Checking if {} is ready".format(self._ip))
        if rc != 0:
            return False

        return True
