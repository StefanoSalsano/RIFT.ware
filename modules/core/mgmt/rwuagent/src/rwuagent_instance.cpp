
/*
 * 
 * (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
 *
 */


/**
 * @file rwuagent_instance.cpp
 *
 * Management agent instance.
 */

#include <memory>

#include "rwvcs.h"
#include "rw_pb_schema.h"
 
#include "rwuagent.hpp"
#include "rwuagent_msg_client.h"

using namespace rw_uagent;
using namespace rw_yang;


RW_CF_TYPE_DEFINE("RW.uAgent RWTasklet Component Type", rwuagent_component_t);
RW_CF_TYPE_DEFINE("RW.uAgent RWTasklet Instance Type", rwuagent_instance_t);

const char *rw_uagent::uagent_yang_ns = "http://riftio.com/ns/riftware-1.0/rw-mgmtagt";

rwuagent_component_t rwuagent_component_init(void)
{
  rwuagent_component_t component = (rwuagent_component_t)RW_CF_TYPE_MALLOC0(sizeof(*component), rwuagent_component_t);
  RW_CF_TYPE_VALIDATE(component, rwuagent_component_t);

  return component;
}

void rwuagent_component_deinit(
    rwuagent_component_t component)
{
  RW_CF_TYPE_VALIDATE(component, rwuagent_component_t);
}

rwuagent_instance_t rwuagent_instance_alloc(
    rwuagent_component_t component,
    struct rwtasklet_info_s * rwtasklet_info,
    RwTaskletPlugin_RWExecURL *instance_url)
{
  // Validate input parameters
  RW_CF_TYPE_VALIDATE(component, rwuagent_component_t);
  RW_ASSERT(instance_url);

  // Allocate a new rwuagent_instance structure
  rwuagent_instance_t instance = (rwuagent_instance_t) RW_CF_TYPE_MALLOC0(sizeof(*instance), rwuagent_instance_t);
  RW_CF_TYPE_VALIDATE(instance, rwuagent_instance_t);
  instance->component = component;

  // Save the rwtasklet_info structure
  instance->rwtasklet_info = rwtasklet_info;

  // Allocate the real instance structure
  instance->instance = new Instance(instance);

  // Return the allocated instance
  return instance;
}

void rwuagent_instance_free(
    rwuagent_component_t component,
    rwuagent_instance_t instance)
{
  // Validate input parameters
  RW_CF_TYPE_VALIDATE(component, rwuagent_component_t);
  RW_CF_TYPE_VALIDATE(instance, rwuagent_instance_t);
}

rwtrace_ctx_t* rwuagent_get_rwtrace_instance(
    rwuagent_instance_t instance)
{
  RW_CF_TYPE_VALIDATE(instance, rwuagent_instance_t);
  return instance->rwtasklet_info ? instance->rwtasklet_info->rwtrace_instance : NULL;
}

void rwuagent_instance_start(
    rwuagent_component_t component,
    rwuagent_instance_t instance)
{
  RW_CF_TYPE_VALIDATE(component, rwuagent_component_t);
  RW_CF_TYPE_VALIDATE(instance, rwuagent_instance_t);
  RW_ASSERT(instance->component == component);
  RW_ASSERT(instance->instance);
  instance->instance->start();
}

void rw_management_agent_xml_log_cb(void *user_data,
                                    rw_xml_log_level_e level,
                                    const char *fn,
                                    const char *log_msg)
{
  /*
   * ATTN: These messages need to get back to the transaction that
   * generated them, so that they can be included in the NETCONF error
   * response, if any.
   *
   * ATTN: I think RW.XML needs more context when generating messages -
   * just binding the errors to manage is insufficient - need to
   * actually bind the messages to a particular client/xact.
   */
  auto *inst = static_cast<Instance*>(user_data);

  switch (level) {
    case RW_XML_LOG_LEVEL_DEBUG:
      RW_MA_DOMMGR_LOG (inst, DommgrDebug, fn, log_msg);
      break;
    case RW_XML_LOG_LEVEL_INFO:
      RW_MA_DOMMGR_LOG (inst, DommgrNotice, fn, log_msg);
      break;
    case RW_XML_LOG_LEVEL_ERROR:
      RW_MA_DOMMGR_LOG (inst, DommgrError, fn, log_msg);
      break;
    default:
      RW_ASSERT_NOT_REACHED();
  }
}

