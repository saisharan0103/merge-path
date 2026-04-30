from fastapi.responses import HTMLResponse


def repo_onboarding_page() -> HTMLResponse:
    return HTMLResponse(
        """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PatchPilot Repositories</title>
  <style>
    :root { color-scheme: light; font-family: Arial, Helvetica, sans-serif; background: #f6f7f9; color: #20242a; }
    body { margin: 0; padding: 32px; }
    main { max-width: 1180px; margin: 0 auto; }
    h1 { margin: 0 0 8px; font-size: 28px; }
    h2 { margin: 0 0 8px; font-size: 20px; }
    p { margin: 0 0 24px; color: #5d6673; }
    form { display: flex; gap: 10px; margin-bottom: 18px; }
    input { flex: 1; min-width: 0; padding: 10px 12px; border: 1px solid #c8ced8; border-radius: 6px; font-size: 14px; }
    button { border: 0; border-radius: 6px; padding: 9px 12px; background: #2457c5; color: white; font-weight: 600; cursor: pointer; white-space: nowrap; }
    button.secondary { background: #e8ebf0; color: #20242a; }
    button:disabled { cursor: not-allowed; opacity: 0.6; }
    table { width: 100%; border-collapse: collapse; background: white; border: 1px solid #d9dee7; margin-bottom: 22px; }
    th, td { padding: 12px; text-align: left; border-bottom: 1px solid #edf0f4; font-size: 14px; vertical-align: top; }
    th { background: #eef2f7; color: #3f4752; }
    .actions { display: flex; flex-wrap: wrap; gap: 8px; }
    .status, .label { display: inline-block; padding: 3px 8px; border-radius: 999px; font-size: 12px; font-weight: 700; }
    .enabled, .eligible, .yes { background: #dff4e7; color: #11612d; }
    .disabled, .not-eligible, .no { background: #f1f2f4; color: #646b76; }
    .label { margin: 0 4px 4px 0; background: #e7efff; color: #244c9a; }
    .message { min-height: 22px; margin-bottom: 12px; color: #9a3412; font-size: 14px; }
    .empty { color: #747d8a; text-align: center; }
    .panel { margin-top: 8px; }
    .summary-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; background: white; border: 1px solid #d9dee7; padding: 14px; margin-bottom: 22px; }
    .summary-grid div { min-width: 0; }
    .summary-grid strong { display: block; margin-bottom: 4px; color: #3f4752; font-size: 12px; text-transform: uppercase; }
    .mono { font-family: Consolas, monospace; overflow-wrap: anywhere; }
    @media (max-width: 760px) {
      body { padding: 18px; }
      form { flex-direction: column; }
      table { display: block; overflow-x: auto; }
      .summary-grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <main>
    <h1>PatchPilot Repositories</h1>
    <p>Add repositories, clone and scan local code, fetch GitHub issues, and review V1 eligibility.</p>

    <form id="repo-form">
      <input id="repo-url" type="url" placeholder="https://github.com/owner/repo" required>
      <button id="add-button" type="submit">Add repository</button>
    </form>
    <div id="message" class="message"></div>

    <table>
      <thead>
        <tr>
          <th>Owner</th>
          <th>Name</th>
          <th>Status</th>
          <th>Scan</th>
          <th>Issues</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody id="repo-table">
        <tr><td class="empty" colspan="6">Loading repositories...</td></tr>
      </tbody>
    </table>

    <section class="panel" id="scan-panel" hidden>
      <h2 id="scan-title"></h2>
      <div class="summary-grid" id="scan-summary"></div>
    </section>

    <section class="panel" id="issue-panel" hidden>
      <h2 id="issue-title"></h2>
      <p id="issue-summary"></p>
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Title</th>
            <th>Labels</th>
            <th>Assigned</th>
            <th>Eligibility</th>
          </tr>
        </thead>
        <tbody id="issue-table"></tbody>
      </table>
    </section>
  </main>

  <script>
    const apiBase = "/api/v1/repos";
    const form = document.querySelector("#repo-form");
    const input = document.querySelector("#repo-url");
    const addButton = document.querySelector("#add-button");
    const repoTable = document.querySelector("#repo-table");
    const scanPanel = document.querySelector("#scan-panel");
    const scanTitle = document.querySelector("#scan-title");
    const scanSummary = document.querySelector("#scan-summary");
    const issuePanel = document.querySelector("#issue-panel");
    const issueTitle = document.querySelector("#issue-title");
    const issueSummary = document.querySelector("#issue-summary");
    const issueTable = document.querySelector("#issue-table");
    const message = document.querySelector("#message");
    let repos = [];
    let issueCounts = {};
    let scanCache = {};

    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
      }[char]));
    }

    function setMessage(text, isError = true) {
      message.textContent = text;
      message.style.color = isError ? "#9a3412" : "#11612d";
    }

    async function requestJson(url, options = {}) {
      const response = await fetch(url, {headers: {"Content-Type": "application/json"}, ...options});
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || `Request failed with ${response.status}`);
      }
      return response.json();
    }

    async function loadIssueCount(repoId) {
      const issues = await requestJson(`${apiBase}/${repoId}/issues`);
      issueCounts[repoId] = {total: issues.length, eligible: issues.filter((issue) => issue.is_eligible).length};
    }

    async function loadScan(repoId) {
      try {
        scanCache[repoId] = await requestJson(`${apiBase}/${repoId}/scan`);
      } catch {
        scanCache[repoId] = null;
      }
    }

    async function refreshSummaries() {
      await Promise.all(repos.map((repo) => Promise.all([
        loadIssueCount(repo.id).catch(() => { issueCounts[repo.id] = {total: 0, eligible: 0}; }),
        loadScan(repo.id)
      ])));
    }

    function renderRepos() {
      if (!repos.length) {
        repoTable.innerHTML = '<tr><td class="empty" colspan="6">No repositories yet.</td></tr>';
        return;
      }
      repoTable.innerHTML = repos.map((repo) => {
        const statusClass = repo.is_enabled ? "enabled" : "disabled";
        const statusText = repo.is_enabled ? "Enabled" : "Disabled";
        const action = repo.is_enabled ? "Disable" : "Enable";
        const endpoint = repo.is_enabled ? "disable" : "enable";
        const counts = issueCounts[repo.id] || {total: 0, eligible: 0};
        const scan = scanCache[repo.id];
        const scanText = scan ? `Scanned ${new Date(scan.last_scanned_at).toLocaleString()}` : "Not scanned";
        return `
          <tr>
            <td>${escapeHtml(repo.owner)}</td>
            <td>${escapeHtml(repo.name)}</td>
            <td><span class="status ${statusClass}">${statusText}</span></td>
            <td>${escapeHtml(scanText)}</td>
            <td>${counts.total} stored, ${counts.eligible} eligible</td>
            <td>
              <div class="actions">
                <button class="secondary" data-action="toggle" data-id="${repo.id}" data-endpoint="${endpoint}">${action}</button>
                <button class="secondary" data-action="scan" data-id="${repo.id}">Clone/Scan</button>
                <button class="secondary" data-action="view-scan" data-id="${repo.id}">View scan</button>
                <button class="secondary" data-action="fetch" data-id="${repo.id}">Fetch issues</button>
                <button class="secondary" data-action="view-issues" data-id="${repo.id}">View issues</button>
              </div>
            </td>
          </tr>
        `;
      }).join("");
    }

    function joinList(values) {
      return values && values.length ? values.map(escapeHtml).join(", ") : "None";
    }

    function boolPill(value) {
      return `<span class="status ${value ? "yes" : "no"}">${value ? "Yes" : "No"}</span>`;
    }

    function renderScan(repo, scan) {
      scanPanel.hidden = false;
      scanTitle.textContent = `${repo.owner}/${repo.name} scan`;
      scanSummary.innerHTML = `
        <div><strong>Local path</strong><span class="mono">${escapeHtml(scan.local_path)}</span></div>
        <div><strong>Cloned</strong>${boolPill(scan.is_cloned)}</div>
        <div><strong>Tech stack</strong>${joinList(scan.tech_stack)}</div>
        <div><strong>Package manager</strong>${escapeHtml(scan.package_manager || "Unknown")}</div>
        <div><strong>Test config</strong>${boolPill(scan.has_test_config)}</div>
        <div><strong>Lint config</strong>${boolPill(scan.has_lint_config)}</div>
        <div><strong>Build config</strong>${boolPill(scan.has_build_config)}</div>
        <div><strong>Last scan</strong>${escapeHtml(new Date(scan.last_scanned_at).toLocaleString())}</div>
        <div><strong>Contribution docs</strong>${joinList(scan.contribution_docs)}</div>
        <div><strong>Important files</strong>${joinList(scan.important_files)}</div>
      `;
    }

    function renderIssues(repo, issues) {
      issuePanel.hidden = false;
      issueTitle.textContent = `${repo.owner}/${repo.name} issues`;
      issueSummary.textContent = `${issues.length} stored issues, ${issues.filter((issue) => issue.is_eligible).length} eligible.`;
      if (!issues.length) {
        issueTable.innerHTML = '<tr><td class="empty" colspan="5">No stored issues yet.</td></tr>';
        return;
      }
      issueTable.innerHTML = issues.map((issue) => {
        const labels = issue.labels.length ? issue.labels.map((label) => `<span class="label">${escapeHtml(label)}</span>`).join("") : "None";
        const eligibleText = issue.is_eligible ? "Eligible" : `Not eligible: ${issue.rejection_reasons.join(", ")}`;
        const eligibleClass = issue.is_eligible ? "eligible" : "not-eligible";
        return `
          <tr>
            <td>${issue.number}</td>
            <td><a href="${escapeHtml(issue.html_url)}" target="_blank" rel="noreferrer">${escapeHtml(issue.title)}</a></td>
            <td>${labels}</td>
            <td>${issue.is_assigned ? "Assigned" : "Unassigned"}</td>
            <td><span class="status ${eligibleClass}">${escapeHtml(eligibleText)}</span></td>
          </tr>
        `;
      }).join("");
    }

    async function loadRepos() {
      repos = await requestJson(apiBase);
      await refreshSummaries();
      renderRepos();
    }

    async function viewScan(repoId) {
      const repo = repos.find((item) => item.id === repoId);
      if (!repo) return;
      const scan = await requestJson(`${apiBase}/${repoId}/scan`);
      scanCache[repoId] = scan;
      renderScan(repo, scan);
      renderRepos();
    }

    async function viewIssues(repoId) {
      const repo = repos.find((item) => item.id === repoId);
      if (!repo) return;
      const issues = await requestJson(`${apiBase}/${repoId}/issues`);
      renderIssues(repo, issues);
      await loadIssueCount(repoId);
      renderRepos();
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      setMessage("");
      addButton.disabled = true;
      try {
        await requestJson(apiBase, {method: "POST", body: JSON.stringify({repo_url: input.value})});
        input.value = "";
        setMessage("Repository added.", false);
        await loadRepos();
      } catch (error) {
        setMessage(error.message);
      } finally {
        addButton.disabled = false;
      }
    });

    repoTable.addEventListener("click", async (event) => {
      const button = event.target.closest("button[data-id]");
      if (!button) return;
      const repoId = Number(button.dataset.id);
      setMessage("");
      button.disabled = true;
      try {
        if (button.dataset.action === "toggle") {
          await requestJson(`${apiBase}/${repoId}/${button.dataset.endpoint}`, {method: "POST"});
          await loadRepos();
        }
        if (button.dataset.action === "scan") {
          const scan = await requestJson(`${apiBase}/${repoId}/scan`, {method: "POST"});
          scanCache[repoId] = scan;
          setMessage("Repository cloned/updated and scanned.", false);
          await loadRepos();
          await viewScan(repoId);
        }
        if (button.dataset.action === "view-scan") {
          await viewScan(repoId);
        }
        if (button.dataset.action === "fetch") {
          const result = await requestJson(`${apiBase}/${repoId}/issues/fetch`, {method: "POST"});
          setMessage(`Fetched ${result.fetched}; stored ${result.stored}; skipped ${result.skipped_existing}.`, false);
          await loadRepos();
          await viewIssues(repoId);
        }
        if (button.dataset.action === "view-issues") {
          await viewIssues(repoId);
        }
      } catch (error) {
        setMessage(error.message);
      } finally {
        button.disabled = false;
      }
    });

    loadRepos().catch((error) => setMessage(error.message));
  </script>
</body>
</html>
        """
    )
