/*
 * 
 * (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
 *
 */
import React from 'react';
import AltContainer from 'alt-container';
import Alt from './skyquakeAltInstance.js';
import SkyquakeNav from './skyquakeNav.jsx';
import SkyquakeContainerStore from './skyquakeContainerStore.js';
import Breadcrumbs from 'react-breadcrumbs';
import Utils from 'utils/utils.js';
import './skyquakeApp.scss';
// import 'style/reset.css';
import 'style/core.css';
export default class skyquakeContainer extends React.Component {
    constructor(props) {
        super(props);
        let self = this;
        this.state = {};
        //This will be populated via a store/source
        this.state.nav = this.props.nav || [];
        this.state.currentPlugin = SkyquakeContainerStore.currentPlugin;
        Utils.bootstrapApplication().then(function() {
            SkyquakeContainerStore.getNav()
            SkyquakeContainerStore.listen(self.listener);
        });
    };
    componentWillUnmount() {
        SkyquakeContainerStore.unlisten(this.listener);
    };
    listener = (state) => {
        console.log(this.props.routes[this.props.routes.length-1])
        this.setState(state);
    };
    matchesLoginUrl() {
        //console.log("window.location.hash=", window.location.hash);
        // First element in the results of match will be the part of the string
        // that matched the expression. this string should be true against
        // (window.location.hash.match(re)[0]).startsWith(Utils.loginHash)
        var re = /#\/login?(\?|\/|$)/i;
        //console.log("res=", window.location.hash.match(re));
        return (window.location.hash.match(re)) ? true : false;
    }

    render() {
        var html;

        if (this.matchesLoginUrl()) {
            html = (
                <AltContainer>
                    <div className="skyquakeApp">
                        {this.props.children}
                    </div>
                </AltContainer>
            );
        } else {
            let tag = this.props.routes[this.props.routes.length-1].name ? ': '
                + this.props.routes[this.props.routes.length-1].name : '';
            html = (
                <AltContainer flux={Alt}>
                    <div className="skyquakeApp">
                            <SkyquakeNav nav={this.state.nav}
                                currentPlugin={this.state.currentPlugin}
                                store={SkyquakeContainerStore} />
                            <div className="titleBar">
                                <h1>{this.state.currentPlugin + tag}</h1>
                            </div>
                            {this.props.children}
                    </div>
                </AltContainer>
            );
        }
        return html;
    }
}
skyquakeContainer.contextTypes = {
    router: React.PropTypes.object
  };

/*
<Breadcrumbs
                            routes={this.props.routes}
                            params={this.props.params}
                            separator=" | "
                        />
 */
