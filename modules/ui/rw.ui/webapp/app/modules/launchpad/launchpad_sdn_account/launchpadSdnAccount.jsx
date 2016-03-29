/*
 * 
 * (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
 *
 */

import React from 'react';
import AppHeader from '../../components/header/header.jsx';
import SdnAccount from './sdnAccount.jsx';
import SdnAccountStore from './sdnAccountStore';
import AccountSidebar from '../account_sidebar/accountSidebar.jsx';

export default class LaunchpadSdnAccount extends React.Component {
    constructor(props) {
        super(props);
        this.state = SdnAccountStore.getState();
        SdnAccountStore.getCatalog();
        SdnAccountStore.listen(this.updateState);
        if(this.props.edit) {
            SdnAccountStore.getSdnAccount(window.location.hash.split('/')[4])
        } else {
            this.state.isLoading = false;
        }
    }
    updateState = (state) => {
        this.setState(state);
    }
    loadComposer = () => {
      let API_SERVER = rw.getSearchParams(window.location).api_server;
      let auth = window.sessionStorage.getItem("auth");
      let mgmtDomainName = window.location.hash.split('/')[2];
        window.location.replace('//' + window.location.hostname + ':9000/index.html?api_server=' + API_SERVER + '&upload_server=' + window.location.protocol + '//' + window.location.hostname + '&clearLocalStorage' + '&mgmt_domain_name=' + mgmtDomainName + '&auth=' + auth);
    }
    render() {
        let html;
        let body;
        let title = "Launchpad: Add SDN Account";
        let mgmtDomainName = window.location.hash.split('/')[2];
        if (this.props.edit) {
            title = "Launchpad: Edit SDN Account";
        }
        let navItems = [{
                name: 'DASHBOARD',
                href: '#/launchpad/' + mgmtDomainName
            },{
                 name: 'CATALOG(' + this.state.descriptorCount + ')',
                'onClick': this.loadComposer
            },
            {
                name: 'Accounts'
            }
        ];
        if (this.props.isDashboard) {
            body = (<div>Edit or Create New Accounts</div>);
        } else {
             body = <SdnAccount {...this.props} />
        }
        html = (<div>
                  <AppHeader title={title} nav={navItems} isLoading={this.state.isLoading} />
                    <div className="flex">
                      <AccountSidebar/>
                      {body}
                    </div>
              </div>);
        return html;
    }
}
