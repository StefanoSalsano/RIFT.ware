/*
 * 
 * (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
 *
 */
//This will reach out to the global routes endpoint

import Alt from './skyquakeAltInstance.js';
import SkyquakeContainerSource from './skyquakeContainerSource.js';
import SkyquakeContainerActions from './skyquakeContainerActions';
import loggingActions from '../logging/loggingActions.js';
import LoggingSource from '../logging/loggingSource.js';
//Temporary, until api server is on same port as webserver
var rw = require('utils/rw.js');
var API_SERVER = rw.getSearchParams(window.location).api_server;
var UPLOAD_SERVER = rw.getSearchParams(window.location).upload_server;

class SkyquakeContainerStore {
    constructor() {
        this.currentPlugin = getCurrentPlugin();
        this.nav = {};
        //Remove logging once new log plugin is implemented
        this.exportAsync(LoggingSource);
        this.bindActions(loggingActions);
        //

        this.bindActions(SkyquakeContainerActions);
        this.exportAsync(SkyquakeContainerSource);


        this.exportPublicMethods({
            // getNav: this.getNav
        })

    }
    getSkyquakeNavSuccess = (data) => {
        var self = this;
        this.setState({
            nav: decorateAndTransformNav(data, self.currentPlugin)
        })
    };
    //Remove once logging plugin is implemented
    getSysLogViewerURLSuccess(data){
        window.open(data.url);
    }
    getSysLogViewerURLError(data){
        console.log('failed', data)
    }
}

/**
 * Receives nav data from routes rest endpoint and decorates the data with internal/external linking information
 * @param  {object} nav           Nav item from /nav endoingpoint
 * @param  {string} currentPlugin Current plugin name taken from url path.
 * @return {array}               Returns list of constructed nav items.
 */
function decorateAndTransformNav(nav, currentPlugin) {
    for ( let k in nav) {
        nav[k].pluginName = k;
            if (k != currentPlugin)  {
                nav[k].routes.map(function(route, i) {
                    if (API_SERVER) {
                        route.route = '/' + k + '/index.html?api_server=' + API_SERVER + '&upload_server=' + UPLOAD_SERVER + '#' + route.route;
                    } else {
                        route.route = '/' + k + '/#' + route.route;
                    }
                    route.isExternal = true;
                })
            }
        }
        return nav;
}

function getCurrentPlugin() {
    var paths = window.location.pathname.split('/');
    var currentPath = null;
    if (paths[0] != "") {
        currentPath = paths[0]
    } else {
        currentPath = paths[1];
    }
    if (currentPath != null) {
        return currentPath;
    } else {
        console.error('Well, something went horribly wrong with discovering the current plugin name - perhaps you should consider moving this logic to the server?')
    }
}

export default Alt.createStore(SkyquakeContainerStore);
