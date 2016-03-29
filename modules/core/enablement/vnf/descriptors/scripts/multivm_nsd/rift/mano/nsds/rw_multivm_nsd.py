#!/usr/bin/env python3

import sys
import os
import argparse
import uuid
import rift.vcs.component as vcs
import xml.etree.ElementTree as etree
import subprocess
from gi.repository import (
    RwYang,
    VnfdYang,
    RwVnfdYang,
    RwNsdYang,
    VldYang)

use_epa = False

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

    

class NetworkService(ManoDescriptor):
    def __init__(self, name):
        super(NetworkService, self).__init__(name)

    def read_vnf_config(self, filename):
      with open(filename, 'r') as content_file:
        content = content_file.read()
        print("**********")
        print(content)
        print("**********")
        return content


    def traffgen_config(self):
        trafgen_cfg = r'''
    <vnf-config xmlns="http://riftio.com/ns/riftware-1.0/mano-base">
      <vnf>
        <name>trafgen</name>
        <instance>0</instance>
        <network-context xmlns="http://riftio.com/ns/riftware-1.0/rw-vnf-base-config">
          <name>trafgen-lb</name>
          <interface>
            <name>N1TenGi-1</name>
            <bind>
              <port>multivm_vnfd/cp0</port>
            </bind>
          </interface>
        </network-context>
        <port xmlns="http://riftio.com/ns/riftware-1.0/rw-vnf-base-config">
          <name>multivm_vnfd/cp0</name>
          <open/>
          <application>
            <rx>rw_trafgen</rx>
            <tx>rw_trafgen</tx>
          </application>
          <receive-q-length>2</receive-q-length>
          <port-identity>
          <ip-address><rw_unique_index:rw_connection_point_name 1:multivm_vnfd/cp1></ip-address>
          <port-mode>direct</port-mode>
          </port-identity>
          <trafgen xmlns="http://riftio.com/ns/riftware-1.0/rw-trafgen">
            <transmit-params>
              <transmit-mode>
                <range/>
              </transmit-mode>
            </transmit-params>
            <range-template>
              <destination-mac>
                <dynamic>
                  <gateway><rw_unique_index:rw_connection_point_name 2:multivm_vnfd/cp1></gateway>
                </dynamic>
              </destination-mac>
              <source-ip>
                <start><rw_unique_index:rw_connection_point_name 1:multivm_vnfd/cp1></start>
                <minimum><rw_unique_index:rw_connection_point_name 1:multivm_vnfd/cp1></minimum>
                <maximum><rw_unique_index:rw_connection_point_name 1:multivm_vnfd/cp1></maximum>
                <increment>1</increment>
              </source-ip>
              <destination-ip>
                <start><rw_unique_index:rw_connection_point_name 2:multivm_vnfd/cp1></start>
                <minimum><rw_unique_index:rw_connection_point_name 2:multivm_vnfd/cp1></minimum>
                <maximum><rw_unique_index:rw_connection_point_name 2:multivm_vnfd/cp1></maximum>
                <increment>1</increment>
              </destination-ip>
              <source-port>
                <start>10000</start>
                <minimum>10000</minimum>
                <maximum>10128</maximum>
                <increment>1</increment>
              </source-port>
              <destination-port>
                <start>5678</start>
                <minimum>5678</minimum>
                <maximum>5678</maximum>
                <increment>1</increment>
              </destination-port>
              <packet-size>
                <start>512</start>
                <minimum>512</minimum>
                <maximum>512</maximum>
                <increment>1</increment>
              </packet-size>
            </range-template>
          </trafgen>
        </port>
      </vnf>
    </vnf-config>
    <logging xmlns="http://riftio.com/ns/riftware-1.0/rwlog-mgmt">
      <sink>
        <name>syslog</name>
        <server-address><rw_mgmt_ip></server-address>
        <port>514</port>
      </sink>
    </logging>
        '''
        return trafgen_cfg

    def trafsink_config(self):
        trafsink_cfg  = r'''
    <vnf-config xmlns="http://riftio.com/ns/riftware-1.0/mano-base">
      <vnf>
        <name>trafgen</name>
        <instance>0</instance>
        <network-context xmlns="http://riftio.com/ns/riftware-1.0/rw-vnf-base-config">
          <name>lb-trafsink</name>
          <interface>
            <name>N3TenGigi-1</name>
            <bind>
              <port>multivm_vnfd/cp0</port>
            </bind>
          </interface>
        </network-context>
        <port xmlns="http://riftio.com/ns/riftware-1.0/rw-vnf-base-config">
          <name>multivm_vnfd/cp0</name>
          <open/>
          <application>
            <rx>rw_trafgen</rx>
            <tx>rw_trafgen</tx>
          </application>
          <receive-q-length>2</receive-q-length>
          <port-identity>
          <ip-address><rw_unique_index:rw_connection_point_name 2:multivm_vnfd/cp1></ip-address>
          <port-mode>direct</port-mode>
          </port-identity>
          <trafgen xmlns="http://riftio.com/ns/riftware-1.0/rw-trafgen">
            <receive-param>
              <receive-echo>
                <on/>
              </receive-echo>
            </receive-param>
          </trafgen>
        </port>
      </vnf>
    </vnf-config>
    <logging xmlns="http://riftio.com/ns/riftware-1.0/rwlog-mgmt">
      <sink>
        <name>syslog</name>
        <server-address><rw_mgmt_ip></server-address>
        <port>514</port>
      </sink>
    </logging>
        '''
        return trafsink_cfg
        
    def default_config(self, const_vnfd, vnfd, src_dir, vnf_info):
        vnf_config = const_vnfd.vnf_configuration
        
        vnf_config.config_access.username = 'admin'
        vnf_config.config_access.password = 'admin'
        vnf_config.input_params.config_priority = 0
        vnf_config.input_params.config_delay = 0

        # Select "netconf" configuration
        vnf_config.config_type = 'netconf'
        vnf_config.netconf.target = 'running'
        vnf_config.netconf.port = 2022

        # print("### TBR ### vnfd.name = ", vnfd.name)
        
        if vnf_info['config'] != "":
            vnf_config.input_params.config_priority = 1
            # First priority config delay will delay the entire NS config delay
            vnf_config.input_params.config_delay = 120
            conf_file = src_dir + "/config/" + vnf_info['config']
            vnf_config.config_template = self.read_vnf_config(conf_file)

        print("### TBR ###", vnfd.name, "vng_config = ", vnf_config)

    def compose(self, vnfd_list, src_dir, template_info):
        self.descriptor = RwNsdYang.YangData_Nsd_NsdCatalog()
        self.id = str(uuid.uuid1())
        nsd = self.descriptor.nsd.add()
        nsd.id = self.id
        nsd.name = self.name
        nsd.short_name = self.name
        nsd.vendor = 'RIFT.io'
        nsd.description = 'NS Trafgen-Trafink'
        nsd.version = '1.0'

        i = 1
        for key,vnfd in vnfd_list.items():
            constituent_vnfd = nsd.constituent_vnfd.add()
            constituent_vnfd.member_vnf_index = i
            constituent_vnfd.vnfd_id_ref = vnfd.id
            i = i+1

            # Add Configuration defaults
            self.default_config(constituent_vnfd, vnfd, src_dir, template_info[key])
        self.nsd = nsd
        print(nsd)


    def compose_cpgroup(self, name, desc, cpgroup , vld_info):
