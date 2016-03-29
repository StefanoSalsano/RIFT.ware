/*
 * 
 * (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
 *
 */
import React from 'react/addons';
import './about.scss';
import UpTime from '../components/uptime/uptime.jsx';
import AppHeader from '../components/header/header.jsx';
var aboutActions = require('./aboutActions.js');
var aboutStore = require('./aboutStore.js');
//var MissionControlStore = require('./missionControlStore.js');
class About extends React.Component {
  constructor(props) {
    super(props)
    var self = this;
    this.state = aboutStore.getState();
    aboutStore.getCatalog();
    aboutStore.listen(function(data) {
      if (data.aboutList) {
        self.setState({
          list:data.aboutList
        })
      }
      if (data.createTime) {
        self.setState({
          createTime:data.createTime
        })
      }
      if (data.descriptorCount) {
        self.setState({
          descriptorCount: data.descriptorCount
        });
      }
    });
    aboutStore.get();
    setTimeout(function(){
      if (window.location.hash.split('/').pop() == 'about') {
        aboutStore.createTime();
      }
    }, 200)
  }
  loadComposer = () => {
  let API_SERVER = rw.getSearchParams(window.location).api_server;
  let auth = window.sessionStorage.getItem("auth");
  let mgmtDomainName = window.location.hash.split('/')[2];
  window.location.replace('//' + window.location.hostname + ':9000/index.html?api_server=' + API_SERVER + '&upload_server=' + window.location.protocol + '//' + window.location.hostname + '&clearLocalStorage' + '&mgmt_domain_name=' + mgmtDomainName + '&auth=' + auth);
};
  render() {
    let self = this;
    let refPage = window.sessionStorage.getItem('refPage') || '{}';
    refPage = JSON.parse(refPage);
    let navItems = [{
      name: refPage.title || 'Dashboard',
      onClick: function() {
        window.location.hash = refPage.hash || '#/'
      }
    },{
      name: 'CATALOG(' + self.state.descriptorCount + ')',
      onClick: self.loadComposer
    }];
    let mgmtDomainName = window.location.hash.split('/')[2];
    navItems.push({
        name: 'ACCOUNTS',
        href: '#/launchpad/' + mgmtDomainName + '/cloud-account/dashboard',
        onClick: this.componentWillUnmount
      })
    // If in the mission control, create an uptime table;
    var uptime = null;
    let loc = window.location.hash.split('/');
    if (loc.pop() == 'about' && this.state) {

      console.log(Math.floor((new Date() / 1000)) - this.state.createTime)
      uptime = (
        <div className="table-container" style={{display: this.state.createTime ? 'inherit' : 'none'}}>
          <h2>Mission Control Uptime</h2>
          <table>
            <tbody>
              <tr>
                <td>
                  <UpTime initialtime={this.state.createTime ? Math.floor((new Date() / 1000)) - this.state.createTime : null} run={true} />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        );
    }


    var vcs_info = [];

    for (let i = 0; this.state && this.state.list && i < this.state.list.vcs.components.component_info.length; i++) {
      var node = this.state.list.vcs.components.component_info[i];
      vcs_info.push(
          <tr>
            <td>
              {node.component_name}
            </td>
            <td>
              {node.component_type}
            </td>
            <td>
              {node.state}
            </td>
          </tr>

        )
    }

    if (this.state != null) {
      var html = (
              <div>
                {uptime}
                <div className="table-container">
                  <h2> Version Info </h2>
                  <table>
                    <thead>
                      <tr>
                        <th>
                          Build SHA
                        </th>
                        <th>
                          Version
                        </th>
                        <th>
                          Build Date
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td>
                          {this.state.list ? this.state.list.version.build_sha : null}
                        </td>
                        <td>
                          {this.state.list ? this.state.list.version.version : null}
                        </td>
                        <td>
                          {this.state.list ? this.state.list.version.build_date : null}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <div className="table-container">
                  <h2> Component Info </h2>
                  <table>
                    <thead>
                      <tr>
                        <th>
                          Component Name
                        </th>
                        <th>
                          Component Type
                        </th>
                        <th>
                          State
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {vcs_info}
                    </tbody>
                  </table>
                </div>
              </div>
              );
    } else {
      html = ''
    }
    return (
            <div className="about-container">
              <AppHeader title={'Launchpad: About'} nav={navItems} />
              {html}
            </div>
            )
  }
}
export default About;
