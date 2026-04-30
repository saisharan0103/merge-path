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
    :root {
      color-scheme: light;
      font-family: Arial, Helvetica, sans-serif;
      background: #f6f7f9;
      color: #20242a;
    }
    body {
      margin: 0;
      padding: 32px;
    }
    main {
      max-width: 980px;
      margin: 0 auto;
    }
    h1 {
      margin: 0 0 8px;
      font-size: 28px;
    }
    p {
      margin: 0 0 24px;
      color: #5d6673;
    }
    form {
      display: flex;
      gap: 10px;
      margin-bottom: 18px;
    }
    input {
      flex: 1;
      min-width: 0;
      padding: 10px 12px;
      border: 1px solid #c8ced8;
      border-radius: 6px;
      font-size: 14px;
    }
    button {
      border: 0;
      border-radius: 6px;
      padding: 10px 14px;
      background: #2457c5;
      color: white;
      font-weight: 600;
      cursor: pointer;
    }
    button.secondary {
      background: #e8ebf0;
      color: #20242a;
    }
    button:disabled {
      cursor: not-allowed;
      opacity: 0.6;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      background: white;
      border: 1px solid #d9dee7;
    }
    th, td {
      padding: 12px;
      text-align: left;
      border-bottom: 1px solid #edf0f4;
      font-size: 14px;
    }
    th {
      background: #eef2f7;
      color: #3f4752;
    }
    .status {
      display: inline-block;
      padding: 3px 8px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
    }
    .enabled {
      background: #dff4e7;
      color: #11612d;
    }
    .disabled {
      background: #f1f2f4;
      color: #646b76;
    }
    .message {
      min-height: 22px;
      margin-bottom: 12px;
      color: #9a3412;
      font-size: 14px;
    }
    .empty {
      color: #747d8a;
      text-align: center;
    }
    @media (max-width: 640px) {
      body {
        padding: 18px;
      }
      form {
        flex-direction: column;
      }
      table {
        display: block;
        overflow-x: auto;
      }
    }
  </style>
</head>
<body>
  <main>
    <h1>PatchPilot Repositories</h1>
    <p>Add repositories, review onboarding records, and toggle whether PatchPilot should consider them active.</p>

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
          <th>Action</th>
        </tr>
      </thead>
      <tbody id="repo-table">
        <tr><td class="empty" colspan="4">Loading repositories...</td></tr>
      </tbody>
    </table>
  </main>

  <script>
    const apiBase = "/api/v1/repos";
    const form = document.querySelector("#repo-form");
    const input = document.querySelector("#repo-url");
    const addButton = document.querySelector("#add-button");
    const table = document.querySelector("#repo-table");
    const message = document.querySelector("#message");

    function setMessage(text, isError = true) {
      message.textContent = text;
      message.style.color = isError ? "#9a3412" : "#11612d";
    }

    async function requestJson(url, options = {}) {
      const response = await fetch(url, {
        headers: {"Content-Type": "application/json"},
        ...options
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || `Request failed with ${response.status}`);
      }
      return response.json();
    }

    function renderRepos(repos) {
      if (!repos.length) {
        table.innerHTML = '<tr><td class="empty" colspan="4">No repositories yet.</td></tr>';
        return;
      }
      table.innerHTML = repos.map((repo) => {
        const statusClass = repo.is_enabled ? "enabled" : "disabled";
        const statusText = repo.is_enabled ? "Enabled" : "Disabled";
        const action = repo.is_enabled ? "Disable" : "Enable";
        const endpoint = repo.is_enabled ? "disable" : "enable";
        return `
          <tr>
            <td>${repo.owner}</td>
            <td>${repo.name}</td>
            <td><span class="status ${statusClass}">${statusText}</span></td>
            <td><button class="secondary" data-id="${repo.id}" data-endpoint="${endpoint}">${action}</button></td>
          </tr>
        `;
      }).join("");
    }

    async function loadRepos() {
      const repos = await requestJson(apiBase);
      renderRepos(repos);
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      setMessage("");
      addButton.disabled = true;
      try {
        await requestJson(apiBase, {
          method: "POST",
          body: JSON.stringify({repo_url: input.value})
        });
        input.value = "";
        setMessage("Repository added.", false);
        await loadRepos();
      } catch (error) {
        setMessage(error.message);
      } finally {
        addButton.disabled = false;
      }
    });

    table.addEventListener("click", async (event) => {
      const button = event.target.closest("button[data-id]");
      if (!button) return;
      setMessage("");
      button.disabled = true;
      try {
        await requestJson(`${apiBase}/${button.dataset.id}/${button.dataset.endpoint}`, {method: "POST"});
        await loadRepos();
      } catch (error) {
        setMessage(error.message);
        button.disabled = false;
      }
    });

    loadRepos().catch((error) => setMessage(error.message));
  </script>
</body>
</html>
        """
    )
