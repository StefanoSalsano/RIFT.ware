#!/usr/bin/env python3

# 
# (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
#
"""
Provides 4 env variables for development convenience:
NOCREATE    : If set, mission_control and launchpad are not created,
              instead existing launchpad & MC instances will be used.
SITE        : If set to "blr" , enable lab along with -s "blr" option
MGMT_NETWORK: If set, this will be used as mgmt_network in cloud account details
PROJECT_NAME: If set, this will be used as the tenant name.

"""
import argparse
import logging
import os
import signal
import subprocess
import sys

from gi import require_version
require_version('RwcalYang', '1.0')
from gi.repository import RwcalYang
import rift.auto.mano as mano


def parse_known_args(argv=sys.argv[1:]):
    """Create a parser and parse system test arguments

    Arguments:
        argv - list of args to parse

    Returns:
        A tuple containg two elements
            A list containg the unparsed portion of argv
            A namespace object populated with parsed args as attributes
    """

    parser = argparse.ArgumentParser()
    parser.add_argument(
            '-c', '--cloud-host',
            help='address of the openstack host')

    parser.add_argument(
            '--dts-cmd',
            help='command to setup a trace of a dts client')

    parser.add_argument(
            '-n', '--num-vm-resources',
            default=0,
            type=int,
            help='This flag indicates the number of additional vm resources to create')

    parser.add_argument(
            '--systest-script',
            help='system test wrapper script')

    parser.add_argument(
            '--systest-args',
            help='system test wrapper script')

    parser.add_argument(
            '--system-script',
            help='script to bring up system')

    parser.add_argument(
            '--system-args',
            help='arguments to the system script')

    parser.add_argument(
            '--test-script',
            help='script to test the system')

    parser.add_argument(
            '--test-args',
            help='arguments to the test script')

    parser.add_argument(
            '--post-restart-test-script',
            help='script to test the system, after restart')

    parser.add_argument(
            '--post-restart-test-args',
            help='args for the script to be tested post restart')

    parser.add_argument(
            '--up-cmd',
            help='command to run to wait until system is up')

    parser.add_argument(
            '-v', '--verbose',
            action='store_true',
            help='This flag sets the logging level to DEBUG')

    parser.add_argument(
            '--wait',
            action='store_true',
            help='wait for interrupt after tests complete')

    parser.add_argument(
            '--lp-standalone',
            action='store_true',
            help='Start launchpad in standalone mode.')

    return parser.parse_known_args(argv)


if __name__ == '__main__':
    (args, unparsed_args) = parse_known_args()

    flavor_id = None
    lp_vdu_id = None
    mc_vdu_id = None
    image_id = None

    vdu_resources = []

    def handle_term_signal(_signo, _stack_frame):
        sys.exit(2)

    def reset_openstack(account):
        openstack = mano.OpenstackCleanup(account)
        openstack.delete_vms()

        openstack.delete_networks(skip_list=mano.OpenstackCleanup.DEFAULT_NETWORKS)
        openstack.delete_ports_on_default_network()

        openstack.delete_images(skip_list=mano.OpenstackCleanup.DEFAULT_IMAGES)
        openstack.delete_flavors(skip_list=mano.OpenstackCleanup.DEFAULT_FLAVORS)

    signal.signal(signal.SIGINT, handle_term_signal)
    signal.signal(signal.SIGTERM, handle_term_signal)

    test_execution_rc = 1

    logging_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=logging_level)
    logger = logging.getLogger(__name__)
    logger.setLevel(logging_level)

    auth_url = 'http://{cloud_host}:5000/v3/'.format(cloud_host=args.cloud_host)
    account = RwcalYang.CloudAccount.from_dict({
            'name': 'rift.auto.openstack',
            'account_type': 'openstack',
            'openstack': {
              'key':  "pluto",
              'secret': "mypasswd",
              'auth_url': auth_url,
              'tenant': os.getenv('PROJECT_NAME', 'demo'),
              'mgmt_network': os.getenv('MGMT_NETWORK', 'private')}})

    use_existing = os.getenv("NOCREATE", None)
    use_existing = True if use_existing is not None else False
    openstack = mano.OpenstackManoSetup(
            account,
            site=os.getenv("SITE"),
            use_existing=use_existing)

    cleanup_clbk = None
    if use_existing is False:
        reset_openstack(account)
        cleanup_clbk = reset_openstack

    with openstack.setup(cleanup_clbk=cleanup_clbk) as (master, slaves):

        system_cmd = ("ssh -q -o BatchMode=yes -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -- "
                "{master_ip} sudo {rift_root}/rift-shell -e -r -- {system_script} {system_args}").format(
                master_ip=master.ip,
                rift_root="${RIFT_ROOT}",
                system_script=args.system_script,
                system_args=args.system_args)

        test_cmd_template = ("{test_script} --confd-host {master_ip} "
                "{launchpad_data} {other_args}")

        confd_ips = [master.ip]
        launchpad_data = ""

        if args.lp_standalone:
            system_cmd = system_cmd.replace("LAUNCHPAD_IPS", master.ip)
            launchpad_data = "--lp-standalone"
        else:
            launchpad = slaves.pop(0)
            confd_ips.append(launchpad.ip)
            launchpad_data = "--launchpad-vm-id {}".format(launchpad.id)

        test_cmd = test_cmd_template.format(
                test_script=args.test_script,
                master_ip=master.ip,
                launchpad_data=launchpad_data,
                other_args=args.test_args)


        systemtest_cmd = ('{systest_script} {other_args} '
                '--up_cmd "{up_cmd}" '
                '--system_cmd "{system_cmd}" '
                '--test_cmd "{test_cmd}" '
                '--confd_ip {confd_ips} ').format(
                        systest_script=args.systest_script,
                        up_cmd=args.up_cmd.replace('CONFD_HOST', master.ip),
                        system_cmd=system_cmd,
                        test_cmd=test_cmd,
                        confd_ips=",".join(confd_ips),
                        other_args=args.systest_args
                        )

        if args.post_restart_test_script is not None:
            post_restart_test_cmd = test_cmd_template.format(
                    test_script=args.post_restart_test_script,
                    master_ip=master.ip,
                    launchpad_data=launchpad_data,
                    other_args=args.post_restart_test_args,
                    )
            systemtest_cmd += '--post_restart_test_cmd "{}" '.format(post_restart_test_cmd)


        print('Executing Systemtest with command: {}'.format(systemtest_cmd))
        test_execution_rc = subprocess.call(systemtest_cmd, shell=True)

        if args.wait:
            # Wait for signal to cleanup
            signal.pause()

    exit(test_execution_rc)
