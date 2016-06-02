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

# Copyright 2016 RIFT.io Inc


import argparse
import logging
import logging.config
import os
import shutil
import tempfile
import zipfile

import magic

from rift.mano.tosca_translator.common.utils import _
from rift.mano.tosca_translator.common.utils import ChecksumUtils
from rift.mano.tosca_translator.rwmano.tosca_translator import TOSCATranslator

from toscaparser.tosca_template import ToscaTemplate


"""
Test the tosca translation from command line as:
#translator
  --template-file=<path to the YAML template or CSAR>
  --template-type=<type of template e.g. tosca>
  --parameters="purpose=test"
  --output_dir=<output directory>
  --validate_only
Takes four user arguments,
1. type of translation (e.g. tosca) (required)
2. Path to the file that needs to be translated (required)
3. Input parameters (optional)
4. Write to output files in a dir (optional), else print on screen

In order to use translator to only validate template,
without actual translation, pass --validate-only along with
other required arguments.

"""


class TranslatorShell(object):

    SUPPORTED_TYPES = ['tosca']
    COPY_DIRS = ['images']
    SUPPORTED_INPUTS = (YAML, ZIP) = ('yaml', 'zip')

    def _parse_args(self, raw_args=None):
        parser = argparse.ArgumentParser(
            description='RIFT TOSCA translator for descriptors')
        parser.add_argument(
            "-f",
            "--template-file",
            required=True,
            help="Template file to translate")
        parser.add_argument(
            "-o",
            "--output-dir",
            help="Directory to output")
        parser.add_argument(
            "-t",
            "--template-type",
            default='tosca',
            help="Template file type. Default tosca")
        parser.add_argument(
            "-p", "--parameters",
            help="Input parameters")
        parser.add_argument(
            "--no-gi",
            help="Do not use the YANG GI to generate descriptors",
            action="store_true")
        parser.add_argument(
            "--validate-only",
            help="Validate template, no translation",
            action="store_true")
        parser.add_argument(
            "--debug",
            help="Enable debug logging",
            action="store_true")
        if raw_args:
            args = parser.parse_args(raw_args)
        else:
            args = parser.parse_args()
        return args

    def main(self, raw_args=None, log=None):
        args = self._parse_args(raw_args)
        if log is None:
            if args.debug:
                logging.basicConfig(level=logging.DEBUG)
            else:
                logging.basicConfig(level=logging.ERROR)
            log = logging.getLogger("tosca-translator")

        self.log = log
        path = os.path.abspath(args.template_file)
        self.in_file = path
        a_file = os.path.isfile(path)
        if not a_file:
            msg = _("The path %(path)s is not a valid file.") % {
                'path': args.template_file}
            log.error(msg)
            raise ValueError(msg)
        # Get the file type
        self.ftype = self._get_file_type()
        self.log.debug(_("Input file {0} is of type {1}").
                       format(path, self.ftype))
        template_type = args.template_type
        if template_type not in self.SUPPORTED_TYPES:
            msg = _("%(value)s is not a valid template type.") % {
                'value': template_type}
            log.error(msg)
            raise ValueError(msg)

        parsed_params = {}
        if args.parameters:
            parsed_params = self._parse_parameters(args.parameters)

        if template_type == 'tosca' and args.validate_only:
            tpl = ToscaTemplate(path, parsed_params, a_file)
            log.debug(_('Template = {}').format(tpl.__dict__))
            msg = (_('The input "%(path)s" successfully passed '
                     'validation.') % {'path': path})
            print(msg)
        else:
            self.use_gi = not args.no_gi
            tpl = self._translate(template_type, path, parsed_params,
                                  a_file)
            if tpl:
                self._write_output(tpl, args.output_dir)

    def _parse_parameters(self, parameter_list):
        parsed_inputs = {}
        if parameter_list:
            # Parameters are semi-colon separated
            inputs = parameter_list.replace('"', '').split(';')
            # Each parameter should be an assignment
            for param in inputs:
                keyvalue = param.split('=')
                # Validate the parameter has both a name and value
                msg = _("'%(param)s' is not a well-formed parameter.") % {
                    'param': param}
                if keyvalue.__len__() is 2:
                    # Assure parameter name is not zero-length or whitespace
                    stripped_name = keyvalue[0].strip()
                    if not stripped_name:
                        self.log.error(msg)
                        raise ValueError(msg)
                    # Add the valid parameter to the dictionary
                    parsed_inputs[keyvalue[0]] = keyvalue[1]
                else:
                    self.log.error(msg)
                    raise ValueError(msg)
        return parsed_inputs

    def _translate(self, sourcetype, path, parsed_params, a_file):
        output = None
        if sourcetype == "tosca":
            self.log.debug(_('Loading the tosca template.'))
            tosca = ToscaTemplate(path, parsed_params, a_file)
            self.log.debug(_('TOSCA Template: {}').format(tosca.__dict__))
            translator = TOSCATranslator(self.log, tosca, parsed_params,
                                         use_gi=self.use_gi)
            self.log.debug(_('Translating the tosca template.'))
            output = translator.translate()
        return output

    def _write_output(self, output, output_dir=None):
        if output:
            for key in output.keys():
                if output_dir:
                    # Create sub dirs like nsd, vnfd etc
                    subdir = os.path.join(output_dir, key)
                    os.makedirs(subdir, exist_ok=True)
                for desc in output[key]:
                    if output_dir:
                        output_file = os.path.join(subdir,
                                                   desc['name']+'.yml')
                        self.log.debug(_("Writing file {0}").
                                       format(output_file))
                        with open(output_file, 'w+') as f:
                            f.write(desc['yang'])
                    else:
                        print(_("Descriptor {0}:\n{1}").
                              format(desc['name'], desc['yang']))

            # Copy other directories, if present in zip
            if output_dir and self.ftype == self.ZIP:
                self.log.debug(_("Input is zip file, copy dirs"))
                # Unzip the file to a tmp location
                with tempfile.TemporaryDirectory() as tmpdirname:
                    prevdir = os.getcwd()
                    try:
                        with zipfile.ZipFile(self.in_file) as zf:
                            zf.extractall(tmpdirname)
                        os.chdir(tmpdirname)
                        dirs = [d for d in os.listdir(tmpdirname)
                                if os.path.isdir(d)]
                        for d in dirs:
                            if d in self.COPY_DIRS:
                                shutil.move(d, output_dir)
                    except Exception as e:
                        msg = _("Exception extracting input file {0}: {1}"). \
                              format(self.in_file, e)
                        self.log.error(msg)
                        raise e
                    finally:
                        os.chdir(prevdir)
                # Create checkum for all files
                flist = {}
                for root, dirs, files in os.walk(output_dir):
                    rel_dir = root.replace(output_dir+'/', '')
                    for f in files:
                        flist[os.path.join(rel_dir, f)] = \
                                        ChecksumUtils.get_md5(os.path.join(root, f))
                self.log.debug(_("Files in output_dir: {}").format(flist))
                chksumfile = os.path.join(output_dir, 'checksums.txt')
                with open(chksumfile, 'w') as c:
                    for key in sorted(flist.keys()):
                        c.write("{}  {}\n".format(flist[key], key))

    def _get_file_type(self):
        m = magic.open(magic.MAGIC_MIME)
        m.load()
        typ = m.file(self.in_file)
        if typ.startswith('text/plain'):
            # Assume to be yaml
            return self.YAML
        elif typ.startswith('application/zip'):
            return self.ZIP
        else:
            msg = _("The file {0} is not a supported type: {1}"). \
                  format(self.in_file, typ)
            self.log.error(msg)
            raise ValueError(msg)


def main(args=None, log=None):
    TranslatorShell().main(raw_args=args, log=log)


if __name__ == '__main__':
    main()
