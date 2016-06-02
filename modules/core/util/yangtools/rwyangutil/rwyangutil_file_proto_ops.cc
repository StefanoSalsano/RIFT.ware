
/*
 * 
 * (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
 *
 */


/**
 * @file rw_file_proto_ops.cc
 * @author Arun Muralidharan
 * @date 01/10/2015
 * @brief App library file protocol operations
 * @details App library file protocol operations
 */

#include <algorithm>
#include <cassert>
#include <cerrno>
#include <chrono>
#include <fcntl.h>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <map>
#include <set>
#include <sstream>
#include <sys/stat.h>
#include <sys/types.h>

#define BOOST_NO_CXX11_SCOPED_ENUMS
#include <boost/filesystem.hpp>
#undef BOOST_NO_CXX11_SCOPED_ENUMS
#include <boost/uuid/random_generator.hpp>
#include <boost/uuid/uuid.hpp>
#include <boost/uuid/uuid_io.hpp>

#include "rwyangutil.h"
#include "rwyangutil_argument_parser.hpp"
#include "rwyangutil_file_proto_ops.hpp"
#include "rwyangutil_helpers.hpp"

namespace fs = boost::filesystem;
namespace rwyangutil {

bool FileProtoOps::validate_command(std::string const & command)
{
  if (command_map.find(command) != command_map.end()) {
    return true;
  }
  return false;
}

bool FileProtoOps::execute_command(std::string const & command, std::vector<std::string> const & params)
{
  auto command_handler = command_map.find(command);
  if (command_handler != command_map.end()) {
    return command_handler->second(this, params);
  }

  return false;
}


FileProtoOps::FileProtoOps()
{
  command_map["--lock-file-create"]         = &FileProtoOps::create_lock_file;
  command_map["--lock-file-delete"]         = &FileProtoOps::delete_lock_file;
  command_map["--version-dir-create"]       = &FileProtoOps::create_new_version_directory;
  command_map["--create-schema-dir"]        = &FileProtoOps::create_schema_directory;
  command_map["--remove-schema-dir"]        = &FileProtoOps::remove_schema_directory;
  command_map["--prune-schema-dir"]         = &FileProtoOps::prune_schema_directory;

#ifdef CONFD_ENABLED
  // ATTN: N0, these should not be new arguments.  The persist support
  // should be the same name, and work on confd or XML regardless.
  command_map["--rm-unique-confd-ws"]       = &FileProtoOps::remove_unique_confd_workspace;
  command_map["--archive-confd-persist-ws"] = &FileProtoOps::archive_confd_persist_workspace;
  command_map["--rm-persist-confd-ws"]      = &FileProtoOps::remove_persist_confd_workspace;
#endif
  command_map["--rm-persist-xml-ws"]        = &FileProtoOps::remove_persist_xml_workspace;
  command_map["--rm-unique-xml-ws"]         = &FileProtoOps::remove_unique_xml_workspace;
  command_map["--archive-xml-persist-ws"]   = &FileProtoOps::archive_xml_persist_workspace;
}

bool FileProtoOps::create_lock_file(std::vector<std::string> const & params)
{
  return rwyangutil::create_lock_file();
}

bool FileProtoOps::delete_lock_file(std::vector<std::string> const & params)
{
  return rwyangutil::remove_lock_file();
}

bool FileProtoOps::create_new_version_directory(std::vector<std::string> const & params)
{
  return rwyangutil::update_version_directory();
}

bool FileProtoOps::remove_schema_directory(std::vector<std::string> const & params)
{
  return rwyangutil::remove_schema_directory();
}

bool FileProtoOps::create_schema_directory(std::vector<std::string> const & params)
{
  if (params.size() < 1) {
    std::cerr << "Create schema directory requires 1 or more northbound schema listing files" << std::endl;
    return false;
  }
  return rwyangutil::create_schema_directory(params);
}

#ifdef CONFD_ENABLED

bool FileProtoOps::remove_unique_confd_workspace(std::vector<std::string> const & params)
{
  return rwyangutil::remove_unique_confd_workspace();
}

bool FileProtoOps::remove_persist_confd_workspace(std::vector<std::string> const & params)
{
  return rwyangutil::remove_persist_confd_workspace();
}

bool FileProtoOps::archive_confd_persist_workspace(std::vector<std::string> const & params)
{
  return rwyangutil::archive_confd_persist_workspace();
}

#endif

bool FileProtoOps::remove_unique_xml_workspace(std::vector<std::string> const & params)
{
  return rwyangutil::remove_unique_xml_workspace();
}

bool FileProtoOps::remove_persist_xml_workspace(std::vector<std::string> const & params)
{
  return rwyangutil::remove_persist_xml_workspace();
}

bool FileProtoOps::archive_xml_persist_workspace(std::vector<std::string> const & params)
{
  return rwyangutil::archive_xml_persist_workspace();
}

bool FileProtoOps::prune_schema_directory(std::vector<std::string> const & params)
{
  return rwyangutil::prune_schema_directory();
}
}

