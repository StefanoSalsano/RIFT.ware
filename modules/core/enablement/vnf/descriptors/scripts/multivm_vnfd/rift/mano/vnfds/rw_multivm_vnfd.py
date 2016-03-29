#!/usr/bin/env python3

import sys
import os
import argparse
import uuid
import rift.vcs.component as vcs
from gi.repository import (
    RwYang,
    VnfdYang,
    RwVnfdYang,
    RwNsdYang,
    VldYang)

use_epa = False
use_sriov = False

class UnknownVNFError(Exception):
    pass

class ManoDescriptor(object):
    def __init__(self, name):
        self.name = name
        self.descriptor = None

    def write_to_file(self, module_list, outdir, output_format):
        model = RwYang.Model.create_libncx()
        for module in module_list:
            model.load_module(module)

        if output_format == 'json':
            with open('%s/%s.json' % (outdir, self.name), "w") as fh:
                fh.write(self.descriptor.to_json(model))
        elif output_format.strip() == 'xml':
            with open('%s/%s.xml' % (outdir, self.name), "w") as fh:
                fh.write(self.descriptor.to_xml_v2(model, pretty_print=True))
        else:
            raise("Invalid output format for the descriptor")

class VirtualLink(ManoDescriptor):
    def __init__(self, name):
        super(VirtualLink, self).__init__(name)

    def compose(self, cptuple_list):
        self.descriptor = VldYang.YangData_Vld_VldCatalog()
        vld = self.descriptor.vld.add()
        vld.id = str(uuid.uuid1())
        vld.name = self.name
        vld.short_name = self.name
        vld.vendor = 'RIFT.io'
        vld.description = 'Fabric VL'
        vld.version = '1.0'
        vld.type_yang = 'ELAN'

        for cp in cptuple_list:
            cpref = vld.vnfd_connection_point_ref.add()
            cpref.member_vnf_index_ref = cp[0]
            cpref.vnfd_id_ref = cp[1]
            cpref.vnfd_connection_point_ref = cp[2]


    def write_to_file(self, outdir, nsd_name, output_format):
        dirpath = "%s/%s/vld" % (outdir, nsd_name)
        if not os.path.exists(dirpath):
            os.makedirs(dirpath)
        super(VirtualLink, self).write_to_file(["vld", "rw-vld"],
                                               "%s/%s/vld" % (outdir, nsd_name),
                                               output_format)

class RwVirtualLink(VirtualLink):
    def __init__(self, name):
        super(RwVirtualLink, self).__init__(name)

