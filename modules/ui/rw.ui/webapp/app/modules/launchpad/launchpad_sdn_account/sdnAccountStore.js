
/*
 * 
 * (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
 *
 */
import LaunchNetworkServiceSource from '../../launchpad/network_service_launcher/launchNetworkServiceSource.js';
import LaunchNetworkServiceActions from '../../launchpad/network_service_launcher/launchNetworkServiceActions.js';

let alt = require('../../core/alt');
import SdnAccountSource from './sdnAccountSource';
import SdnAccountActions from './sdnAccountActions';
import AppHeaderActions from '../../components/header/headerActions.js';


/*

  Create and Updated:
  {"name":"odltwo","account-type":"odl","odl":{"username":"un","Password":"pw","url":"url"}}

  {"account-type":"odl","name":"odltwo","odl":{"username":"un","url":"url"}}
 */

class createSdnAccountStore {
    constructor() {
        this.exportAsync(SdnAccountSource);
        this.exportAsync(LaunchNetworkServiceSource);
        this.bindAction(SdnAccountActions.CREATE_SUCCESS, this.createSuccess);
        this.bindAction(SdnAccountActions.CREATE_LOADING, this.createLoading);
        this.bindAction(SdnAccountActions.CREATE_FAIL, this.createFail);
        this.bindAction(SdnAccountActions.UPDATE_SUCCESS, this.updateSuccess);
        this.bindAction(SdnAccountActions.UPDATE_LOADING, this.updateLoading);
        this.bindAction(SdnAccountActions.UPDATE_FAIL, this.updateFail);
        this.bindAction(SdnAccountActions.DELETE_SUCCESS, this.deleteSuccess);
        this.bindAction(SdnAccountActions.DELETE_FAIL, this.deleteFail);
        this.bindAction(SdnAccountActions.GET_SDN_ACCOUNT_SUCCESS, this.getSdnAccountSuccess);
        this.bindAction(SdnAccountActions.GET_SDN_ACCOUNT_FAIL, this.getSdnAccountFail);
        this.bindAction(SdnAccountActions.GET_SDN_ACCOUNTS_SUCCESS, this.getSdnAccountsSuccess);
        // this.bindAction(SdnAccountActions.GET_SDN_ACCOUNTS_FAIL, this.getSdnAccountsFail);
        this.bindAction(SdnAccountActions.VALIDATE_ERROR, this.validateError);
        this.bindAction(SdnAccountActions.VALIDATE_RESET, this.validateReset);
        this.bindListeners({
            getCatalogSuccess: LaunchNetworkServiceActions.getCatalogSuccess
        });
        this.exportPublicMethods({
          resetState: this.resetState.bind(this),
          updateName: this.updateName.bind(this),
          updateAccount: this.updateAccount.bind(this)
        });
        this.sdnAccount = {};
        this.sdnAccounts = [];
        this.descriptorCount = 0;
        this.validateErrorEvent = false;
        this.validateErrorMsg = "";
        this.isLoading = true;
        this.params = {
            "odl": [{
                label: "Username",
                ref: 'username'
            }, {
                label: "Password",
                ref: 'password'
            }, {
                label: "URL",
                ref: 'url'
            }],
            // "sdnsim": [{
            //     label: "Username",
            //     ref: "username"
            // }],
            // "mock":[
            //     {
            //         label: "Username",
            //         ref: "username"
            //     }
            // ]
        };
        this.accountType = [{
            "name": "ODL",
            "account-type": "odl",
        }];
        // }, {
        //     "name": "Mock",
        //     "account-type": "mock",
        // }, {
        //     "name": "SdnSim",
        //     "account-type": "sdnsim"
        // }];

        this.sdnAccount = {
            name: '',
            'account-type': 'odl'
        };
    }

    createSuccess = () => {
        console.log('successfully created SDN account. API response:', arguments);
        this.setState({
            isLoading: false
        });
    }

    createLoading = () => {
        console.log('sent request to create SDN account. Arguments:', arguments);
        this.setState({
            isLoading: true
        });
    }

    createFail = () => {
        let xhr = arguments[0];
        this.setState({
            isLoading: false
        });
        AppHeaderActions.validateError.defer("There was an error creating your SDN Account. Please contact your system administrator.");
    }

    updateSuccess = () => {
        console.log('successfully updated SDN account. API response:', arguments);
        this.setState({
            isLoading: false
        });
    }

    updateLoading = () => {
        console.log('sent request to update SDN account. Arguments:', arguments);
        this.setState({
            isLoading: true
        });
    }

    updateFail = () => {
        let xhr = arguments[0];
        this.setState({
            isLoading: false
        });
        AppHeaderActions.validateError.defer("There was an error updating your SDN Account. Please contact your system administrator.");
    }

    deleteSuccess = (data) => {
        console.log('successfully deleted SDN account. API response:', arguments);
        this.setState({
            isLoading: false
        });
        if(data.cb) {
            data.cb();
        }
    }

    deleteFail = (data) => {
        let xhr = arguments[0];
        this.setState({
            isLoading: false
        });
        AppHeaderActions.validateError.defer("There was an error deleting your SDN Account. Please contact your system administrator.");
    }

    getSdnAccountSuccess = (data) => {
        this.setState({
            sdnAccount: data.sdnAccount,
            isLoading: false
        });
    }

    getSdnAccountFail = function(data) {
        this.setState({
            isLoading:false
        });
    }

    validateError = (msg) => {
        this.setState({
            validateErrorEvent: true,
            validateErrorMsg: msg
        });
    }

    validateReset = () => {
        this.setState({
            validateErrorEvent: false
        });
    }

    getSdnAccountsSuccess = (sdnAccounts) => {
        let data = null;
        // if(sdnAccounts.statusCode == 204) {
        //     data = null;
        // } else {
            data = sdnAccounts;
        // }
        this.setState({
            sdnAccounts: data || [],
            isLoading: false
        })
    }

    getCatalogSuccess = (data) => {
        let self = this;
        let descriptorCount = 0;
        data.forEach((catalog) => {
            descriptorCount += catalog.descriptors.length;
        });

        self.setState({
            descriptorCount: descriptorCount
        });
    }

    resetState = () => {
        this.setState({
            sdnAccount: {
                name: '',
                'account-type': 'odl'
            }
        })
    }

    updateName = (sdn) => {
        this.setState({
            sdnAccount: sdn
        });
    }

    updateAccount = (sdn) => {
        this.setState({
            sdnAccount: sdn
        });
    }
}

export default alt.createStore(createSdnAccountStore);;
