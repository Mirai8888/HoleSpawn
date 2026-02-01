(function () {
  const titles = {
    profiles: "Profiles",
    search: "Agenda search",
    network: "Network reports",
  };

  function showPanel(name) {
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    document.querySelectorAll(".nav-btn").forEach((b) => b.classList.remove("active"));
    const panel = document.getElementById("panel-" + name);
    const btn = document.querySelector('.nav-btn[data-panel="' + name + '"]');
    if (panel) panel.classList.add("active");
    if (btn) btn.classList.add("active");
    document.getElementById("panel-title").textContent = titles[name] || name;
    if (name === "profiles") loadProfiles();
    if (name === "network") loadNetworkReports();
  }

  document.querySelectorAll(".nav-btn").forEach((btn) => {
    btn.addEventListener("click", function () {
      showPanel(this.getAttribute("data-panel"));
    });
  });

  function show(el, visible) {
    if (!el) return;
    if (visible) el.classList.remove("hidden");
    else el.classList.add("hidden");
  }

  function showBrief(title, body, isMarkdown) {
    const modal = document.getElementById("modal");
    const bodyEl = document.getElementById("modal-body");
    document.getElementById("modal-title").textContent = title;
    bodyEl.textContent = body || "(empty)";
    bodyEl.classList.toggle("markdown", !!isMarkdown);
    if (isMarkdown && body) {
      bodyEl.innerHTML = body
        .replace(/^### (.*)$/gm, "<h3>$1</h3>")
        .replace(/^## (.*)$/gm, "<h2>$1</h2>")
        .replace(/^# (.*)$/gm, "<h1>$1</h1>")
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
        .replace(/\n- (.*)/g, "\n<ul><li>$1</li></ul>")
        .replace(/<\/ul>\s*<ul>/g, "");
    }
    modal.classList.remove("hidden");
  }

  document.querySelector(".modal-close").addEventListener("click", function () {
    document.getElementById("modal").classList.add("hidden");
  });
  document.querySelector(".modal-backdrop").addEventListener("click", function () {
    document.getElementById("modal").classList.add("hidden");
  });

  // Profiles
  function loadProfiles() {
    const loading = document.getElementById("profiles-loading");
    const err = document.getElementById("profiles-error");
    const wrap = document.getElementById("profiles-table-wrap");
    const tbody = document.getElementById("profiles-tbody");
    show(loading, true);
    show(err, false);
    show(wrap, false);
    fetch("/api/profiles")
      .then((r) => r.json())
      .then((data) => {
        show(loading, false);
        if (data.error) {
          err.textContent = data.error;
          show(err, true);
          return;
        }
        if (!data.length) {
          tbody.innerHTML = "<tr><td colspan=\"6\" class=\"muted\">No profiles stored. Run build_site with --db or store a run dir.</td></tr>";
        } else {
          tbody.innerHTML = data
            .map(
              (p) =>
                `<tr>
                  <td class="cell-run-id">${escapeHtml(p.run_id)}</td>
                  <td>${escapeHtml(p.source_username)}</td>
                  <td>${escapeHtml(p.created_at || "")}</td>
                  <td>${escapeHtml(p.data_source || "")}</td>
                  <td>
                    ${p.has_brief ? `<button type="button" class="btn-link" data-run-id="${escapeHtml(p.run_id)}" data-brief="profile">Brief</button>` : `<span class="muted">Missing</span>`}
                  </td>
                  <td><button type="button" class="btn-link btn-repair" data-run-id="${escapeHtml(p.run_id)}">Repair</button></td>
                </tr>`
            )
            .join("");
          tbody.querySelectorAll("[data-brief=profile]").forEach((b) => {
            b.addEventListener("click", function () {
              const runId = this.getAttribute("data-run-id");
              fetch("/api/profiles/" + encodeURIComponent(runId) + "/brief")
                .then((r) => r.json())
                .then((d) => showBrief("Engagement brief — " + runId, d.brief, true));
            });
          });
          tbody.querySelectorAll(".btn-repair").forEach((b) => {
            b.addEventListener("click", function () {
              const runId = this.getAttribute("data-run-id");
              const btn = this;
              btn.disabled = true;
              btn.textContent = "…";
              fetch("/api/profiles/" + encodeURIComponent(runId) + "/repair", { method: "POST" })
                .then((r) => r.json())
                .then((d) => {
                  btn.disabled = false;
                  btn.textContent = "Repair";
                  if (d.error) {
                    alert(d.error);
                    return;
                  }
                  showBrief("Engagement brief — " + runId + " (repaired)", d.brief, true);
                  loadProfiles();
                })
                .catch((e) => {
                  btn.disabled = false;
                  btn.textContent = "Repair";
                  alert(e.message || "Repair failed");
                });
            });
          });
        }
        show(wrap, true);
      })
      .catch((e) => {
        show(loading, false);
        err.textContent = e.message || "Failed to load profiles";
        show(err, true);
      });
  }

  // Search
  document.getElementById("search-btn").addEventListener("click", function () {
    const agenda = document.getElementById("agenda-input").value.trim();
    const limit = parseInt(document.getElementById("search-limit").value, 10) || 10;
    const loading = document.getElementById("search-loading");
    const err = document.getElementById("search-error");
    const wrap = document.getElementById("search-results-wrap");
    const tbody = document.getElementById("search-tbody");
    if (!agenda) {
      err.textContent = "Enter an agenda query.";
      show(err, true);
      return;
    }
    show(err, false);
    show(loading, true);
    show(wrap, false);
    fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ agenda, limit }),
    })
      .then((r) => r.json())
      .then((data) => {
        show(loading, false);
        if (data.error) {
          err.textContent = data.error;
          show(err, true);
          return;
        }
        if (!data.length) {
          tbody.innerHTML = "<tr><td colspan=\"5\" class=\"muted\">No results or no profiles in DB.</td></tr>";
        } else {
          tbody.innerHTML = data
            .map(
              (r) =>
                `<tr>
                  <td>${r.rank}</td>
                  <td class="cell-run-id">${escapeHtml(r.run_id)}</td>
                  <td>${escapeHtml(r.source_username)}</td>
                  <td class="cell-reason">${escapeHtml(r.reason)}</td>
                  <td><button type="button" class="btn-link" data-run-id="${escapeHtml(r.run_id)}" data-brief="profile">Brief</button></td>
                </tr>`
            )
            .join("");
          tbody.querySelectorAll("[data-brief=profile]").forEach((b) => {
            b.addEventListener("click", function () {
              const runId = this.getAttribute("data-run-id");
              fetch("/api/profiles/" + encodeURIComponent(runId) + "/brief")
                .then((res) => res.json())
                .then((d) => showBrief("Engagement brief — " + runId, d.brief, true));
            });
          });
        }
        show(wrap, true);
      })
      .catch((e) => {
        show(loading, false);
        err.textContent = e.message || "Search failed";
        show(err, true);
      });
  });

  // Network reports
  function loadNetworkReports() {
    const loading = document.getElementById("network-loading");
    const err = document.getElementById("network-error");
    const wrap = document.getElementById("network-table-wrap");
    const tbody = document.getElementById("network-tbody");
    show(loading, true);
    show(err, false);
    show(wrap, false);
    fetch("/api/network_reports")
      .then((r) => r.json())
      .then((data) => {
        show(loading, false);
        if (data.error) {
          err.textContent = data.error;
          show(err, true);
          return;
        }
        if (!data.length) {
          tbody.innerHTML = "<tr><td colspan=\"4\" class=\"muted\">No network reports stored.</td></tr>";
        } else {
          tbody.innerHTML = data
            .map(
              (n) =>
                `<tr>
                  <td class="cell-run-id">${escapeHtml(n.run_id)}</td>
                  <td>${escapeHtml(n.created_at || "")}</td>
                  <td>${escapeHtml(n.source || "")}</td>
                  <td><button type="button" class="btn-link" data-run-id="${escapeHtml(n.run_id)}" data-brief="network">Brief</button></td>
                </tr>`
            )
            .join("");
          tbody.querySelectorAll("[data-brief=network]").forEach((b) => {
            b.addEventListener("click", function () {
              const runId = this.getAttribute("data-run-id");
              fetch("/api/network_reports/" + encodeURIComponent(runId) + "/brief")
                .then((r) => r.json())
                .then((d) => showBrief("Network brief — " + runId, d.brief, true));
            });
          });
        }
        show(wrap, true);
      })
      .catch((e) => {
        show(loading, false);
        err.textContent = e.message || "Failed to load network reports";
        show(err, true);
      });
  }

  function escapeHtml(s) {
    if (s == null) return "";
    const div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  loadProfiles();
})();
