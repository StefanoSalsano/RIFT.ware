
/*
 * 
 * (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
 *
 */
import NS_ACTIONS from './launchNetworkServiceActions.js';
import $ from 'jquery';
let Utils = require('utils/utils.js');
let rw = require('utils/rw.js');
const API_SERVER = require('utils/rw.js').getSearchParams(window.location).api_server;
const API_PORT = require('utils/rw.js').getSearchParams(window.location).api_port;
const NODE_PORT = API_PORT || 3000;
export default {
  getCatalog() {
    return {
      remote (state) {
        return new Promise((resolve,reject) => {
          $.ajax({
            url: '//' + window.location.hostname + ':' + NODE_PORT + '/launchpad/decorated-catalog?api_server=' + API_SERVER,
            type: 'GET',
            beforeSend: Utils.addAuthorizationStub,
            success: function (data) {
              resolve(
                      typeof(data) == "string" ? JSON.parse(data):data
                      );
            }
          }).fail(function(xhr){
            console.log(xhr)
            //Authentication and the handling of fail states should be wrapped up into a connection class.
            Utils.checkAuthentication(xhr.status);
          });
        });
      },
      success: NS_ACTIONS.getCatalogSuccess,
      error: NS_ACTIONS.getCatalogError
    }
  },
  getCloudAccount() {
    return {
      remote (state, cb) {
        return new Promise((resolve, reject) => {
          $.ajax({
            url: '//' + window.location.hostname + ':' +
              NODE_PORT + '/launchpad/cloud-account?api_server=' +
              API_SERVER,
              type: 'GET',
              beforeSend: Utils.addAuthorizationStub,
              success: function (data) {
                resolve(data);
                if(cb) {
                  cb();
                }
              }
          })
        })
      },
      success: NS_ACTIONS.getCloudAccountSuccess,
      error: NS_ACTIONS.getCloudAccountError
    }
  },
  getDataCenters() {
    return {
      remote () {
        return new Promise((resolve, reject) => {
          $.ajax({
            url: '//' + window.location.hostname + ':' +
              NODE_PORT + '/launchpad/data-centers?api_server=' +
              API_SERVER,
              type: 'GET',
              beforeSend: Utils.addAuthorizationStub,
              success: function (data) {
                resolve(data);
              }
          })
        })
      },
      success: NS_ACTIONS.getDataCentersSuccess,
      error: NS_ACTIONS.getDataCentersError
    }
  },
  getVDU() {
    return {
      remote (state, VNFDid) {
        return new Promise((resolve,reject) => {
          $.ajax({
            url: '//' + window.location.hostname + ':' + NODE_PORT + '/launchpad/vnfd?api_server=' + API_SERVER,
            type: 'POST',
            beforeSend: Utils.addAuthorizationStub,
            dataType:'json',
            data: {
              data: VNFDid
            },
            success: function (data) {
              resolve(
                typeof(data) == "string" ? JSON.parse(data):data
              );
            }
          })
        });
      },
      success: NS_ACTIONS.getVDUSuccess,
      error: NS_ACTIONS.getVDUError
    }
  },
  launchNSR() {
    return {
      remote (state, NSR) {
        return new Promise((resolve, reject) => {
          console.log('Attempting to instantiate NSR:', NSR)
          $.ajax({
            url: '//' + window.location.hostname + ':' + NODE_PORT + '/launchpad/nsr?api_server=' + API_SERVER,
            type: 'POST',
            beforeSend: Utils.addAuthorizationStub,
            dataType:'json',
            data: {
              data: NSR
            },
            success: function (data) {
              resolve(
                      typeof(data) == "string" ? JSON.parse(data):data
                      );
            },
            error: function (err) {
              reject({});
            }
          })
        })
      },
      loading: NS_ACTIONS.launchNSRLoading,
      success: NS_ACTIONS.launchNSRSuccess,
      error: NS_ACTIONS.launchNSRError
    }
  },
  getInputParams() {
    return {
      remote(state, NSDId) {
        return new Promise((resolve, reject) => {
          $.ajax({
            url: '//' + window.location.hostname + ':' + NODE_PORT + '/launchpad/nsd/' + NSDId + '/input-param?api_server=' + API_SERVER,
            type: 'GET',
              beforeSend: Utils.addAuthorizationStub,
              success: function (data) {
                resolve(data);
              }
          });
        });
      }
    }
  },
  getLaunchpadConfig: function() {
    return {
      remote: function() {
        return new Promise(function(resolve, reject) {
          $.ajax({
            url: '//' + window.location.hostname + ':' + NODE_PORT + '/launchpad/config?api_server=' + API_SERVER,
            type: 'GET',
            beforeSend: Utils.addAuthorizationStub,
            success: function(data) {
              resolve(data);
            }
          });
        });
      },
      success: NS_ACTIONS.getLaunchpadConfigSuccess,
      error: NS_ACTIONS.getLaunchpadConfigError
    };
  }
  // getCatalog() {
  //   return {
  //     remote (state) {
  //       return new Promise((resolve,reject) => {
  //         $.ajax({
  //           url: '//' + window.location.hostname + ':' + NODE_PORT + '/launchpad/catalog?api_server=' + API_SERVER,
  //           success: function (data) {
  //             resolve(
  //                     typeof(data) == "string" ? JSON.parse(data):data
  //                     );
  //           }
  //         })
  //       });
  //     },
  //     success: NS_ACTIONS.getCatalogSuccess,
  //     error: NS_ACTIONS.getCatalogError
  //   }
  // }
}