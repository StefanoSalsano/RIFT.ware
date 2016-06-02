
/*
 * 
 * (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
 *
 */



/*!
 * @file rw_schema_defs.h
 * @date 2016/04/20
 * @brief RIFT.ware schema directory structure definitions.
 */

#ifndef RW_SCHEMA_DEFS_H_
#define RW_SCHEMA_DEFS_H_

#define RW_INSTALL_YANG_PATH ("usr/data/yang")
#define RW_INSTALL_MANIFEST_PATH ("usr/data/manifest")

#define RW_SCHEMA_LOCK_PATH ("var/rift/schema/lock")
#define RW_SCHEMA_TMP_PATH ("var/rift/schema/tmp")
#define RW_SCHEMA_TMP_ALL_PATH ("var/rift/schema/tmp/all")
#define RW_SCHEMA_TMP_NB_PATH ("var/rift/schema/tmp/northbound")
#define RW_SCHEMA_VER_PATH ("var/rift/schema/version")
#define RW_SCHEMA_VER_LATEST_PATH ("var/rift/schema/version/latest")
#define RW_SCHEMA_VER_LATEST_ALL_PATH ("var/rift/schema/version/latest/all")
#define RW_SCHEMA_VER_LATEST_NB_PATH ("var/rift/schema/version/latest/northbound")
#define RW_SCHEMA_ROOT_PATH ("var/rift/schema")

#define RW_SCHEMA_INIT_TMP_PREFIX ("var/rift/tmp.")

#define RW_SCHEMA_CONFD_TEST_PREFIX ("confd_ws.")
#define RW_SCHEMA_CONFD_PERSIST_PREFIX ("confd_persist_")
#define RW_SCHEMA_CONFD_ARCHIVE_PREFIX ("ar_confd_persist_")
#define RW_SCHEMA_CONFD_PROTOTYPE_CONF ("etc/rw_confd_prototype.conf")

#define RW_SCHEMA_XML_TEST_PREFIX ("xml_ws.")
#define RW_SCHEMA_XML_PERSIST_PREFIX ("xml_persist_")
#define RW_SCHEMA_XML_ARCHIVE_PREFIX ("ar_xml_persist_")

#define RW_SCHEMA_META_FILE_SUFFIX (".meta_info.txt")

#define RW_SCHEMA_LOCK_FILENAME ("schema.lock")

#endif /* RW_SCHEMA_DEFS_H_ */
