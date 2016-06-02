
/*
 * 
 * (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
 *
 */


/**
 * @file rwuagent_sb_req_editcfg.cpp
 *
 * Management agent southbound request support for configuration changes
 */

#include "rwuagent.hpp"
#include "rw_xml_dom_merger.hpp"
#include "rw_xml_validate_dom.hpp"

using namespace rw_uagent;
using namespace rw_yang;

SbReqEditConfig::SbReqEditConfig(
    Instance* instance,
    NbReq* nbreq,
    RequestMode request_mode,
    const char *xml_fragment)
: SbReq(
    instance,
    nbreq,
    RW_MGMTAGT_SB_REQ_TYPE_EDITCONFIG,
    request_mode,
    "SbReqEditConfigString",
    xml_fragment)
{
  // Build the DOM from the fragment.
  // Let any execptions propagate upwards - the clients that start a transaction
  // should handle it?
  RW_MA_SBREQ_LOG (this, __FUNCTION__, xml_fragment);

  std::string error_out;
  rw_yang::XMLDocument::uptr_t req =
      std::move(instance_->xml_mgr()->create_document_from_string(xml_fragment, error_out, false));

  // For deleting a node from the configuration the xml_fragment is expected to
  // contain the attribute operation=delete
  delta_ = std::move(req);

  update_stats(RW_UAGENT_NETCONF_PARSE_REQUEST);
}

SbReqEditConfig::SbReqEditConfig(
    Instance* instance,
    NbReq* nbreq,
    RequestMode request_mode,
    UniquePtrKeySpecPath::uptr_t delete_ks)
  : SbReq(
      instance,
      nbreq,
      RW_MGMTAGT_SB_REQ_TYPE_EDITCONFIG,
      request_mode,
      "SbReqEditConfigDeleteKS")
{
  RW_MA_SBREQ_LOG (this, __FUNCTION__, "for direct delete");

  delta_ = std::move(instance_->xml_mgr()->create_document(instance_->yang_model()->get_root_node()));
  delete_ks_.push_back(std::move(delete_ks));

  instance_->log_file_manager()->log_string(this, "SbReqEditConfigDeleteKS",delta_->to_string().c_str());

  update_stats(RW_UAGENT_NETCONF_PARSE_REQUEST);
}

SbReqEditConfig::SbReqEditConfig(
    Instance* instance,
    NbReq* nbreq,
    RequestMode request_mode,
    XMLBuilder *builder)
: SbReq(
    instance,
    nbreq,
    RW_MGMTAGT_SB_REQ_TYPE_EDITCONFIG,
    request_mode,
    "SbReqEditConfigDom")
{
  delta_ = std::move(builder->merge_);
  delete_ks_.splice (delete_ks_.begin(), builder->delete_ks_);

  instance_->log_file_manager()->log_string(this, "SbReqEditConfigDom", delta_->to_string().c_str());

  update_stats(RW_UAGENT_NETCONF_PARSE_REQUEST);
}

SbReqEditConfig::~SbReqEditConfig ()
{
  instance_->update_stats(sbreq_type(), req_.c_str(), &statistics_);
}

