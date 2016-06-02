# Copyright 2016 RIFT.io Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import argparse
import logging
import logging.config
import os
import shutil
import tarfile
import tempfile
import zipfile

import rift.mano.tosca_translator.shell as shell


class ToscaPackage(object):

    SUPPORTED_INPUTS = (YAML, ZIP) = ('yaml', 'zip')
    FILE_EXTS = (ZIP, TARGZ) = ('.zip', '.tar.gz')

    def __init__(self, log, in_file, out_file=None):
        self.log = log
        self.in_file = os.path.abspath(os.path.normpath(in_file))
        if out_file:
            self.out_file = os.path.abspath(os.path.normpath(out_file))
        if zipfile.is_zipfile(in_file):
            if in_file.endswith(self.TARGZ):
                if out_file is None:
                    self.out_file = self.in_file
                # Currently we store all the files uploaded
                # in lauchpad as tar.gz
                self.in_file = self.in_file.replace(self.TARGZ, self.ZIP)
                shutil.move(self.out_file, self.in_file)
            elif in_file.endswith(self.ZIP):
                if out_file is None:
                    self.out_file = self.in_file.replace(self.ZIP, self.TARGZ)
            self.log.debug("Tosca file: {}, Output file: {}".
                           format(self.in_file, self.out_file))
        else:
            err_msg = "{} is not a zip file.".format(in_file)
            self.log.error(err_msg)
            raise ValueError(err_msg)

    def translate(self):
        try:
            out_file = None
            prevdir = os.getcwd()
            # Create a temp directory to generate the yang descriptors
            with tempfile.TemporaryDirectory() as tmpdirname:
                output_dir = tmpdirname+'/yang'
                tmpl_file = '--template-file='+self.in_file
                out_dir = '--output-dir='+output_dir
                trans_args = [tmpl_file, out_dir]
                self.log.debug("Calling tosca-translator with args:{}".
                               format(trans_args))
                shell.main(args=trans_args, log=self.log)

                # Get the list of translated files
                os.chdir(output_dir)
                flist = []
                for root, dirs, files in os.walk(output_dir):
                    rel_dir = (root.replace(output_dir, '')).lstrip('/')
                    for f in files:
                        flist.append(os.path.join(rel_dir, f))
                self.log.debug("File list to archive: {}".format(flist))

                # Generate a tar file with the output files
                with tarfile.open(self.out_file, 'w:gz') as tar:
                    for f in flist:
                        tar.add(f)
                out_file = self.out_file
                self.log.debug("Output file: {}".format(out_file))
        except Exception as e:
            self.log.error("Error processing TOSCA file {}: {}".
                           format(self.in_file, e))
            self.log.exception(e)
        finally:
                os.chdir(prevdir)

        return out_file

    @staticmethod
    def is_tosca_package(in_file):
        if zipfile.is_zipfile(in_file):
            return True
        else:
            return False


def main(raw_args=None, log=None):
    parser = argparse.ArgumentParser(
        description='RIFT TOSCA translator for descriptors')
    parser.add_argument(
        "-f",
        "--csar-file",
        required=True,
        help="TOSCA CSAR file to translate")
    parser.add_argument(
        "-o",
        "--output-file",
        help="Output filename")
    parser.add_argument(
        "--debug",
        help="Enable debug logging",
        action="store_true")
    if raw_args:
        args = parser.parse_args(raw_args)
    else:
        args = parser.parse_args()

    if log is None:
        if args.debug:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.ERROR)
        log = logging.getLogger("tosca-translator")

    return ToscaPackage(log, args.csar_file,
                        out_file=args.output_file).translate()


if __name__ == '__main__':
    main()