#        vld = self.nsd.vld.add()
#        vld.id = str(uuid.uuid1())
#        vld.name = name
#        vld.short_name = name
#        vld.vendor = 'RIFT.io'
#        vld.description = desc
#        vld.version = '1.0'
#        vld.type_yang = 'ELAN'
#        if use_epa:
#            vld.provider_network.physical_network = physnet
#            vld.provider_network.overlay_type = 'FLAT'
#
#        for cp in cpgroup:
#            cpref = vld.vnfd_connection_point_ref.add()
#            cpref.member_vnf_index_ref = cp[0]
#            cpref.vnfd_id_ref = cp[1]
#            cpref.vnfd_connection_point_ref = cp[2]

        vld = self.nsd.vld.add()
        vld.id = str(uuid.uuid1())
        vld.name = name
        vld.short_name = name
        vld.vendor = 'RIFT.io'
        vld.description = desc
        vld.version = '1.0'
        vld.type_yang = 'ELAN'

        vld.provider_network.physical_network = vld_info['provider']
        vld.provider_network.overlay_type = vld_info['overlay']

        for cp in cpgroup:
            cpref = vld.vnfd_connection_point_ref.add()
            cpref.member_vnf_index_ref = cp[0]
            cpref.vnfd_id_ref = cp[1]
            cpref.vnfd_connection_point_ref = cp[2]


    def write_to_file(self, template_name, outdir, output_format):
        dirpath = "%s/%s_multivm_nsd/nsd" % (outdir, template_name)
        if not os.path.exists(dirpath):
            os.makedirs(dirpath)
        super(NetworkService, self).write_to_file(["nsd", "rw-nsd"],
                                                  "%s/%s_multivm_nsd/nsd" % (outdir, template_name),
                                                  output_format)

    def read_from_file(self, module_list, infile, input_format):
        model = RwYang.Model.create_libncx()
        for module in module_list:
            model.load_module(module)

        vnf = VnfdYang.YangData_Vnfd_VnfdCatalog_Vnfd()
        if input_format == 'json':
            json_str = open(infile).read()

            vnf.from_json(model, json_str)

        elif input_format.strip() == 'xml':
            tree = etree.parse(infile)
            root = tree.getroot()
            xmlstr = etree.tostring(root, encoding="unicode")

            vnf.from_xml_v2(model, xmlstr)
        else:
            raise("Invalid input format for the descriptor")

        return vnf