class VirtualNetworkFunction(ManoDescriptor):
    def __init__(self, name):
        self.vnfd_catalog = None
        self.vnfd = None
        super(VirtualNetworkFunction, self).__init__(name)

    def is_exists(self, component_name):
        for component in self.vnfd.component:
            if component_name == component.component_name:
                return True
        return False

    def get_cloud_init(self, vnfd, vdu, master_vdu_id):
        if (vdu.name.split(".", -1))[2] == 'LEAD':
         return '''#cloud-config
password: fedora
chpasswd: { expire: False }
ssh_pwauth: True
write_files:
  - path: /opt/rift/.vnf_start_conf
    content: |
        VNFNAME=%s
        VDUNAME={{ vdu.name }}
        MASTERIP=
runcmd:
  - [ systemctl, daemon-reload ]
  - [ systemctl, enable, multivmvnf.service ]
  - [ systemctl, start, --no-block, multivmvnf.service ]
''' % vnfd.name
        else:
         return '''#cloud-config
password: fedora
chpasswd: { expire: False }
ssh_pwauth: True
write_files:
  - path: /opt/rift/.vnf_start_conf
    content: |
        VNFNAME=%s
        VDUNAME={{ vdu.name }}
        MASTERIP={{ vdu[%s].mgmt.ip }}
runcmd:
  - [ systemctl, daemon-reload ]
  - [ systemctl, enable, multivmvnf.service ]
  - [ systemctl, start, --no-block, multivmvnf.service ]
''' % (vnfd.name, master_vdu_id)


    def create_vdu(self, vnfd, vdu_info, vnf_info, master_vdu_id):
        # VDU Specification
        vdu = vnfd.vdu.add()
        vdu.id = str(uuid.uuid1())
        vdu.name = vdu_info['vduname']
        vdu.count = 1

        # specify the VM flavor
        vdu.vm_flavor.vcpu_count = 4
        vdu.vm_flavor.memory_mb = 8192
        vdu.vm_flavor.storage_gb = 32

        vdu.image = vdu_info['image']

        vdu.cloud_init = self.get_cloud_init(vnfd, vdu, master_vdu_id)

        for i in range(0, int(vdu_info['external_port'])):
            external_interface = vdu.external_interface.add()
            external_interface.name = 'eth%d' % (i+1)
            external_interface.vnfd_connection_point_ref = '%s/cp%d' % (self.name, i)
            if vnf_info['ext_port_type'] != 'virtio':
                external_interface.virtual_interface.type_yang = 'SR_IOV'
            else:
                external_interface.virtual_interface.type_yang = 'VIRTIO'

        print(vdu)
        return vdu

    def compose(self, template_info, credentials, endpoint_list, mgmt_port=8888):
        self.descriptor = RwVnfdYang.YangData_Vnfd_VnfdCatalog()
        self.id = str(uuid.uuid1())
        vnfd = self.descriptor.vnfd.add()
        vnfd.id = self.id
        vnfd.name = self.name
        vnfd.short_name = self.name
        vnfd.vendor = 'RIFT.io'
        vnfd.description = 'This is a RIFT.ware Trafgen VNF'
        vnfd.version = '1.0'
        self.vnfd = vnfd

        vnf_info = template_info['VNF']
        num_external_ports = 0

        for key,value in template_info.items():
           if key.startswith('VDU'):
              print("Starts With VDU %s" % key)
              vdu_name = value['vduname'] 
              if (vdu_name.split(".", -1))[2] == 'LEAD':
                print("LeadVM found")
                lead_vdu = self.create_vdu(vnfd, value, vnf_info, "")
                num_external_ports = num_external_ports + int(value['external_port'])

        for key,value in template_info.items():
           if key.startswith('VDU'):
              print("Starts With VDU %s" % key)
              vdu_name = value['vduname'] 
              if (vdu_name.split(".", -1))[2] != 'LEAD':
                print("nonLeadVM found")
                nonlead_vdu = self.create_vdu(vnfd, value, vnf_info, lead_vdu.id)
                num_external_ports = num_external_ports + int(value['external_port'])
                 

        print("Composing VNFD for %s" %  vnfd.name)
        # For fabric
        #internal_vld = vnfd.internal_vld.add()
        #internal_vld.id = str(uuid.uuid1())
        #internal_vld.name = 'fabric'
        #internal_vld.short_name = 'fabric'
        #internal_vld.description = 'Virtual link for internal fabric'
        #internal_vld.type_yang = 'ELAN'

        for i in range(0, num_external_ports):
            cp = vnfd.connection_point.add()
            cp.type_yang = 'VPORT'
            cp.name = '%s/cp%d' % (self.name, i)


        # HTTP endpoint of Monitoring params
        for endpoint in endpoint_list:
            endp = VnfdYang.YangData_Vnfd_VnfdCatalog_Vnfd_HttpEndpoint(
                    path=endpoint['path'], port=endpoint['port'], username=credentials['username'],
                    password=credentials['password'],polling_interval_secs=3
                    )
            vnfd.http_endpoint.append(endp)
            hdr1 = VnfdYang.YangData_Vnfd_VnfdCatalog_Vnfd_HttpEndpoint_Headers(
                            key='Content-type', value='application/vnd.yang.data+json')
            endp.headers.append(hdr1)
            hdr2 = VnfdYang.YangData_Vnfd_VnfdCatalog_Vnfd_HttpEndpoint_Headers(
                            key='Accept', value='json')
            endp.headers.append(hdr2)


            # Monitoring params
            for monp_dict in endpoint['mon-params']:
                monp = VnfdYang.YangData_Vnfd_VnfdCatalog_Vnfd_MonitoringParam.from_dict(monp_dict)
                monp.http_endpoint_ref = endpoint['path']
                vnfd.monitoring_param.append(monp)


