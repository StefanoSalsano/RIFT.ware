/*
 * 
 * (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
 *
 */

import React from 'react/addons';
import AppHeaderActions from '../../components/header/headerActions.js';
import './sdnAccount.scss';
import Button from '../../components/button/rw.button.js';
var SdnAccountStore = require('./sdnAccountStore')
var SdnAccountActions = require('./sdnAccountActions')
class SdnAccount extends React.Component {
    constructor(props) {
        super(props);
        SdnAccountStore.resetState();
        this.state = SdnAccountStore.getState();
        SdnAccountStore.listen(this.storeListener);
    }
    storeListener = (state) => {
        this.setState(
            {
                sdnAccount: {
                    name:state.sdnAccount.name,
                    "account-type":state.sdnAccount["account-type"],
                    params:state.sdnAccount[state.sdnAccount["account-type"]]
                },
                isLoading: state.isLoading
            }
        )
    }
    create() {
        var self = this;
        if (self.state.sdnAccount.name == "") {
            AppHeaderActions.validateError("Please give the SDN account a name");
            return;
        } else {
            var type = self.state.sdnAccount['account-type'];
            if (typeof(self.state.params[type]) != 'undefined') {
                var params = self.state.params[type];
                for (var i = 0; i < params.length; i++) {
                    var param = params[i].ref;
                    if (typeof(self.state.sdnAccount[type]) == 'undefined' || typeof(self.state.sdnAccount[type][param]) == 'undefined' || self.state.sdnAccount[type][param] == "") {
                        if (!params[i].optional) {
                            AppHeaderActions.validateError("Please fill all account details");
                            return;
                        }
                    }
                }
            }
        }
        SdnAccountActions.validateReset();
        SdnAccountStore.create(self.state.sdnAccount).then(function() {
            let loc = window.location.hash.split('/');
            loc.pop();
            // hack to restore MC redirects from create SDN account page
            if (loc.indexOf('launchpad') == -1) {
                // this is a MC app URL
                loc.pop();
                loc.push('/');
            }
            loc.push('dashboard');
            window.location.hash = loc.join('/');
        });
    }
    update() {
        var self = this;

        if (self.state.sdnAccount.name == "") {
            AppHeaderActions.validateError("Please give the SDN account a name");
            return;
        }

          var submit_obj = {
            'account-type':self.state.sdnAccount['account-type'],
            name:self.state.sdnAccount.name
          }
          submit_obj[submit_obj['account-type']] = self.state.sdnAccount[submit_obj['account-type']];
          if(!submit_obj[submit_obj['account-type']]) {
            submit_obj[submit_obj['account-type']] = {};
          }
          for (var key in self.state.sdnAccount.params) {
            if (submit_obj[submit_obj['account-type']][key]) {
                //submit_obj[submit_obj['account-type']][key] = self.state.sdnAccount.params[key];
                console.log('hold')
            } else {
                submit_obj[submit_obj['account-type']][key] = self.state.sdnAccount.params[key];
            }
          }

         SdnAccountStore.update(submit_obj).then(function() {
            // hack to restore MC app URL
            let loc = window.location.hash.split('/');
            if (loc.indexOf('launchpad') == -1) {
                // this is a MC app URL
                loc.pop();
                loc.pop();
                loc.pop();
                loc.push('/');
                window.location.hash = loc.join('/');
            } else {
                SdnAccountStore.unlisten(self.storeListener);
                self.cancel();
            }
         });
    }
    cancel() {
        let loc = window.location.hash.split('/');
        // hack to restore MC redirects from create SDN account page
        if (loc.indexOf('launchpad') == -1) {
            // this is a MC app URL
            if (loc.indexOf('edit') != -1) {
                // this is edit link
                loc.pop();
            }
            loc.pop();
            loc.pop();
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
    handleDelete = () => {
        let self = this;
        SdnAccountStore.delete(self.state.sdnAccount.name, function() {
            // hack to restore MC app URL
            let loc = window.location.hash.split('/');
            if (loc.indexOf('launchpad') == -1) {
                // this is a MC app URL
                loc.pop();
                loc.pop();
                loc.pop();
                loc.push('/');
                window.location.hash = loc.join('/');
            } else {
                self.cancel();
            }
        });
    }
    handleNameChange(event) {
        var temp = this.state.sdnAccount;
        temp.name = event.target.value;
        this.setState({
            sdnAccount: temp
        });
        SdnAccountStore.updateName(temp);
    }
    handleAccountChange(node, event) {
        var temp = this.state.sdnAccount;
        temp['account-type'] = event.target.value;
        this.setState({
            sdnAccount: temp
        });
        SdnAccountStore.updateAccount(temp);
    }
    handleParamChange(node, event) {
        var temp = this.state.sdnAccount;
        if (!this.state.sdnAccount[this.state.sdnAccount['account-type']]) {
            temp[temp['account-type']] = {}
        }
        temp[temp['account-type']][node.ref] = event.target.value;
        this.setState({
            sdnAccount: temp
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

    render() {
        // This section builds elements that only show up on the create page.
        var name = <label>Name <input type="text" onChange={this.handleNameChange.bind(this)} style={{'text-align':'left'}} /></label>
        var buttons = [
            <a onClick={this.cancel} class="cancel">Cancel</a>,
            <Button role="button" onClick={this.create.bind(this)} className="save" label="Save" />
        ]
        if (this.props.edit) {
            name = <label>{this.state.sdnAccount.name}</label>
            var buttons = [
                <a onClick={this.handleDelete} ng-click="create.delete(create.sdnAccount)" className="delete">Remove Account</a>,
                    <a  onClick={this.cancel} class="cancel">Cancel</a>,
                    <Button role="button" onClick={this.update.bind(this)} className="update" label="Update" />
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
        if (this.state.params[this.state.sdnAccount['account-type']]) {
            var paramsStack = [];
            for (var i = 0; i < this.state.params[this.state.sdnAccount['account-type']].length; i++) {
                var optionalField = '';
                var node = this.state.params[this.state.sdnAccount['account-type']][i];
                var value = ""
                if (this.state.sdnAccount[this.state.sdnAccount['account-type']]) {
                    value = this.state.sdnAccount[this.state.sdnAccount['account-type']][node.ref]
                }
                if (this.props.edit && this.state.sdnAccount.params) {
                    value = this.state.sdnAccount.params[node.ref];
                }

                // If you're on the edit page, but the params have not been recieved yet, this stops us from defining a default value that is empty.
                if (this.props.edit && !this.state.sdnAccount.params) {
                    break;
                }
                if (node.optional) {
                    optionalField = <span className="optional">Optional</span>;
                }
                paramsStack.push(
                    <label key={i}>
                      <label className="create-fleet-pool-params">{node.label} {optionalField}</label>
                      <input className="create-fleet-pool-input" type="text" onChange={this.handleParamChange.bind(this, node)} defaultValue={value}/>
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

        // This section builds elements that only show up in the edit page.
        if (this.props.edit) {
            name = <label>{this.state.sdnAccount.name}</label>
            var buttons = [
                <a onClick={this.handleDelete} ng-click="create.delete(create.sdnAccount)" className="delete">Remove Account</a>,
                    <a onClick={this.cancel} class="cancel">Cancel</a>,
                    <Button role="button" onClick={this.update.bind(this)} className="update" label="Update" />
            ]
            let selectAccount = null;
            let params = null;
        }

        var html = (

              <form className="app-body create sdnAccount"  onSubmit={this.preventDefault} onKeyDown={this.evaluateSubmit}>
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
        )
        return html;
    }
}
export default SdnAccount
