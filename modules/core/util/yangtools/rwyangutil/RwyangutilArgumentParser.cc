/*
 * 
 * (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
 *
 * Creation Date: 1/22/16
 * 
 */

#include <algorithm>
#include <iostream>
#include <string>
#include <stdexcept>

#include <boost/algorithm/string/predicate.hpp>

#include "RwyangutilArgumentParser.hpp"

namespace rwyangutil {

ArgumentParser::ArgumentParser(const char* const* argv, size_t argc)
{
  parse_arguments(argv, argc);
}

void ArgumentParser::parse_arguments(const char* const* argv, size_t argc)
{
  std::vector<std::string> raw_arguments;
  for (size_t i = 0; i < argc; ++i) {
    raw_arguments.emplace_back(argv[i]);
  }

  std::string & current_command = raw_arguments.front();
  for (std::string const & current_argument : raw_arguments)
  {

    if (boost::starts_with(current_argument, "--")) {
      current_command = current_argument;

      arguments_[current_command] = std::vector<std::string>();
      ordered_arguments_.emplace_back(current_command);
      continue;
    }

    arguments_[current_command].emplace_back(current_argument);

  }
  
}

//ATTN: This does not seem to be the right place to print help ??
void ArgumentParser::print_help() const
{
  std::cout << "Usage: ./rw_file_proto_ops <operation>" << "\n";
  std::cout << "Valid set of operations: " << "\n";
  std::cout << "1. Create lock file:                    --lock-file-create\n";
  std::cout << "2. Delete lock file:                    --lock-file-delete\n";
  std::cout << "3. Create new version directory:        --version-dir-create\n";
  std::cout << "4. Clean temporary files:               --tmp-file-cleanup\n";
  std::cout << "5. Copy files from temporary dir to permanent dir: --copy-from-tmp\n";
  std::cout << "6. Create Schema Directory:             --create-schema-dir\n";
  std::cout << "7. Remove Schema Directory:             --remove-schema-dir\n";
  std::cout << "8. Init Schema Directory:               --init-schema-dir\n";
  std::cout << "9. Prune Schema Directories:            --prune-schema-dir\n";
  std::cout << "10. Remove non unique Confd workspaces: --rm-non-unique-confd-ws\n";
  std::cout << "11. Remove unique Confd workspace:      --rm-unique-confd-ws\n";
  std::cout << std::endl;
}

ArgumentParser::const_iterator ArgumentParser::begin() const
{
  return ordered_arguments_.begin();
}

ArgumentParser::const_iterator ArgumentParser::end() const
{
  return ordered_arguments_.end();
}

bool ArgumentParser::exists(const std::string& option) const
{
  return arguments_.count(option) > 0;
}

std::vector<std::string> const & ArgumentParser::get_params_list(std::string const & option) const
{
  return arguments_.at(option);
}

std::string const& ArgumentParser::get_param(std::string const& option) const
{
  auto& vec = get_params_list(option);
  if (vec.size() != 1) throw std::range_error("Number of params does not match");
  return vec[0];
}

}
