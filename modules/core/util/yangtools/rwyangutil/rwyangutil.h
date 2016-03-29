
/*
 * 
 * (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
 *
 */



#ifndef _RWYANGUTIL_H_
#define _RWYANGUTIL_H_

#define MAX_HOSTNAME_SZ 64

#define LOCK_FILE_NAME (".schema.lck")
#define SCHEMA_LOCK_FILE ("/var/rift/schema/lock/.schema.lck")
#define SCHEMA_LOCK_DIR ("/var/rift/schema/lock")
#define SCHEMA_TMP_LOC ("/var/rift/schema/tmp")
#define SCHEMA_TMP_ALL_LOC ("/var/rift/schema/tmp/all")
#define SCHEMA_TMP_NORTHBOUND_LOC ("/var/rift/schema/tmp/northbound")
#define SCHEMA_VER_DIR ("/var/rift/schema/version")
#define LATEST_VER_DIR ("/var/rift/schema/version/latest")
#define LATEST_NORTHBOUND_VER_DIR ("/var/rift/schema/version/latest/northbound")
#define IMAGE_SCHEMA_DIR ("/usr/data/yang")
#define DYNAMIC_SCHEMA_DIR ("/var/rift/schema")
#define CONFD_WS_PREFIX ("confd_ws.")
#define CONFD_PWS_PREFIX ("confd_persist_")
#define AR_CONFD_PWS_PREFIX ("ar_confd_persist_")
#define SCHEMA_LISTING_DIR ("/usr/data/manifest")
#define META_INFO_FILE_PREFIX (".meta_info.txt")

// The number of top level directories in DYNAMIC_SCHEMA_DIR
#define TOP_LEVEL_DIRECTORY_COUNT (9)

// Lock file liveness, in seconds
#define LIVENESS_THRESH (60)

// Version directory staleness, in seconds
#define STALENESS_THRESH (60)

// File protocol ops binary
#define FILE_PROTO_OPS_EXE ("/usr/bin/rwyangutil")

#ifdef __cplusplus
#include <set>
#include <string>

namespace rwyangutil {

std::set<std::string> const read_northbound_schema_listing(std::string const & rift_root,
                                                           std::string const & northbound_listing);

std::string get_rift_install();

std::string execute_command_and_get_result(const std::string& cmd);

/*
 * Gets the Shared object file provided the module name
 * by executing the pkg-config command.
 * Returns the absolute path of the shared object file.
 */
std::string get_so_file_for_module(const std::string& module_name);

/*
 * Validates the yang module by comparing the hash
 * of the module against the meta info file for the
 * module.
 */
bool validate_module_consistency(const std::string& module_name,
                                 const std::string& mangled_name,
                                 const std::string& upper_to_lower,
                                 std::string& error_str);

}
#endif

#endif
