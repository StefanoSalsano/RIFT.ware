/*
 * 
 * (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
 *
 * Creation Date: 1/22/16
 * 
 */

#ifndef __RWYANGUTIL_FILE_PROTO_OPS_H__
#define __RWYANGUTIL_FILE_PROTO_OPS_H__

#include <functional>
#include <string>
#include <vector>
#include <map>

namespace rwyangutil {
class FileProtoOps
{
 public:

  typedef std::map<std::string, std::function<bool(FileProtoOps*, std::vector<std::string> const & )>> command_func_map_t;
  typedef std::map<std::string, const char*> fext_dir_map_t;

  static void init_command_map();

  bool execute_command(std::string const & command, std::vector<std::string> const & params);

  bool validate_command(std::string const & command);

  FileProtoOps();

 private:

  // exposed via cli arguments
  bool archive_confd_persist_workspace(std::vector<std::string> const & params);
  bool create_lock_file(std::vector<std::string> const & params);
  bool create_new_version_directory(std::vector<std::string> const & params);
  bool create_schema_directory(std::vector<std::string> const & params);
  bool delete_lock_file(std::vector<std::string> const & params);
  bool init_schema_directory(std::vector<std::string> const & params);
  bool prune_schema_directory(std::vector<std::string> const & params);
  bool remove_non_unique_confd_workspace(std::vector<std::string> const & params);
  bool remove_schema_directory(std::vector<std::string> const & params);
  bool remove_unique_confd_workspace(std::vector<std::string> const & params);

  bool cleanup_lock_files();
  bool cleanup_excess_version_dirs();
  bool cleanup_stale_version_dirs();
  bool remove_confd_workspace(const char*);

  std::tuple<unsigned, unsigned> get_max_version_number_and_count();

 private:

  static command_func_map_t command_map;
  static fext_dir_map_t fext_map;

  std::string base_schema_path_;
  std::string latest_version_dir_;
  std::string lock_dir_;
  std::string lock_file_;
  std::string rift_install_;
  std::string schema_tmp_;
  std::string schema_all_tmp_;
  std::string schema_northbound_tmp_;
  std::string schema_path_;
  std::string schema_version_dir_;
};

}

#endif