/**
 * Construct a uAgent instance.
 */
Instance::Instance(rwuagent_instance_t rwuai)
    : memlog_inst_("MgmtAgent", 200),
      memlog_buf_(
          memlog_inst_,
          "Instance",
          reinterpret_cast<intptr_t>(this)),
      rwuai_(rwuai),
      //ATTN: management system handler could be either for Confd or
      // libnetconf server. Currently defaulting to 
      // Confd.
      initializing_composite_schema_(true),
      mgmt_handler_(new ConfdMgmtSystem(this))      
{
  RWMEMLOG_TIME_SCOPE(memlog_buf_, RWMEMLOG_MEM2, "Instance constructor");
  RW_CF_TYPE_VALIDATE(rwuai_, rwuagent_instance_t);

  // ATTN: stdout?  is that for error logs?  Don't we want to capture that?
  confd_init ("rwUagent", stdout, CONFD_DEBUG);

  // Create a concurrent dispatch queue for multi-threading.
  concurrent_q_ = rwsched_dispatch_queue_create(
      rwsched_tasklet(), 
      "agent-cc-queue", 
      RWSCHED_DISPATCH_QUEUE_CONCURRENT);
  
  upgrade_ctxt_.serial_upgrade_q_ = rwsched_dispatch_queue_create(
      rwsched_tasklet(),
      "upgrade-queue",
      RWSCHED_DISPATCH_QUEUE_SERIAL);

  schema_load_q_ = rwsched_dispatch_queue_create(
      rwsched_tasklet(),
      "schema-load-queue",
      RWSCHED_DISPATCH_QUEUE_SERIAL);

  serial_q_ = rwsched_dispatch_queue_create(
      rwsched_tasklet(),
      "agent-serial-queue",
      RWSCHED_DISPATCH_QUEUE_SERIAL);
}

/**
 * Destroy a uAgent instance.
 */
Instance::~Instance()
{
  // ATTN: close the messaging services and channels

  // ATTN: Iterate through all the Clients, destroying them

  rwmemlog_instance_dts_deregister(memlog_inst_, false/*dts_internal*/);

  // De-register the memlog instance of the xmlmgr.
  rwmemlog_instance_dts_deregister(xml_mgr_->get_memlog_inst(), false/*dts_internal*/);

  RW_CF_TYPE_VALIDATE(rwuai_, rwuagent_instance_t);
}

void Instance::async_start(void *ctxt)
{
  auto* self = static_cast<Instance*>(ctxt);
  RW_ASSERT (self);
  auto& memlog_buf = self->memlog_buf_;

  RWMEMLOG( memlog_buf, RWMEMLOG_MEM2, "setup dom" );
  self->setup_dom("rw-mgmtagt-composite");

  RWMEMLOG( memlog_buf, RWMEMLOG_MEM2, "load schema" );

#if 0 // RIFT-10722
  char* err_str = nullptr;
  rw_yang_validate_schema("rw-mgmtagt-composite", &err_str);
  
  if (err_str) {
    RW_MA_INST_LOG(self, InstanceError, err_str);
    free (err_str);
  }
#endif

  // Load the schema specified at boot time
  self->ypbc_schema_ = rw_load_schema("librwuagent_yang_gen.so", "rw-mgmtagt-composite");
  RW_ASSERT(self->ypbc_schema_);

  RWMEMLOG( memlog_buf, RWMEMLOG_MEM2, "register schema" );
  self->yang_model()->load_schema_ypbc(self->ypbc_schema_);

  rw_status_t status = self->yang_model()->register_ypbc_schema(self->ypbc_schema_);
  if ( RW_STATUS_SUCCESS != status ) {
    RW_MA_INST_LOG(self, InstanceCritInfo, "Error while registering for ypbc schema.");
  }

  rwsched_dispatch_async_f(self->rwsched_tasklet(),
                           rwsched_dispatch_get_main_queue(self->rwsched()),
                           self,
                           Instance::async_start_dts);
}


