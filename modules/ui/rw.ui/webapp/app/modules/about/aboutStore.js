
/*
 * 
 * (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
 *
 */
import LaunchNetworkServiceSource from '../launchpad/network_service_launcher/launchNetworkServiceSource.js';
import LaunchNetworkServiceActions from '../launchpad/network_service_launcher/launchNetworkServiceActions.js';
var alt = require('../core/alt');
function aboutStore () {
  this.descriptorCount = 0;
  this.exportAsync(require('./aboutSource.js'));
  this.exportAsync(LaunchNetworkServiceSource);
  this.bindActions(require('./aboutActions.js'));
  this.bindListeners({
    getCatalogSuccess: LaunchNetworkServiceActions.getCatalogSuccess
  });
}

aboutStore.prototype.getAboutSuccess = function(list) {
  this.setState({
    aboutList:list
  })
  console.log('success', list)
};
aboutStore.prototype.getCatalogSuccess = function(data) {
  var self = this;
  var descriptorCount = 0;
  data.forEach(function(catalog) {
    descriptorCount += catalog.descriptors.length;
  });

  self.setState({
    descriptorCount: descriptorCount
  });
};

aboutStore.prototype.getCreateTimeSuccess = function(time) {
	this.setState({
		createTime:time['rw-mc:create-time']
	})
	console.log('uptime success', time)
}

module.exports = alt.createStore(aboutStore);;

