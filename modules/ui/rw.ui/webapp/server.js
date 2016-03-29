
/*
 * 
 * (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
 *
 */
var argv = require('minimist')(process.argv.slice(2));
var https = require('https');
var http = require('http');
var express = require('express');
var path = require('path');
var httpProxy = require('http-proxy');
var fs = require('fs');

var httpServer = null;
var httpsConfigured = false;
var sslOptions = null;
var sslConfig = null;

try {
  if (argv['enable-https']) {
    var keyFilePath = argv['keyfile-path'];
    var certFilePath = argv['certfile-path'];

    sslOptions = {
      key: fs.readFileSync(keyFilePath),
      cert: fs.readFileSync(certFilePath)
    };

    httpsConfigured = true;

    sslConfig = {
      httpsConfigured: true,
      sslOptions: sslOptions
    }
  }
} catch (e) {
  console.log('HTTPS enabled but file paths missing/incorrect');
  process.exit(code = -1);
}

var proxy = httpProxy.createProxyServer();


var app = express();

var isProduction = process.env.NODE_ENV === 'production';
var port = isProduction ? 8080 : 8000;
var publicPath = path.resolve(__dirname, 'public');

app.use(express.static(publicPath));

// We only want to run the workflow when not in production
if (!isProduction) {

  // We require the bundler inside the if block because
  // it is only needed in a development environment. Later
  // you will see why this is a good idea
  var bundle = require('./server/bundle.js');

  bundle(sslConfig);

  // Any requests to localhost:3000/build is proxied
  // to webpack-dev-server
  app.all('/build/*', function (req, res) {
    var proxyConfig = {};
    
    if (httpsConfigured) {
      proxyConfig.ssl = sslOptions;
      proxyConfig.target = 'https://localhost:8080';
      proxyConfig.secure = false;
    } else {
      proxyConfig.target = 'http://localhost:8080';
    }

    proxy.web(req, res, proxyConfig);
  });

}

// It is important to catch any errors from the proxy or the
// server will crash. An example of this is connecting to the
// server when webpack is bundling
proxy.on('error', function(e) {
  console.log('Could not connect to proxy, please try again...', e);
});

if (httpsConfigured) {
  httpServer = https.createServer(sslOptions, app);
} else {
  httpServer = http.createServer(app);
}

httpServer.listen(port, function() {
  console.log('Dev server listening on port', port, 'HTTPS configured:', httpsConfigured ? 'YES': 'NO');
});