void Instance::async_start_dts(void *ctxt)
{
  auto* self = static_cast<Instance*>(ctxt);
  RW_ASSERT (self);
  auto& memlog_buf = self->memlog_buf_;

  RWMEMLOG( memlog_buf, RWMEMLOG_MEM2, "start dts member" );
  self->dts_ = new DtsMember(self);

  RWMEMLOG( memlog_buf, RWMEMLOG_MEM2, "register rwmemlog" );
  rwmemlog_instance_dts_register( self->memlog_inst_,
                                  self->rwtasklet(),
                                  self->dts_->api() );

  RWMEMLOG( memlog_buf, RWMEMLOG_MEM2, "register XMLMgr rwmemlog instance" );
  rwmemlog_instance_dts_register( self->xml_mgr_->get_memlog_inst(),
                                  self->rwtasklet(),
                                  self->dts_->api() );

  // ATTN: Move this to a manager?
  RWMEMLOG( memlog_buf, RWMEMLOG_MEM2, "start dynamic schema driver" );
  self->schema_driver_.reset( new DynamicSchemaDriver(self, self->dts_->api()) );
  rwsched_dispatch_async_f(self->rwsched_tasklet(), // ATTN: Should be in constr?
                           rwsched_dispatch_get_main_queue(self->rwsched()),
                           self->schema_driver_.get(),
                           DynamicSchemaDriver::run);

  RWMEMLOG( memlog_buf, RWMEMLOG_MEM2, "register schema listener" );
  if (AgentDynSchemaHelper::register_for_dynamic_schema(self) != RW_STATUS_SUCCESS) {
    RW_MA_INST_LOG(self, InstanceError, "Error while registering for dynamic schema.");
    return;
  } 

  if (self->confd_addr_) {
    RWMEMLOG( memlog_buf, RWMEMLOG_MEM2, "configure confd proc" );
    self->mgmt_handler_->create_proxy_manifest_config();
  }

  // Instantiate the rw-msg interfaces
  RWMEMLOG( memlog_buf, RWMEMLOG_MEM2, "start messaging server" );
  self->msg_client_ = new MsgClient(self);

  rwsched_dispatch_async_f(self->rwsched_tasklet(),
                           rwsched_dispatch_get_main_queue(self->rwsched()),
                           self,
                           Instance::async_start_confd);

}

void Instance::async_start_confd(void* ctxt)
{
  auto* self = static_cast<Instance*>(ctxt);
  RW_ASSERT (self);
  auto& memlog_buf = self->memlog_buf_;

  if (self->initializing_composite_schema_) {
    // still loading composite schema, try again
    RWMEMLOG( memlog_buf, RWMEMLOG_MEM2, "waiting on composite to start confd" );
    rwsched_dispatch_async_f(self->rwsched_tasklet(),
                             rwsched_dispatch_get_main_queue(self->rwsched()),
                             self,
                             Instance::async_start_confd);
    return;
  }
 
  // initialize confd 
  if (self->confd_addr_) {

    RWMEMLOG( memlog_buf, RWMEMLOG_MEM2, "start confd data provider" );
    self->confd_config_ = new NbReqConfdConfig(self);

    RWMEMLOG( memlog_buf, RWMEMLOG_MEM2, "start confd daemon" );
    self->confd_daemon_ = new ConfdDaemon(self);

    RWMEMLOG( memlog_buf, RWMEMLOG_MEM2, "attempt confd connection" );
    self->try_confd_connection();
  }

  // Register for logrotate config subscription
  RWMEMLOG( memlog_buf, RWMEMLOG_MEM2, "register logrotate cfg subscription" );
  self->confd_daemon_->confd_log()->register_config();
}


