
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

#include "RwyangutilArgumentParser.hpp"
#include "RwyangutilFileProtoOps.hpp"
#include "rwyangutil.h"

static const char* RANDOM_SCHEMA_DIR_PREFIX = "./var/rift/.s.";

namespace fs = boost::filesystem;
namespace rwyangutil {
FileProtoOps::command_func_map_t FileProtoOps::command_map;
FileProtoOps::fext_dir_map_t FileProtoOps::fext_map;

namespace {
std::vector<std::string> get_filestems(fs::path const & directory)
{
  std::vector<std::string> filestems;
  std::array<std::string, TOP_LEVEL_DIRECTORY_COUNT> paths
  {"/fxs", "/xml", "/lib", "/yang", "/lock", "/tmp", "/version", "/cli", "/meta"};

  for (fs::recursive_directory_iterator it(directory);
       it != fs::recursive_directory_iterator();
       ++it) {
    std::string const filestem = it->path().stem().string();
    if (std::find(paths.begin(), paths.end(), filestem) != paths.end()) {
      continue;
    }

    filestems.push_back(filestem);
  }      
  std::sort(filestems.begin(), filestems.end());
  return filestems;
}

bool schema_directory_is_old(std::string const & rift_install,
                             std::string const & schema_directory,
                             std::string const & schema_listing)
{

  std::string const schema_listing_path = rift_install
                                          + "/"
                                          + SCHEMA_LISTING_DIR
                                          + "/"
                                          + schema_listing;

  std::time_t const schema_directory_age = fs::last_write_time(schema_directory);
  std::time_t const schema_listing_age = fs::last_write_time(schema_listing_path);

  return schema_directory_age < schema_listing_age;
}

bool fs_create_directory(const std::string& path)
{
  try {
    if (!fs::create_directory(path)) {
      return false;
    }
  } catch (const fs::filesystem_error& e) {
    std::cerr << "Exception while creating directory: "
              << path << " "
              << e.what() << std::endl;
    return false;
  }

  return true;
}

bool fs_create_directories(const std::string& path)
{
  try {
    if (!fs::create_directories(path)) {
      std::cerr << "Failed to create directory " << path << std::endl;
      return false;
    }
  } catch (const fs::filesystem_error& e) {
    std::cerr << "Exception while creating directories: "
              << path << " "
              << e.what() << std::endl;
    return false;
  }

  return true;
}

bool fs_create_hardlinks(const std::string& spath,
                         const std::string& dpath)
{
  for (fs::directory_iterator file(spath); file != fs::directory_iterator(); ++file) {
    try {
      fs::create_hard_link(file->path(), dpath + "/" + file->path().filename().string());
    } catch (const fs::filesystem_error& e) {
      std::cerr << "Exception while creating symbolic link to: "
                << file->path().string() << ": "
                << e.what() << std::endl;
      return false;
    }
  }
  return true;
}

bool fs_empty_the_directory(const std::string& dpath)
{
  for (fs::directory_iterator file(dpath); file != fs::directory_iterator(); ++file) {
    fs::remove_all(file->path());
  }
  return true;
}

bool fs_remove_directory(const std::string& dpath)
{
  try {
    fs::remove_all(dpath);
  } catch (const fs::filesystem_error& e) {
    std::cerr << "Exception while removing the dir: "
              << dpath << " "
              << e.what() << std::endl;
    return false;
  }
  return true;
}

std::string fs_read_symlink(const std::string& sym_link)
{
  std::string target;

  try {
    fs::path const tpath = fs::read_symlink(sym_link);
    if (!tpath.empty()) {
      target = tpath.string();
    }
  } catch (const fs::filesystem_error& e) {
    std::cerr << "Exception while reading the symlink: "
              << sym_link << " "
              << e.what() << std::endl;
    return target;
  }

  return target;
}

bool fs_create_symlink(const std::string& target,
                                     const std::string& link)
{
  try {
    fs::create_symlink(target, link);
  } catch (const fs::filesystem_error& e) {
    std::cerr << "Exception while creating sym link to "
              << target << " as " << link << " "
              << e.what() << std::endl;
    return false;
  }

  return true;
}

bool fs_rename(const std::string& old_path,
                             const std::string& new_path)
{
  try {
    fs::rename(old_path, new_path);
  } catch (const fs::filesystem_error& e) {
    std::cerr << "Exception while renaming " 
              << old_path << " to " << new_path << " "
              << e.what() << std::endl;
    return false;
  }

  return true;
}

bool fs_remove(const std::string& path)
{
  try {
    fs::remove(path);
  } catch (const fs::filesystem_error& e) {
    std::cerr << "Exception while removing "
              << path << " "
              << e.what() << std::endl;
    return false;
  }

  return true;
}

/**
 * Create the /tmp directory structure
 * @param base_path the base path to the /tmp directory
 */
bool create_tmp_directory_tree(std::string const & base_path)
{

  std::array<std::string, 5> const tmp_paths {"/fxs", "/xml", "/lib", "/yang", "/meta"};
  std::string const all_tmp_base = base_path + "/tmp/all";
  std::string const northbound_tmp_base = base_path + "/tmp/northbound";

  for (std::string const & path : tmp_paths) {

    std::string const all_tmp = all_tmp_base + path;
    std::string const northbound_tmp = northbound_tmp_base + path;

    if (!fs_create_directories(all_tmp)){
      fs_remove_directory(all_tmp);
      return false;
    }
    if (!fs_create_directories(northbound_tmp)){
      fs_remove_directory(all_tmp);
      return false;
    }
  }

  return true;
}

}

void FileProtoOps::init_command_map()
{
  // Initialize the command to function map.
  command_map["--lock-file-create"]         = &FileProtoOps::create_lock_file;
  command_map["--lock-file-delete"]         = &FileProtoOps::delete_lock_file;
  command_map["--version-dir-create"]       = &FileProtoOps::create_new_version_directory;
  command_map["--create-schema-dir"]        = &FileProtoOps::create_schema_directory;
  command_map["--remove-schema-dir"]        = &FileProtoOps::remove_schema_directory;
  command_map["--init-schema-dir"]          = &FileProtoOps::init_schema_directory;
  command_map["--prune-schema-dir"]         = &FileProtoOps::prune_schema_directory;
  command_map["--rm-non-unique-confd-ws"]   = &FileProtoOps::remove_non_unique_confd_workspace;
  command_map["--rm-unique-confd-ws"]       = &FileProtoOps::remove_unique_confd_workspace;
  command_map["--archive-confd-persist-ws"] = &FileProtoOps::archive_confd_persist_workspace;

  // Initialize the file extension to directory map.
  fext_map[".yang"] = "/yang";
  fext_map[".dsdl"] = "/xml";
  fext_map[".fxs"]  = "/fxs";
  fext_map[".cli.xml"]  = "/cli";
  fext_map[".cli.ssi.sh"]  = "/cli";  
  fext_map[".txt"] = "/meta";
}

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
  rift_install_ = getenv("RIFT_INSTALL");
  if (!rift_install_.length()) {
    rift_install_ = "/";
  }

