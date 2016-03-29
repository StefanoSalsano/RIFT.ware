
/*
 * 
 * (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
 *
 */


/**
* @file rwuagent_confd_log.cpp
*
* Confd logging action manager.
*/

#include "rwuagent_confd.hpp"

using namespace rw_uagent;


const char* ConfdLog::LOGROTATE_CFG_FILE = "/etc/logrotate.d/rwconfd";

ConfdLog::ConfdLog(Instance* instance):
  instance_(instance),
  apih_(instance->dts_api()),
  memlog_buf_(instance_->get_memlog_inst(),
              "ConfdLog",
              reinterpret_cast<intptr_t>(this))
{
  RW_ASSERT (apih_);
  postrotate_script_ = ::get_rift_install() + "/usr/local/confd/bin/confd_cmd -c reopen_logs";
  auto log_dir = get_rift_install() + "/" + instance_->mgmt_handler()->mgmt_dir() +
                 "/usr/local/confd/var/confd/log/";
  logs_.emplace_back(log_dir + "audit.log");
  logs_.emplace_back(log_dir + "confd.log");
  logs_.emplace_back(log_dir + "devel.log");
  logs_.emplace_back(log_dir + "netconf.log");
}

ConfdLog::~ConfdLog()
{
  rwdts_member_deregister(sub_regh_);
}

rw_status_t ConfdLog::register_config()
{
  RWMEMLOG (memlog_buf_, RWMEMLOG_MEM2, "register logrotate config");
  RW_MA_INST_LOG (instance_, InstanceDebug, "Registering logrotate config");

  RWPB_M_PATHSPEC_DECL_INIT(RwMgmtagt_LogrotateConf, cfg_pathspec);
  auto keyspec = (rw_keyspec_path_t *)&cfg_pathspec;
  rw_keyspec_path_set_category (keyspec, nullptr, RW_SCHEMA_CATEGORY_CONFIG);

  // Create DTS registration as subscriber
  rwdts_member_event_cb_t sub_reg_cb = {};
  sub_reg_cb.ud = this;
  sub_reg_cb.cb.prepare = &ConfdLog::create_logrotate_cfg_cb;

  sub_regh_ = rwdts_member_register(
                    nullptr,
                    apih_,
                    keyspec,
                    &sub_reg_cb,
                    RWPB_G_MSG_PBCMD(RwMgmtagt_LogrotateConf),
                    RWDTS_FLAG_SUBSCRIBER,
                    nullptr);

  if (!sub_regh_) {
    RW_MA_INST_LOG (instance_, InstanceError,
        "Failed to register logrotate config as subscriber");
    return RW_STATUS_FAILURE;
  }

  return RW_STATUS_SUCCESS;
}


rwdts_member_rsp_code_t ConfdLog::create_logrotate_cfg_cb(
    const rwdts_xact_info_t * xact_info,
    RWDtsQueryAction action,
    const rw_keyspec_path_t * keyspec,
    const ProtobufCMessage * msg,
    uint32_t credits,
    void * get_next_key)
{
  RW_ASSERT(xact_info);
  RW_ASSERT(xact_info->ud);
  auto self = static_cast<ConfdLog*>( xact_info->ud );
  
  return self->create_logrotate_config( msg );
}


rwdts_member_rsp_code_t ConfdLog::create_logrotate_config(const ProtobufCMessage* msg)
    
{
  RWMEMLOG(memlog_buf_, RWMEMLOG_MEM2, "create logrotate config");

  if (!is_production()) {
    RW_MA_INST_LOG (instance_, InstanceDebug,
        "Non production mode, not creating the logrotate config");
    return RWDTS_ACTION_OK;
  }

  RW_ASSERT (msg);
  auto logrotate_cfg = (ConfdLog::LogrotateConf *)msg;

  std::ofstream ofile(LOGROTATE_CFG_FILE);
  chmod(LOGROTATE_CFG_FILE, 0644);

  if (!ofile) {
    std::string err_log("Failed: ");
    err_log += strerror(errno);
    RW_MA_INST_LOG (instance_, InstanceError, err_log.c_str());
    return RWDTS_ACTION_NOT_OK;
  }
  auto fmt_write = [&ofile](const char* item, bool no_indent = false) {
     if (!no_indent) ofile << "\t";
     ofile << item << "\n";
  };

  auto wr_common_attribs = [logrotate_cfg, &fmt_write, &ofile]() {
    fmt_write ("missingok");
    if (logrotate_cfg->compress) fmt_write ("compress");
    ofile << "\tsize " <<  logrotate_cfg->size << "M\n";
    fmt_write ("su root root");
    ofile << "\trotate " << logrotate_cfg->rotations << "\n";
  };

    // Log files to be rotated
  for (const auto& file: logs_) {
    fmt_write (file.c_str(), true);
  }

  fmt_write ("{", true);
  {
    wr_common_attribs ();
    fmt_write ("sharedscripts");
    fmt_write ("postrotate");
    ofile << "\t\t" << postrotate_script_ << " > /dev/null\n";
    fmt_write ("endscript");
  }
  fmt_write ("}", true);

  // Special rule for netconf.trace file as confd does not
  // reopen file handle for trace log
  // Using copy truncate option instead
  auto nc_trace_file = get_rift_install() + "/" + instance_->mgmt_handler()->mgmt_dir() +
                       "/usr/local/confd/var/confd/log/netconf.trace";
  fmt_write (nc_trace_file.c_str(), true);
  fmt_write ("{", true);
  {
    wr_common_attribs ();
    fmt_write ("copytruncate");
  }
  fmt_write ("}", true);

  if (!ofile) {
    RW_MA_INST_LOG (instance_, InstanceError, 
        "Failure while writing to configuration file");
    unlink (LOGROTATE_CFG_FILE);
    return RWDTS_ACTION_NOT_OK;
  }

  ofile.close();
  return RWDTS_ACTION_OK;
}


