'use strict';

var angular = require('angular');

var ACCOUNT_ACTIONS = [
  ['login', 'POST'],
  ['logout', 'POST'],
  ['register', 'POST'],
  ['forgot_password', 'POST'],
  ['reset_password', 'POST'],
  ['profile', 'GET'],
  ['edit_profile', 'POST'],
  ['disable_user', 'POST']
];

function sessionActions() {
  var actions = {
    load: {
      method: 'GET',
      withCredentials: true
    },
    profile: {
      method: 'GET',
      params: {
        __formid__: 'profile'
      },
      withCredentials: true
    }
  };

  // These map directly to views in `h.accounts`, and all have a similar form:
  for (var i = 0, len = ACCOUNT_ACTIONS.length; i < len; i++) {
    var name = ACCOUNT_ACTIONS[i][0];
    var method = ACCOUNT_ACTIONS[i][1];
    actions[name] = {
      method: method,
      params: {
        __formid__: name
      },
      withCredentials: true
    };
  }

  return actions;
}


/**
 * @ngdoc service
 * @name session
 * @description
 * Access to the application session and account actions.
 */
session.$inject = ['$document', '$http', '$resource', 'flash', 'xsrf'];
function session(   $document,   $http,   $resource,   flash,   xsrf) {
  var instance = {state: {}};
  var actions = sessionActions();

  function prepare(data, headersGetter) {
    headersGetter()[$http.defaults.xsrfHeaderName] = xsrf.token;
    return angular.toJson(data);
  }

  function process(data, headersGetter) {
    // Parse as json
    data = angular.fromJson(data);

    // Lift response data
    var model = data.model || {};
    model.errors = data.errors;
    model.reason = data.reason;

    // Fire flash messages.
    for (var type in data.flash) {
      var msgs = data.flash[type];
      for (var i = 0, len = msgs.length; i < len; i++) {
        flash[type](msgs[i]);
      }
    }

    xsrf.token = model.csrf;
    instance.state = model;

    // Return the model
    return model;
  }

  var name;
  for (name in actions) {
    actions[name].transformRequest = prepare;
    actions[name].transformResponse = process;
  }

  var base = $document.prop('baseURI');
  var endpoint = new URL('/app', base).href;
  var resource = $resource(endpoint, {}, actions);

  // Expose session actions
  for (name in actions) {
    instance[name] = resource[name];
  }

  return resource;
}

module.exports = session;