  base_schema_path_ = rift_install_ + "/" + IMAGE_SCHEMA_DIR;
  latest_version_dir_ = rift_install_ + "/" + LATEST_VER_DIR;
  lock_dir_ = rift_install_ + "/" + SCHEMA_LOCK_DIR;
  lock_file_ = rift_install_ + "/" + SCHEMA_LOCK_FILE;
  schema_all_tmp_ = rift_install_ + "/" + SCHEMA_TMP_ALL_LOC;
  schema_northbound_tmp_ = rift_install_ + "/" + SCHEMA_TMP_NORTHBOUND_LOC;
  schema_path_ = rift_install_ + "/" + DYNAMIC_SCHEMA_DIR;
  schema_version_dir_ = rift_install_ + "/" + SCHEMA_VER_DIR;
  schema_tmp_ = rift_install_ + "/" + SCHEMA_TMP_LOC;
}

bool FileProtoOps::create_lock_file(std::vector<std::string> const & params)
{
  // check liveness
  if (fs::exists(lock_file_)) {
    auto last_write_timer = fs::last_write_time(lock_file_);
    auto now = std::time(nullptr);
    
    if ((now - last_write_timer) >= LIVENESS_THRESH) {
      fs_remove(lock_file_);
    }
  }

  // if parent directory doesn't exist, create it
  if (!fs::exists(lock_dir_)) {
    if (!fs_create_directories(lock_dir_)) {
      return false;
    }
    fs::permissions(lock_dir_, fs::all_all);
  }

  const int fd = open(lock_file_.c_str(), O_CREAT | O_EXCL | O_WRONLY, 0760);
  if (fd == -1) {

    std::cerr << "Failed to create lock file " << lock_file_ << "\n";
    return false;
  }

  return true;
}

