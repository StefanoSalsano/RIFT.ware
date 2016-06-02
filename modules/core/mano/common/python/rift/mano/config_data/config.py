import json
import os
import xml.etree.ElementTree as etree
import yaml

class ConfigPrimitiveConvertor(object):
    PARAMETER = "parameter"
    PARAMETER_GROUP = "parameter_group"
    CONFIG_PRIMITIVE = "config_primitive"
    INITIAL_CONFIG_PRIMITIVE = "initial_config_primitive"

    def _extract_param(self, param, field="default_value"):
        key = param.name
        value = getattr(param, field, None)

        if value is not None:
            setattr(param, field, None)

        return key, value

    def _extract_parameters(self, parameters, input_data, field="default_value"):
        input_data[self.PARAMETER] = {}
        for param in parameters:
            key, value = self._extract_param(param, field)

            if value is None:
                continue

            input_data[self.PARAMETER][key] = value

        if not input_data[self.PARAMETER]:
            del input_data[self.PARAMETER]

    def _extract_parameter_group(self, param_groups, input_data):
        input_data[self.PARAMETER_GROUP] = {}
        for param_group in param_groups:
            input_data[self.PARAMETER_GROUP][param_group.name] = {}
            for param in param_group.parameter:
                key, value = self._extract_param(param)

                if value is None:
                    continue

                input_data[self.PARAMETER_GROUP][param_group.name][key] = value

        if not input_data[self.PARAMETER_GROUP]:
            del input_data[self.PARAMETER_GROUP]

    def extract_nsd_config(self, nsd, format="yaml"):
        input_data = {}
        for config_primitive in nsd.config_primitive:
            input_data[config_primitive.name] = {}
            self._extract_parameters(
                    config_primitive.parameter,
                    input_data[config_primitive.name])

            self._extract_parameter_group(
                config_primitive.parameter_group,
                input_data[config_primitive.name])

        if format == "json":
            return json.dumps(input_data)
        elif format == "yaml":
            return yaml.dump(input_data, default_flow_style=False)

    def extract_vnfd_config(self, vnfd, format="yaml"):
        input_data = {}

        input_data[self.CONFIG_PRIMITIVE] = {}
        for config_primitive in vnfd.mgmt_interface.vnf_configuration.config_primitive:
            input_data[self.CONFIG_PRIMITIVE][config_primitive.name] = {}
            self._extract_parameters(
                    config_primitive.parameter,
                    input_data[self.CONFIG_PRIMITIVE][config_primitive.name])

            if not input_data[self.CONFIG_PRIMITIVE][config_primitive.name]:
                del input_data[self.CONFIG_PRIMITIVE][config_primitive.name]

        if not input_data[self.CONFIG_PRIMITIVE]:
            del input_data[self.CONFIG_PRIMITIVE]

        input_data[self.INITIAL_CONFIG_PRIMITIVE] = {}
        for in_config_primitive in vnfd.mgmt_interface.vnf_configuration.initial_config_primitive:
            input_data[self.INITIAL_CONFIG_PRIMITIVE][in_config_primitive.name] = {}
            self._extract_parameters(
                    in_config_primitive.parameter,
                    input_data[self.INITIAL_CONFIG_PRIMITIVE][in_config_primitive.name],
                    field="value")

            if not input_data[self.INITIAL_CONFIG_PRIMITIVE][in_config_primitive.name]:
                del input_data[self.INITIAL_CONFIG_PRIMITIVE][in_config_primitive.name]

        if not input_data[self.INITIAL_CONFIG_PRIMITIVE]:
            del input_data[self.INITIAL_CONFIG_PRIMITIVE]


        if format == "json":
            return json.dumps(input_data)
        elif format == "yaml":
            return yaml.dump(input_data, default_flow_style=False)

    def merge_params(self, parameters, input_config, field="default_value"):
        for param in parameters:
            try:
                setattr(param, field, input_config[param.name])
            except KeyError:
                pass

    def merge_nsd_config(self, nsd, input_data):
        # if input_data_format == "yaml":
        #     input_data = yaml.load(input_data)
        # elif input_data_format == "json":
        #     input_data = json.load(input_data)

        for config_primitive in nsd.config_primitive:
            try:
                cfg = input_data[config_primitive.name]
            except KeyError:
                continue

            self.merge_params(
                    config_primitive.parameter,
                    cfg[self.PARAMETER])

            for param_group in config_primitive.parameter_group:
                self.merge_params(
                        param_group.parameter,
                        cfg[self.PARAMETER_GROUP][param_group.name])


    def merge_vnfd_config(self, vnfd, input_data):

        for config_primitive in vnfd.mgmt_interface.vnf_configuration.config_primitive:
            try:
                cfg = input_data[self.CONFIG_PRIMITIVE][config_primitive.name]
            except KeyError:
                continue

            self.merge_params(
                config_primitive.parameter,
                cfg[self.PARAMETER])

        for in_config_primitive in vnfd.mgmt_interface.vnf_configuration.initial_config_primitive:
            try:
                cfg = input_data[self.INITIAL_CONFIG_PRIMITIVE][in_config_primitive.name]
            except KeyError:
                continue

            self.merge_params(
                in_config_primitive.parameter,
                cfg[self.PARAMETER],
                field="value")





class ConfigStore(object):
    """Convenience class that fetches all the instance related data from the
    $RIFT_ARTIFACTS/launchpad/libs directory.
    """
    def __init__(self, log):
        """
        Args:
            log : Log handle.
        """
        self._log = log
        self.converter = ConfigPrimitiveConvertor()


    def merge_vnfd_config(self, nsd_id, vnfd):
        """Load the vnfd config from the config directory.

        Args:
            nsd_id (str): Id of the NSD object
            const_vnfd : Constituent VNFD object containing the VNFD id and
                the member index ref.

        Returns:
            Vnfd Gi object containing the vnf configuration.
        """
        nsd_archive = os.path.join(
                        os.getenv('RIFT_ARTIFACTS'),
                        "launchpad/libs",
                        nsd_id,
                        "config")

        self._log.info("Looking for config from the archive {}".format(nsd_archive))

        if not os.path.exists(nsd_archive):
            return

        config_file = os.path.join(
                            nsd_archive,
                            "{}.yaml".format(vnfd.id))

        self._log.info("Loaded config file {}".format(config_file))

        input_data = self.read_from_file(config_file)
        self.converter.merge_vnfd_config(vnfd, input_data)

    def read_from_file(self, filename):
        with open(filename) as fh:
            input_data = yaml.load(fh)
        return input_data

    def merge_nsd_config(self, nsd):
        nsd_archive = os.path.join(
                        os.getenv('RIFT_ARTIFACTS'),
                        "launchpad/libs",
                        nsd.id,
                        "config")

        self._log.info("Looking for config from the archive {}".format(nsd_archive))

        if not os.path.exists(nsd_archive):
            return

        config_file = os.path.join(
                            nsd_archive,
                            "{}.yaml".format(nsd.id))
        if not os.path.exists(config_file):
            return

        input_data = self.read_from_file(config_file)
        self.converter.merge_nsd_config(nsd, input_data)
