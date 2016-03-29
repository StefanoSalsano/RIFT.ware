
/*
 * 
 * (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
 *
 */


/*
* @file rwuagent_confd_startup.cpp
*
* Management agent startup phase handler
*/
#include <sstream>
#include <iostream>
#include <chrono>
#include <fstream>

#include <confd_lib.h>
#include <confd_cdb.h>
#include <confd_dp.h>
#include <confd_maapi.h>
#include "rwuagent_confd.hpp"
#include "rw-vcs.pb-c.h"
#include "rw-base.pb-c.h"
#include "reaper_client.h"

using namespace rw_uagent;

void ConfdMgmtSystem::start_confd_phase_1_cb(void* ctx)
{
  RW_ASSERT(ctx);
  static_cast<ConfdMgmtSystem*>(ctx)->start_confd_phase_1();
}

void ConfdMgmtSystem::start_confd_reload_cb(void* ctx)
{
  RW_ASSERT(ctx);
  static_cast<ConfdMgmtSystem*>(ctx)->start_confd_reload();
}

void ConfdMgmtSystem::start_confd_phase_2_cb(void* ctx)
{
  RW_ASSERT(ctx);
  static_cast<ConfdMgmtSystem*>(ctx)->start_confd_phase_2();
}

#define CREATE_STATE(S1, S2, Func)                                      \
    std::make_pair(std::make_pair(S1, S2), &ConfdMgmtSystem::Func)

#define ADD_STATE(S1, S2, Func)                 \
  state_mc_.insert(                             \
          CREATE_STATE(S1, S2, Func))

ConfdMgmtSystem::ConfdMgmtSystem(Instance* instance):
                     BaseMgmtSystem(instance, "ConfdMgmtSystem")
{
  RWMEMLOG (memlog_buf_, RWMEMLOG_MEM2, "ConfdMgmtSystem ctor");

  ADD_STATE (PHASE_0,       PHASE_1, start_confd_phase_1_cb);
  ADD_STATE (TRANSITIONING, PHASE_1, start_confd_phase_1_cb);
  ADD_STATE (PHASE_1,       RELOAD,  start_confd_reload_cb);
  ADD_STATE (RELOAD,        PHASE_2, start_confd_phase_2_cb);
  ADD_STATE (TRANSITIONING, PHASE_2, start_confd_phase_2_cb);
}

#undef CREATE_STATE
#undef ADD_STATE


void ConfdMgmtSystem::create_proxy_manifest_config()
{
  RWMEMLOG(memlog_buf_, RWMEMLOG_MEM2, "create proxy manifest cfg" );
  RW_MA_INST_LOG(instance_, InstanceDebug, "Create manifest entry configuration");

  std::string error_out;
  rw_yang::XMLDocument::uptr_t req;
  std::string xml(manifest_cfg_);

  if (!instance_->unique_ws_) {
    char hostname[MAX_HOSTNAME_SZ];
    hostname[MAX_HOSTNAME_SZ - 1] = 0;
    int res = gethostname(hostname, MAX_HOSTNAME_SZ - 2);
    RW_ASSERT(res != -1);

    unsigned long seconds_since_epoch =
          std::chrono::duration_cast<std::chrono::seconds>
                  (std::chrono::system_clock::now().time_since_epoch()).count();

    std::ostringstream oss;
    oss << "confd_ws." << &hostname[0] << "." << seconds_since_epoch;
    confd_dir_ = std::move(oss.str());
  } else {
    confd_dir_ = instance_->mgmt_workspace_.c_str();
  }

  auto pos = xml.find('$');
  RW_ASSERT(pos != std::string::npos);
  xml.replace(pos, 1, confd_dir_.c_str());
  req = std::move(instance_->xml_mgr()->create_document_from_string(xml.c_str(), error_out, false));

  // ATTN: We are not publishing this data since
  // there is no subscriber for rw-manifest.
  // What happens is, when the vstart RPC is fired,
  // the specified parent instance reads this
  // configuration entry from uAgent
  // and creates a registration for it at runtime.
  instance_->dom()->merge(req.get());

  RW_MA_INST_LOG(instance_, InstanceInfo, "Manifest entry configuration created successfully");
}


