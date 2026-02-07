/**
 * HoleSpawn trap tracker — inject into generated traps.
 * Set before script load: window.HOLESPAWN_TRACKER = { trapId: 1, apiBase: 'https://c2.example.com' };
 * Or use data attributes on script tag: data-trap-id, data-api-base.
 */
(function () {
  var script = document.currentScript;
  var config = window.HOLESPAWN_TRACKER || {};
  var trapId = config.trapId || (script && script.getAttribute('data-trap-id'));
  var apiBase = (config.apiBase || (script && script.getAttribute('data-api-base')) || '').replace(/\/$/, '');
  if (!trapId || !apiBase) return;

  function sessionId() {
    var key = 'holespawn_sid';
    var sid = sessionStorage.getItem(key);
    if (!sid) {
      sid = 's_' + Math.random().toString(36).slice(2) + '_' + Date.now();
      sessionStorage.setItem(key, sid);
    }
    return sid;
  }

  function fingerprint() {
    var n = navigator;
    var s = screen;
    var parts = [
      n.userAgent,
      n.language,
      s.width + 'x' + s.height,
      new Date().getTimezoneOffset(),
      !!window.sessionStorage
    ];
    var str = parts.join('|');
    var hash = 0;
    for (var i = 0; i < str.length; i++) {
      hash = ((hash << 5) - hash) + str.charCodeAt(i);
      hash = hash & hash;
    }
    return 'fp_' + Math.abs(hash).toString(36);
  }

  var sessionIdVal = sessionId();
  var fingerprintVal = fingerprint();
  var pageStartTime = Date.now();
  var visitedPages = [window.location.pathname || '/'];
  var maxScroll = 0;

  function send(method, path, body) {
    var url = apiBase + path;
    if (typeof fetch !== 'undefined') {
      fetch(url, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined,
        keepalive: method === 'POST' && path.indexOf('/end') !== -1
      }).catch(function () {});
    } else if (typeof XMLHttpRequest !== 'undefined') {
      var xhr = new XMLHttpRequest();
      xhr.open(method, url, true);
      xhr.setRequestHeader('Content-Type', 'application/json');
      xhr.send(body ? JSON.stringify(body) : null);
    }
  }

  send('POST', '/api/track/start', {
    trap_id: parseInt(trapId, 10),
    session_id: sessionIdVal,
    fingerprint: fingerprintVal,
    entry_page: window.location.pathname || '/',
    referrer: document.referrer || '',
    utm_params: (function () {
      var p = {};
      (window.location.search || '').replace(/^\?/, '').split('&').forEach(function (pair) {
        var kv = pair.split('=');
        if (kv[0] && kv[0].toLowerCase().indexOf('utm_') === 0) p[kv[0]] = decodeURIComponent(kv[1] || '');
      });
      return Object.keys(p).length ? p : undefined;
    })()
  });

  if (typeof document.addEventListener === 'function') {
    document.addEventListener('click', function (e) {
      var a = e.target && e.target.closest ? e.target.closest('a') : null;
      if (a && a.href) {
        var path = a.pathname || a.getAttribute('href');
        if (path && visitedPages.indexOf(path) === -1) visitedPages.push(path);
      }
    });
    window.addEventListener('scroll', function () {
      var doc = document.documentElement;
      var scrollTop = (window.pageYOffset || doc.scrollTop);
      var scrollHeight = (doc.scrollHeight - doc.clientHeight) || 1;
      var pct = (scrollTop + window.innerHeight) / document.body.scrollHeight;
      if (pct > maxScroll) maxScroll = pct;
    });
  }

  window.addEventListener('beforeunload', function () {
    var duration = (Date.now() - pageStartTime) / 1000;
    send('POST', '/api/track/end', {
      trap_id: parseInt(trapId, 10),
      session_id: sessionIdVal,
      duration: duration,
      exit_page: window.location.pathname || '/',
      pages_visited: visitedPages,
      depth: visitedPages.length,
      max_scroll: maxScroll
    });
  });
})();