bool FileProtoOps::delete_lock_file(std::vector<std::string> const & params)
{
  return fs::remove(lock_file_);
}

std::tuple<unsigned, unsigned> FileProtoOps::get_max_version_number_and_count()
{
  unsigned max   = 0;
  unsigned count = 0;

  for (fs::directory_iterator it(schema_version_dir_); it != fs::directory_iterator(); ++it) {
    const std::string & name = it->path().string();
    if (!fs::is_directory(name)) {
      continue;
    }

    const std::string & version = fs::basename(name);
    if (!std::all_of(version.begin(), version.end(), [](char c) {return std::isxdigit(c);})) {
      continue;
    }

    count++;
    unsigned num = 0;
    std::stringstream strm("0x" + version);
    strm >> std::hex >> num;
    if (num > max) {
      max = num;
    }
  }

  return std::make_tuple(max, count);
}

bool FileProtoOps::create_new_version_directory(std::vector<std::string> const & params)
{
  unsigned curr_ver = 0, count = 0;
  std::tie (curr_ver, count) = get_max_version_number_and_count();

  std::ostringstream new_strm;
  new_strm << std::setfill('0') << std::setw(8) << std::hex << std::uppercase << (curr_ver + 1);

  std::ostringstream old_strm;
  old_strm << std::setfill('0') << std::setw(8) << std::hex << std::uppercase << curr_ver;

  std::string new_version_path(schema_version_dir_ +  "/" + new_strm.str());
  std::string old_version_path(schema_version_dir_ + "/" + old_strm.str());

  // if /tmp is a subset of the current version we have no work to do
  std::vector<std::string> tmp_all_filestems = get_filestems(schema_all_tmp_);
  std::vector<std::string> tmp_nb_filestems = get_filestems(schema_northbound_tmp_);

  std::string const current_all = latest_version_dir_ + "/all";
  std::string const current_nb = latest_version_dir_ + "/northbound";
  std::vector<std::string> current_all_filestems = get_filestems(current_all);
  std::vector<std::string> current_nb_filestems = get_filestems(current_nb);

  if ( std::includes(current_all_filestems.begin(), current_all_filestems.end(),
                     tmp_all_filestems.begin(), tmp_all_filestems.end())
       && std::includes(current_nb_filestems.begin(), current_nb_filestems.end(),
                        tmp_nb_filestems.begin(), tmp_nb_filestems.end()))
  {
    // Cleanup files from tmp directory
    fs_empty_the_directory(schema_tmp_);
    if (!create_tmp_directory_tree(schema_path_)){
      std::cerr << "Creation of tmp directory structure failed\n";
      return false;
    }
    return true;
  }                     

  // make sure /tmp has all the right directories 
  std::array<std::string, 5> paths {"/fxs", "/xml", "/lib", "/yang", "/meta"};
  for (auto path : paths) {
    std::string const all_path = schema_all_tmp_ + path;
    std::string const northbound_path = schema_northbound_tmp_ + path;

    if (!fs::exists(all_path)) {
      if (!fs_create_directories(all_path)){
        return false;
      }
    }
    fs::permissions(all_path, fs::all_all);

    if (!fs::exists(northbound_path)) {
      if (!fs_create_directories(northbound_path)){
        return false;
      }
    }
    fs::permissions(northbound_path, fs::all_all);

    std::string const old_all_path = old_version_path + "/all/" + path;
    std::string const old_northbound_path = old_version_path + "/northbound/" + path;    

    // Create symlinks for files into /all subdirectory
    auto res1 = fs_create_hardlinks(old_all_path, all_path);
    if (!res1) {
      return false;
    }

    // Create symlinks for base schema files into /northbound subdirectory
    auto res2 = fs_create_hardlinks(old_northbound_path, northbound_path);
    if (!res2) {
      return false;
    }
  } 

  // Move /tmp directory into new version directory
  if (!fs_rename(schema_tmp_, new_version_path)) {
    return false;
  }

  // Create all and northbound tmp directories
  if (!create_tmp_directory_tree(schema_path_)){
    return false;
  }

  // Make symlink to latest
  (void)fs_remove(latest_version_dir_);
  if (!fs_create_symlink(new_version_path, latest_version_dir_)) {
    return false;
  }

  // Create a stamp file
  std::string const stamp_filename = new_version_path + "/stamp";
  const int fd = open(stamp_filename.c_str(), O_CREAT | O_EXCL | O_WRONLY, 0770);
  if (fd == -1) {
    std::cerr << "Failed to create stamp file: " << std::strerror(errno) << std::endl;;
    return false;
  }
  close(fd);
  fs::permissions(stamp_filename, fs::all_all);

  return true;
}