rw_status_t ConfdMgmtSystem::initialize_conn()
{
  RWMEMLOG(memlog_buf_, RWMEMLOG_MEM2, "initialize connection" );
  RW_ASSERT(curr_phase() == PHASE_0);
  std::string tmp_log;

  close_sockets();

  sock_ = socket(instance_->confd_addr_->sa_family, SOCK_STREAM | SOCK_CLOEXEC, 0);
  RW_ASSERT(sock_ >= 0);

  auto ret = maapi_connect(sock_, instance_->confd_addr_, instance_->confd_addr_size_);
  if (ret != CONFD_OK) {
    tmp_log="MAAPI connect failed: " + std::string(confd_lasterr()) + ". Retrying.";
    RW_MA_INST_LOG (instance_, InstanceError, tmp_log.c_str());
    RWMEMLOG(memlog_buf_, RWMEMLOG_MEM2, "failed maapi_connect" );
    return RW_STATUS_FAILURE;
  }

  RW_MA_INST_LOG(instance_, InstanceNotice, "MAAPI connection succeeded");

  read_sock_ = socket(instance_->confd_addr_->sa_family, SOCK_STREAM, 0);
  RW_ASSERT(read_sock_ >= 0);

  ret = cdb_connect(read_sock_, CDB_READ_SOCKET, instance_->confd_addr_,
      instance_->confd_addr_size_);
  if (ret != CONFD_OK) {
    tmp_log="CDB read socket connection failed. Retrying. " + std::string(confd_lasterr());
    RW_MA_INST_LOG (instance_, InstanceError, tmp_log.c_str());
    RWMEMLOG(memlog_buf_, RWMEMLOG_MEM2, "failed cdb_connect" );
    return RW_STATUS_FAILURE;
  }

  return RW_STATUS_SUCCESS;
}

void ConfdMgmtSystem::close_sockets()
{
  if (sock_ >= 0) close(sock_);
  sock_ = -1;

  if (read_sock_ >= 0) close(read_sock_);
  read_sock_ = -1;
}

void ConfdMgmtSystem::proceed_to_next_state()
{
  RW_ASSERT(next_phase() != DONE);

  rwsched_dispatch_async_f(
      instance_->rwsched_tasklet(),
      rwsched_dispatch_get_main_queue(instance_->rwsched()),
      this,
      state_mc_[state_]);
}

void ConfdMgmtSystem::retry_phase_cb(ConfdMgmtSystem::CB cb)
{
  auto curr_state_str = phase_2_str[curr_phase()];
  auto next_state_str = phase_2_str[next_phase()];
  RWMEMLOG(memlog_buf_, RWMEMLOG_MEM2, "retry phase cb",
           RWMEMLOG_ARG_STRNCPY(sizeof(curr_state_str), curr_state_str),
           RWMEMLOG_ARG_STRNCPY(sizeof(next_state_str), next_state_str));

  auto when = dispatch_time(DISPATCH_TIME_NOW, NSEC_PER_SEC / 2LL);
  rwsched_dispatch_after_f(
        instance_->rwsched_tasklet(),
        when,
        rwsched_dispatch_get_main_queue(instance_->rwsched()),
        this,
        cb);

  return;
}

#define OK_RETRY(retval, err_msg) \
  if (retval != CONFD_OK) { \
    const char* s_ = err_msg; \
    RW_MA_INST_LOG (instance_, InstanceError, s_); \
    RWMEMLOG(memlog_buf_, RWMEMLOG_MEM2, "start confd err", \
             RWMEMLOG_ARG_STRCPY_MAX(s_,128) ); \
    return retry_phase_cb(cb); \
  }

#define SET_STATE(curr_state, next_state) \
  state_.first = curr_state;              \
  state_.second = next_state;

