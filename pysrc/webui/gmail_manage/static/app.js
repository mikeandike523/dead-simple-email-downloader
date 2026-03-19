/**
 * Gmail Manage Web UI — client logic.
 *
 * Communicates with the Flask/Socket.IO server via events:
 *   server → client:  email, sidebar, status, done, fatal
 *   client → server:  command
 */

(function () {
  "use strict";

  // ── DOM refs ───────────────────────────────────────────────────────────────
  const emailContent  = document.getElementById("email-content");
  const sidebarContent = document.getElementById("sidebar-content");
  const statusText    = document.getElementById("status-text");
  const cmdInput      = document.getElementById("cmd-input");
  const connDot       = document.getElementById("topbar-conn");

  // ── Command history state ─────────────────────────────────────────────────
  const cmdHistory = [];  // Most-recent command at index 0
  let historyIdx   = -1;  // -1 = not browsing history
  let inTypoGuard  = false;

  // ── Current email state ───────────────────────────────────────────────────
  let currentMessageId = null;

  // ── Socket.IO connection ──────────────────────────────────────────────────
  // Connect to the same host/port that served this page.
  const socket = io({ transports: ["websocket", "polling"] });

  function setConnState(state) {
    connDot.className = `conn-dot ${state}`;
    const labels = { connecting: "connecting…", connected: "connected", disconnected: "disconnected" };
    connDot.title = labels[state] || state;
  }

  socket.on("connect",    () => { setConnState("connected"); enableInput(true); });
  socket.on("disconnect", () => { setConnState("disconnected"); enableInput(false); });
  socket.on("connect_error", () => setConnState("disconnected"));

  // ── Incoming events ───────────────────────────────────────────────────────

  socket.on("email", (data) => {
    currentMessageId = data.id || null;
    renderEmail(data);
    enableInput(true);
  });

  socket.on("sidebar", (data) => {
    renderSidebar(data.labels || [], data.categories || []);
  });

  socket.on("status", (data) => {
    setStatus(data.msg || "", data.level || "info");
    inTypoGuard = (data.level === "typo");
  });

  socket.on("done", (data) => {
    emailContent.innerHTML = `
      <p class="state-done">✓ All done!</p>
      <p class="state-done-sub">${esc(String(data.processed || 0))} emails processed.</p>
      <p class="state-done-sub" style="margin-top:8px">No more inbox emails to triage.</p>`;
    enableInput(false);
  });

  socket.on("fatal", (data) => {
    emailContent.innerHTML = `<pre class="state-fatal">${esc(data.msg || "Fatal error")}</pre>`;
    enableInput(false);
  });

  // ── Command input ─────────────────────────────────────────────────────────

  cmdInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      const text = cmdInput.value;
      // Track history for top-level commands only (not typo-guard y/n/c responses)
      if (text.trim() && !inTypoGuard) {
        cmdHistory.unshift(text);
      }
      historyIdx = -1;
      cmdInput.value = "";
      socket.emit("command", { text });
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (cmdHistory.length > 0) {
        historyIdx = Math.min(historyIdx + 1, cmdHistory.length - 1);
        cmdInput.value = cmdHistory[historyIdx];
        // Move cursor to end
        setTimeout(() => cmdInput.setSelectionRange(cmdInput.value.length, cmdInput.value.length), 0);
      }
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      if (historyIdx > 0) {
        historyIdx--;
        cmdInput.value = cmdHistory[historyIdx];
      } else {
        historyIdx = -1;
        cmdInput.value = "";
      }
    }
  });

  // ── View full body ────────────────────────────────────────────────────────

  emailContent.addEventListener("click", (e) => {
    if (e.target.classList.contains("btn-view-body") && currentMessageId) {
      window.open(`/email-body?messageId=${encodeURIComponent(currentMessageId)}`, "_blank");
    }
  });

  function enableInput(on) {
    cmdInput.disabled = !on;
    if (on) cmdInput.focus();
  }

  // ── Render helpers ────────────────────────────────────────────────────────

  function renderEmail(e) {
    emailContent.innerHTML = `
      <div class="email-field">
        <span class="email-label">FROM:</span>
        <span class="email-value">${esc(e.from || "(unknown)")}</span>
      </div>
      <div class="email-field">
        <span class="email-label">DATE:</span>
        <span class="email-value">${esc(e.date || "")}</span>
      </div>
      <div class="email-field email-subject">
        <span class="email-label">SUBJECT:</span>
        <span class="email-value">${esc(e.subject || "(no subject)")}</span>
      </div>
      <hr class="email-divider" />
      <p class="email-snippet">${esc(e.snippet || "")}</p>
      <div class="email-body-row">
        <button class="btn-view-body">View Full Body ↗</button>
      </div>
      <hr class="email-divider" />
      <p class="email-footer">${esc(String(e.processed || 0))} processed · ~${esc(String(e.total || 0))} in inbox</p>`;
  }

  function renderSidebar(labels, categories) {
    let html = `
      <p class="sidebar-section-title">Gmail Labels</p>
      <hr class="sidebar-divider" />
      <ul class="sidebar-list">`;

    if (labels.length === 0) {
      html += `<li class="muted">Loading…</li>`;
    } else {
      for (const lbl of labels) {
        const name   = esc(lbl.name || "");
        const unread = lbl.unread || 0;
        if (unread > 0) {
          html += `<li class="has-unread">${name} <span class="unread-count">(${unread})</span></li>`;
        } else {
          html += `<li>${name}</li>`;
        }
      }
    }

    html += `</ul>
      <p class="sidebar-section-title">Categories</p>
      <hr class="sidebar-divider" />
      <ul class="sidebar-list">`;

    if (categories.length === 0) {
      html += `<li class="sidebar-none">(none yet)</li>`;
    } else {
      for (const cat of categories) {
        html += `<li>${esc(cat.name || "")}</li>`;
      }
    }

    html += `</ul>`;
    sidebarContent.innerHTML = html;
  }

  function setStatus(msg, level) {
    statusText.textContent = msg;
    // Remove all level classes then apply the new one
    statusText.className = `level-${level}`;
  }

  /** Escape HTML special chars to prevent XSS from email content. */
  function esc(str) {
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

})();
