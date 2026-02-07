/**
 * C2 Command Center: auth, targets, traps, campaigns, intel, jobs.
 */
(function () {
  var API = "/api";

  function api(path, options) {
    options = options || {};
    options.credentials = "same-origin";
    if (options.body && typeof options.body === "object" && !(options.body instanceof FormData)) {
      options.headers = options.headers || {};
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(options.body);
    }
    return fetch(API + path, options).then(function (r) {
      if (r.status === 401) {
        setAuth(false);
        return Promise.reject(new Error("Unauthorized"));
      }
      return r.json().catch(function () { return {}; });
    });
  }

  function setAuth(authenticated) {
    var loginScreen = document.getElementById("login-screen");
    var app = document.getElementById("app");
    if (loginScreen && app) {
      if (authenticated) {
        loginScreen.classList.add("hidden");
        app.classList.remove("hidden");
      } else {
        loginScreen.classList.remove("hidden");
        app.classList.add("hidden");
      }
    }
  }

  function show(el, visible) {
    if (!el) return;
    if (visible) el.classList.remove("hidden");
    else el.classList.add("hidden");
  }

  // ---------- Auth ----------
  function checkAuth() {
    api("/auth/status").then(function (data) {
      setAuth(!!data.authenticated);
    }).catch(function () {
      setAuth(false);
    });
  }

  document.getElementById("login-btn").addEventListener("click", function () {
    var pass = (document.getElementById("passphrase") && document.getElementById("passphrase").value) || "";
    var errEl = document.getElementById("login-error");
    show(errEl, false);
    api("/auth/login", { method: "POST", body: { passphrase: pass } })
      .then(function (data) {
        if (data.error) {
          errEl.textContent = data.error;
          show(errEl, true);
          return;
        }
        setAuth(true);
        if (window.showPanel) window.showPanel("targets");
      })
      .catch(function () {
        errEl.textContent = "Login failed.";
        show(errEl, true);
      });
  });

  document.getElementById("logout-btn").addEventListener("click", function () {
    api("/auth/logout", { method: "POST" }).then(function () {
      setAuth(false);
    });
  });

  // ---------- Targets ----------
  function loadTargets() {
    var loading = document.getElementById("targets-loading");
    var err = document.getElementById("targets-error");
    var wrap = document.getElementById("targets-table-wrap");
    var tbody = document.getElementById("targets-tbody");
    if (!tbody) return;
    show(loading, true);
    show(err, false);
    show(wrap, false);
    api("/targets").then(function (data) {
      show(loading, false);
      if (data.error) {
        err.textContent = data.error;
        show(err, true);
        return;
      }
      if (!data.length) {
        tbody.innerHTML = "<tr><td colspan=\"6\" class=\"muted\">No targets. Add one below.</td></tr>";
      } else {
        tbody.innerHTML = data.map(function (t) {
          return "<tr><td>" + t.id + "</td><td>" + escapeHtml(t.identifier) + "</td><td>" + escapeHtml(t.platform || "-") + "</td><td>" + escapeHtml(t.status) + "</td><td>" + t.priority + "</td><td>" + (t.created_at ? t.created_at.slice(0, 19) : "-") + "</td></tr>";
        }).join("");
      }
      show(wrap, true);
    }).catch(function () {
      show(loading, false);
      err.textContent = "Failed to load targets.";
      show(err, true);
    });
  }

  document.getElementById("add-target-btn").addEventListener("click", function () {
    var input = document.getElementById("new-target-identifier");
    var identifier = (input && input.value || "").trim();
    if (!identifier) return;
    api("/targets", { method: "POST", body: { identifier: identifier } })
      .then(function (data) {
        if (data.error) {
          alert(data.error);
          return;
        }
        input.value = "";
        loadTargets();
      })
      .catch(function () { alert("Failed to add target"); });
  });

  // ---------- Traps ----------
  function loadTraps() {
    var loading = document.getElementById("traps-loading");
    var err = document.getElementById("traps-error");
    var wrap = document.getElementById("traps-table-wrap");
    var tbody = document.getElementById("traps-tbody");
    if (!tbody) return;
    show(loading, true);
    show(err, false);
    show(wrap, false);
    api("/traps").then(function (data) {
      show(loading, false);
      if (data.error) {
        err.textContent = data.error;
        show(err, true);
        return;
      }
      if (!data.length) {
        tbody.innerHTML = "<tr><td colspan=\"6\" class=\"muted\">No traps yet.</td></tr>";
      } else {
        tbody.innerHTML = data.map(function (t) {
          var eff = t.trap_effectiveness != null ? t.trap_effectiveness.toFixed(1) : "-";
          return "<tr><td>" + t.id + "</td><td>" + t.target_id + "</td><td>" + escapeHtml(t.url || "-") + "</td><td>" + (t.total_visits || 0) + "</td><td>" + eff + "</td><td>" + (t.is_active ? "Yes" : "No") + "</td></tr>";
        }).join("");
      }
      show(wrap, true);
    }).catch(function () {
      show(loading, false);
      err.textContent = "Failed to load traps.";
      show(err, true);
    });
  }

  // ---------- Campaigns ----------
  function loadCampaigns() {
    var loading = document.getElementById("campaigns-loading");
    var err = document.getElementById("campaigns-error");
    var wrap = document.getElementById("campaigns-table-wrap");
    var tbody = document.getElementById("campaigns-tbody");
    if (!tbody) return;
    show(loading, true);
    show(err, false);
    show(wrap, false);
    api("/campaigns").then(function (data) {
      show(loading, false);
      if (data.error) {
        err.textContent = data.error;
        show(err, true);
        return;
      }
      if (!data.length) {
        tbody.innerHTML = "<tr><td colspan=\"5\" class=\"muted\">No campaigns.</td></tr>";
      } else {
        tbody.innerHTML = data.map(function (c) {
          return "<tr><td>" + c.id + "</td><td>" + escapeHtml(c.name) + "</td><td>" + escapeHtml(c.status) + "</td><td>" + (c.total_targets || 0) + "</td><td>" + escapeHtml(c.goal || "-") + "</td></tr>";
        }).join("");
      }
      show(wrap, true);
    }).catch(function () {
      show(loading, false);
      err.textContent = "Failed to load campaigns.";
      show(err, true);
    });
  }

  // ---------- Intel ----------
  function loadIntel() {
    var loading = document.getElementById("intel-loading");
    var err = document.getElementById("intel-error");
    var networksEl = document.getElementById("intel-networks");
    var patternsEl = document.getElementById("intel-patterns");
    if (!networksEl) return;
    show(loading, true);
    show(err, false);
    show(networksEl, false);
    show(patternsEl, false);
    Promise.all([api("/intel/networks"), api("/intel/effectiveness")]).then(function (results) {
      show(loading, false);
      var nets = results[0].error ? [] : results[0];
      var patterns = results[1].error ? {} : results[1];
      if (nets.length) {
        networksEl.innerHTML = "<h3>Networks</h3><table class=\"data-table\"><thead><tr><th>ID</th><th>Name</th><th>Nodes</th><th>Edges</th><th>Scraped</th></tr></thead><tbody>" +
          nets.map(function (n) {
            return "<tr><td>" + n.id + "</td><td>" + escapeHtml(n.name) + "</td><td>" + (n.node_count || 0) + "</td><td>" + (n.edge_count || 0) + "</td><td>" + (n.scraped_at ? n.scraped_at.slice(0, 19) : "-") + "</td></tr>";
          }).join("") + "</tbody></table>";
        show(networksEl, true);
      }
      if (patterns.by_architecture && Object.keys(patterns.by_architecture).length) {
        patternsEl.innerHTML = "<h3>Effectiveness by architecture</h3><pre class=\"muted\">" + escapeHtml(JSON.stringify(patterns.by_architecture, null, 2)) + "</pre>";
        show(patternsEl, true);
      }
    }).catch(function () {
      show(loading, false);
      err.textContent = "Failed to load intel.";
      show(err, true);
    });
  }

  // ---------- Jobs ----------
  function loadJobs() {
    var loading = document.getElementById("jobs-loading");
    var err = document.getElementById("jobs-error");
    var wrap = document.getElementById("jobs-table-wrap");
    var tbody = document.getElementById("jobs-tbody");
    if (!tbody) return;
    show(loading, true);
    show(err, false);
    show(wrap, false);
    api("/jobs").then(function (data) {
      show(loading, false);
      if (data.error) {
        err.textContent = data.error;
        show(err, true);
        return;
      }
      if (!data.length) {
        tbody.innerHTML = "<tr><td colspan=\"6\" class=\"muted\">No jobs.</td></tr>";
      } else {
        tbody.innerHTML = data.map(function (j) {
          return "<tr><td>" + j.id + "</td><td>" + escapeHtml(j.job_type) + "</td><td>" + (j.target_id || "-") + "</td><td>" + escapeHtml(j.status) + "</td><td>" + (j.progress != null ? j.progress + "%" : "-") + "</td><td>" + (j.created_at ? j.created_at.slice(0, 19) : "-") + "</td></tr>";
        }).join("");
      }
      show(wrap, true);
    }).catch(function () {
      show(loading, false);
      err.textContent = "Failed to load jobs.";
      show(err, true);
    });
  }

  function escapeHtml(s) {
    if (s == null) return "";
    var div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  // Expose loaders and panel trigger for app.js
  window.loadTargets = loadTargets;
  window.loadTraps = loadTraps;
  window.loadCampaigns = loadCampaigns;
  window.loadIntel = loadIntel;
  window.loadJobs = loadJobs;

  // Run auth check on load
  checkAuth();
})();
