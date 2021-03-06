/**
 * Feature flag client.
 *
 * This is a small utility which will periodically retrieve the application
 * feature flags from a JSON endpoint in order to expose these to the
 * client-side application.
 *
 * All feature flags implicitly start toggled off. When `flagEnabled` is first
 * called (or alternatively when `fetch` is called explicitly) an XMLHTTPRequest
 * will be made to retrieve the current feature flag values from the server.
 * Once these are retrieved, `flagEnabled` will return current values.
 *
 * If `flagEnabled` is called and the cache is more than `CACHE_TTL`
 * milliseconds old, then it will trigger a new fetch of the feature flag
 * values. Note that this is again done asynchronously, so it is only later
 * calls to `flagEnabled` that will return the updated values.
 *
 * Users of this service should assume that the value of any given flag can
 * change at any time and should write code accordingly. Feature flags should
 * not be cached, and should not be interrogated only at setup time.
 */
'use strict';

var CACHE_TTL = 5 * 60 * 1000; // 5 minutes

function features ($document, $http, $log) {
  var cache = null;
  var pending = false;
  var featuresUrl = new URL('/app/features', $document.prop('baseURI')).href;

  function fetch() {
    // Short-circuit if a fetch is already in progress...
    if (pending) {
      return;
    }
    pending = true;
    $http.get(featuresUrl)
    .success(function(data) {
      cache = [Date.now(), data];
    })
    .error(function() {
      $log.warn('features service: failed to load features data');
    })
    .finally(function() {
      pending = false;
    });
  }

  function flagEnabled(name) {
    // Trigger a fetch if the cache is more than CACHE_TTL milliseconds old.
    // We don't wait for the fetch to complete, so it's not this call that
    // will see new data.
    if (cache === null || (Date.now() - cache[0]) > CACHE_TTL) {
      fetch();
    }

    if (cache === null) {
      return false;
    }
    var flags = cache[1];
    if (!flags.hasOwnProperty(name)) {
      $log.warn('features service: looked up unknown feature:', name);
      return false;
    }
    return flags[name];
  }

  return {
    fetch: fetch,
    flagEnabled: flagEnabled
  };
}

module.exports = ['$document', '$http', '$log', features];