#        # VDU Specification
#        vdu = vnfd.vdu.add()
#        # vdu.id = str(uuid.uuid1())
#        vdu.id = 'c1bb1a92-aa48-4908-89b2-5a78ff324953'
#        vdu.name = 'RW.VM.MASTER'
#        vdu.count = 1
#
#        # specify the VM flavor
#        vdu.vm_flavor.vcpu_count = 4
#        vdu.vm_flavor.memory_mb = 8192
#        vdu.vm_flavor.storage_gb = 32
#
#        # Management interface
#        mgmt_intf = vnfd.mgmt_interface
#        mgmt_intf.vdu_id = vdu.id
#        mgmt_intf.port = mgmt_port
#
#        vdu.cloud_init = cloud_init
#
#
#        # spcify the guest EPA
#        if use_epa:
#            #vdu.guest_epa.trusted_execution = True
#            vdu.guest_epa.mempage_size = 'PREFER_LARGE'
#            vdu.guest_epa.cpu_pinning_policy = 'DEDICATED'
#            vdu.guest_epa.cpu_thread_pinning_policy = 'PREFER'
#            vdu.guest_epa.numa_node_policy.node_cnt = 2
#            vdu.guest_epa.numa_node_policy.mem_policy = 'STRICT'
#
#            node = vdu.guest_epa.numa_node_policy.node.add()
#            node.id = 0
#            node.memory_mb = 8192
#            node.vcpu = [ 0, 1 ]
#
#            node = vdu.guest_epa.numa_node_policy.node.add()
#            node.id = 1
#            node.memory_mb = 8192
#            node.vcpu = [ 2, 3 ]

            # specify PCI passthru devices
            #pcie_dev = vdu.guest_epa.pcie_device.add()
            #pcie_dev.device_id = "ALIAS_ONE"
            #pcie_dev.count = 1
            #pcie_dev = vdu.guest_epa.pcie_device.add()
            #pcie_dev.device_id = "ALIAS_TWO"
            #pcie_dev.count = 3

            # specify the vswitch EPA
            #vdu.vswitch_epa.ovs_acceleration = 'DISABLED'
            #vdu.vswitch_epa.ovs_offload = 'DISABLED'

            # Specify the hypervisor EPA
            #vdu.hypervisor_epa.type_yang = 'PREFER_KVM'

            # Specify the host EPA
            #vdu.host_epa.cpu_model = 'PREFER_SANDYBRIDGE'
            #vdu.host_epa.cpu_arch = 'PREFER_X86_64'
            #vdu.host_epa.cpu_vendor = 'PREFER_INTEL'
            #vdu.host_epa.cpu_socket_count = 'PREFER_TWO'
            #vdu.host_epa.cpu_feature = [ 'PREFER_AES', 'PREFER_CAT' ]

        #vdu.image = template_info[key][image]

        #for i in range(0, 1):
        #    internal_cp = vdu.internal_connection_point.add()
        #    internal_cp.id = str(uuid.uuid1())
        #    internal_cp.type_yang = 'VPORT'
        #    internal_vld.internal_connection_point_ref.append(internal_cp.id)

        #    internal_interface = vdu.internal_interface.add()
        #    internal_interface.name = 'eth%d' % i
        #    internal_interface.vdu_internal_connection_point_ref = internal_cp.id
        #    internal_interface.virtual_interface.type_yang = 'VIRTIO'

#        for i in range(0, 1):
#            external_interface = vdu.external_interface.add()
#            external_interface.name = 'eth%d' % (i + 1)
#            external_interface.vnfd_connection_point_ref = '%s/cp%d' % (self.name, i)
#            if use_sriov:
#                external_interface.virtual_interface.type_yang = 'SR_IOV'
#            else:
#                external_interface.virtual_interface.type_yang = 'VIRTIO'