StartStatus ConfdLog::show_logs(SbReqRpc* rpc,
         const RWPB_T_MSG(RwMgmtagt_input_ShowAgentLogs)* req)
{
  RWMEMLOG (memlog_buf_, RWMEMLOG_MEM2, "show logs");
  RW_ASSERT (req);
  RW_MA_INST_LOG(instance_, InstanceInfo, "Reading management system logs.");

  if (req->has_string) {
    return output_to_string(rpc);
  } else {
    return output_to_file(rpc, req->file);
  }
}

std::string ConfdLog::get_log_records(const std::string& file)
{
  RWMEMLOG (memlog_buf_, RWMEMLOG_MEM2, "get log records");
  RW_MA_INST_LOG (instance_, InstanceDebug, "Get log records from log file");

  std::string records;
  std::ifstream in(file, std::ios::in | std::ios::binary);
  if (in) {
    std::ostringstream contents;
    contents << in.rdbuf();
    records = std::move(contents.str());
    in.close();
  } else {
    std::string log("Log file not found: ");
    log += file;
    RW_MA_INST_LOG (instance_, InstanceError, log.c_str());
  }
  return records;
}

StartStatus ConfdLog::output_to_string(SbReqRpc* rpc)
{
  RWMEMLOG (memlog_buf_, RWMEMLOG_MEM2, "output to string");
  RW_MA_INST_LOG (instance_, InstanceDebug, "Output logs records to string");

  RWPB_M_MSG_DECL_INIT(RwMgmtagt_AgentLogsOutput, output);
  output.n_result = logs_.size();
  output.result = (RWPB_T_MSG(RwMgmtagt_AgentLogsOutput_Result) **)
     RW_MALLOC (sizeof (RWPB_T_MSG(RwMgmtagt_AgentLogsOutput_Result)*) * output.n_result);

  std::vector<RWPB_T_MSG(RwMgmtagt_AgentLogsOutput_Result)>
    results (output.n_result);
  std::vector<std::string> records(output.n_result);
  size_t idx = 0;

  for (auto& file: logs_) {
    RWPB_M_MSG_DECL_INIT(RwMgmtagt_AgentLogsOutput_Result, res);
    records[idx] = get_log_records(file);
    res.log_records = &records[idx][0];
    res.log_name = &logs_[idx][0];
    results[idx] = res;

    output.result[idx] = &results[idx];
    idx++;
  }

  // Send the response
  rpc->internal_done(
      &RWPB_G_PATHSPEC_VALUE(RwMgmtagt_AgentLogsOutput)->rw_keyspec_path_t, &output.base);

  RW_FREE (output.result);

  return StartStatus::Done;
}

StartStatus ConfdLog::output_to_file(SbReqRpc* rpc,
                                     const std::string& file_name)
{
  RWMEMLOG (memlog_buf_, RWMEMLOG_MEM2, "output to file");
  RW_MA_INST_LOG (instance_, InstanceDebug, "Output logs records to file");

  std::string ofile = get_rift_install() + "/" + file_name;
  std::ofstream out(ofile);

  for (auto& file: logs_) {
    out << "------" << file << "-----------\n";
    out << get_log_records(file);
    out << "-------------------------------\n";
  }
  out.close();

  if (!out) {
    // error
    NetconfErrorList nc_errors;
    NetconfError& err = nc_errors.add_error();
    std::string log("Error while writing to file: ");
    log += ofile;
    err.set_error_message(log.c_str());
    rpc->internal_done(&nc_errors);
  } else {
    RWPB_M_MSG_DECL_INIT(RwMgmtagt_AgentLogsOutput, output);
    output.n_result = 1;
    output.result = (RWPB_T_MSG(RwMgmtagt_AgentLogsOutput_Result) **)
       RW_MALLOC (sizeof (RWPB_T_MSG(RwMgmtagt_AgentLogsOutput_Result)*) * output.n_result);

    RWPB_M_MSG_DECL_INIT(RwMgmtagt_AgentLogsOutput_Result, res);
    output.result[0] = &res;

    res.log_name = (char*)"All files";
    std::string rec("Log records saved to file: ");
    rec += ofile;
    res.log_records = &rec[0];

    rpc->internal_done(
         &RWPB_G_PATHSPEC_VALUE(RwMgmtagt_AgentLogsOutput)->rw_keyspec_path_t, &output.base);
    RW_FREE (output.result);
  }

  return StartStatus::Done;
}