void Instance::dyn_schema_dts_registration(void *ctxt)
{
  auto *self = static_cast<Instance*>(ctxt);
  RW_ASSERT (self);

  self->dts_->load_registrations(self->yang_model());

  self->initializing_composite_schema_ = false;
}

void Instance::start()
{
  RWMEMLOG_TIME_SCOPE(memlog_buf_, RWMEMLOG_MEM2, "start agent");

  rw_status_t rwstatus;
  char cmdargs_var_str[] = "$cmdargs_str";
  char cmdargs_str[1024];
  int argc = 0;
  char **argv = NULL;
  gboolean ret;

  yang_schema_ = "rwuagent";
  std::string log_string;
  RW_MA_INST_LOG(this, InstanceInfo, (log_string = "Schema configured is " + yang_schema_).c_str());

  // HACK: This eventually need to come from management agent
  rwstatus = rwvcs_variable_evaluate_str(rwvcs(),
                                         cmdargs_var_str,
                                         cmdargs_str,
                                         sizeof(cmdargs_str));
  RW_ASSERT(RW_STATUS_SUCCESS == rwstatus);

  std::string log_str = "cmdargs_str";
  log_str += cmdargs_str;

  RW_MA_INST_LOG(this, InstanceCritInfo, log_str.c_str());

  ret = g_shell_parse_argv(cmdargs_str, &argc, &argv, NULL);
  RW_ASSERT(ret == TRUE);

  rwyangutil::ArgumentParser arg_parser(argv, argc);
  ret = parse_cmd_args(arg_parser);
  if (!ret) {
    RW_MA_INST_LOG (this, InstanceError, "Bad arguments given to Agent."
        "Using default arguments");
  }

  g_strfreev (argv);

  // set rift environment variables for rw.cli to connect to confd
  // ATTN: this should be read from the manifest when the agent generates confd.conf at runtime (RIFT-5059)
  rw_status_t const status = rw_setenv("NETCONF_PORT_NUMBER","2022");

  if (status != RW_STATUS_SUCCESS) {
    RW_MA_INST_LOG(this,
                   InstanceError,
                   "Couldn't set NETCONF port number in Rift environment variable");
  }

  // Set the instance name
  instance_name_ = rwtasklet()->identity.rwtasklet_name;

  rwsched_dispatch_async_f(rwsched_tasklet(),
                           schema_load_q_,
                           this,
                           Instance::async_start);
}