#        # VDU Specification - add second VDU
#        vdu = vnfd.vdu.add()
#        #vdu.id = str(uuid.uuid1())
#        vdu.id = 'd1bb1a92-aa48-4908-89b2-5a78ff324953'
#        vdu.name = 'RW.VM.FASTPATH.LEAD'
#        vdu.count = 1
#
#        # specify the VM flavor
#        vdu.vm_flavor.vcpu_count = 4
#        vdu.vm_flavor.memory_mb = 8192
#        vdu.vm_flavor.storage_gb = 32
#
#        vdu.cloud_init = MEMBERVM_CLOUD_INIT
#
#        # spcify the guest EPA
#        if use_epa:
#            #vdu.guest_epa.trusted_execution = True
#            vdu.guest_epa.mempage_size = 'PREFER_LARGE'
#            vdu.guest_epa.cpu_pinning_policy = 'DEDICATED'
#            vdu.guest_epa.cpu_thread_pinning_policy = 'PREFER'
#            vdu.guest_epa.numa_node_policy.node_cnt = 2
#            vdu.guest_epa.numa_node_policy.mem_policy = 'STRICT'
#
#            node = vdu.guest_epa.numa_node_policy.node.add()
#            node.id = 0
#            node.memory_mb = 4096
#            node.vcpu = [ 0, 1 ]
#
#            node = vdu.guest_epa.numa_node_policy.node.add()
#            node.id = 1
#            node.memory_mb = 4096
#            node.vcpu = [ 2, 3 ]

            # specify PCI passthru devices
            #pcie_dev = vdu.guest_epa.pcie_device.add()
            #pcie_dev.device_id = "ALIAS_ONE"
            #pcie_dev.count = 1
            #pcie_dev = vdu.guest_epa.pcie_device.add()
            #pcie_dev.device_id = "ALIAS_TWO"
            #pcie_dev.count = 3

            # specify the vswitch EPA
            #vdu.vswitch_epa.ovs_acceleration = 'DISABLED'
            #vdu.vswitch_epa.ovs_offload = 'DISABLED'

            # Specify the hypervisor EPA
            #vdu.hypervisor_epa.type_yang = 'PREFER_KVM'

            # Specify the host EPA
            #vdu.host_epa.cpu_model = 'PREFER_SANDYBRIDGE'
            #vdu.host_epa.cpu_arch = 'PREFER_X86_64'
            #vdu.host_epa.cpu_vendor = 'PREFER_INTEL'
            #vdu.host_epa.cpu_socket_count = 'PREFER_TWO'
            #vdu.host_epa.cpu_feature = [ 'PREFER_AES', 'PREFER_CAT' ]

        #vdu.image = image_name

        #for i in range(0, 1):
        #    internal_cp = vdu.internal_connection_point.add()
        #    internal_cp.id = str(uuid.uuid1())
        #    internal_cp.type_yang = 'VPORT'
        #    internal_vld.internal_connection_point_ref.append(internal_cp.id)

        #    internal_interface = vdu.internal_interface.add()
        #    internal_interface.name = 'eth%d' % i
        #    internal_interface.vdu_internal_connection_point_ref = internal_cp.id
        #    internal_interface.virtual_interface.type_yang = 'VIRTIO'

    def write_to_file(self, outdir, filename, output_format):
        dirpath = "%s/%s_vnfd/vnfd" % (outdir, filename)
        print("Dirpath %s" % dirpath)
        if not os.path.exists(dirpath):
            os.makedirs(dirpath)
        super(VirtualNetworkFunction, self).write_to_file(['vnfd', 'rw-vnfd'],
                                                          "%s/%s_vnfd/vnfd" % (outdir, filename),
                                                          output_format)