bool FileProtoOps::cleanup_lock_files()
{
  if (!fs::exists(lock_dir_) || !fs::is_directory(lock_dir_)) {
    return false;
  }

  return fs_empty_the_directory(lock_dir_);
}

bool FileProtoOps::remove_schema_directory(std::vector<std::string> const & params)
{
  if (!fs::exists(schema_path_)) {
    return true;
  }

  //std::cout << "Removing schema directory " << schema_path_ << std::endl;
  return fs_remove_directory(schema_path_);
}

bool FileProtoOps::create_schema_directory(std::vector<std::string> const & params)
{
  if (params.size() != 1) {
    std::cerr << "Create schema directory requires 1 argument, the northbound schema listing. " << std::endl;
    return false;
  }

  std::string const & schema_listing_file = params[0];

  bool lock_directory_exists = false;
  if (fs::exists(schema_path_)) {
    /*
     * If there is only one subdirectory of the schema directory it is the lock
     * directory, and the rest of it needs to be created.
     */
    size_t subdirectory_count = 0;
    for (fs::directory_iterator it(schema_path_);
         it != fs::directory_iterator();
         ++it) {
      if (fs::is_directory(it->path())) {
        subdirectory_count++;
      }
    }

    if (subdirectory_count > 1) {
      // directory structure has been created

      if (schema_directory_is_old(rift_install_, schema_path_, schema_listing_file)) {
        // delete the schema directory and re-create it if the listing has been changed
        fs_remove_directory(schema_path_);
      } else {
        return true;
      }
    } else {
      // only the lock directory has been created
      lock_directory_exists = true;
    }
  }


  /* Check to make sure the image schema path exists */
  if (!fs::exists(base_schema_path_)) {
    std::cerr << "Image schema path does not exists " << base_schema_path_ << std::endl;
    return false;
  }

  std::set<std::string> const northbound_schema_list = rwyangutil::read_northbound_schema_listing(rift_install_,
                                                                                                  schema_listing_file);

  /* Create a random directory, create links to the image schema files, and rename it. */
  boost::uuids::uuid const uuid = boost::uuids::random_generator()();
  std::string suuid = boost::uuids::to_string(uuid);

  suuid.erase(std::remove_if(suuid.begin(), suuid.end(), [](char c) 
                             { if (c == '-') { return true; } return false; }), suuid.end());

  std::ostringstream random_directory;
  random_directory << rift_install_ << "/" << RANDOM_SCHEMA_DIR_PREFIX << suuid;

  std::string random_spath = random_directory.str();

  if (!fs_create_directories(random_spath)) {
    return false;
  }

  // ATTN:- Fix this.Setting permissions to 777 for now, so that make clean works.
  fs::permissions(random_spath, fs::all_all); 

  std::array<std::string, TOP_LEVEL_DIRECTORY_COUNT> paths
  {"/fxs", "/xml", "/lib", "/yang", "/lock", "/tmp", "/version", "/cli", "/meta"};

  // create top level directories
  for (auto path : paths) {
    if (lock_directory_exists && path == "/lock") {
      continue;
    }

    std::string const top_path = random_spath + path;

    if (!fs_create_directory(top_path)){
      fs_remove_directory(random_spath);
      return false;
    }

    fs::permissions(top_path, fs::all_all);

    if (lock_directory_exists) {
      // make lock file in temporary directory so it's still valid when the directory is copied
      std::string const new_lock_file = top_path + LOCK_FILE_NAME;
      auto fd = open(new_lock_file.c_str(), O_CREAT | O_EXCL | O_WRONLY, 0760);
      if (fd == -1) {
        std::cerr << "Failed to create temporary lock file " << new_lock_file 
                  << ": " << std::strerror(errno) << std::endl;
        return false;
      }

    }
  }

  // create all and northbound tmp directories
  if (!create_tmp_directory_tree(random_spath)){
    return false;
  }

  // create all and northbound version directories
  std::ostringstream strm;
  strm << std::setfill('0') << std::setw(8) << 0;
  std::string version_path(random_spath + "/version/" + strm.str());

  for (auto path : paths) {
    std::string const all_path = version_path + "/all/" + path;
    std::string const northbound_path = version_path + "/northbound/" + path;    

    if (!fs_create_directories(all_path)){
      fs_remove_directory(random_spath);
      return false;
    }
    if (!fs_create_directories(northbound_path)) {
      fs_remove_directory(random_spath);
      return false;
    }

    fs::permissions(all_path, fs::all_all);
    fs::permissions(northbound_path, fs::all_all);
  }

  // Create symlinks for the image schema files from /usr/data/yang.
  for ( fs::directory_iterator it(base_schema_path_); it != fs::directory_iterator(); ++it) {

    if (!fs::is_regular_file(it->path()) &&
        !fs::is_symlink(it->path()))  {
      continue;
    }

    std::string ext; 
    fs::path fn = it->path().filename();

    // ATTN: this isn't actually looping, is it?
    for (; !fn.extension().empty(); fn = fn.stem()) {
      ext = fn.extension().string() + ext;
    }

    auto fd_map = fext_map.find(ext);

    if (fd_map != fext_map.end()) {

      std::string target_path = it->path().string();

      if (fs::is_symlink(it->path())) {

        const std::string tpath = fs_read_symlink(it->path().string());
        if (!tpath.length()) {
          std::cerr << "Failed to read the sym link " << it->path().string() << std::endl;
          fs_remove_directory(random_spath);
          return false;
        }

        target_path = fs::canonical(tpath, base_schema_path_).string();
      }

      // make link into top-level directory schema directory
      std::string target_dir = random_spath + fd_map->second;
      std::string tsymb_link = target_dir + "/" + it->path().filename().string();

      if (!fs_create_symlink(target_path, tsymb_link)) {
        fs_remove_directory(random_spath);
        return false;
      }

      // make link into /all schema directory
      std::string all_target_dir = version_path + "/all/" + fd_map->second;
      std::string all_tsymb_link = all_target_dir + "/" + it->path().filename().string();

      if (!fs_create_symlink(target_path, all_tsymb_link)) {
        fs_remove_directory(random_spath);
        return false;
      }


      // make link into /northbound schema directory
      std::string const file_stem = it->path().filename().stem().string();
      if (northbound_schema_list.count(file_stem)) {
        std::string northbound_target_dir = version_path + "/northbound/" + fd_map->second;
        std::string northbound_tsymb_link = northbound_target_dir + "/" + it->path().filename().string();

        if (!fs_create_symlink(target_path, northbound_tsymb_link)) {
          fs_remove_directory(random_spath);
          return false;
        }
        
      }

    }
  }

  if (lock_directory_exists) {
    // only move the contents, excluding the /lock directory
    for (auto path : paths) {
      if (path == "/lock") {
        continue;
      }
      std::string const tmp_path = random_spath + path;
      std::string const perm_path = schema_path_ + path;
      if (!fs_rename(tmp_path, perm_path)) {
        fs_remove_directory(random_spath);
      }
    }
  } else {
    if (!fs_rename(random_spath, schema_path_)) {
      fs_remove_directory(random_spath);
    }
  }

  // make latest directory
  std::string const initial_version_path = rift_install_ + "/" + SCHEMA_VER_DIR + "/00000000";
  if (!fs_create_symlink(initial_version_path, latest_version_dir_)) {
    return false;
  }

  // recursively chmod 777 the schema directory
  fs::directory_iterator dir_end;
  for(fs::recursive_directory_iterator dir(schema_path_), dir_end; dir!=dir_end ;++dir) {
    if (fs::is_directory(dir->path())) {
      fs::permissions(dir->path(), fs::all_all);
    }
  }

  if (!fs::exists(schema_path_) || !fs::is_directory(schema_path_)) {
    std::cerr << "Failed to create schema directory " << schema_path_ << std::endl;
    return false;
  }

  //std::cout << "Schema directory " << schema_path_ << " created" << std::endl;
  return true;
}

