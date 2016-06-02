#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# Copyright 2016 RIFT.io Inc


import uuid

import yaml

from rift.mano.tosca_translator.common.utils import _

from rift.mano.tosca_translator.common.utils import dict_convert_values_to_str

try:
    import gi
    gi.require_version('RwYang', '1.0')
    gi.require_version('RwNsdYang', '1.0')
    gi.require_version('NsdYang', '1.0')

    from gi.repository import NsdYang
    from gi.repository import RwNsdYang
    from gi.repository import RwYang
except ImportError:
    pass
except ValueError as e:
    pass


class ManoTemplate(object):
    '''Container for full RIFT.io MANO template.'''

    YANG_NS = (NSD, VNFD) = ('nsd', 'vnfd')
    OUTPUT_FIELDS = (NAME, YANG) = ('name', 'yang')

    def __init__(self, log):
        self.log = log
        self.resources = []
        self.outputs = []
        self.parameters = []
        self.description = "Translated from TOSCA"
        self.metadata = None
        self.policies = []
        self.groups = []

    def output_to_yang(self, use_gi=False, indent=4):
        self.log.debug(_('Converting translated output to yang format.'))

        vnfds = []

        if use_gi:
            try:
                nsd_cat = RwNsdYang.YangData_Nsd_NsdCatalog()
                nsd = nsd_cat.nsd.add()
                nsd.id = str(uuid.uuid1())
                nsd.name = self.metadata['name']
                nsd.description = self.description
                nsd.vendor = self.metadata['vendor']
                nsd.short_name = self.metadata['name']
                nsd.version = self.metadata['version']
            except Exception as e:
                self.log.error(_("Unable to use YANG GI to generate "
                                 "descriptors, falling back to alternate "
                                 "method: {}").format(e))
                self.log.exception(e)
                use_gi = False

        if not use_gi:
            nsd = {
                'id': str(uuid.uuid1()),
                'name': self.metadata['name'],
                'description': self.description,
                'vendor': self.metadata['vendor'],
                'short-name': self.metadata['name'],
                'version': self.metadata['version'],
            }

        for resource in self.resources:
            # Do the vnfds first
            if resource.type == 'vnfd':
                resource.generate_yang_model(nsd, vnfds, use_gi=use_gi)

        for resource in self.resources:
            # Do the other nodes
            if resource.type != 'vnfd':
                resource.generate_yang_model(nsd, vnfds, use_gi=use_gi)

        for group in self.groups:
            group.generate_yang_model(nsd, vnfds, use_gi=use_gi)

        for policy in self.policies:
            policy.generate_yang_model(nsd, vnfds, use_gi=use_gi)

        # Add input params to nsd
        if use_gi:
            for param in self.parameters:
                nsd.input_parameter_xpath.append(
                 NsdYang.YangData_Nsd_NsdCatalog_Nsd_InputParameterXpath(
                    xpath=param.get_xpath(),
                    )
                )
        else:
            nsd['input-parameter-xpath'] = []
            for param in self.parameters:
                nsd['input-parameter-xpath'].append(
                    {'xpath': param.get_xpath()})

        tpl = {}
        # Do the final processing and convert to yaml string
        # Convert all non string to strings
        if use_gi:
            nsd_pf = self.get_yaml(['nsd', 'rw-nsd'], nsd_cat)
            name = nsd_cat.nsd[0].name
            tpl[self.NSD] = [{self.NAME: name,
                              self.YANG: nsd_pf}]
            tpl[self.VNFD] = []
            for vnfd in vnfds:
                vnfd_pf = self.get_yaml(['vnfd', 'rw-vnfd'], vnfd)
                name = vnfd.vnfd[0].name
                tpl[self.VNFD].append({self.NAME: name,
                                       self.YANG: vnfd_pf})
        else:
            # In case of non gi proecssing,
            # - convert all values to string
            # - enclose in a catalog dict
            # - prefix all keys with nsd or vnfd
            nsd_pf = self.prefix_dict(
                self.add_cat(dict_convert_values_to_str(nsd),
                             self.NSD),
                self.NSD)
            name = self._get_name(nsd_pf, self.NSD)
            tpl[self.NSD] = [{self.NAME: name,
                              self.YANG: yaml.dump(nsd_pf,
                                                   default_flow_style=False)}]

            tpl[self.VNFD] = []
            for vnfd in vnfds:
                vnfd_pf = self.prefix_dict(
                    self.add_cat(dict_convert_values_to_str(vnfd),
                                 self.VNFD),
                    self.VNFD)
                name = self._get_name(vnfd_pf, self.VNFD)
                tpl[self.VNFD].append({self.NAME: name,
                                       self.YANG:  yaml.dump(vnfd_pf,
                                                    default_flow_style=False)})

        self.log.debug(_("NSD: {0}").format(tpl[self.NSD]))
        self.log.debug(_("VNFDs:"))
        for vnfd in tpl[self.VNFD]:
            self.log.debug(_("{0}").format(vnfd))

        return tpl

    def _get_name(self, d, pf):
        '''Get the name given for the descriptor'''
        # Search within the desc for a key pf:name
        key = pf+':'+self.NAME
        name = None
        if isinstance(d, dict):
            # If it is a dict, search for pf:name
            if key in d:
                return d[key]
            else:
                for k, v in d.items():
                    result = self._get_name(v, pf)
                    if result:
                        return result
        elif isinstance(d, list):
            for memb in d:
                result = self._get_name(memb, pf)
                if result:
                        return result

    def prefix_dict(self, d, pf):
        '''Prefix all keys of a dict with a specific prefix:'''
        if isinstance(d, dict):
            dic = {}
            for key in d.keys():
                # Only prefix keys without any prefix
                # so later we can do custom prefixing
                # which will not get overwritten here
                if ':' not in key:
                    dic[pf+':'+key] = self.prefix_dict(d[key], pf)
                else:
                    dic[key] = self.prefix_dict(d[key], pf)
            return dic
        elif isinstance(d, list):
            arr = []
            for memb in d:
                arr.append(self.prefix_dict(memb, pf))
            return arr
        else:
            return d

    def add_cat(self, desc, pf):
        return {pf+'-catalog': {pf: [desc]}}

    def get_yaml(self, module_list, desc):
        model = RwYang.Model.create_libncx()
        for module in module_list:
            model.load_module(module)
        return desc.to_yaml(model)