def get_multivm_mon_params1(path):
    if use_epa:
        return [
             {
               'id': '1',
                'name': 'Cp0 Tx Rate',
                'json_query_method': "OBJECTPATH",
                'value_type': "INT",
                'numeric_constraints': {'min_value':0, 'max_value':10000},
                'json_query_params': {'object_path':"$..*[@.portname is 'multivm_vnfd/cp0'].counters.'tx-rate-mbps'"},
                'description': 'Outgoing byte rate of interface',
                'group_tag': 'Group1',
                'widget_type': 'GAUGE',
                'units': 'mbps'
                },
             {
               'id': '2',
                'name': 'Cp0 Rx Rate',
                'json_query_method': "OBJECTPATH",
                'value_type': "INT",
                'numeric_constraints': {'min_value':0, 'max_value':10000},
                'json_query_params': {'object_path':"$..*[@.portname is 'multivm_vnfd/cp0'].counters.'rx-rate-mbps'"},
                'description': 'Incoming byte rate of interface',
                'group_tag': 'Group1',
                'widget_type': 'GAUGE',
                'units': 'mbps'
                },

            ]
    else:
        return [
             {
               'id': '1',
                'name': 'Cp0 Tx Rate',
                'json_query_method': "OBJECTPATH",
                'value_type': "INT",
                'numeric_constraints': {'min_value':0, 'max_value':1000},
                'json_query_params': {'object_path':"$..*[@.portname is 'multivm_vnfd/cp0'].counters.'tx-rate-mbps'"},
                'description': 'Outgoing byte rate of interface',
                'group_tag': 'Group1',
                'widget_type': 'GAUGE',
                'units': 'mbps'
                },
             {
               'id': '2',
                'name': 'Cp0 Rx Rate',
                'json_query_method': "OBJECTPATH",
                'value_type': "INT",
                'numeric_constraints': {'min_value':0, 'max_value':1000},
                'json_query_params': {'object_path':"$..*[@.portname is 'multivm_vnfd/cp0'].counters.'rx-rate-mbps'"},
                'description': 'Incoming byte rate of interface',
                'group_tag': 'Group1',
                'widget_type': 'GAUGE',
                'units': 'mbps'
                },

            ]


def generate_multivm_descriptors(fmt="json", write_to_file=False, out_dir="./", template_name="", template_info = {}):
    vnfname = template_info['VNF']['vnfname']
    multivm = VirtualNetworkFunction(vnfname+"_vnfd")
    multivm.compose(
            template_info,
            {'username':'fedora', 'password':'fedora'},
            [
            {'path': "api/operational/vnf-opdata/vnf/multivm,0/port-state",
             'port': 8008,
             'mon-params': get_multivm_mon_params1("interface"),
             },
            ],
            mgmt_port=2022,
            )

    if write_to_file:
        multivm.write_to_file(out_dir, template_name, fmt)

    return (multivm)


def main(argv=sys.argv[1:]):
    global outdir, output_format, use_epa, use_sriov, vnfname
    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--outdir', default='.')
    parser.add_argument('-i', '--srcdir', default='.')
    parser.add_argument('-f', '--format', default='json')
    parser.add_argument('-e', '--epa', action="store_true", default = False )
    parser.add_argument('-s', '--sriov', action="store_true", default = False )
    parser.add_argument('-v', '--vnfname', default = "multivm" )
    parser.add_argument('-t', '--template', default = "" )
    args = parser.parse_args()
    outdir = args.outdir
    output_format = args.format
    use_epa = args.epa
    use_sriov = args.sriov

    template_info={}
    with open(args.srcdir + "/templates/" + args.template ) as fd:
      s = [line.strip().split(None, 1) for line in fd]
      print("S0 %s" % s[0])
      print("S1 %s" % s[1])
      for l in s:
        print(l[1])
        j = [k.strip().split("=", -1) for k in l[1].strip().split(",",-1)]
        print(j)
        print(s[0])
        template_info[l[0]] = dict(j)
      for keys,values in template_info.items():
        print(keys)
        print(values)
    print(template_info)
    try:
      p=template_info['RW.VM.FASTPATH.LEAD']
      print(p)
      print(p['external_port'])
    except  KeyError:
      print("Element not found");

    try:
      vnf = template_info['VNF']
    except KeyError:
      print("Template does not have VNF specified");
      raise

    generate_multivm_descriptors(args.format, True, args.outdir, args.template, template_info)

if __name__ == "__main__":
    main()

