/*
 * 
 * (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
 *
 */

import React from 'react/addons';
import AppHeader from '../../components/header/header.jsx';
import AppHeaderActions from '../../components/header/headerActions.js';
import Button from '../../components/button/rw.button.js';

class SdnAccount extends React.Component {
    constructor(props) {
        super(props);
        this.props.store.resetState();
        this.state = this.props.store.getState();
        this.props.store.listen(this.storeListener);
        this.state.actions = this.props.actions;
        this.state.store = this.props.store;

    }
    storeListener = (state) => {
        this.setState(state);
    }
    create() {
        var self = this;
        if (self.state.sdn.name == "") {
            AppHeaderActions.validateError("Please give the sdn account a name");
            return;
        } else {
            var type = self.state.sdn['account-type'];
            if (typeof(self.state.params[type]) != 'undefined') {
                var params = self.state.params[type];
                for (var i = 0; i < params.length; i++) {
                    var param = params[i].ref;
                    if (typeof(self.state.sdn[type]) == 'undefined' || typeof(self.state.sdn[type][param]) == 'undefined' || self.state.sdn[type][param] == "") {
                        AppHeaderActions.validateError("Please fill all account details");
                        return;
                    }
                }
            }
        }
        this.state.actions.validateReset();
        this.state.store.create(self.state.sdn).then(function() {
            let loc = window.location.hash.split('/');
            loc.pop();
            loc.push('dashboard');
            window.location.hash = loc.join('/');
        });
    }
    update = () => {
        var self = this;

        if (self.state.sdn.name == "") {
            AppHeaderActions.validateError("Please give the cloud account a name");
            return;
        }
        this.state.store.update(self.state.sdn).then(function() {
            this.state.store.unlisten(self.storeListener);
            self.cancel();
        });
    }

    cancel() {
        let loc = window.location.hash.split('/');
        // hack to restore MC redirects from create cloud account page
        if (loc.indexOf('launchpad') == -1) {
            // this is a MC app URL
            if (loc.indexOf('edit') != -1) {
                // this is edit link
                loc.pop();
            }
            loc.pop();
            loc.pop()
            loc.push('/');
        } else {
            if (loc.indexOf('edit') != -1) {
                // this is edit link
                loc.pop();
                loc.pop();
                loc.push('dashboard');
            } else {
                loc.pop();
                loc.push('dashboard');
            }
        }
        window.location.hash = loc.join('/');
    }
    componentWillReceiveProps(nextProps) {}
    shouldComponentUpdate(nextProps) {
        return true;
    }
    handleNameChange(event) {
        var temp = this.state.sdn;
        temp.name = event.target.value;
        this.state.store.updateName(temp);
    }
    handleAccountChange(node, event) {
        var temp = {};
        temp.name = this.state.sdn.name;
        temp['account-type'] = event.target.value;
        this.state.store.updateAccount(temp);
    }
    handleParamChange(node, event) {
            var temp = this.state.sdn;
            if (!this.state.sdn[this.state.sdn['account-type']]) {
                temp[temp['account-type']] = {}
            }
            temp[temp['account-type']][node.ref] = event.target.value;
            this.setState({
                sdn: temp
            });
    }
    preventDefault = (e) => {
        e.preventDefault();
        e.stopPropagation();
    }
    evaluateSubmit = (e) => {
        if (e.keyCode == 13) {
            this.update(e);
            e.preventDefault();
            e.stopPropagation();
        }
    }
        // openCreate() {
        //   window.location.hash = window.location.hash + 'management-domain/create'
        // }
    render() {
        // This section builds elements that only show up on the create page.
        var name = <label>Name <input type="text" onChange={this.handleNameChange.bind(this)} style={{'text-align':'left'}} /></label>
        var buttons = [
            <a onClick={this.cancel} class="cancel">Cancel</a>,
            <Button role="button" onClick={this.create.bind(this)} className="save" label="Save" type="submit" />
        ]
        var title = "Add SDN Account"
        // This section builds elements that only show up in the edit page.
        if (this.props.edit) {
            title = "Edit SDN Account";
            name = <label>{this.state.sdn.name}</label>
            buttons = [
                <a ng-click="create.delete(create.sdn)" className="delete">Remove Account</a>,
                <a onClick={this.cancel} class="cancel">Cancel</a>,
                <Button role="button" onClick={this.update.bind(this)} className="update" label="Update" type="submit"/>
            ]
            let selectAccount = null;
            let params = null;
        }
        // This creates the create screen radio button for account type.
        var selectAccountStack = [];
        if (!this.props.edit) {
            for (var i = 0; i < this.state.accountType.length; i++) {
                var node = this.state.accountType[i];
                selectAccountStack.push(
                    <label>
                    <input type="radio" name="account" onChange={this.handleAccountChange.bind(this, node)} defaultChecked={node.name == this.state.accountType[0].name} value={node['account-type']} /> {node.name}
                  </label>
                )

            }
            var selectAccount = (
                <div className="select-type" style={{"margin-left":"27px"}}>
                    Select Account Type:
                    {selectAccountStack}
                </div>
            )
        }

        // This sections builds the parameters for the account details.
        var params = null;
        if (this.state.params[this.state.sdn['account-type']]) {
            var paramsStack = [];
            for (var i = 0; i < this.state.params[this.state.sdn['account-type']].length; i++) {
                var node = this.state.params[this.state.sdn['account-type']][i];
                var value = this.state.sdn[this.state.sdn['account-type']] && this.state.sdn[this.state.sdn['account-type']][node.ref] || "";
                if (this.props.edit) {
                    value = this.state.sdn[this.state.sdn['account-type']][node.ref];
                }
                paramsStack.push(
                    <label>
                  <label className="create-fleet-pool-params">{node.label}</label>
                  <input className="create-fleet-pool-input" value={value} atype="text" onChange={this.handleParamChange.bind(this, node)} />
              </label>
                );
            }

            params = (
                <li className="create-fleet-pool">
                    <h3> Enter Account Details</h3>
                    {paramsStack}
                </li>
            )
        } else {
            params = (
                <li className="create-fleet-pool">
                    <h3> Enter Account Details</h3>
                    <label style={{'margin-left':'17px', color:'#888'}}>No Details Required</label>
                </li>
            )
        }

        var html = (
            <div>
          <form className="app-body create" onSubmit={this.preventDefault} onKeyDown={this.evaluateSubmit}>
              <screen-loader store={this.state.store}></screen-loader>
              <h2 className="create-management-domain-header name-input">
                   {name}
              </h2>
              {selectAccount}
              <ol className="flex-row">
                  {params}
              </ol>
              <div className="form-actions">
                  {buttons}
              </div>
          </form>
        </div>
        )
        return html;
    }
}
export default SdnAccount
