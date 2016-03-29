
# 
# (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
#

import pytest
import os

import gi
import rift.auto.session
import rift.mano.examples.ping_pong_nsd as ping_pong
import rift.vcs.vcs

gi.require_version('RwMcYang', '1.0')
from gi.repository import RwMcYang


class PackageError(Exception):
    pass

@pytest.fixture(scope='session', autouse=True)
def cloud_account_name(request):
    '''fixture which returns the name used to identify the cloud account'''
    return 'cloud-0'

@pytest.fixture(autouse=True)
def mc_only(request, standalone_launchpad):
    """Fixture to skip any tests that needs to be run only when a MC is used,
    and not in lp standalone mode.

    Arugments:
        request - pytest request fixture
        standalone_launchpad - indicates if the launchpad is running standalone
    """
    if request.node.get_marker('mc_only'):
        if standalone_launchpad:
            pytest.skip('Test marked skip for launchpad standalone mode')


@pytest.fixture(scope='session')
def launchpad_session(mgmt_session, mgmt_domain_name, session_type, standalone_launchpad, use_https):
    '''Fixture containing a rift.auto.session connected to the launchpad

    Arguments:
        mgmt_session         - session connected to the mission control instance 
                               (or launchpad in the case of a standalone session)
        mgmt_domain_name     - name of the mgmt_domain being used
        session_type         - Restconf or Netconf
        standalone_launchpad - indicates if the launchpad is running standalone
    '''
    if standalone_launchpad:
        return mgmt_session

    mc_proxy = mgmt_session.proxy(RwMcYang)
    launchpad_host = mc_proxy.get("/mgmt-domain/domain[name='%s']/launchpad/ip_address" % mgmt_domain_name)

    if session_type == 'netconf':
        launchpad_session = rift.auto.session.NetconfSession(host=launchpad_host)
    elif session_type == 'restconf':
        launchpad_session = rift.auto.session.RestconfSession(
                host=launchpad_host,
                use_https=use_https)

    launchpad_session.connect()
    rift.vcs.vcs.wait_until_system_started(launchpad_session)

    return launchpad_session


@pytest.fixture(scope='session')
def ping_pong_install_dir():
    '''Fixture containing the location of ping_pong installation
    '''
    install_dir = os.path.join(
        os.environ["RIFT_ROOT"],
        "images"
        )
    return install_dir

@pytest.fixture(scope='session')
def ping_vnfd_package_file(ping_pong_install_dir):
    '''Fixture containing the location of the ping vnfd package

    Arguments:
        ping_pong_install_dir - location of ping_pong installation
    '''
    ping_pkg_file = os.path.join(
            ping_pong_install_dir,
            "ping_vnfd_with_image.tar.gz",
            )
    if not os.path.exists(ping_pkg_file):
        raise_package_error()

    return ping_pkg_file


@pytest.fixture(scope='session')
def pong_vnfd_package_file(ping_pong_install_dir):
    '''Fixture containing the location of the pong vnfd package

    Arguments:
        ping_pong_install_dir - location of ping_pong installation
    '''
    pong_pkg_file = os.path.join(
            ping_pong_install_dir,
            "pong_vnfd_with_image.tar.gz",
            )
    if not os.path.exists(pong_pkg_file):
        raise_package_error()

    return pong_pkg_file


@pytest.fixture(scope='session')
def ping_pong_nsd_package_file(ping_pong_install_dir):
    '''Fixture containing the location of the ping_pong_nsd package

    Arguments:
        ping_pong_install_dir - location of ping_pong installation
    '''
    ping_pong_pkg_file = os.path.join(
            ping_pong_install_dir,
            "ping_pong_nsd.tar.gz",
            )
    if not os.path.exists(ping_pong_pkg_file):
        raise_package_error()

    return ping_pong_pkg_file


# Setting scope to be module, so that we get a different UUID when called
# by different files/modules.
@pytest.fixture(scope='module')
def ping_pong_records():
    '''Fixture containing a set of generated ping and pong descriptors
    '''
    return ping_pong.generate_ping_pong_descriptors(pingcount=1)