bool FileProtoOps::cleanup_excess_version_dirs()
{
  unsigned vmax = 0;
  unsigned vcount = 0;

  std::tie (vmax, vcount) = get_max_version_number_and_count();
  if (vcount <= 8) {
    return true;
  }

  unsigned svnum  = vmax - vcount + 1;
  unsigned to_del = vcount - 8;

  for (unsigned vern = svnum; vern < (svnum + to_del); ++vern) {

    std::ostringstream strm;
    strm << std::setfill('0') << std::setw(8) << std::hex << std::uppercase << vern;
    std::string version_dir = schema_version_dir_ + strm.str();

    //std::cout << "Removing excess version directory " << version_dir << std::endl;
    fs_remove_directory(version_dir);
  }

  return true;
}

bool FileProtoOps::cleanup_stale_version_dirs()
{
  unsigned vmax = 0;
  unsigned vcount = 0;

  std::tie (vmax, vcount) = get_max_version_number_and_count();

  unsigned svnum  = vmax - vcount + 1;
  for (unsigned vern = svnum; vern < (svnum + vcount); ++vern) {

    std::ostringstream strm;
    strm << std::setfill('0') << std::setw(8) << std::hex << std::uppercase << vern;

    std::string version_dir    = schema_version_dir_ + strm.str();
    std::string stamp_file = version_dir + "/stamp";

    if (!fs::exists(stamp_file) && (vern != vmax)) {
      //std::cout << "Removing stale version directory " << version_dir << std::endl;
      fs_remove_directory(version_dir);
    }
  }

  return true;
}