def generate_multivm_nsd_descriptors(fmt="json", write_to_file=False, out_dir="./", src_dir="./", template="", template_info={}):
    # List of connection point groups
    # Each connection point group refers to a virtual link
    # the CP group consists of tuples of connection points
    model = RwYang.Model.create_libncx()
    nsd_catalog = NetworkService(template_info['NS']['nsname'] + "_nsd")

#    rift_root_dir = os.environ['RIFT_ROOT']
#    mano_vnfds_dir = rift_root_dir + '/.build/modules/ext/vnfs/src/ext_vnfs-build'

    vnfd = {}
    # Open vnf pkg and read vnfdid
    for key,value in template_info.items():
      if key.startswith('VNF'):
        print("Starts With VNF %s" % key)

        vnf_info = value
        vnf_pkg = vnf_info['pkgname']
        vnf_dir = vnf_pkg.split(".", -1)[0]
        vnfd_dir = "./"+ vnf_dir +"/vnfd/"
        print(vnf_dir)
        cmd = "tar -zxvf {}{}".format(out_dir, '/../multivm_vnfd/' + vnf_pkg)
        print("Cmd is ", cmd)
        subprocess.call(cmd, shell=True)
        file_names = [fn for fn in os.listdir(vnfd_dir) if any(fn.endswith(ext) for ext in ["xml", "json"])]
        if len(file_names) != 1:
          print("%s have more files than expected" % vnfd_dir)
          exit
        if file_names[0].endswith("xml"):
          vnfd[key] = nsd_catalog.read_from_file(["vnfd"], vnfd_dir + "/" + file_names[0], "xml")
        else:
          vnfd[key] = nsd_catalog.read_from_file(["vnfd"], vnfd_dir + "/" + file_names[0], "json")
        print(vnfd[key])
        subprocess.call('rm -rf ./' + vnf_dir, shell=True)

    nsd_catalog.compose(vnfd, src_dir, template_info)

    for key,value in template_info.items():
      if key.startswith('VLD'):
        print("Starts With VLD %s" % key)
        cpgroup = []
        i = 1
        for cp,cp_info in value.items():
           if cp.startswith('cp'):
             print("Starts With cp %s" % cp)
             sp = cp_info.split(":", -1);
             vnfn = sp[0]
             cpindex = int(sp[1])-1
             cpname = vnfd[vnfn].connection_point[cpindex].name
             print(cpname)
             cpgroup.append((i, vnfd[vnfn].id, cpname))
             i = i + 1

        print(cpgroup)
        #cpgroup =  [ (1, tg_vnfd.id, 'multivm_vnfd/cp1'), (2, ts_vnfd.id, 'multivm_vnfd/cp1') ] 
        nsd_catalog.compose_cpgroup(value['linkname'], 'Link', cpgroup, value)

    print(nsd_catalog.nsd)

    if write_to_file:
        nsd_catalog.write_to_file(template, out_dir, fmt)

    return (nsd_catalog)


def main(argv=sys.argv[1:]):
    global outdir, output_format, use_epa
    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--outdir', default='.')
    parser.add_argument('-s', '--srcdir', default='.')
    parser.add_argument('-f', '--format', default='json')
    parser.add_argument('-e', '--epa', action="store_true", default = False )
    parser.add_argument('-t', '--template', default = "" )
    args = parser.parse_args()
    outdir = args.outdir
    output_format = args.format
    use_epa = args.epa

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
      vnf = template_info['NS']
    except KeyError:
      print("Template does not have NS specified");
      raise

    generate_multivm_nsd_descriptors(args.format, True, args.outdir, args.srcdir, args.template, template_info)

if __name__ == "__main__":
    main()

