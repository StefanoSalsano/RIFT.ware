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

#include "rwyangutil_argument_parser.hpp"

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
  std::cout << "Valid set of operations:" << "\n";
  std::cout << "  --lock-file-create          Create lock file\n";
  std::cout << "  --lock-file-delete          Delete lock file\n";
  std::cout << "  --version-dir-create        Create new version directory\n";
  std::cout << "  --create-schema-dir         Create Schema Directory\n";
  std::cout << "  --remove-schema-dir         Remove Schema Directory\n";
  std::cout << "  --prune-schema-dir          Prune Schema Directories\n";
#ifdef CONFD_ENABLED
  std::cout << "  --rm-unique-confd-ws        Remove unique Confd workspace\n";
  std::cout << "  --rm-persist-confd-ws       Remove persist Confd workspaces\n";
  std::cout << "  --archive-confd-persist-ws  Archive persist Confd workspace\n";
#endif
  std::cout << "  --rm-persist-xml-ws         Remove persist XML workspaces\n";
  std::cout << "  --rm-unique-xml-ws          Remove unique XML workspace\n";
  std::cout << "  --archive-xml-persist-ws    Archive persist XML workspace\n";
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
