/*
/ (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
/*/
/*!
 * @file rwdts_kv_light_api_gi.h
 * @brief Top level RWDTS KV LIGHT API GI header
 * @author Prashanth Bhaskar(Prashanth.Bhaskar@riftio.com)
 * @date 2014/10/02
 */
#ifndef __RWDTS_KV_LIGHT_API_GI_H__
#define __RWDTS_KV_LIGHT_API_GI_H__

#include <glib-object.h>

typedef struct rwdts_kv_handle_s rwdts_kv_handle_t;


__BEGIN_DECLS

GType rwdts_kv_handle_get_type(void);

typedef enum rwdts_avail_db {
  REDIS_DB = 0,
  BK_DB = 1,
  MAX_DB
} rwdts_avail_db_t;

GType rwdts_avail_db_get_type(void);

/*!
 * rwdts_kv_handle_open_db
 * Arguments: rwdts_kv_handle_t *handle, const char *file_name,
 *            const char *program_name, FILE *error_file_pointer
 *
 * Returns: rw_status_t
 *
 * API to create and open the file-db. Program_name and error_file_pointer is not used
 * for now and NULL have to supplied.
 */
/// @cond GI_SCANNER
/**
 * rwdts_kv_handle_open_db:
 * @kv_handle: 
 * @file_name:
 * @program_name: (nullable) 
 * @error_file_pointer: (nullable) 
 * Returns: (type RwTypes.RwStatus) (transfer none)
 */
/// @endcond
rw_status_t
rwdts_kv_handle_open_db(rwdts_kv_handle_t* kv_handle,
                        const char* file_name,
                        const char* program_name, 
                        void* error_file_pointer);

/*!
 * API rwdts_kv_allocate_handle
 * Arguments: rwdts_avail_db_t db
 *
 * Returns : rwdts_kv_handle_t *
 *
 * API to allocate KV handle needed to connect to a DB type. Accepts DB type as
 * argument and returns KV handle. Currently only REDIS_DB db type is supported.
 * This is the first API to be used by the KV client */

/// @cond GI_SCANNER
/**
 * rwdts_kv_allocate_handle:
 * @db: 
 * Returns: (transfer full)
 */
/// @endcond
rwdts_kv_handle_t* 
rwdts_kv_allocate_handle(rwdts_avail_db_t db);

/*!
 * rwdts_kv_handle_file_get_cursor
 * Arguments: rwdts_kv_handle_t *handle
 *
 * Returns: void*
 *
 * API to get the DB cursor handle.
 */
/// @cond GI_SCANNER
/**
 * rwdts_kv_handle_file_get_cursor:
 * @handle: 
 * Returns: (nullable) (transfer full)
 */
/// @endcond
void*
rwdts_kv_handle_file_get_cursor(rwdts_kv_handle_t* handle);


/*!
 * rwdts_kv_handle_file_getnext
 * Arguments: rwdts_kv_handle_t *handle, void **dbc (DB cursor-handle),
 *            uint8_t **key, size_t *key_len, uint8_t **val, size_t *val_len
 *
 * Returns: rw_status_t
 *
 * API to get the next Key/Value pair from the DB cursor handle.
 */
/// @cond GI_SCANNER
/**
 * rwdts_kv_handle_file_getnext:
 * @handle:
 * @cursor: 
 * @key: (out) (transfer none)
 * @key_len: (out)
 * @val: (out) (transfer none)
 * @val_len: (out)
 * @out_cursor: (out) (transfer none)
 * Returns: (type RwTypes.RwStatus) (transfer none)
 */
/// @endcond
rw_status_t
rwdts_kv_handle_file_getnext(rwdts_kv_handle_t* handle,
                             void* cursor, 
                             char** key,
                             int* key_len, 
                             char** val, 
                             int* val_len,
                             void** out_cursor);


/*!
 * rwdts_kv_handle_file_close
 * Arguments: rwdts_kv_handle_t *handle
 *
 * Returns: rw_status_t
 *
 * API to close the open file-db. 
 */
/// @cond GI_SCANNER
/**
 * rwdts_kv_handle_file_close:
 * @kv_handle: 
 * Returns: (type RwTypes.RwStatus) (transfer none)
 */
/// @endcond
rw_status_t
rwdts_kv_handle_file_close(rwdts_kv_handle_t* kv_handle);

/*!
 * rwdts_kv_handle_file_remove
 * Arguments: rwdts_kv_handle_t *handle
 *
 * Returns: rw_status_t
 *
 * API to remove the file-DB.
 */
/// @cond GI_SCANNER
/**
 * rwdts_kv_handle_file_remove:
 * @handle: 
 * Returns: (type RwTypes.RwStatus) (transfer none)
 */
/// @endcond
rw_status_t
rwdts_kv_handle_file_remove(rwdts_kv_handle_t* handle);

/*!
 * rwdts_kv_handle_file_set_keyval
 * Arguments: rwdts_kv_handle_t *handle
 *            char *key, int key_len,
 *            char *val, int val_len 
 *
 * Returns: rw_status_t
 *
 * API to set Key/Value pair in File-DB.
 */
/// @cond GI_SCANNER
/**
 * rwdts_kv_handle_file_set_keyval:
 * @handle: 
 * @key:
 * @key_len: 
 * @val: 
 * @val_len:
 * Returns: (type RwTypes.RwStatus) (transfer none)
 */
/// @endcond
rw_status_t
rwdts_kv_handle_file_set_keyval(rwdts_kv_handle_t* handle,
                                char* key,
                                int key_len,
                                char* val,
                                int val_len);


/*!
 * rwdts_kv_handle_file_del_keyval
 * Arguments: rwdts_kv_handle_t *handle
 *            char *key, int key_len,
 *
 * Returns: rw_status_t
 *
 * API to delete Key/Value pair from File-DB.
 */
/// @cond GI_SCANNER
/**
 * rwdts_kv_handle_file_del_keyval:
 * @handle:                    
 * @key:
 * @key_len: 
 * Returns: (type RwTypes.RwStatus) (transfer none)
 */
/// @endcond
rw_status_t
rwdts_kv_handle_file_del_keyval(rwdts_kv_handle_t* handle,
                                char* key, 
                                int key_len);


/*!
 * rwdts_kv_handle_file_get_keyval
 * Arguments: rwdts_kv_handle_t *handle
 *            char *key, int key_len,
 *            char **val, int *val_len 
 *
 * Returns: rw_status_t
 *
 * API to get Value details for a given key from File-DB.
 */
/// @cond GI_SCANNER
/**
 * rwdts_kv_handle_file_get_keyval:
 * @handle: 
 * @key: 
 * @key_len: 
 * @val: (out callee-allocates)
 * @val_len: (out)
 * Returns: (type RwTypes.RwStatus) (transfer none)
 */
/// @endcond
rw_status_t
rwdts_kv_handle_file_get_keyval(rwdts_kv_handle_t *handle,
                                char* key,
                                int key_len,
                                char** val,
                                int* val_len);

__END_DECLS


#endif //__RWDTS_KV_LIGHT_API_GI_H__
