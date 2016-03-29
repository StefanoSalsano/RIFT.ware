
/*
 * 
 * (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
 *
 */

  var API_SERVER =  rw.getSearchParams(window.location).api_server;
  if (!API_SERVER) {
    window.location.href = "//" + window.location.host + '/index.html?api_server=' + window.location.protocol + '//localhost';
  }

  require.ensure(['./modules/missioncontrol/missioncontrol.js', './modules/launchpad/launchpad.js', './modules/login/login.js', './modules/core/app.js'], function() {
    require('./modules/missioncontrol/missioncontrol.js');
    require('./modules/launchpad/launchpad.js');
    require('./modules/core/app.js');
    require('./modules/login/login.js');
    var Utils = require('./modules/utils/utils.js');
    Utils.bootstrapApplication().then(function() {
      angular.bootstrap(document.getElementsByTagName('body'), ['app', 'login']);
    },
    function() {
      console.log('Unable to get response from "inactivity-timeout"');
      angular.bootstrap(document.getElementsByTagName('body'), ['app', 'login']);
    });

  });
