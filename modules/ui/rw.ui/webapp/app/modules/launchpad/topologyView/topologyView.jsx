
/*
 * 
 * (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
 *
 */
import React from 'react';
import TopologyStore from './topologyStore.js';
import RecordDetail from '../recordViewer/recordDetails.jsx';
import './topologyView.scss';
import DashboardCard from '../../components/dashboard_card/dashboard_card.jsx';
import AppHeader from '../../components/header/header.jsx';
import TopologyTree from '../../components/topology/topologyTree.jsx';
import LaunchpadBreadcrumbs from '../launchpadBreadcrumbs.jsx';
import Button from '../../components/button/rw.button.js';

export default class Topologyview extends React.Component {
    constructor(props) {
        super(props);
        this.state = TopologyStore.getState();
        TopologyStore.listen(this.storeListener);
    }
    openLog() {
        var LaunchpadStore = require('../launchpadFleetStore.js')
        LaunchpadStore.getSysLogViewerURL('lp');
    }
    openAbout = () => {
        this.componentWillUnmount();
        let loc = window.location.hash.split('/');
        loc.pop();
        loc.pop();
        loc.push('lp-about');
        window.location.hash = loc.join('/');
    }
    openDebug = () =>  {
        this.componentWillUnmount();
        let loc = window.location.hash.split('/');
        loc.pop();
        loc.pop();
        loc.push('lp-debug');
        window.location.hash = loc.join('/');
    }
    storeListener = (state) => {
        this.setState(state);
    }

    componentWillUnmount = () => {
        TopologyStore.closeSocket();
        TopologyStore.unlisten(this.storeListener);
    }
    componentDidMount() {
        let nsrRegEx = new RegExp("([0-9a-zA-Z-]+)\/compute-topology");
        let nsr_id;
        try {
          nsr_id = window.location.hash.match(nsrRegEx)[1];
        } catch (e) {
            console.log("TopologyView.componentDidMount exception: ", e);
        }
        TopologyStore.getTopologyData(nsr_id);
    }
    selectNode = (node) => {
        TopologyStore.selectNode(node);
    }

    handleReloadData = () => {
        this.componentDidMount();
    }

    render() {
        let html;
        let mgmtDomainName = window.location.hash.split('/')[2];
        let nsrId = window.location.hash.split('/')[3];
        let navItems = [{
          href: '#/launchpad/' + mgmtDomainName,
          name: 'DASHBOARD',
          onClick: this.componentWillUnmount
        },
        {
          href: '#/launchpad/' + mgmtDomainName + '/' + nsrId + '/detail',
          name: 'VIEWPORT',
          onClick: this.componentWillUnmount
        },{
          name: 'COMPUTE TOPOLOGY'
        },{
            href: '#/launchpad/' + mgmtDomainName + '/' + nsrId + '/topologyL2',
            name: 'NETWORK TOPOLOGY',
            onClick: this.componentWillUnmount
        }
        ];

        let nav = <AppHeader title="Launchpad: Viewport: Compute Topology" nav={navItems} />
        let reloadButton = null;

        if (this.state.ajax_mode) {
            reloadButton = <Button label="Reload data" className="reloadButton"
                onClick={this.handleReloadData} />
        }
 
        html = (
            <div className="app-body">
                {nav}
                {reloadButton}
                <div className="topologyView">
                    <i className="corner-accent top left"></i>
                    <i className="corner-accent top right"></i>
                    <TopologyTree
                        data={this.state.topologyData}
                        selectNode={this.selectNode}
                        hasSelected={this.state.hasSelected}
                        headerExtras={reloadButton}
                    />
                    <RecordDetail data={this.state.detailView || {}} isLoading={this.state.detailsLoading} />
                    <i className="corner-accent bottom left"></i>
                    <i className="corner-accent bottom right"></i>
                </div>
            </div>
        );
        return html;
    }
}