bool Instance::parse_cmd_args(const rwyangutil::ArgumentParser& arg_parser)
{
  RWMEMLOG_TIME_SCOPE(memlog_buf_, RWMEMLOG_MEM2, "parse cmd args");
  bool status = true;

  std::string proto;
  if (arg_parser.exists("--confd-proto")) {
    proto = arg_parser.get_param("--confd-proto");
  } else {
    RW_MA_INST_LOG(this, InstanceError, "Confd proto not provided. Taking default as AF_INET");
    proto = "AF_INET";
    status = false;
  }

  if (proto == "AF_INET") {
    if (arg_parser.exists("--confd-ip")) {
      auto ret = inet_aton(arg_parser.get_param("--confd-ip").c_str(), 
                           &confd_inet_addr_.sin_addr);
      if (ret == 0) {
        std::string log;
        log = "Incorrect IP address passed: " + arg_parser.get_param("--confd-ip");
        RW_MA_INST_LOG (this, InstanceError, log.c_str());
        inet_aton("127.0.0.1", &confd_inet_addr_.sin_addr);
        status = false;
      }
    } else {
      auto ret = inet_aton("127.0.0.1", &confd_inet_addr_.sin_addr);
      if (ret == 0) {
        RW_MA_INST_LOG (this, InstanceError, "Failed to convert localhost to network byte");
        status = false;
      }
    }
    uint32_t port = CONFD_PORT;
    if (arg_parser.exists("--confd-port")) {
      port = atoi(arg_parser.get_param("--confd-port").c_str());
      if (port == 0 || port > 65535) {
        RW_MA_INST_LOG (this, InstanceError, "Port must be between 0 and 65536");
        port = CONFD_PORT;
        status = false;
      }
    }
    confd_inet_addr_.sin_port = htons(port);
    confd_inet_addr_.sin_family = AF_INET;
    confd_inet_addr_.sin_addr.s_addr = INADDR_ANY;
    confd_addr_ = (struct sockaddr *) &confd_inet_addr_;
    confd_addr_size_ = sizeof (confd_inet_addr_);
  } 
  else if (proto == "AF_UNIX") {
    if (arg_parser.exists("--confd-unix-path")) {
      confd_unix_socket_ = arg_parser.get_param("--confd-unix-path");

      memset (&confd_unix_addr_, 0, sizeof (confd_unix_addr_));
      strcpy (confd_unix_addr_.sun_path, confd_unix_socket_.c_str());
      confd_unix_addr_.sun_family = AF_UNIX;

      confd_addr_ = (struct sockaddr *) &confd_unix_addr_;
      confd_addr_size_ = sizeof (confd_unix_addr_);
    }
  }

  if (arg_parser.exists("--confd_ws")) {
    unique_ws_ = true;
    mgmt_workspace_ = arg_parser.get_param("--confd_ws");
  }

  return status;
}


rw_status_t Instance::handle_dynamic_schema_update(const int batch_size,
                                                   rwdynschema_module_t * modules)
{
  RWMEMLOG_TIME_SCOPE(memlog_buf_, RWMEMLOG_MEM2, "handle dynamic schema");

  rw_status_t status = RW_STATUS_SUCCESS;
  update_dyn_state(RW_MGMT_SCHEMA_APPLICATION_STATE_WORKING);

  for (int i = 0; i < batch_size; ++i) {
    RW_ASSERT(modules[i].module_name);
    RW_ASSERT(modules[i].so_filename);

    module_details_t mod;
    mod.module_name = modules[i].module_name;
    mod.so_filename = modules[i].so_filename;
    mod.exported    = modules[i].exported;

    pending_schema_modules_.emplace_front(mod);
  }
  // start confd in-service upgrade
  // ATTN: Signature to be changed based upon
  // the future of CLI command for upgrade
  if (initializing_composite_schema_) {
    // loading composite schema on boot
    perform_dynamic_schema_update();
  } else {   
    // normal dynamic schema operation
    start_upgrade(1, nullptr);
  }
  RW_MA_INST_LOG(this, InstanceInfo, "Dynamic schema update callback completed");

  return status;
}


rw_status_t Instance::perform_dynamic_schema_update()
{
  RWMEMLOG_TIME_SCOPE(memlog_buf_, RWMEMLOG_MEM2, "perform dynamic schema");

  for (const module_details_t& module : pending_schema_modules_) {
    auto module_name = module.module_name.c_str();
    auto so_filename = module.so_filename.c_str();

    const rw_yang_pb_schema_t* new_schema = rw_load_schema(so_filename, module_name);
    RW_ASSERT(new_schema);
    
    // make a temporary model in case of failure
    auto *tmp_model = rw_yang::YangModelNcx::create_model();
    RW_ASSERT(tmp_model);

    tmp_model->load_schema_ypbc(new_schema);
    rw_status_t status = tmp_model->register_ypbc_schema(new_schema);
    if ( RW_STATUS_SUCCESS != status ) {
      RW_MA_INST_LOG(this, InstanceCritInfo, "Error while registering for ypbc schema.");
    }

    // Create new schema
    const rw_yang_pb_schema_t * merged_schema = rw_schema_merge(nullptr, ypbc_schema_, new_schema);

    if (!merged_schema) {
      std::string log_str;
      RW_MA_INST_LOG(this, InstanceError,
                     (log_str=std::string("Dynamic schema update for ")
                      + module_name + so_filename+ " failed").c_str());

      return RW_STATUS_FAILURE;
    }
  
    RW_MA_INST_LOG(this, InstanceDebug, "Load and merge completed.");

    load_module(module_name);
    // Overwrite the old schema with new
    ypbc_schema_ = merged_schema;

    if (module.exported) {
      exported_modules_.emplace(module.module_name);
    }

    tmp_models_.emplace_back(tmp_model);
    yang_model()->load_schema_ypbc(merged_schema);

    status = yang_model()->register_ypbc_schema(merged_schema);
    if ( RW_STATUS_SUCCESS != status ) {
      RW_MA_INST_LOG(this, InstanceCritInfo, "Error while registering for ypbc schema.");
    }
  }

  rwdts_api_set_ypbc_schema( dts_api(), ypbc_schema_ );

  rwsched_dispatch_async_f(rwsched_tasklet(),
                           rwsched_dispatch_get_main_queue(rwsched()),
                           this,
                           Instance::dyn_schema_dts_registration);

  pending_schema_modules_.clear();

  return fill_in_confd_info();
}

