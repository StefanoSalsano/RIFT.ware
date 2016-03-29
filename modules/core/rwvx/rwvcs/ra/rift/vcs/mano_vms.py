# 
# (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
#
# @file mano_vms.py
# @author Karun Ganesharatnam (karun.ganesharatnam@riftio.com)
# @date 02/29/2016
# @brief This module contains classes representing VMs used in MANO System
# 
import rift.vcs

class StandardLeadVM(rift.vcs.VirtualMachine):
    """
    This class represents a master VM with all infrastructure components

    This is a merge of both the CliVM and MgmtVM components
    """

    def __init__(self, name=None, *args, **kwargs):
        """Creates a StandardLeadVM object.

        Arguments:
            name          - the name of the VM

        """
        name = "RW.VDU.LEAD.STND" if name is None else name
        super().__init__(name=name, *args, **kwargs)

        self.add_proc(rift.vcs.uAgentTasklet())
        self.add_proc(rift.vcs.RiftCli())
        self.add_proc(rift.vcs.MsgBrokerTasklet())
        self.add_proc(rift.vcs.RestconfTasklet(rest_port="8008"))
        self.add_proc(rift.vcs.Watchdog())
        self.add_proc(rift.vcs.RestPortForwardTasklet())

        self.add_proc(rift.vcs.DtsRouterTasklet())
        self.add_proc(rift.vcs.UIServerLauncher())


class StandardVM(rift.vcs.VirtualMachine):
    """
    This class represents a master VM with all infrastructure components
    """
    def __init__(self, name=None, *args, **kwargs):
        """Creates a StandardVM object.

        Arguments:
            name          - the name of the VM

        """
        name = "RW.VDU.MEMB.STND" if name is None else name
        super().__init__(name=name, *args, **kwargs)


class LeadFastpathVM(rift.vcs.VirtualMachine):
    """
    This class represents the lead virtual fabric VM composed of process components
    necessary for a base fast path lead VM
    """

    def __init__(self, name=None, *args, **kwargs):
        """Creates a LeadFastpathVM object.

        Arguments:
            name          - the name of the VM

        """
        name = "RW.VDU.MEMB.DDPL" if name is None else name
        super().__init__(name=name, *args, **kwargs)
        self.subcomponents = [
                rift.vcs.Proc(
                    name="rw.proc.fpath",
                    run_as="root",
                    tasklets=[rift.vcs.Fastpath(name='RW.Fpath')],
                    ),
                rift.vcs.Proc(
                    name="rw.proc.ncmgr",
                    run_as="root",
                    tasklets=[rift.vcs.NetworkContextManager()],
                    ),
                rift.vcs.Proc(
                    name="rw.proc.fpctrl",
                    tasklets=[rift.vcs.Controller(),rift.vcs.NNLatencyTasklet(), rift.vcs.Controller(), rift.vcs.SfMgr(),
                              rift.vcs.SffMgr()],
                    ),
                rift.vcs.Proc(
                    name="rw.proc.ifmgr",
                    tasklets=[rift.vcs.InterfaceManager()],
                    ),
                ]


class DistDataPathLeadVM(StandardLeadVM):
    """
    This class represents VM with master components and
    LeadVM components combined into a single VM
    """
    def __init__(self, name=None, *args, **kwargs):
        """Creates a DistDataPathLeadVM object.

        Arguments:
            name          - the name of the VM

        """
        name = "RW.VDU.LEAD.DDPL" if name is None else name
        super().__init__(name=name, *args, **kwargs)
        self.subcomponents.extend(LeadFastpathVM().subcomponents)


class FastpathVM(rift.vcs.VirtualMachine):
    """
    This class is used for VM running applications that require a fastpath tasklets.
    """

    def __init__(self, name=None, *args, **kwargs):
        """Creates a FastpathVM object.

        Arguments:
            name          - the name of the VM

        """
        name = "RW.VDU.MEMB.DDPM" if name is None else name
        super().__init__(name=name, *args, **kwargs)

        self.subcomponents = [
                rift.vcs.Proc(
                    name="rw.proc.fpath",
                    run_as="root",
                    tasklets=[rift.vcs.Fastpath(name='RW.Fpath')],
                    ),
                ]