StartStatus SbReqEditConfig::start_xact_int()
{
  RWMEMLOG(memlog_buf_, RWMEMLOG_MEM2, "xact edit-config start" );

  xact_ = rwdts_api_xact_create(
    dts_->api(),
    RWDTS_XACT_FLAG_ADVISE|dts_flags_,
    dts_config_event_cb,
    this);

  RWMEMLOG(memlog_buf_, RWMEMLOG_MEM2, "xact dts created",
    RWMEMLOG_ARG_PRINTF_INTPTR("dts xact=0x%" PRIXPTR, (intptr_t)xact_) );

  if (request_mode_ == RequestMode::CONFD) {
    auto *root_node = delta_->get_root_node();
    ProtoSplitter splitter(xact_, instance_->yang_model(),
                           dts_flags_, root_node);
    XMLWalkerInOrder walker(root_node->get_first_child());
    walker.walk(&splitter);
    // The transaction is all set to be shipped now?
    if (!(splitter.valid_ || delete_ks_.size())) {
      RW_MA_SBREQ_LOG (this, __FUNCTION__, "Skipping invalid edit config");
      rwdts_xact_abort(xact_, RW_STATUS_FAILURE, "Unable to convert edit-config to protobuf" );
      return done_with_error( "Unable to convert edit-config to protobuf" );
    }
    
  } else if (request_mode_ == RequestMode::XML) {

    XMLDocMerger merger(instance_->xml_mgr(), instance_->dom());
    bool no_edits = true;

    // Callback from copy_and_merge operation. Populate the xact_ with 
    // config xml changes
    merger.on_update_ = [&no_edits, this](XMLNode* update_node) {
      ProtoSplitter splitter(xact_, instance_->yang_model(),
                             dts_flags_, update_node);
      XMLWalkerInOrder walker(update_node->get_first_child());
      walker.walk(&splitter);
      if (!splitter.valid_) {
        return RW_STATUS_FAILURE;
      }
      no_edits = false;
      return RW_STATUS_SUCCESS;
    };

    merger.on_delete_ = [&no_edits, this](UniquePtrKeySpecPath::uptr_t del_ks) {
      delete_ks_.push_back(std::move(del_ks));
      no_edits = false;
      return RW_STATUS_SUCCESS; 
    };

    NetconfErrorList err_list;
    merger.on_error_ = [&err_list](rw_yang_netconf_op_status_t nc_status,
                                   const char* err_msg, const char* err_path) {
      NetconfError& err = err_list.add_error().set_rw_error_tag(nc_status);
      if (err_msg) {
        err.set_error_message(err_msg);
      }
      if (err_path) {
        err.set_error_path(err_path);
      }
      return RW_STATUS_SUCCESS; 
    };

    new_instance_dom_ = std::move(merger.copy_and_merge(delta_.get()));

    if (err_list.length()) {
      RW_MA_SBREQ_LOG (this, __FUNCTION__, "Edit config merge error");
      return done_with_error(&err_list);
    }

    // The transaction is all set to be shipped now?
    if (!(new_instance_dom_ || delete_ks_.size())) {
      RW_MA_SBREQ_LOG (this, __FUNCTION__, "Skipping invalid edit config");
      rwdts_xact_abort(xact_, RW_STATUS_FAILURE, "Unable to convert edit-config to protobuf" );
      return done_with_error( "Unable to convert edit-config to protobuf" );
    }

    if (no_edits) {
      // No Updates or Deletes
       RW_MA_SBREQ_LOG (this, __FUNCTION__, "Nothing to Update/Delete");
      return done_with_success();
    }

    // Validate pending dom
    ValidationStatus validation_result = validate_dom(new_instance_dom_.get(), instance_);
    if (validation_result.failed()) {
      std::string log_str = "Validation failed: " + validation_result.reason();
      RW_MA_SBREQ_LOG (this, __FUNCTION__, log_str.c_str());
      rwdts_xact_abort(xact_, RW_STATUS_FAILURE, log_str.c_str());
      return done_with_error( log_str.c_str());
    }

    // save the dom
    rw_status_t rs = instance_->mgmt_handler()->prepare_config(new_instance_dom_.get());
    if (rs != RW_STATUS_SUCCESS) {
      RW_MA_SBREQ_LOG (this, __FUNCTION__, "Failed to save config dom");
    }

  } else {
    RW_ASSERT_NOT_REACHED();
  }

  for (auto &ks : delete_ks_) {
    rwdts_xact_block_t *blk = rwdts_xact_block_create(xact_);
    RW_ASSERT(blk);

    rw_status_t rs = rwdts_xact_block_add_query_ks(
        blk, ks.get(), RWDTS_QUERY_DELETE, RWDTS_XACT_FLAG_ADVISE | dts_flags_,
        0, nullptr);
    if (rs != RW_STATUS_SUCCESS) {
      RW_MA_SBREQ_LOG (this, __FUNCTION__, "DTS Query add block failed");
      return done_with_error( "DTS operation failed" );
    }

    rs = rwdts_xact_block_execute(blk, dts_flags_, NULL, NULL, NULL);
    RW_ASSERT(rs == RW_STATUS_SUCCESS);
  }

  rw_status_t rs = rwdts_xact_commit(xact_);
  RW_MA_SBREQ_LOG (this, __FUNCTION__, "Executing transaction");
  RW_ASSERT(RW_STATUS_SUCCESS == rs);
  update_stats(RW_UAGENT_NETCONF_DTS_XACT_START);

  return StartStatus::Async;
}