rw_status_t Instance::fill_in_confd_info()
{
  if (!initializing_composite_schema_
      && confd_load_schemas(confd_addr_, confd_addr_size_) != CONFD_OK) {
    RW_MA_INST_LOG (this, InstanceNotice,
                    "RW.uAgent - load of  Confdb schema failed.");
    return RW_STATUS_FAILURE;
  }

  bool ret = xml_mgr_->get_yang_model()->app_data_get_token(
      YANGMODEL_ANNOTATION_KEY, 
      YANGMODEL_ANNOTATION_CONFD_NS,
      &xml_mgr_->get_yang_model()->adt_confd_ns_);
  RW_ASSERT(ret);

  ret = xml_mgr_->get_yang_model()->app_data_get_token(
      YANGMODEL_ANNOTATION_KEY, 
      YANGMODEL_ANNOTATION_CONFD_NAME,
      &xml_mgr_->get_yang_model()->adt_confd_name_);
  RW_ASSERT(ret);

  if (!initializing_composite_schema_) {
    annotate_yang_model_confd();
  }

  return RW_STATUS_SUCCESS;
}

void Instance::close_cf_socket(rwsched_CFSocketRef s)
{
  RWMEMLOG_TIME_SCOPE(memlog_buf_, RWMEMLOG_MEM2, "close cf socket");
  rwsched_instance_ptr_t sched = rwsched();
  rwsched_tasklet_ptr_t tasklet = rwsched_tasklet();
  rwsched_CFRunLoopRef runloop = rwsched_tasklet_CFRunLoopGetCurrent(tasklet);

  cf_src_map_t::iterator src = cf_srcs_.find (s);
  RW_ASSERT (src != cf_srcs_.end());

  rwsched_tasklet_CFRunLoopRemoveSource(tasklet,runloop,src->second,sched->main_cfrunloop_mode);
  cf_srcs_.erase(src);

  rwsched_tasklet_CFSocketRelease(tasklet, s);
}

void Instance::setup_dom(const char *module_name)
{
  // ATTN: Split this func. XMLMgr and model stuff belongs in instance constr.
  //    ... the doc create and model load belong in separate funcs, and async
  RWMEMLOG_TIME_SCOPE(memlog_buf_, RWMEMLOG_MEM2, "setup dom");

  RW_MA_INST_LOG (this, InstanceDebug, "Setting up configuration dom");
  RW_ASSERT (!xml_mgr_.get()); // ATTN:- Assumption that there is a single instance.
  xml_mgr_ = std::move(xml_manager_create_xerces());
  xml_mgr_->set_log_cb(rw_management_agent_xml_log_cb,this);

  // register app data for confd hash registration
  auto model = yang_model();
  bool ret = model->app_data_get_token(YANGMODEL_ANNOTATION_KEY, YANGMODEL_ANNOTATION_CONFD_NS,
                                       &model->adt_confd_ns_);
  RW_ASSERT(ret);

  ret =  model->app_data_get_token(YANGMODEL_ANNOTATION_KEY, YANGMODEL_ANNOTATION_CONFD_NAME,
                                   &model->adt_confd_name_);
  RW_ASSERT(ret);

  auto *module = load_module(module_name);
  module->mark_imports_explicit();

  dom_ = std::move(xml_mgr_->create_document());
}

