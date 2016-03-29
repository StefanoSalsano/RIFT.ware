/*
 * 
 * (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
 *
 */
import React from 'react/addons';
import Utils from '../utils/utils.js';
import Button from '../components/button/rw.button.js';
import './login.scss'
class LoginScreen extends React.Component{
  constructor(props) {
    super(props);
    var API_SERVER =  rw.getSearchParams(window.location).api_server;
    if (!API_SERVER) {
      window.location.href = "//" + window.location.host + '/index.html?api_server=' + window.location.protocol + '//localhost';
    }
    this.state = {
      username: '',
      password: ''
    };

  }
  updateValue = (e) => {
    let state = {};
    state[e.target.name] = e.target.value;
    this.setState(state);
  }
  validate = (e) => {
    e.preventDefault();
    let state = this.state;
    console.log(this.state)
    if (state.username == '' || state.password == '') {
      console.log('false');
      return false;
    } else {
      Utils.setAuthentication(state.username, state.password, function() {
         let hash = window.sessionStorage.getItem("locationRefHash") || '#/';
        if (hash == '#/login') {
          hash = '#/'
        }
        window.location.hash = hash;
      });

    }
  }
  render() {
    let html;
    html = (
      <form className="login-cntnr" autocomplete="on">
        <div className="logo"> </div>
        <h1 className="riftio">Launchpad Login</h1>
        <p>
            <input type="text" placeholder="Username" name="username" value={this.state.username} onChange={this.updateValue} autocomplete="username"></input>
        </p>
        <p>
            <input type="password" placeholder="Password" name="password" onChange={this.updateValue} value={this.state.password} autocomplete="password"></input>
        </p>
        <p>
           <Button className="sign-in" onClick={this.validate} style={{cursor: 'pointer'}} type="submit" label="Sign In"/>
        </p>
      </form>
    )
    return html;
  }
}

export default LoginScreen;
