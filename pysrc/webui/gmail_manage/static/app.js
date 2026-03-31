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
  const emailContent   = document.getElementById("email-content");
  const sidebarContent = document.getElementById("sidebar-content");
  const statusText     = document.getElementById("status-text");
  const cmdInput       = document.getElementById("cmd-input");
  const connDot        = document.getElementById("topbar-conn");
  const completionsPop = document.getElementById("completions-popup");

  // ── Command history state ─────────────────────────────────────────────────
  const cmdHistory = [];  // Most-recent command at index 0
  let historyIdx   = -1;  // -1 = not browsing history
  let inTypoGuard  = false;

  // ── Known labels / categories (updated from sidebar event) ───────────────
  let knownLabels     = [];  // [{id, name, type?, ...}]
  let knownCategories = [];  // [{id, name}]

  // ── Tab-completion state ──────────────────────────────────────────────────
  let completions    = [];   // String list of current matches
  let completionIdx  = -1;   // Highlighted index (-1 = none)
  let completionBase = null; // Input value when Tab was first pressed this cycle

  // ── Current email state ───────────────────────────────────────────────────
  let currentMessageId = null;

  // ── Socket.IO connection ──────────────────────────────────────────────────
  const socket = io({ transports: ["websocket", "polling"] });

  function setConnState(state) {
    connDot.className = `conn-dot ${state}`;
    const labels = { connecting: "connecting…", connected: "connected", disconnected: "disconnected" };
    connDot.title = labels[state] || state;
  }

  socket.on("connect",      () => { setConnState("connected"); enableInput(true); });
  socket.on("disconnect",   () => { setConnState("disconnected"); enableInput(false); });
  socket.on("connect_error", () => setConnState("disconnected"));

  // ── Incoming events ───────────────────────────────────────────────────────

  socket.on("email", (data) => {
    currentMessageId = data.id || null;
    renderEmail(data);
    enableInput(true);
  });

  socket.on("sidebar", (data) => {
    knownLabels     = data.labels     || [];
    knownCategories = data.categories || [];
    renderSidebar(knownLabels, knownCategories);
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

  // ── Tab completion ────────────────────────────────────────────────────────

  const PRIMARY_CMDS   = ["cat", "hard-delete", "soft-delete", "move", "skip"];
  const SECONDARY_CMDS = ["hard-delete", "soft-delete", "move"];

  /**
   * Determine what part of the input is being completed.
   * Returns { prefix, partial, type } or null if no completion context applies.
   *   prefix  — the part of the input that stays unchanged
   *   partial — the token currently being typed (to filter candidates against)
   *   type    — "command" | "category" | "label" | "secondary"
   */
  function getCompletionContext(value) {
    let m;

    // "cat <category> move <label-partial>"
    m = value.match(/^(cat\s+\S+\s+move\s+)(\S*)$/i);
    if (m) return { prefix: m[1], partial: m[2], type: "label" };

    // "cat <category> <secondary-partial>"  (category already complete)
    m = value.match(/^(cat\s+\S+\s+)(\S*)$/i);
    if (m) return { prefix: m[1], partial: m[2], type: "secondary" };

    // "move <label-partial>"
    m = value.match(/^(move\s+)(\S*)$/i);
    if (m) return { prefix: m[1], partial: m[2], type: "label" };

    // "cat <category-partial>"
    m = value.match(/^(cat\s+)(\S*)$/i);
    if (m) return { prefix: m[1], partial: m[2], type: "category" };

    // First word (no space yet)
    if (!value.includes(" ")) {
      return { prefix: "", partial: value, type: "command" };
    }

    return null;
  }

  function getCandidates(type) {
    switch (type) {
      case "command":   return PRIMARY_CMDS.slice();
      case "secondary": return SECONDARY_CMDS.slice();
      case "category":  return knownCategories.map(c => c.name);
      case "label":     return knownLabels.map(l => l.name);
      default:          return [];
    }
  }

  function computeCompletions(value) {
    if (inTypoGuard) return [];
    const ctx = getCompletionContext(value);
    if (!ctx) return [];
    const partial = ctx.partial.toLowerCase();
    return getCandidates(ctx.type).filter(c => c.toLowerCase().startsWith(partial));
  }

  function applyCompletion(baseValue, completion) {
    const ctx = getCompletionContext(baseValue);
    if (!ctx) return;
    cmdInput.value = ctx.prefix + completion + " ";
  }

  // ── Completion popup rendering ────────────────────────────────────────────

  function renderCompletionPopup() {
    if (completions.length === 0) { hideCompletionPopup(); return; }

    let html = completions.map((item, i) => {
      const cls = i === completionIdx ? "completion-item active" : "completion-item";
      return `<div class="${cls}" data-idx="${i}">${esc(item)}</div>`;
    }).join("");

    if (completions.length > 1) {
      html += `<div class="completion-hint">Tab / ↑↓ to cycle · Esc to cancel</div>`;
    }

    completionsPop.hidden = false;
    completionsPop.innerHTML = html;

    // Scroll active item into view
    const active = completionsPop.querySelector(".active");
    if (active) active.scrollIntoView({ block: "nearest" });
  }

  function hideCompletionPopup() {
    completionsPop.hidden = true;
    completionsPop.innerHTML = "";
  }

  function resetCompletion() {
    completions    = [];
    completionIdx  = -1;
    completionBase = null;
    hideCompletionPopup();
  }

  // Click on a popup item to accept it
  completionsPop.addEventListener("mousedown", (e) => {
    const item = e.target.closest(".completion-item");
    if (!item) return;
    e.preventDefault();  // keep input focused
    const idx = parseInt(item.dataset.idx, 10);
    if (!isNaN(idx) && completionBase !== null && completions[idx]) {
      applyCompletion(completionBase, completions[idx]);
    }
    resetCompletion();
  });

  // ── Command input keydown ─────────────────────────────────────────────────

  cmdInput.addEventListener("keydown", (e) => {
    const popupOpen = !completionsPop.hidden;

    // ── Tab: cycle through completions ─────────────────────────────────────
    if (e.key === "Tab") {
      e.preventDefault();

      if (completionBase === null) {
        // Start a fresh completion cycle
        completionBase = cmdInput.value;
        completions    = computeCompletions(completionBase);
        completionIdx  = -1;
      }

      if (completions.length === 0) { resetCompletion(); return; }

      if (e.shiftKey) {
        // Shift+Tab: cycle backward
        completionIdx = completionIdx <= 0 ? completions.length - 1 : completionIdx - 1;
      } else {
        // Tab: cycle forward
        completionIdx = (completionIdx + 1) % completions.length;
      }

      applyCompletion(completionBase, completions[completionIdx]);

      if (completions.length > 1) {
        renderCompletionPopup();
      } else {
        // Single match — apply and close immediately
        resetCompletion();
      }
      return;
    }

    // ── Escape: cancel completion, restore original input ──────────────────
    if (e.key === "Escape") {
      if (popupOpen) {
        e.preventDefault();
        if (completionBase !== null) cmdInput.value = completionBase;
        resetCompletion();
      }
      return;
    }

    // ── Arrow keys: navigate popup (when open) or history (when closed) ────
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (popupOpen) {
        completionIdx = (completionIdx + 1) % completions.length;
        applyCompletion(completionBase, completions[completionIdx]);
        renderCompletionPopup();
      } else {
        if (historyIdx > 0) {
          historyIdx--;
          cmdInput.value = cmdHistory[historyIdx];
        } else {
          historyIdx = -1;
          cmdInput.value = "";
        }
      }
      return;
    }

    if (e.key === "ArrowUp") {
      e.preventDefault();
      if (popupOpen) {
        completionIdx = completionIdx <= 0 ? completions.length - 1 : completionIdx - 1;
        applyCompletion(completionBase, completions[completionIdx]);
        renderCompletionPopup();
      } else {
        if (cmdHistory.length > 0) {
          historyIdx = Math.min(historyIdx + 1, cmdHistory.length - 1);
          cmdInput.value = cmdHistory[historyIdx];
          setTimeout(() => cmdInput.setSelectionRange(cmdInput.value.length, cmdInput.value.length), 0);
        }
      }
      return;
    }

    // ── Enter: always submit (closing popup first if open) ─────────────────
    if (e.key === "Enter") {
      e.preventDefault();
      resetCompletion();
      const text = cmdInput.value;
      if (text.trim() && !inTypoGuard) {
        cmdHistory.unshift(text);
      }
      historyIdx    = -1;
      cmdInput.value = "";
      socket.emit("command", { text });
      return;
    }

    // ── Any other key: close popup (keep current applied text) ────────────
    resetCompletion();
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