YangModule* Instance::load_module(const char* module_name)
{
  RWMEMLOG_TIME_SCOPE(memlog_buf_, RWMEMLOG_MEM2, "load new module",
                      RWMEMLOG_ARG_STRNCPY(32, module_name) );
  RW_MA_INST_LOG(this, InstanceDebug, "Reloading dom with new module");

  YangModule *module = yang_model()->load_module(module_name);
  // ATTN: Should not crash!
  RW_ASSERT(module);

  //ATTN: Need to call mark_imports_explicit for
  //dynamically loaded modules ??
  // locked_cache_set_flag_only

  return module;
}

static inline void recalculate_mean (uint32_t *mean,
                                     uint32_t old_count,
                                     uint32_t new_value)
{
  RW_ASSERT(mean);
  uint64_t sum = (*mean) * old_count;
  *mean = (sum + new_value)/(old_count + 1);
}


void Instance::update_stats(RwMgmtagt_SbReqType type,
                            const char *req,
                            RWPB_T_MSG(RwMgmtagt_SpecificStatistics_ProcessingTimes) *sbreq_stats)
{
  RWMEMLOG_TIME_SCOPE(memlog_buf_, RWMEMLOG_MEM7, "update stats");
  RW_ASSERT(type < RW_MGMTAGT_SB_REQ_TYPE_MAXIMUM);

  if (nullptr == statistics_[type].get()) {
    statistics_[type].reset(new OperationalStats());
    RWPB_F_MSG_INIT (RwMgmtagt_Statistics, &statistics_[type]->statistics);
    statistics_[type]->statistics.operation = type;
    gettimeofday (&statistics_[type]->start_time_, 0);
    statistics_[type]->statistics.has_processing_times = 1;
    statistics_[type]->statistics.has_request_count = 1;
    statistics_[type]->statistics.has_parsing_failed = 1;

  }

  OperationalStats *stats = statistics_[type].get();

  RW_ASSERT(stats->commands.size() <= RWUAGENT_MAX_CMD_STATS);

  if (RWUAGENT_MAX_CMD_STATS == stats->commands.size()) {
    stats->commands.pop_front();
  }
  CommandStat t;
  t.request = req;
  t.statistics = *sbreq_stats;

  stats->commands.push_back (t);
  stats->statistics.request_count++;
  // Update the instance level stats
  if (!sbreq_stats->has_transaction_start_time) {
    stats->statistics.parsing_failed++;
    return;
  }

  // the success count has to be the old success count for recalulating mean
  uint32_t success = stats->statistics.request_count - stats->statistics.parsing_failed - 1;

  RWPB_T_MSG(RwMgmtagt_Statistics_ProcessingTimes) *pt =
      &stats->statistics.processing_times;

  if (!success) {
    // set all the present flags
    pt->has_request_parse_time = 1;
    pt->has_transaction_start_time = 1;
    pt->has_dts_response_time = 1;
    pt->has_response_parse_time = 1;
  }

  recalculate_mean (&pt->request_parse_time, success, sbreq_stats->request_parse_time);
  recalculate_mean (&pt->transaction_start_time, success, sbreq_stats->transaction_start_time);
  recalculate_mean (&pt->dts_response_time, success, sbreq_stats->dts_response_time);
  recalculate_mean (&pt->response_parse_time, success, sbreq_stats->response_parse_time);
}

bool Instance::module_is_exported(std::string const & module_name)
{
  return exported_modules_.count(module_name) > 0;
}
