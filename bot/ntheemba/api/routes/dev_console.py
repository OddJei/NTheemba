"""Developer-only browser console for traces and fake dependency controls."""

# ruff: noqa: E501

from __future__ import annotations

from secrets import token_urlsafe

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/dev", tags=["developer-console"], include_in_schema=False)

_CONSOLE_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Ntheemba Developer Trace Console</title>
  <style nonce="__CSP_NONCE__">
    :root { color-scheme: dark; font-family: Inter, system-ui, sans-serif; }
    * { box-sizing: border-box; }
    body { margin: 0; background: #101217; color: #eef1f6; }
    header { padding: 1rem 1.25rem; border-bottom: 1px solid #2b303a; display: flex;
      gap: 1rem; align-items: center; justify-content: space-between; flex-wrap: wrap; }
    h1 { font-size: 1.1rem; margin: 0; }
    a { color: #7eb4ff; text-decoration: none; }
    h2 { font-size: 1rem; margin: 0 0 .8rem; }
    h3 { font-size: .92rem; margin: 0 0 .6rem; }
    main { display: grid; grid-template-columns: minmax(20rem, 35rem) 1fr; min-height: calc(100vh - 4rem); }
    aside, section { padding: 1rem; overflow: auto; }
    aside { border-right: 1px solid #2b303a; }
    .panel { border: 1px solid #2c323d; border-radius: .65rem; padding: .85rem; margin-bottom: 1rem; background: #151920; }
    .toolbar, .actions { display: flex; gap: .5rem; flex-wrap: wrap; margin-bottom: .75rem; }
    .field-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .65rem; }
    label { color: #aeb7c6; display: grid; gap: .3rem; font-size: .78rem; }
    label.wide { grid-column: 1 / -1; }
    input, select, button { border: 1px solid #3b4350; border-radius: .45rem; padding: .55rem .7rem;
      background: #191d25; color: inherit; min-width: 0; }
    input[type="checkbox"] { width: auto; justify-self: start; }
    .toolbar input { flex: 1; min-width: 10rem; }
    button { cursor: pointer; }
    button:hover { background: #252b36; }
    button.danger { border-color: #8e3e48; }
    button.primary { border-color: #4d70a8; }
    .health, .hint, .result { color: #aeb7c6; font-size: .82rem; }
    .result { min-height: 1.2rem; margin-top: .45rem; overflow-wrap: anywhere; }
    .result.ok { color: #70d49b; }
    .result.error { color: #ff8793; }
    .trace { width: 100%; text-align: left; margin: 0 0 .55rem; padding: .7rem;
      background: #171b22; border: 1px solid #2c323d; border-radius: .55rem; }
    .trace.failed { border-color: #a44c58; }
    .trace strong, .trace span { display: block; overflow-wrap: anywhere; }
    .trace span { color: #aeb7c6; font-size: .8rem; margin-top: .25rem; }
    table { width: 100%; border-collapse: collapse; font-size: .86rem; }
    th, td { border-bottom: 1px solid #2b303a; padding: .55rem; text-align: left; vertical-align: top; }
    td.attributes { max-width: 34rem; white-space: pre-wrap; overflow-wrap: anywhere; }
    .empty { color: #aeb7c6; padding: 2rem 0; text-align: center; }
    .status-passed { color: #70d49b; }
    .status-failed { color: #ff8793; }
    @media (max-width: 900px) {
      main { grid-template-columns: 1fr; }
      aside { border-right: 0; border-bottom: 1px solid #2b303a; }
    }
    @media (max-width: 520px) { .field-grid { grid-template-columns: 1fr; } label.wide { grid-column: auto; } }
  </style>
</head>
<body>
<header>
  <h1>Ntheemba Developer Console</h1>
  <div><a href="/dev/simulator">Open conversation simulator</a></div>
  <div class="health" id="health">Loading trace store…</div>
</header>
<main>
  <aside>
    <div class="panel" id="dependency-panel">
      <h2>Fake dependency controls</h2>
      <div class="field-grid">
        <label class="wide">Dependency
          <select id="dependency"></select>
        </label>
        <label>Latency (ms)
          <input id="latency" type="number" min="0" max="30000" value="0">
        </label>
        <label>Fail next calls
          <input id="fail-next" type="number" min="0" max="100" value="0">
        </label>
        <label>Persistent failure
          <input id="always-fail" type="checkbox">
        </label>
        <label>Probe operation
          <input id="probe-operation" value="probe" maxlength="80">
        </label>
        <label class="wide">Target operations (comma-separated; blank means all)
          <input id="operations" placeholder="search_products, create_order_request">
        </label>
        <label class="wide">Failure message
          <input id="failure-message" maxlength="200" value="Injected fake dependency failure">
        </label>
      </div>
      <div class="actions">
        <button id="save-dependency" class="primary" type="button">Apply</button>
        <button id="probe-dependency" type="button">Probe</button>
        <button id="reset-dependency" type="button">Reset selected</button>
        <button id="reset-all-dependencies" class="danger" type="button">Reset all</button>
      </div>
      <div class="hint">Controls are memory-only and available only in development or test.</div>
      <div id="dependency-result" class="result" aria-live="polite"></div>
    </div>

    <div class="panel">
      <h2>Execution traces</h2>
      <div class="toolbar">
        <input id="conversation" placeholder="Filter by conversation ID" aria-label="Conversation ID">
        <button id="refresh" type="button">Refresh</button>
        <button id="clear" class="danger" type="button">Clear</button>
      </div>
      <div id="traces" aria-live="polite"></div>
    </div>
  </aside>
  <section>
    <h2 id="detail-title">Trace details</h2>
    <div id="details" class="empty">Select a trace to inspect its events.</div>
  </section>
</main>
<script nonce="__CSP_NONCE__">
  const tracesEl = document.getElementById('traces');
  const detailsEl = document.getElementById('details');
  const titleEl = document.getElementById('detail-title');
  const conversationEl = document.getElementById('conversation');
  const healthEl = document.getElementById('health');
  const dependencyEl = document.getElementById('dependency');
  const dependencyResultEl = document.getElementById('dependency-result');
  let dependencies = [];

  function escapeHtml(value) {
    return String(value).replace(/[&<>'"]/g, char => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
    })[char]);
  }

  async function fetchJson(url, options = {}) {
    const response = await fetch(url, { ...options, credentials: 'same-origin' });
    if (!response.ok) {
      let detail = `${response.status} ${response.statusText}`;
      try { detail = JSON.stringify((await response.json()).detail); } catch (_) { /* no JSON body */ }
      throw new Error(detail);
    }
    if (response.status === 204) return null;
    return response.json();
  }

  function selectedDependency() {
    return dependencies.find(item => item.dependency === dependencyEl.value);
  }

  function showDependencyResult(message, ok = true) {
    dependencyResultEl.textContent = message;
    dependencyResultEl.className = `result ${ok ? 'ok' : 'error'}`;
  }

  function populateDependencyForm() {
    const behavior = selectedDependency();
    if (!behavior) return;
    document.getElementById('latency').value = behavior.latency_ms;
    document.getElementById('fail-next').value = behavior.fail_next;
    document.getElementById('always-fail').checked = behavior.always_fail;
    document.getElementById('operations').value = behavior.operations.join(', ');
    document.getElementById('failure-message').value = behavior.failure_message;
  }

  async function loadDependencies(preferred = '') {
    const current = preferred || dependencyEl.value;
    dependencies = await fetchJson('/dev/dependencies');
    dependencyEl.innerHTML = dependencies.map(item =>
      `<option value="${escapeHtml(item.dependency)}">${escapeHtml(item.dependency)}</option>`
    ).join('');
    if (dependencies.some(item => item.dependency === current)) dependencyEl.value = current;
    populateDependencyForm();
  }

  async function saveDependency() {
    const dependency = dependencyEl.value;
    const operations = document.getElementById('operations').value
      .split(',').map(value => value.trim()).filter(Boolean);
    const payload = {
      latency_ms: Number(document.getElementById('latency').value),
      fail_next: Number(document.getElementById('fail-next').value),
      always_fail: document.getElementById('always-fail').checked,
      operations,
      failure_message: document.getElementById('failure-message').value
    };
    try {
      await fetchJson(`/dev/dependencies/${encodeURIComponent(dependency)}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
      });
      await loadDependencies(dependency);
      showDependencyResult(`Applied controls to ${dependency}.`);
    } catch (error) { showDependencyResult(`Could not apply controls: ${error.message}`, false); }
  }

  async function probeDependency() {
    const dependency = dependencyEl.value;
    const operation = document.getElementById('probe-operation').value.trim() || 'probe';
    try {
      const result = await fetchJson(`/dev/dependencies/${encodeURIComponent(dependency)}/probe`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ operation })
      });
      await loadDependencies(dependency);
      showDependencyResult(`${result.dependency}.${result.operation}: ${result.status}`);
    } catch (error) {
      await loadDependencies(dependency);
      showDependencyResult(`Probe failed as configured: ${error.message}`, false);
    }
  }

  async function loadHealth() {
    try {
      const health = await fetchJson('/dev/health/tracing');
      healthEl.textContent = `${health.events} events · ${health.traces} traces · limit ${health.max_events}`;
    } catch (error) { healthEl.textContent = `Trace store unavailable: ${error.message}`; }
  }

  async function loadTraces() {
    tracesEl.innerHTML = '<div class="empty">Loading…</div>';
    const conversation = conversationEl.value.trim();
    const url = conversation
      ? `/dev/conversations/${encodeURIComponent(conversation)}/traces`
      : '/dev/traces';
    try {
      const traces = await fetchJson(url);
      if (!traces.length) {
        tracesEl.innerHTML = '<div class="empty">No retained traces.</div>';
        return;
      }
      tracesEl.innerHTML = traces.map(trace => `
        <button class="trace ${trace.failed ? 'failed' : ''}" data-trace-id="${escapeHtml(trace.trace_id)}">
          <strong>${escapeHtml(trace.trace_id)}</strong>
          <span>${escapeHtml(trace.conversation_id || 'No conversation')} · ${trace.event_count} events</span>
          <span>${Number(trace.duration_ms).toFixed(2)} ms · ${escapeHtml(trace.started_at)}</span>
        </button>`).join('');
      document.querySelectorAll('[data-trace-id]').forEach(button => {
        button.addEventListener('click', () => loadTrace(button.dataset.traceId));
      });
    } catch (error) {
      tracesEl.innerHTML = `<div class="empty">Could not load traces: ${escapeHtml(error.message)}</div>`;
    }
  }

  async function loadTrace(traceId) {
    titleEl.textContent = `Trace ${traceId}`;
    detailsEl.innerHTML = '<div class="empty">Loading…</div>';
    try {
      const events = await fetchJson(`/dev/traces/${encodeURIComponent(traceId)}`);
      detailsEl.innerHTML = `<table>
        <thead><tr><th>Time</th><th>Node</th><th>Status</th><th>Duration</th><th>Attributes / Error</th></tr></thead>
        <tbody>${events.map(event => `
          <tr>
            <td>${escapeHtml(event.occurred_at)}</td>
            <td><strong>${escapeHtml(event.node_id)}</strong><br>${escapeHtml(event.component)}</td>
            <td class="status-${escapeHtml(event.status)}">${escapeHtml(event.status)}</td>
            <td>${event.duration_ms == null ? '—' : `${Number(event.duration_ms).toFixed(2)} ms`}</td>
            <td class="attributes">${escapeHtml(JSON.stringify(event.attributes, null, 2))}${event.error_message ? `<br><strong>${escapeHtml(event.error_type)}:</strong> ${escapeHtml(event.error_message)}` : ''}</td>
          </tr>`).join('')}</tbody>
      </table>`;
    } catch (error) {
      detailsEl.innerHTML = `<div class="empty">Could not load trace: ${escapeHtml(error.message)}</div>`;
    }
  }

  dependencyEl.addEventListener('change', populateDependencyForm);
  document.getElementById('save-dependency').addEventListener('click', saveDependency);
  document.getElementById('probe-dependency').addEventListener('click', probeDependency);
  document.getElementById('reset-dependency').addEventListener('click', async () => {
    const dependency = dependencyEl.value;
    await fetchJson(`/dev/dependencies/${encodeURIComponent(dependency)}`, { method: 'DELETE' });
    await loadDependencies(dependency);
    showDependencyResult(`Reset ${dependency}.`);
  });
  document.getElementById('reset-all-dependencies').addEventListener('click', async () => {
    if (!window.confirm('Reset every fake dependency control?')) return;
    await fetchJson('/dev/dependencies/reset', { method: 'POST' });
    await loadDependencies();
    showDependencyResult('Reset all fake dependency controls.');
  });
  document.getElementById('refresh').addEventListener('click', async () => {
    await Promise.all([loadTraces(), loadHealth(), loadDependencies()]);
  });
  conversationEl.addEventListener('keydown', event => {
    if (event.key === 'Enter') loadTraces();
  });
  document.getElementById('clear').addEventListener('click', async () => {
    if (!window.confirm('Clear all retained developer traces?')) return;
    await fetchJson('/dev/traces', { method: 'DELETE' });
    titleEl.textContent = 'Trace details';
    detailsEl.innerHTML = '<div class="empty">Select a trace to inspect its events.</div>';
    await Promise.all([loadTraces(), loadHealth()]);
  });

  Promise.all([loadTraces(), loadHealth(), loadDependencies()]).catch(error => {
    showDependencyResult(`Developer console initialization failed: ${error.message}`, false);
  });
</script>
</body>
</html>
"""


@router.get("/console", response_class=HTMLResponse, include_in_schema=False)
async def developer_console() -> HTMLResponse:
    """Render the local developer console."""

    nonce = token_urlsafe(18)
    html = _CONSOLE_HTML.replace("__CSP_NONCE__", nonce)
    return HTMLResponse(
        html,
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": (
                f"default-src 'none'; style-src 'nonce-{nonce}'; "
                f"script-src 'nonce-{nonce}'; connect-src 'self'; img-src 'self'; "
                "base-uri 'none'; form-action 'none'; object-src 'none'; "
                "frame-ancestors 'none'"
            ),
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
        },
    )