bool FileProtoOps::init_schema_directory(std::vector<std::string> const & params)
{
  cleanup_lock_files();
  return prune_schema_directory(params);
}

bool FileProtoOps::prune_schema_directory(std::vector<std::string> const & params)
{
  cleanup_excess_version_dirs();
  cleanup_stale_version_dirs();
  return true;
}

bool FileProtoOps::remove_confd_workspace(const char* prefix)
{
  for (fs::directory_iterator entry(rift_install_);
       entry != fs::directory_iterator(); ++entry)
  {
    if (!fs::is_directory(entry->path())) continue;

    const std::string dir_name = entry->path().filename().string();
    const size_t pos = dir_name.find(prefix);

    if (pos != 0) continue;

    if (!fs_remove_directory(entry->path().string())) {
      return false;
    }
  }
  return true;
}

bool FileProtoOps::remove_unique_confd_workspace(std::vector<std::string> const & params)
{
  // Remove the non persisting directories and the archived one as well
  auto ret1 = remove_confd_workspace(CONFD_WS_PREFIX);
  auto ret2 = remove_confd_workspace(AR_CONFD_PWS_PREFIX);

  return ret1 && ret2;
}

bool FileProtoOps::remove_non_unique_confd_workspace(std::vector<std::string> const & params)
{
  return remove_confd_workspace(CONFD_PWS_PREFIX);
}

bool FileProtoOps::archive_confd_persist_workspace(std::vector<std::string> const & params)
{
  for (fs::directory_iterator entry(rift_install_);
       entry != fs::directory_iterator(); ++entry)
  {
    if (!fs::is_directory(entry->path())) continue;

    auto dir_name = entry->path().filename().string();
    auto pos = dir_name.find(CONFD_PWS_PREFIX);

    if (pos != 0) continue;
    // rename the persist directory
    auto mod_time = fs::last_write_time(entry->path());
    auto epoch = std::chrono::duration_cast<std::chrono::seconds> (
        std::chrono::system_clock::from_time_t(mod_time).time_since_epoch()).count();

    auto new_dir_name = rift_install_+ "/ar_" + dir_name + "_" + std::to_string(epoch);

    fs::rename(entry->path(), fs::path(new_dir_name));
    if (!fs::exists(new_dir_name)) {
      std::cerr << "Rename failed: " << new_dir_name << ": " 
                << std::strerror(errno)<< std::endl;
      return false;
    }
  }

  return true;
}

}

