
/*
 * 
 * (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
 *
 */
import React from 'react';
import TopologyL2Store from './topologyL2Store.js';
import TopologyL2Actions from './topologyL2Actions.js';
import RecordDetail from '../recordViewer/recordDetails.jsx';
import './topologyL2View.scss';
import TopologyDetail from './detailView.jsx';
import DashboardCard from '../../components/dashboard_card/dashboard_card.jsx';
import AppHeader from '../../components/header/header.jsx';
import TopologyL2Graph from '../../components/topology/topologyL2Graph.jsx';
import Button from '../../components/button/rw.button.js';

export default class TopologyL2view extends React.Component {
    constructor(props) {
        super(props);
        this.state = TopologyL2Store.getState();
        TopologyL2Store.listen(this.storeListener);
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
    openDebug = () => {
        this.compoentWillUnmount();
        let loc = window.location.hash.split('/');
        loc.pop();
        loc.pop();
        loc.push('lp-debug');
        window.location.hash = loc.join('/');
    }
    storeListener = (state) => {
        this.setState(state);
    }

    componentWillUnmount() {
        TopologyL2Store.closeSocket();
        TopologyL2Store.unlisten(this.storeListener);
    }
    componentDidMount() {
        TopologyL2Store.getTopologyData('dummy-id');
    }

    onNodeEvent = (node_id) => {
        TopologyL2Actions.nodeClicked(node_id);
    }

    handleReloadData = () => {
        console.log("TopologyView.handleReloadData");
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
          href: '#/launchpad/' + mgmtDomainName + '/' + nsrId + '/compute-topology',
          name: 'COMPUTE TOPOLOGY',
          onClick: this.componentWillUnmount
        },{
            name: 'NETWORK TOPOLOGY'
        }];

        let nav = <AppHeader title="Launchpad: Viewport: Network Topology" nav={navItems} />
        let reloadButton = null;
        if (this.state.ajax_mode) {
            reloadButton = <Button label="Reload data" className="reloadButton"
                onClick={this.handleReloadData} />
        }

        html = (
            <div className="app-body">
                {nav}
                {reloadButton}
                <div className="topologyL2View">
                    <i className="corner-accent top left"></i>
                    <i className="corner-accent top right"></i>
                    <TopologyL2Graph data={this.state.topologyData} 
                                     nodeEvent={this.onNodeEvent}
                                     debugMode={this.props.debugMode}
                                     headerExtras={reloadButton}
                    />
                    <TopologyDetail data={this.state.detailData || {}} 
                                    isLoading={this.state.isLoading}
                                    debugMode={this.props.debugMode}
                    />
                    <i className="corner-accent bottom left"></i>
                    <i className="corner-accent bottom right"></i>
                </div>
            </div>
        );

        return html;
    }
}

TopologyL2view.propTypes = {
    debugMode: React.PropTypes.bool
}
TopologyL2view.defaultProps = {
    debugMode: false
}