void SbReqEditConfig::dts_config_event_cb(
  rwdts_xact_t *xact,
  rwdts_xact_status_t* xact_status,
  void *ud)
{

  const bool alive = xact_status->xact_done;
  if (alive) {
    SbReqEditConfig *edit_cfg = static_cast<SbReqEditConfig *> (ud);
    RW_ASSERT (edit_cfg);
    edit_cfg->commit_cb (xact);
  }
}

void SbReqEditConfig::commit_cb(rwdts_xact_t *xact)
{
  RWMEMLOG(memlog_buf_, RWMEMLOG_MEM2, "dts xact callback",
    RWMEMLOG_ARG_PRINTF_INTPTR("dts xact=0x%" PRIXPTR, (intptr_t)xact_) );

  update_stats( RW_UAGENT_NETCONF_DTS_XACT_DONE );

  rwdts_xact_status_t status;
  auto rs = rwdts_xact_get_status (xact, &status);
  RW_ASSERT(RW_STATUS_SUCCESS == rs);

  switch (status.status) {
    case RWDTS_XACT_COMMITTED: {
      RW_MA_SBREQ_LOG (this, __FUNCTION__, "RWDTS_XACT_COMMITTED");
      if (request_mode_ == RequestMode::XML) {
        // Update the instance dom to reflect that changes
        instance_->reset_dom(std::move(new_instance_dom_));
      
        auto ret = instance_->mgmt_handler()->commit_config();
        if (ret != RW_STATUS_SUCCESS) {
          RWMEMLOG (memlog_buf_, RWMEMLOG_MEM6, "commit config failed",
                    RWMEMLOG_ARG_PRINTF_INTPTR("sbreq=0x%" PRIX64,(intptr_t)this),
                    RWMEMLOG_ARG_PRINTF_INTPTR("dts xact=0x%" PRIXPTR, (intptr_t)xact));
        }
      }
      update_stats( RW_UAGENT_NETCONF_RESPONSE_BUILT );
      done_with_success();
      return;
    }

    default:
    case RWDTS_XACT_FAILURE:
    case RWDTS_XACT_ABORTED: {

      RW_MA_SBREQ_LOG (this, __FUNCTION__, "RWDTS_XACT_ABORTED");
      rw_status_t rs;
      char *err_str = nullptr;
      char *xpath = nullptr;
      NetconfErrorList nc_errors;

      if (RW_STATUS_SUCCESS ==
          rwdts_xact_get_error_heuristic(xact, 0, &xpath, &rs, &err_str)) {
        RWMEMLOG(memlog_buf_, RWMEMLOG_MEM6, "Error response",
                 RWMEMLOG_ARG_PRINTF_INTPTR("sbreq=0x%" PRIX64,(intptr_t)this),
                 RWMEMLOG_ARG_PRINTF_INTPTR("dts xact=0x%" PRIXPTR, (intptr_t)xact) );

        NetconfError& err = nc_errors.add_error();
        if (xpath) {
          err.set_error_path(xpath);
          RW_FREE(xpath);
          xpath = nullptr;
        }
        err.set_rw_error_tag(rs);
        if (err_str) {
          err.set_error_message(err_str);
          RW_FREE(err_str);
          err_str = nullptr;
        }
      }

      if (!nc_errors.length()) {
        nc_errors.add_error()
                 .set_error_message( "Distributed transaction aborted or failed" );
      }

      if (instance_->get_request_mode() == RequestMode::XML
          && instance_->mgmt_handler()->is_under_reload()) {
        // update config dom
        instance_->reset_dom(std::move(new_instance_dom_));
      }

      done_with_error (&nc_errors);
      return;
    }
  }
}

rw_yang::XMLDocument::uptr_t SbReqEditConfig::move_delta()
{
  return std::move(delta_);
}

std::list<UniquePtrKeySpecPath::uptr_t> SbReqEditConfig::move_deletes()
{
  return std::move(delete_ks_);
}
