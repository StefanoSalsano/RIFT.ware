/*
 * 
 * (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
 *
 */
import Alt from './skyquakeAltInstance.js';
import $ from 'jquery';
import SkyquakeContainerActions from './skyquakeContainerActions'

export default {
    getNav: function() {
    return {
      remote: function() {
        return new Promise(function(resolve, reject) {
          $.ajax({
            url: '/nav',
            type: 'GET',
            // beforeSend: Utils.addAuthorizationStub,
            success: function(data) {
              resolve(data);
            }
          })
        })
      },
      success: SkyquakeContainerActions.getSkyquakeNavSuccess,
    }
}
}

