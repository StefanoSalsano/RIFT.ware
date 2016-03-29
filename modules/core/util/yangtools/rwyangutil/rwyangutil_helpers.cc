/*
 * 
 * (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
 *
 * Creation Date: 1/22/16
 * 
 */

#include <map>
#include <set>
#include <string>
#include <fstream>
#define BOOST_NO_CXX11_SCOPED_ENUMS
#include <boost/filesystem.hpp>
#undef BOOST_NO_CXX11_SCOPED_ENUMS

#include "rwyangutil.h"

namespace fs = boost::filesystem;

namespace rwyangutil {

std::string get_rift_install()
{
  auto rift_install = getenv("RIFT_INSTALL");
  if (!rift_install) return "/home/rift/.install";
  return rift_install;
}

std::set<std::string> const read_northbound_schema_listing(std::string const & rift_root,
                                                           std::string const & northbound_listing)
{

  std::string const northbound_listing_filename = rift_root
                                                  + "/usr/data/manifest/"
                                                  + northbound_listing;
  
  std::ifstream northbound_listing_file(northbound_listing_filename);
  std::set<std::string> northbound_schema_listing;

  std::string line;
  while (std::getline(northbound_listing_file,line)) {
    northbound_schema_listing.insert(line);
  }

  return northbound_schema_listing;
}

std::string execute_command_and_get_result(const std::string& cmd)
{
  std::shared_ptr<FILE> pipe(popen(cmd.c_str(), "r"), pclose);

  if (!pipe) return std::string();

  size_t const buffer_size = 128;
  char buffer[buffer_size];
  std::string result;

  while (!feof(pipe.get())) {
    if (fgets(buffer, buffer_size, pipe.get()) != NULL)
      result += buffer;
  }

  return result;
}

std::string get_so_file_for_module(const std::string& module_name)
{
  auto prefix_directory = get_rift_install() + "/usr";
  const std::string& cmd = "pkg-config --define-variable=prefix=" + prefix_directory
                         + " --libs " + module_name;

  auto result = execute_command_and_get_result(cmd);
  auto lpos = result.find("-l");
  if (lpos == std::string::npos) return std::string();

  auto Lpos = result.find("-L");
  if (Lpos == std::string::npos) return std::string();

  auto split_pos = result.find(" ");
  if (split_pos == std::string::npos) return std::string();

  std::string so_file = result.substr(2, split_pos - 2) + "/lib"
    + result.substr(lpos + 2, result.length() - (lpos + 2) - 2) + ".so";

  return so_file;
}

bool validate_module_consistency(const std::string& module_name,
                                 const std::string& mangled_name,
                                 const std::string& upper_to_lower,
                                 std::string& error_str)
{
  //ATTN: Ignore ietf for now
  // fxs files are not found at correct path
  if (module_name.find("ietf") == 0) return true;

  std::string meta_name = module_name + META_INFO_FILE_PREFIX;
  std::string rift_install = get_rift_install();

  std::string version_dir = rift_install + "/" + LATEST_VER_DIR;
  auto meta_info = rift_install + IMAGE_SCHEMA_DIR;

  std::ifstream inf(meta_info + "/" + meta_name);
  if (!inf) {
    error_str = meta_name + " file not found";
    return false;
  }
  auto get_sha_sum = [](const std::string& file){
    //ATTN: if the algorithm to compute hash is changed here,
    //please change it in rift_schema_info.cmake as well!
    std::string cmd = "sha1sum " + file + " | cut -d ' ' -f 1";
    return execute_command_and_get_result(cmd);
  };

  // Get shared-object name for the module
  std::string so_file = get_so_file_for_module(module_name);
  if (!so_file.length()) {
    error_str = meta_name + " so file not found: ";
    error_str += std::strerror(errno);
    return false;
  }

  std::map<std::string, std::vector<std::string>> prefix_path_map = {
    {module_name + ".yang",    {rift_install + IMAGE_SCHEMA_DIR}},
    {module_name + ".fxs",     {rift_install + IMAGE_SCHEMA_DIR}},
    {module_name + ".pc",      {rift_install + "/usr/lib/pkgconfig/"}},
    {mangled_name + "Yang-1.0.typelib",     {rift_install + "/usr/lib/rift/girepository-1.0/"}},
    {fs::path(so_file).filename().string(), {rift_install + "/usr/lib/"}},
  };

  std::string line;
  while (std::getline(inf, line)) {
    size_t pos = line.find(':');
    if (pos == std::string::npos) {
      error_str = meta_name + " ':' not found";
      return false;
    }

    auto file_name = line.substr(0, pos);

    // Compare the hashes from the file entry
    auto it = prefix_path_map.find(file_name);
    if (it == prefix_path_map.end()) {
      error_str += file_name + "Not found.";
      continue;
    }

    auto sha1 = line.substr(pos + 1, line.length() - pos);

    std::string file_path = prefix_path_map[file_name][0] + "/" + file_name;
    if (!fs::exists(file_path)) {
      continue;
    }

    auto sha_res = get_sha_sum(file_path);
    sha_res = sha_res.substr(0, sha_res.find('\n'));

    if (sha_res != sha1) {
      error_str = "Hashes do not match. ";
      error_str += "Mismatch: " + line + " : " + sha_res;
      return false;
    }

    prefix_path_map.erase(it);
  }

  if (prefix_path_map.size() != 0) {
    error_str = "Not all meta information present in ";
    error_str += meta_name;
    return false;
  }
  return true;
}

}