void ConfdMgmtSystem::start_confd_phase_1()
{
  RWMEMLOG (memlog_buf_, RWMEMLOG_MEM2, "start confd phase 1");
  RW_MA_INST_LOG (instance_, InstanceInfo, "start confd phase 1");

  RW_ASSERT (next_phase() == PHASE_1);
  std::string tmp_log;

  auto cb = state_mc_[state_];
  RW_ASSERT (cb);

  if (curr_phase() == PHASE_0) {
    auto ret = maapi_start_phase(sock_, PHASE_1, 0/*async*/);
    OK_RETRY (ret,
              (tmp_log="Maapi start phase1 failed. Retrying. "
                        + std::string(confd_lasterr())).c_str());

    SET_STATE (TRANSITIONING, PHASE_1);
    return retry_phase_cb(cb);
  }

  if ((curr_phase() == TRANSITIONING) && (next_phase() == PHASE_1)) {
    struct cdb_phase cdb_phase;

    auto ret = cdb_get_phase(read_sock_, &cdb_phase);
    OK_RETRY (ret,
              (tmp_log="CDB get phase failed. Current phase 0. Retrying. "
                        + std::string(confd_lasterr())).c_str());

    if (cdb_phase.phase == PHASE_1) {
      SET_STATE (PHASE_1, RELOAD);
    } else {
      return retry_phase_cb(cb);
    }
  }

  RW_MA_INST_LOG(instance_, InstanceCritInfo,
      "Configuration management phase-1 finished. Starting config subscription");

  instance_->setup_confd_subscription();
}

void ConfdMgmtSystem::start_confd_reload()
{
  RWMEMLOG(memlog_buf_, RWMEMLOG_MEM2, "start confd reload phase");
  RW_MA_INST_LOG(instance_, InstanceInfo, "start confd reload phase");
  RW_ASSERT (next_phase() == RELOAD);

  is_under_reload_ = true;
  instance_->start_confd_reload();
  SET_STATE (RELOAD, PHASE_2);
}

void ConfdMgmtSystem::start_confd_phase_2()
{
  RWMEMLOG (memlog_buf_, RWMEMLOG_MEM2, "start confd phase 2");
  RW_MA_INST_LOG (instance_, InstanceInfo, "start confd phase 2");

  RW_ASSERT (next_phase() == PHASE_2);
  std::string tmp_log;

  auto cb = state_mc_[state_];
  RW_ASSERT (cb);

  // Confd reload is done if we are here
  is_under_reload_ = false;

  if (curr_phase() == RELOAD) {
    auto ret = maapi_start_phase(sock_, PHASE_2, 0/*async*/);
    OK_RETRY (ret,
        (tmp_log="Maapi start phase2 failed. Retrying. "
                 + std::string(confd_lasterr())).c_str());

    SET_STATE (TRANSITIONING, PHASE_2);
    return retry_phase_cb(cb);
  }

  if ((curr_phase() == TRANSITIONING) && (next_phase() == PHASE_2)) {
    struct cdb_phase cdb_phase;
    auto ret = cdb_get_phase(read_sock_, &cdb_phase);
    OK_RETRY (ret,
        (tmp_log="CDB get phase failed. Current phase 1. Retrying. "
                 + std::string(confd_lasterr())).c_str());

    if (cdb_phase.phase == PHASE_2) {
      SET_STATE (PHASE_2, DONE);
    } else {
      return retry_phase_cb(cb);
    }
  }

  auto confd_init_file = get_rift_install() + "/" + confd_dir_ +
    std::string("/") + CONFD_INIT_FILE;

  struct stat fst;
  if (stat(confd_init_file.c_str(), &fst) != 0) {
    RW_MA_INST_LOG (instance_, InstanceCritInfo,
        "Creating agent confd init file");
    std::fstream ofile(confd_init_file, std::ios::out);
    RW_ASSERT_MESSAGE(ofile.good(), "Failed to create confd init file");
    ofile.close();
  }

  RW_MA_INST_LOG(instance_, InstanceCritInfo,
      "Configuration management startup complete. Northbound interfaces are enabled.");
  return;
}

#undef OK_RETRY
#undef SET_STATE
