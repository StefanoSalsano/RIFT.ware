
/*
 * 
 * (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
 *
 */


/*
* @file rwuagent_mgmt_system.cpp
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

using VcsInfo = RWPB_T_MSG(RwBase_data_Vcs_Info);

static void config_mgmt_start_cb(
      rwdts_xact_t* xact,
      rwdts_xact_status_t* xact_status,
      void* user_data)
{
  auto* self = static_cast<BaseMgmtSystem*>(user_data);
  self->config_mgmt_start( xact, xact_status );
}

static void retry_mgmt_start_cb(void* user_data)
{
  auto* self = static_cast<BaseMgmtSystem*>(user_data);
  self->start_mgmt_instance();
}

BaseMgmtSystem::BaseMgmtSystem(Instance* inst,
                               const char* trace_name)
  : instance_(inst),
    memlog_buf_(
        inst->get_memlog_inst(),
        trace_name,
        reinterpret_cast<intptr_t>(this) )
{
}

void BaseMgmtSystem::start_mgmt_instance()
{
  RWMEMLOG(memlog_buf_, RWMEMLOG_MEM2, "start management server" );

  RWPB_T_PATHSPEC(RwVcs_input_Vstart) start_act = *(RWPB_G_PATHSPEC_VALUE(RwVcs_input_Vstart));
  RWPB_M_MSG_DECL_INIT(RwVcs_input_Vstart, start_act_msg);

  start_act_msg.parent_instance = const_cast<char*>(instance_->rwvcs()->identity.rwvm_name);
  start_act_msg.component_name = const_cast<char*>(get_component_name());

  std::string log("Starting management instance. ");
  log += "Parent instance: " + std::string(start_act_msg.parent_instance)
       + ". Component name: " + start_act_msg.component_name;
  RW_MA_INST_LOG(instance_, InstanceCritInfo, log.c_str());

  auto* xact = rwdts_api_query_ks(instance_->dts_api(),
                                  (rw_keyspec_path_t*)&start_act,
                                  RWDTS_QUERY_RPC,
                                  0,
                                  config_mgmt_start_cb,
                                  this,
                                  &start_act_msg.base);
  RW_ASSERT(xact);
}

void BaseMgmtSystem::config_mgmt_start(
    rwdts_xact_t* xact,
    rwdts_xact_status_t* xact_status)
{
  RW_MA_INST_LOG(instance_, InstanceDebug, "confd vstart response");
  RWMEMLOG(memlog_buf_, RWMEMLOG_MEM2, "confd vstart result",
           RWMEMLOG_ARG_PRINTF_INTPTR("st=%" PRIdPTR, (intptr_t)xact_status->status),
           RWMEMLOG_ARG_PRINTF_INTPTR("dts xact=0x%" PRIXPTR, (intptr_t)xact) );

  switch (xact_status->status) {
    case RWDTS_XACT_COMMITTED:
      RWMEMLOG(memlog_buf_, RWMEMLOG_MEM2, "confd vstart complete");
      RW_MA_INST_LOG(instance_, InstanceCritInfo, "confd started");
      inst_ready_ = true;
      break;

    default:
    case RWDTS_XACT_FAILURE:
    case RWDTS_XACT_ABORTED: {
      RW_MA_INST_LOG(instance_, InstanceError, "Unable to start management instance, retrying");
      auto when = dispatch_time(DISPATCH_TIME_NOW, NSEC_PER_SEC * 5);
      rwsched_dispatch_after_f(instance_->rwsched_tasklet(),
                               when,
                               rwsched_dispatch_get_main_queue(instance_->rwsched()),
                               this,
                               retry_mgmt_start_cb);
      break;
    }
  }
}


void BaseMgmtSystem::start_tasks_ready_timer()
{
  RWMEMLOG(memlog_buf_, RWMEMLOG_MEM2, "start readiness timer");
  rwsched_tasklet_ptr_t tasklet = instance_->rwsched_tasklet();
  RW_MA_INST_LOG(instance_, InstanceInfo, "Starting timer to wait for critical tasklets");

  tasks_ready_timer_ = rwsched_dispatch_source_create(
      tasklet,
      RWSCHED_DISPATCH_SOURCE_TYPE_TIMER,
      0,
      0,
      rwsched_dispatch_get_main_queue(instance_->rwsched()));

  rwsched_dispatch_source_set_event_handler_f(
      tasklet,
      tasks_ready_timer_,
      BaseMgmtSystem::tasks_ready_timer_expire_cb);

  rwsched_dispatch_set_context(
      tasklet,
      tasks_ready_timer_,
      this);

  rwsched_dispatch_source_set_timer(
      tasklet,
      tasks_ready_timer_,
      dispatch_time(DISPATCH_TIME_NOW, CRITICAL_TASKLETS_WAIT_TIME),
      0,
      0);

  rwsched_dispatch_resume(tasklet, tasks_ready_timer_);
}

void BaseMgmtSystem::tasks_ready_timer_expire_cb(void* ctx)
{
  RW_ASSERT(ctx);
  static_cast<BaseMgmtSystem*>(ctx)->tasks_ready_timer_expire();
}

void BaseMgmtSystem::tasks_ready_timer_expire()
{
  RWMEMLOG(memlog_buf_, RWMEMLOG_MEM2, "ready timer expired, start mgmt server anyway");
  RW_MA_INST_LOG(instance_, InstanceError,
                 "Critical tasks not ready after 5 minutes, continuing");
  tasks_ready();
}

void BaseMgmtSystem::stop_tasks_ready_timer()
{
  RWMEMLOG(memlog_buf_, RWMEMLOG_MEM2, "stop ready timer",
           RWMEMLOG_ARG_PRINTF_INTPTR("t=%" PRIdPTR, (intptr_t)tasks_ready_timer_));
  if (tasks_ready_timer_) {
    rwsched_tasklet_ptr_t tasklet = instance_->rwsched_tasklet();
    rwsched_dispatch_source_cancel(tasklet, tasks_ready_timer_);
    rwsched_dispatch_release(tasklet, tasks_ready_timer_);
  }
  tasks_ready_timer_ = nullptr;
}

void BaseMgmtSystem::tasks_ready_cb(void* ctx)
{
  RW_ASSERT(ctx);
  auto self = static_cast<BaseMgmtSystem*>(ctx);
  RW_MA_INST_LOG(self->instance_, InstanceCritInfo, "Critical tasklets are in running state.");

  self->tasks_ready();
}

void BaseMgmtSystem::tasks_ready()
{
  RWMEMLOG(memlog_buf_, RWMEMLOG_MEM2, "tasks ready");
  RW_ASSERT (!inst_ready_);

  stop_tasks_ready_timer();
  start_mgmt_instance();
}

rw_status_t BaseMgmtSystem::wait_for_critical_tasklets()
{
  RWMEMLOG(memlog_buf_, RWMEMLOG_MEM2, "wait for critical tasklets");
  RW_ASSERT (!inst_ready_);

  rw_status_t ret = RW_STATUS_SUCCESS;
  // Wait for critical tasklets to come in Running state
  RW_ASSERT(instance_->dts_api());
  
  start_tasks_ready_timer();
  cb_data_ = rwdts_api_config_ready_register(
                instance_->dts_api(),
                tasks_ready_cb,
                this);
  
  return ret;
}
