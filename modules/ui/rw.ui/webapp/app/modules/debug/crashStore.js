
/*
 * 
 * (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
 *
 */
import LaunchNetworkServiceSource from '../launchpad/network_service_launcher/launchNetworkServiceSource.js';
import LaunchNetworkServiceActions from '../launchpad/network_service_launcher/launchNetworkServiceActions.js';
var alt = require('../core/alt');
function crashStore () {
this.descriptorCount = 0;
  this.exportAsync(require('./crashSource.js'));
  this.exportAsync(LaunchNetworkServiceSource);
  this.bindActions(require('./crashActions.js'));
  this.bindListeners({
    getCatalogSuccess: LaunchNetworkServiceActions.getCatalogSuccess
  });
}

crashStore.prototype.getCrashDetailsSuccess = function(list) {
  this.setState({
    crashList:list
  })
  console.log('success', list)
};
crashStore.prototype.getCatalogSuccess = function(data) {
  var self = this;
  var descriptorCount = 0;
  data.forEach(function(catalog) {
    descriptorCount += catalog.descriptors.length;
  });

  self.setState({
    descriptorCount: descriptorCount
  });
};

module.exports = alt.createStore(crashStore);;

