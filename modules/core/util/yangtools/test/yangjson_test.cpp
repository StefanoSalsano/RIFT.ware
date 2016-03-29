/* 
 * (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
 * */
/**
 * @file yangjson_test.hpp
 * @date 2016/02/05
 * @brief Tests for  yang node to json conversion.
 */

#include <limits.h>
#include <cstdlib>
#include <iostream>
#include <boost/property_tree/json_parser.hpp>
#include <boost/foreach.hpp>
#include "gmock/gmock.h"
#include "gtest/rw_gtest.h"
#include "yangmodel.h"
#include "yangncx.hpp"
#include "rw_pb_schema.h"
#include "rw_yang_json.h"
#include "test-yang-json.pb-c.h"
#include "test-yang-json-aug-base.pb-c.h"

using namespace rw_yang;
namespace pt = boost::property_tree;

TEST (YangJsonBasic, BasicTest)
{
  TEST_DESCRIPTION ("Test for simple yang to json conversion");
  YangModelNcx* model = YangModelNcx::create_model();
  YangModel::ptr_t p(model);
  ASSERT_TRUE(model);
  YangNode* root = model->get_root_node();
  ASSERT_TRUE(root);
  
  YangModule* tnaa1 = model->load_module("test-yang-json");
  ASSERT_TRUE(tnaa1);
  YangAugment* person = tnaa1->get_first_augment();
  ASSERT_TRUE(person);
  YangNode* node = person->get_target_node();

  std::stringstream oss;
  JsonPrinter printer(oss, node, true);
  oss << "{";
  printer.convert_to_json();
  oss << "}";
  std::cout << oss.str() << std::endl;

  pt::ptree tree;
  pt::read_json(oss, tree);
  bool found_comp_list = false;

  BOOST_FOREACH(const pt::ptree::value_type& val, tree.get_child("person.properties"))
  {
    auto name = val.second.get<std::string>("name");

    if (name == "test-yang-json:company-list") {
      found_comp_list = true;
      EXPECT_STREQ (val.second.get<std::string>("type").c_str(), "list");
      EXPECT_STREQ (val.second.get<std::string>("cardinality").c_str(), "0..N");

      BOOST_FOREACH (const pt::ptree::value_type& v, val.second.get_child("properties")) {
        auto iname = v.second.get<std::string>("name");
        std::cout << iname << std::endl;
        if (iname == "iref1") {
          const auto& dtype = v.second.get_child("data-type.idref");
          EXPECT_STREQ (dtype.get<std::string>("base").c_str(), "tyj:riftio");
        }
        if (iname == "iref2") {
          const auto& dtype = v.second.get_child("data-type.idref");
          EXPECT_STREQ (dtype.get<std::string>("base").c_str(), "tyj:cloud-platform");
        }
      }
    }
  }

  EXPECT_TRUE (found_comp_list);

}
