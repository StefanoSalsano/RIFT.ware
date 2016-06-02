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

'''
Unittest for TOSCA tranlator to RIFT.io YANG model

Run using pytest
'''

import os
import shutil
import tempfile

import pytest

import unittest

from rift.mano.tosca_translator.common.utils import _
import rift.mano.tosca_translator.compare_desc as cmpdesc
import rift.mano.tosca_translator.shell as shell

from toscaparser.common.exception import TOSCAException


_TRUE_VALUES = ('True', 'true', '1', 'yes')


class TestToscaTranlator(unittest.TestCase):

    tosca_helloworld = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "data/tosca_helloworld.yaml")
    template_file = '--template-file=' + tosca_helloworld
    template_type = '--template-type=tosca'
    template_validation = "--validate-only"
    debug="--debug"
    failure_msg = _('The program raised an exception unexpectedly.')

    def test_missing_arg(self):
       self.assertRaises(SystemExit, shell.main, '')

    def test_invalid_file_arg(self):
        self.assertRaises(SystemExit, shell.main, 'translate me')

    def test_invalid_file_value(self):
        self.assertRaises(ValueError,
                          shell.main,
                          ('--template-file=template.txt',
                           self.template_type))

    def test_invalid_type_value(self):
        self.assertRaises(ValueError, shell.main,
                          (self.template_file, '--template-type=xyz'))

    def test_invalid_parameters(self):
        self.assertRaises(ValueError, shell.main,
                          (self.template_file, self.template_type,
                           '--parameters=key'))

    def test_valid_template(self):
        try:
            shell.main([self.template_file, self.template_type])
        except Exception:
            self.fail(self.failure_msg)

    def test_validate_only(self):
        try:
            shell.main([self.template_file, self.template_type,
                        self.template_validation])
        except Exception:
            self.fail(self.failure_msg)

        template = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "data/tosca_helloworld_invalid.yaml")
        invalid_template = '--template-file=' + template
        self.assertRaises(TOSCAException, shell.main,
                          [invalid_template, self.template_type,
                           self.template_validation])

    def compare_desc(self, gen_desc, exp_desc):
        gen = "--generated-file="+gen_desc
        exp = "--expected-file="+exp_desc
        cmpdesc.main([gen, exp])

    def test_output_dir(self):
        test_base_dir = os.path.join(os.path.dirname(
            os.path.abspath(__file__)), 'data')
        template_file = os.path.join(test_base_dir,
                            "ping_pong_csar/Definitions/ping_pong_nsd.yaml")
        template = '--template-file='+template_file
        temp_dir = tempfile.mkdtemp()
        output_dir = "--output-dir=" + temp_dir
        try:
            shell.main([template, output_dir])

            # Check the dirs are present
            dirs = os.listdir(temp_dir)
            expected_dirs = ['nsd', 'vnfd']
            self.assertTrue(set(expected_dirs) <= set(dirs))

            # Compare the descriptors
            mano_desc_dir = os.path.join(test_base_dir, 'ping_pong_nsd')
            for vnfd in os.listdir(os.path.join(temp_dir, 'vnfd')):
                gen_desc = os.path.join(temp_dir, 'vnfd', vnfd)
                exp_desc = os.path.join(mano_desc_dir, 'vnfd', vnfd)
                self.compare_desc(gen_desc, exp_desc)
            for nsd in os.listdir(os.path.join(temp_dir, 'nsd')):
                gen_desc = os.path.join(temp_dir, 'nsd', nsd)
                exp_desc = os.path.join(mano_desc_dir, 'nsd', nsd)
                self.compare_desc(gen_desc, exp_desc)

        except Exception as e:
            self.fail("Exception in test_output_dir: {}".format(e))
        finally:
            if temp_dir:
                shutil.rmtree(temp_dir)
                self.assertTrue(temp_dir is None or
                                not os.path.exists(temp_dir))

    def test_input_csar(self):
        test_base_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'data')
        template_file = os.path.join(test_base_dir, "ping_pong_csar.zip")
        template = '--template-file='+template_file
        temp_dir = tempfile.mkdtemp()
        output_dir = "--output-dir=" + temp_dir
        try:
            shell.main([template, output_dir])

            # Check the dirs are present
            dirs = os.listdir(temp_dir)
            expected_dirs = ['nsd', 'vnfd', 'images']
            self.assertTrue(set(expected_dirs) <= set(dirs))

            # Compare the descriptors
            mano_desc_dir = os.path.join(test_base_dir, 'ping_pong_nsd')
            for vnfd in os.listdir(os.path.join(temp_dir, 'vnfd')):
                gen_desc = os.path.join(temp_dir, 'vnfd', vnfd)
                exp_desc = os.path.join(mano_desc_dir, 'vnfd', vnfd)
                self.compare_desc(gen_desc, exp_desc)
            for nsd in os.listdir(os.path.join(temp_dir, 'nsd')):
                gen_desc = os.path.join(temp_dir, 'nsd', nsd)
                exp_desc = os.path.join(mano_desc_dir, 'nsd', nsd)
                self.compare_desc(gen_desc, exp_desc)

        except Exception as e:
            self.fail("Exception in test_output_dir: {}".format(e))
        finally:
            if temp_dir:
                shutil.rmtree(temp_dir)
                self.assertTrue(temp_dir is None or
                                not os.path.exists(temp_dir))

    def test_input_csar_no_gi(self):
        test_base_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'data')
        template_file = os.path.join(test_base_dir, "ping_pong_csar.zip")
        template = '--template-file='+template_file
        temp_dir = tempfile.mkdtemp()
        output_dir = "--output-dir=" + temp_dir
        no_gi = '--no-gi'
        try:
            shell.main([template, output_dir, no_gi])

            # Check the dirs are present
            dirs = os.listdir(temp_dir)
            expected_dirs = ['nsd', 'vnfd', 'images']
            self.assertTrue(set(expected_dirs) <= set(dirs))

            # Compare the descriptors
            mano_desc_dir = os.path.join(test_base_dir, 'ping_pong_nsd')
            for vnfd in os.listdir(os.path.join(temp_dir, 'vnfd')):
                gen_desc = os.path.join(temp_dir, 'vnfd', vnfd)
                exp_desc = os.path.join(mano_desc_dir, 'vnfd', vnfd)
                self.compare_desc(gen_desc, exp_desc)
            for nsd in os.listdir(os.path.join(temp_dir, 'nsd')):
                gen_desc = os.path.join(temp_dir, 'nsd', nsd)
                exp_desc = os.path.join(mano_desc_dir, 'nsd', nsd)
                self.compare_desc(gen_desc, exp_desc)

        except Exception as e:
            raise e
            self.fail("Exception in input_csar_no_gi: {}".format(e))
        finally:
            if temp_dir:
                shutil.rmtree(temp_dir)
                self.assertTrue(temp_dir is None or
                                not os.path.exists(temp_dir))


def main():
    pytest.main(__file__)


if __name__ == '__main__':
    main()
