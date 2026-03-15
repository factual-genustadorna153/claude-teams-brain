#!/usr/bin/env python3
"""
claude-teams-brain Dashboard Server
Pure Python stdlib web dashboard for reviewing and curating brain memory.

Usage:
  python3 dashboard_server.py --project-dir /path/to/project [--port 7432]
"""

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

BRAIN_HOME = Path(os.environ.get("CLAUDE_BRAIN_HOME", Path.home() / ".claude-teams-brain"))

# Map Claude Code system agent types to readable names
ROLE_DISPLAY = {
    'general-purpose': 'General',
    'explore': 'Explorer',
    'plan': 'Architect',
    'claude-code-guide': 'Docs',
    'unknown': 'Agent',
    '': 'Agent',
}


def project_id(project_dir: str) -> str:
    return hashlib.sha256(str(Path(project_dir).resolve()).encode()).hexdigest()[:12]


def get_db_path(project_dir: str) -> Path:
    pid = project_id(project_dir)
    return BRAIN_HOME / "projects" / pid / "brain.db"


def get_db(project_dir: str) -> sqlite3.Connection:
    path = get_db_path(project_dir)
    if not path.exists():
        print(f"Error: brain.db not found at {path}", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>claude-teams-brain Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;700&family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg: #05080f;
  --surface: rgba(12,20,40,0.85);
  --glass: rgba(25,45,85,0.35);
  --border: rgba(78,159,255,0.12);
  --border-hover: rgba(78,159,255,0.3);
  --accent: #4e9fff;
  --green: #00e5a0;
  --red: #ff6b6b;
  --yellow: #ffd43b;
  --purple: #c084fc;
  --orange: #fb923c;
  --text: #c0cfe0;
  --dim: #4a5568;
  --bright: #f0f4ff;
  --heading: 'Outfit', -apple-system, sans-serif;
  --mono: 'JetBrains Mono', 'Fira Code', monospace;
}

body {
  background: var(--bg); color: var(--text);
  font-family: var(--heading); line-height: 1.6;
  min-height: 100vh; position: relative;
}

/* Background effects */
body::before {
  content: '';
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background:
    radial-gradient(ellipse at 15% 20%, rgba(78,159,255,0.06) 0%, transparent 50%),
    radial-gradient(ellipse at 85% 80%, rgba(0,229,160,0.04) 0%, transparent 40%),
    radial-gradient(ellipse at 50% 50%, rgba(192,132,252,0.03) 0%, transparent 50%);
  z-index: 0; pointer-events: none;
}
body::after {
  content: '';
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background-image:
    linear-gradient(rgba(78,159,255,0.02) 1px, transparent 1px),
    linear-gradient(90deg, rgba(78,159,255,0.02) 1px, transparent 1px);
  background-size: 60px 60px;
  z-index: 0; pointer-events: none;
}

a { color: var(--accent); text-decoration: none; }

/* Header */
.header {
  position: relative; z-index: 10;
  background: linear-gradient(180deg, rgba(5,8,15,0.95), rgba(5,8,15,0.7));
  backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--border);
  padding: 16px 28px; display: flex; align-items: center; gap: 16px;
}
.header h1 {
  font-family: var(--heading); font-size: 22px; font-weight: 700; color: var(--bright);
  display: flex; align-items: center; gap: 10px;
}
.header h1 .accent { color: var(--accent); }
.header .subtitle {
  font-family: var(--mono); color: var(--dim); font-size: 11px;
  letter-spacing: 0.3px; margin-left: auto;
}
.header .status-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--green); box-shadow: 0 0 8px var(--green);
  display: inline-block; margin-right: 6px;
  animation: pulse 2s infinite;
}
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }

/* Tabs */
.tabs {
  position: relative; z-index: 10;
  display: flex; gap: 0;
  background: rgba(5,8,15,0.8);
  backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--border);
  padding: 0 28px;
}
.tab {
  padding: 14px 22px; cursor: pointer; font-size: 13px; font-weight: 500;
  color: var(--dim); border-bottom: 2px solid transparent;
  transition: all 0.25s; user-select: none; letter-spacing: 0.3px;
}
.tab:hover { color: var(--text); }
.tab.active { color: var(--accent); border-bottom-color: var(--accent); }

/* Main */
.main { position: relative; z-index: 5; max-width: 1280px; margin: 0 auto; padding: 28px; }
.section { display: none; animation: fadeIn 0.4s ease; }
.section.active { display: block; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }

/* Stat cards */
.stat-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px; margin-bottom: 36px;
}
.stat-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 14px; padding: 24px; text-align: center;
  backdrop-filter: blur(20px);
  transition: border-color 0.3s, transform 0.2s;
}
.stat-card:hover { border-color: var(--border-hover); transform: translateY(-2px); }
.stat-card .value {
  font-family: var(--heading); font-size: 40px; font-weight: 800;
  color: var(--bright); line-height: 1;
}
.stat-card .label {
  font-family: var(--mono); font-size: 10px; color: var(--dim);
  margin-top: 8px; text-transform: uppercase; letter-spacing: 1.5px;
}

/* Timeline */
.timeline { position: relative; padding-left: 28px; margin-top: 8px; }
.timeline::before {
  content: ''; position: absolute; left: 8px; top: 0; bottom: 0;
  width: 1px; background: linear-gradient(180deg, var(--accent), transparent);
}
.timeline-item {
  position: relative; margin-bottom: 16px; padding: 14px 18px;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 12px; backdrop-filter: blur(10px);
  transition: border-color 0.2s;
}
.timeline-item:hover { border-color: var(--border-hover); }
.timeline-item::before {
  content: ''; position: absolute; left: -24px; top: 18px;
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--accent); box-shadow: 0 0 8px var(--accent);
}
.timeline-item .time { font-family: var(--mono); font-size: 11px; color: var(--dim); }
.timeline-item .title { font-size: 14px; font-weight: 600; color: var(--bright); margin-top: 3px; }
.timeline-item .detail { font-size: 13px; color: var(--dim); margin-top: 4px; line-height: 1.5; }

/* Tables */
.table-wrap { overflow-x: auto; border-radius: 14px; border: 1px solid var(--border); }
table {
  width: 100%; border-collapse: collapse; font-size: 14px;
  background: var(--surface);
}
thead th {
  text-align: left; padding: 14px 18px;
  background: rgba(12,20,40,0.9);
  border-bottom: 1px solid var(--border);
  font-family: var(--mono); font-size: 10px; font-weight: 500;
  color: var(--dim); text-transform: uppercase; letter-spacing: 1.5px;
}
tbody td { padding: 14px 18px; border-bottom: 1px solid rgba(78,159,255,0.06); }
tbody tr:last-child td { border-bottom: none; }
tbody tr { transition: background 0.15s; }
tbody tr:hover { background: rgba(78,159,255,0.04); }

/* Badges */
.badge {
  display: inline-block; padding: 3px 10px; border-radius: 6px;
  font-family: var(--mono); font-size: 10px; font-weight: 500;
  text-transform: uppercase; letter-spacing: 0.8px;
}
.badge-green { background: rgba(0,229,160,0.12); color: var(--green); }
.badge-blue { background: rgba(78,159,255,0.12); color: var(--accent); }
.badge-gray { background: rgba(74,85,104,0.2); color: var(--dim); }
.badge-yellow { background: rgba(255,212,59,0.12); color: var(--yellow); }
.badge-red { background: rgba(255,107,107,0.12); color: var(--red); }
.badge-purple { background: rgba(192,132,252,0.12); color: var(--purple); }

/* Buttons */
.btn {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 5px 12px; border-radius: 8px;
  font-family: var(--heading); font-size: 12px; font-weight: 500;
  cursor: pointer; border: 1px solid var(--border);
  background: var(--surface); color: var(--text);
  transition: all 0.2s; backdrop-filter: blur(10px);
}
.btn:hover { background: var(--glass); border-color: var(--border-hover); }
.btn-approve { border-color: rgba(0,229,160,0.3); color: var(--green); }
.btn-approve:hover { background: rgba(0,229,160,0.15); }
.btn-reject { border-color: rgba(255,107,107,0.3); color: var(--red); }
.btn-reject:hover { background: rgba(255,107,107,0.15); }
.btn-flag { border-color: rgba(255,212,59,0.3); color: var(--yellow); }
.btn-flag:hover { background: rgba(255,212,59,0.15); }

/* Filters */
.filters {
  display: flex; gap: 12px; margin-bottom: 20px; flex-wrap: wrap;
  align-items: center;
}
.filters select {
  background: var(--surface); color: var(--text);
  border: 1px solid var(--border); border-radius: 8px;
  padding: 7px 14px; font-family: var(--heading); font-size: 13px;
  backdrop-filter: blur(10px);
  transition: border-color 0.2s;
}
.filters select:focus { border-color: var(--accent); outline: none; }
.filters label {
  font-family: var(--mono); font-size: 10px; color: var(--dim);
  text-transform: uppercase; letter-spacing: 1px;
}

/* Decisions */
.decision-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 12px; padding: 18px; margin-bottom: 12px;
  border-left: 3px solid var(--border);
  backdrop-filter: blur(10px);
  transition: border-color 0.2s;
}
.decision-card:hover { border-color: var(--border-hover); }
.decision-card.flagged { background: rgba(255,212,59,0.05); border-left-color: var(--yellow); }
.decision-card.decision-user { border-left-color: var(--green); }
.decision-card.decision-signal { border-left-color: var(--accent); }
.decision-card.decision-noise { border-left-color: var(--dim); }
.decision-card .decision-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 10px;
}
.decision-card .decision-text { font-size: 14px; margin-bottom: 8px; color: var(--bright); line-height: 1.6; }
.decision-card .decision-rationale { font-size: 13px; color: var(--dim); line-height: 1.5; }
.decision-card .decision-meta {
  font-family: var(--mono); font-size: 10px; color: var(--dim);
  margin-top: 10px; letter-spacing: 0.3px;
}
.decisions-group-title {
  font-family: var(--mono); font-size: 10px; font-weight: 500;
  margin: 24px 0 12px 0; color: var(--accent);
  text-transform: uppercase; letter-spacing: 1.5px;
  display: flex; align-items: center; gap: 8px;
}
.decisions-group-title::after {
  content: ''; flex: 1; height: 1px; background: var(--border);
}
.decisions-group-title:first-child { margin-top: 0; }
.decisions-group-note {
  font-size: 12px; color: var(--dim); margin-bottom: 12px; font-style: italic;
}
.toggle-row {
  display: flex; align-items: center; gap: 10px; margin-bottom: 20px;
}
.toggle-row label {
  font-size: 13px; color: var(--dim); cursor: pointer; user-select: none;
}
.toggle-row input[type="checkbox"] {
  cursor: pointer; accent-color: var(--accent);
}

/* File grid */
.file-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 14px;
}
.file-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 12px; padding: 18px;
  backdrop-filter: blur(10px);
  transition: border-color 0.2s;
}
.file-card:hover { border-color: var(--border-hover); }
.file-card .file-path {
  font-family: var(--mono); font-size: 12px;
  color: var(--accent); word-break: break-all; margin-bottom: 8px;
}
.file-card .file-meta {
  font-family: var(--mono); font-size: 10px; color: var(--dim);
  margin-bottom: 10px; letter-spacing: 0.3px;
}
.file-card .agent-list { display: flex; gap: 6px; flex-wrap: wrap; }

/* Toast */
.toast-container {
  position: fixed; bottom: 24px; right: 24px; z-index: 1000;
  display: flex; flex-direction: column; gap: 8px;
}
.toast {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 10px; padding: 12px 20px; font-size: 13px;
  backdrop-filter: blur(20px);
  box-shadow: 0 8px 32px rgba(0,0,0,0.4);
  animation: toastIn 0.3s ease, toastOut 0.3s ease 2.7s forwards;
}
.toast.success { border-color: rgba(0,229,160,0.4); color: var(--green); }
.toast.error { border-color: rgba(255,107,107,0.4); color: var(--red); }
@keyframes toastIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
@keyframes toastOut { to { opacity: 0; transform: translateY(10px); } }

/* Section headers */
.section-title {
  font-family: var(--heading); font-size: 20px; font-weight: 700;
  color: var(--bright); margin-bottom: 20px;
  display: flex; align-items: center; gap: 10px;
}
.section-title::before {
  content: ''; width: 3px; height: 20px; border-radius: 2px;
  background: var(--accent);
}
.empty-state {
  text-align: center; padding: 60px 24px; color: var(--dim);
  font-size: 14px; font-weight: 300;
}

/* Editable fields */
.editable {
  cursor: pointer; border-bottom: 1px dashed transparent;
  transition: all 0.2s; padding: 2px 4px; border-radius: 4px;
}
.editable:hover { background: rgba(78,159,255,0.06); border-bottom-color: var(--dim); }
.editable input, .editable textarea {
  background: var(--bg); color: var(--bright);
  border: 1px solid var(--accent); border-radius: 6px;
  padding: 6px 10px; width: 100%;
  font-family: inherit; font-size: inherit;
}
.editable textarea { min-height: 60px; resize: vertical; }
.btn-delete {
  background: rgba(255,107,107,0.15); color: var(--red);
  border: 1px solid rgba(255,107,107,0.2); padding: 3px 8px;
  border-radius: 6px; cursor: pointer; font-size: 11px;
  transition: all 0.2s;
}
.btn-delete:hover { background: rgba(255,107,107,0.25); }
.btn-edit {
  background: transparent; color: var(--dim);
  border: 1px solid var(--border); padding: 3px 8px;
  border-radius: 6px; cursor: pointer; font-size: 11px;
  transition: all 0.2s;
}
.btn-edit:hover { color: var(--accent); border-color: var(--accent); }
.edit-actions { display: flex; gap: 6px; margin-top: 6px; }
.btn-save {
  background: linear-gradient(135deg, var(--green), #00c890);
  color: #fff; border: none; padding: 4px 14px;
  border-radius: 6px; cursor: pointer; font-size: 12px; font-weight: 500;
  transition: all 0.2s;
}
.btn-save:hover { box-shadow: 0 0 12px rgba(0,229,160,0.3); }
.btn-cancel {
  background: var(--surface); color: var(--text);
  border: 1px solid var(--border); padding: 4px 14px;
  border-radius: 6px; cursor: pointer; font-size: 12px;
  transition: all 0.2s;
}
.btn-cancel:hover { border-color: var(--dim); }
</style>
</head>
<body>

<div class="header">
  <h1>
    <span>&#129504;</span>
    <span>claude-teams-brain</span>
    <span class="accent">Dashboard</span>
  </h1>
  <div class="subtitle"><span class="status-dot"></span><span id="project-info">Loading...</span></div>
</div>

<div class="tabs">
  <div class="tab active" data-tab="overview">Overview</div>
  <div class="tab" data-tab="memories">Memory Curation</div>
  <div class="tab" data-tab="decisions">Decisions</div>
  <div class="tab" data-tab="files">File Map</div>
</div>

<div class="main">
  <div class="section active" id="section-overview">
    <div class="stat-grid" id="stat-cards"></div>
    <h2 class="section-title">Recent Activity</h2>
    <div class="timeline" id="activity-timeline"></div>
  </div>

  <div class="section" id="section-memories">
    <h2 class="section-title">Memory Curation</h2>
    <div style="background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:14px 18px;margin-bottom:20px;backdrop-filter:blur(10px);font-size:13px;line-height:1.7;color:var(--dim);">
      <span style="color:var(--bright);font-weight:600;">How memory curation works:</span>
      Memories are automatically captured from agent sessions and scored by confidence.
      <span style="color:var(--green);">Approve</span> promotes a memory to HIGH confidence — it will be prioritized when injecting context into future teammates.
      <span style="color:var(--red);">Reject</span> excludes a memory from future injection entirely.
      <span style="color:var(--yellow);">Flag</span> marks it for human review. Click any <span style="color:var(--accent);">subject</span>, <span style="color:var(--accent);">role</span>, or <span style="color:var(--accent);">summary</span> to edit inline.
    </div>
    <div class="filters">
      <label>Role</label>
      <select id="filter-role"><option value="">All Roles</option></select>
      <label>Confidence</label>
      <select id="filter-confidence">
        <option value="">All</option>
        <option value="HIGH">High</option>
        <option value="MEDIUM">Medium</option>
        <option value="LOW">Low</option>
        <option value="PENDING">Pending</option>
      </select>
      <label>Status</label>
      <select id="filter-status">
        <option value="">All</option>
        <option value="active">Active</option>
        <option value="rejected">Rejected</option>
        <option value="flagged">Flagged</option>
      </select>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Subject</th><th>Role</th><th>Confidence</th>
            <th>Status</th><th>Completed</th><th>Actions</th>
          </tr>
        </thead>
        <tbody id="memories-body"></tbody>
      </table>
    </div>
  </div>

  <div class="section" id="section-decisions">
    <h2 class="section-title">Decision Log</h2>
    <div class="toggle-row">
      <input type="checkbox" id="hide-noise" checked>
      <label for="hide-noise">Hide low-quality entries</label>
    </div>
    <div id="decisions-list"></div>
  </div>

  <div class="section" id="section-files">
    <h2 class="section-title">File Map</h2>
    <div class="file-grid" id="file-grid"></div>
  </div>
</div>

<div class="toast-container" id="toast-container"></div>

<script>
const API = '';
let allMemories = [];

// ── Toast ──
function toast(msg, type = 'success') {
  const el = document.createElement('div');
  el.className = 'toast ' + type;
  el.textContent = msg;
  document.getElementById('toast-container').appendChild(el);
  setTimeout(() => el.remove(), 3000);
}

// ── Tabs ──
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById('section-' + tab.dataset.tab).classList.add('active');
  });
});

// ── Badge helpers ──
function confidenceBadge(c) {
  const map = { HIGH: 'green', MEDIUM: 'blue', LOW: 'gray', PENDING: 'yellow' };
  return `<span class="badge badge-${map[c] || 'gray'}">${c || 'N/A'}</span>`;
}
function statusBadge(s) {
  const map = { active: 'green', rejected: 'red', flagged: 'yellow' };
  return `<span class="badge badge-${map[s] || 'gray'}">${s || 'N/A'}</span>`;
}
function agentBadge(name) {
  return `<span class="badge badge-purple">${name || 'unknown'}</span>`;
}
function fmtTime(ts) {
  if (!ts) return 'N/A';
  try { return new Date(ts).toLocaleString(); } catch { return ts; }
}
function shortTime(ts) {
  if (!ts) return '';
  try {
    const d = new Date(ts);
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) +
      ' ' + d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
  } catch { return ts; }
}

// ── Fetch helpers ──
async function apiGet(path) {
  const r = await fetch(API + path);
  return r.json();
}
async function apiPost(path) {
  const r = await fetch(API + path, { method: 'POST' });
  return r.json();
}
async function apiPut(path, body) {
  const r = await fetch(API + path, { method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body) });
  return r.json();
}
async function apiDelete(path) {
  const r = await fetch(API + path, { method: 'DELETE' });
  return r.json();
}

// ── Overview ──
async function loadOverview() {
  const stats = await apiGet('/api/stats');
  document.getElementById('project-info').textContent =
    `Project: ${stats.project_dir || 'unknown'} | DB: ${stats.db_path || 'unknown'}`;
  const cards = [
    { label: 'Tasks', value: stats.tasks || 0 },
    { label: 'Decisions', value: stats.decisions || 0 },
    { label: 'Sessions', value: stats.runs || 0 },
    { label: 'Files Tracked', value: stats.files || 0 },
  ];
  document.getElementById('stat-cards').innerHTML = cards.map(c =>
    `<div class="stat-card"><div class="value">${c.value}</div><div class="label">${c.label}</div></div>`
  ).join('');

  // Timeline: merge recent sessions and decisions
  const sessions = await apiGet('/api/sessions');
  const decisions = await apiGet('/api/decisions');
  let items = [];
  (sessions || []).slice(0, 10).forEach(s => {
    items.push({ time: s.started_at, title: 'Session started', detail: s.summary || 'No summary', type: 'session' });
  });
  (decisions || []).slice(0, 10).forEach(d => {
    items.push({ time: d.created_at, title: `Decision by ${d.agent_name || 'unknown'}`, detail: d.decision, type: 'decision' });
  });
  items.sort((a, b) => (b.time || '').localeCompare(a.time || ''));
  items = items.slice(0, 15);

  const tl = document.getElementById('activity-timeline');
  if (items.length === 0) {
    tl.innerHTML = '<div class="empty-state">No activity recorded yet.</div>';
    return;
  }
  tl.innerHTML = items.map(i => `
    <div class="timeline-item">
      <div class="time">${shortTime(i.time)}</div>
      <div class="title">${esc(i.title)}</div>
      <div class="detail">${esc(i.detail || '').slice(0, 200)}</div>
    </div>
  `).join('');
}

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s || '';
  return d.innerHTML;
}
function escAttr(s) {
  return esc(s).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// ── Memories ──
async function loadMemories() {
  allMemories = await apiGet('/api/memories') || [];
  // Build role filter using display names, keyed by raw role
  const roleMap = {};
  allMemories.forEach(m => {
    if (m.agent_role) roleMap[m.agent_role] = m.role_display || m.agent_role;
  });
  const sel = document.getElementById('filter-role');
  sel.innerHTML = '<option value="">All Roles</option>' +
    Object.entries(roleMap).map(([raw, display]) => `<option value="${raw}">${display}</option>`).join('');
  renderMemories();
}

function renderMemories() {
  const roleF = document.getElementById('filter-role').value;
  const confF = document.getElementById('filter-confidence').value;
  const statF = document.getElementById('filter-status').value;
  let filtered = allMemories;
  if (roleF) filtered = filtered.filter(m => m.agent_role === roleF);
  if (confF) filtered = filtered.filter(m => (m.confidence || '').toUpperCase() === confF);
  if (statF) filtered = filtered.filter(m => m.status === statF);

  const body = document.getElementById('memories-body');
  if (filtered.length === 0) {
    body.innerHTML = '<tr><td colspan="6" class="empty-state">No memories found.</td></tr>';
    return;
  }
  body.innerHTML = filtered.map(m => `
    <tr data-mem-id="${m.id}">
      <td>
        <div class="editable" onclick="inlineEdit(this,'${m.id}','subject','input')" data-field="subject" data-value="${escAttr(m.task_subject || '')}">${esc(m.display_subject || m.task_subject || 'Untitled')}</div>
        ${m.summary_preview ? `<div style="font-size:12px;color:#8b949e;margin-top:4px;line-height:1.4;cursor:pointer;" onclick="editSummary('${m.id}')" title="Click to edit summary">${esc(m.summary_preview)}</div>` : `<div style="font-size:12px;color:#484f58;margin-top:4px;cursor:pointer;" onclick="editSummary('${m.id}')">[no summary — click to add]</div>`}
      </td>
      <td><span class="editable" onclick="inlineEdit(this,'${m.id}','role','input')" data-field="role" data-value="${escAttr(m.agent_role || '')}">${agentBadge(m.role_display || m.agent_role || m.agent_name)}</span></td>
      <td>${confidenceBadge((m.confidence || '').toUpperCase())}</td>
      <td>${statusBadge(m.status)}</td>
      <td>${shortTime(m.completed_at)}</td>
      <td style="white-space:nowrap;">
        <button class="btn btn-approve" onclick="memAction('${m.id}','approve')" title="Promote to HIGH confidence — this memory will be prioritized in future teammate context injection">Approve</button>
        <button class="btn btn-reject" onclick="memAction('${m.id}','reject')" title="Mark as rejected — this memory will be excluded from future context injection">Reject</button>
        <button class="btn btn-flag" onclick="memAction('${m.id}','flag')" title="Flag for review — this memory needs human verification before being trusted">Flag</button>
        <button class="btn-edit" onclick="editSummary('${m.id}')" title="Edit summary">&#9998;</button>
        <button class="btn-delete" onclick="deleteMem('${m.id}')" title="Delete memory">&#10005;</button>
      </td>
    </tr>
  `).join('');
}

// Inline editing for subject and role
function inlineEdit(el, id, field, type) {
  if (el.querySelector('input')) return; // already editing
  const oldVal = el.dataset.value || el.textContent.trim();
  const input = document.createElement('input');
  input.type = 'text';
  input.value = oldVal;
  el.textContent = '';
  el.appendChild(input);
  input.focus();
  input.select();

  async function save() {
    const newVal = input.value.trim();
    if (newVal && newVal !== oldVal) {
      try {
        const body = {};
        body[field] = newVal;
        await apiPut('/api/memories/' + id, body);
        toast('Updated ' + field);
        await loadMemories();
      } catch (e) { toast('Save failed: ' + e.message, 'error'); }
    } else {
      await loadMemories(); // revert
    }
  }
  input.addEventListener('blur', save);
  input.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); input.blur(); } if (e.key === 'Escape') { loadMemories(); } });
}

// Edit summary in a modal-like inline textarea
function editSummary(id) {
  const mem = allMemories.find(m => m.id === id);
  if (!mem) return;
  const row = document.querySelector(`tr[data-mem-id="${id}"]`);
  if (!row || row.querySelector('.summary-editor')) return;
  const td = row.querySelector('td');
  const editor = document.createElement('div');
  editor.className = 'summary-editor';
  editor.style.cssText = 'margin-top:8px;';
  editor.innerHTML = `<textarea style="background:#0d1117;color:#e6edf3;border:1px solid #58a6ff;padding:6px 8px;border-radius:4px;width:100%;min-height:80px;font-family:inherit;font-size:13px;resize:vertical;">${esc(mem.output_summary || '')}</textarea>
    <div class="edit-actions"><button class="btn-save" onclick="saveSummary('${id}',this)">Save</button><button class="btn-cancel" onclick="loadMemories()">Cancel</button></div>`;
  td.appendChild(editor);
  editor.querySelector('textarea').focus();
}

async function saveSummary(id, btn) {
  const textarea = btn.closest('.summary-editor').querySelector('textarea');
  const val = textarea.value.trim();
  try {
    await apiPut('/api/memories/' + id, { summary: val });
    toast('Summary updated');
    await loadMemories();
  } catch (e) { toast('Save failed: ' + e.message, 'error'); }
}

async function deleteMem(id) {
  if (!confirm('Delete this memory permanently?')) return;
  try {
    await apiDelete('/api/memories/' + id);
    toast('Memory deleted');
    await loadMemories();
  } catch (e) { toast('Delete failed: ' + e.message, 'error'); }
}

document.getElementById('filter-role').addEventListener('change', renderMemories);
document.getElementById('filter-confidence').addEventListener('change', renderMemories);
document.getElementById('filter-status').addEventListener('change', renderMemories);

async function memAction(id, action) {
  try {
    await apiPost(`/api/memories/${id}/${action}`);
    toast(`Memory ${id} ${action}d`);
    await loadMemories();
  } catch (e) {
    toast('Action failed: ' + e.message, 'error');
  }
}

// ── Decisions ──
const NOISE_PREFIXES = ['Now ', 'Good.', 'Perfect.', 'Here is', 'The function', 'The test', 'Before ', '- **'];
const SIGNAL_WORDS = ['decided', 'convention', 'rule', 'must', 'always', 'never', 'switched', 'approach'];

function classifyDecision(d) {
  if ((d.agent_name || '').toLowerCase() === 'user') return 'user';
  const text = d.decision || '';
  const textLower = text.toLowerCase();
  const hasSignal = SIGNAL_WORDS.some(w => textLower.includes(w));
  const agentDisplay = (d.agent_display || '').toLowerCase();
  const isNoisy =
    NOISE_PREFIXES.some(p => text.startsWith(p)) ||
    text.length > 200 ||
    ((['explorer', 'architect'].includes(agentDisplay) || ['explore', 'plan'].includes((d.agent_name || '').toLowerCase())) && !hasSignal);
  if (isNoisy) return 'noise';
  return hasSignal ? 'signal' : 'team';
}

function renderDecisionCard(d, cls) {
  const cardClass = cls === 'user' ? 'decision-user' : cls === 'signal' ? 'decision-signal' : cls === 'noise' ? 'decision-noise' : '';
  return `
    <div class="decision-card ${cardClass}${d.status === 'flagged' ? ' flagged' : ''}" data-decision-class="${cls}" data-dec-id="${d.id}">
      <div class="decision-header">
        ${agentBadge(d.agent_display || d.agent_name)}
        <div style="display:flex;gap:6px;align-items:center;">
          ${statusBadge(d.status)}
          <button class="btn-edit" onclick="editDecision('${d.id}')" title="Edit decision">&#9998;</button>
          <button class="btn-delete" onclick="deleteDecision('${d.id}')" title="Delete decision">&#10005;</button>
        </div>
      </div>
      <div class="decision-text editable" onclick="inlineEditDecision(this,'${d.id}','decision')" data-value="${escAttr(d.decision || '')}">${esc(d.decision)}</div>
      <div class="decision-rationale editable" onclick="inlineEditDecision(this,'${d.id}','rationale')" data-value="${escAttr(d.rationale || '')}">${esc(d.rationale || '') || '<em style="color:#484f58;">no rationale — click to add</em>'}</div>
      <div class="decision-meta">
        ${d.context ? '<strong>Context:</strong> ' + esc(d.context) + ' | ' : ''}
        ${d.tags ? '<strong>Tags:</strong> ' + esc(d.tags) + ' | ' : ''}
        ${shortTime(d.created_at)}
      </div>
    </div>`;
}

function inlineEditDecision(el, id, field) {
  if (el.querySelector('textarea')) return;
  const oldVal = el.dataset.value || el.textContent.trim();
  const textarea = document.createElement('textarea');
  textarea.value = oldVal;
  textarea.style.cssText = 'background:#0d1117;color:#e6edf3;border:1px solid #58a6ff;padding:4px 8px;border-radius:4px;width:100%;min-height:40px;font-family:inherit;font-size:inherit;resize:vertical;';
  el.textContent = '';
  el.appendChild(textarea);
  const actions = document.createElement('div');
  actions.className = 'edit-actions';
  actions.innerHTML = `<button class="btn-save" onclick="saveDecisionField('${id}','${field}',this)">Save</button><button class="btn-cancel" onclick="loadDecisions()">Cancel</button>`;
  el.appendChild(actions);
  textarea.focus();
}

async function saveDecisionField(id, field, btn) {
  const textarea = btn.closest('.edit-actions').previousElementSibling || btn.closest('.editable').querySelector('textarea');
  // Find the textarea within the parent editable element
  const editable = btn.closest('.editable') || btn.parentElement.parentElement;
  const ta = editable.querySelector('textarea');
  const val = ta ? ta.value.trim() : '';
  try {
    const body = {};
    body[field] = val;
    await apiPut('/api/decisions/' + id, body);
    toast('Decision updated');
    await loadDecisions();
  } catch (e) { toast('Save failed: ' + e.message, 'error'); }
}

function editDecision(id) {
  const card = document.querySelector(`[data-dec-id="${id}"] .decision-text`);
  if (card) inlineEditDecision(card, id, 'decision');
}

async function deleteDecision(id) {
  if (!confirm('Delete this decision permanently?')) return;
  try {
    await apiDelete('/api/decisions/' + id);
    toast('Decision deleted');
    await loadDecisions();
  } catch (e) { toast('Delete failed: ' + e.message, 'error'); }
}

let allDecisions = [];

async function loadDecisions() {
  allDecisions = await apiGet('/api/decisions') || [];
  renderDecisions();
}

function renderDecisions() {
  const list = document.getElementById('decisions-list');
  if (allDecisions.length === 0) {
    list.innerHTML = '<div class="empty-state">No decisions recorded yet.</div>';
    return;
  }

  const hideNoise = document.getElementById('hide-noise').checked;
  const userDecs = [];
  const teamDecs = [];
  const noiseDecs = [];

  allDecisions.forEach(d => {
    const cls = classifyDecision(d);
    if (cls === 'user') userDecs.push({ d, cls });
    else if (cls === 'noise') noiseDecs.push({ d, cls });
    else teamDecs.push({ d, cls });
  });

  let html = '';

  if (userDecs.length > 0) {
    html += '<div class="decisions-group-title">Project Rules</div>';
    html += userDecs.map(x => renderDecisionCard(x.d, x.cls)).join('');
  }

  if (teamDecs.length > 0) {
    html += '<div class="decisions-group-title">Team Decisions</div>';
    html += '<div class="decisions-group-note">Auto-extracted from agent transcripts</div>';
    html += teamDecs.map(x => renderDecisionCard(x.d, x.cls)).join('');
  }

  if (!hideNoise && noiseDecs.length > 0) {
    html += '<div class="decisions-group-title">Low-quality entries (' + noiseDecs.length + ')</div>';
    html += noiseDecs.map(x => renderDecisionCard(x.d, x.cls)).join('');
  } else if (hideNoise && noiseDecs.length > 0) {
    html += '<div class="decisions-group-note">' + noiseDecs.length + ' low-quality entries hidden</div>';
  }

  list.innerHTML = html;
}

document.getElementById('hide-noise').addEventListener('change', renderDecisions);

// ── Files ──
async function loadFiles() {
  const files = await apiGet('/api/files') || [];
  const grid = document.getElementById('file-grid');
  if (files.length === 0) {
    grid.innerHTML = '<div class="empty-state">No files tracked yet.</div>';
    return;
  }
  grid.innerHTML = files.map(f => `
    <div class="file-card">
      <div class="file-path">${esc(f.file_path)}</div>
      <div class="file-meta">${f.touch_count} touch${f.touch_count !== 1 ? 'es' : ''} | Last: ${shortTime(f.last_touched)}</div>
      <div class="agent-list">${(f.agents || []).map(a => agentBadge(a)).join('')}</div>
    </div>
  `).join('');
}

// ── Init ──
async function init() {
  await Promise.all([loadOverview(), loadMemories(), loadDecisions(), loadFiles()]);
}
init();
setInterval(init, 30000);
</script>
</body>
</html>"""


class DashboardHandler(BaseHTTPRequestHandler):
    project_dir = None

    def log_message(self, format, *args):
        pass  # Suppress default logging

    def _send_json(self, data, status=200):
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html):
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _get_db(self):
        return get_db(self.project_dir)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "" or path == "/":
            self._send_html(DASHBOARD_HTML)
            return

        try:
            conn = self._get_db()
        except SystemExit:
            self._send_json({"error": "brain.db not found"}, 500)
            return

        try:
            if path == "/api/stats":
                self._handle_stats(conn)
            elif path == "/api/memories":
                self._handle_memories(conn)
            elif path == "/api/decisions":
                self._handle_decisions(conn)
            elif path == "/api/files":
                self._handle_files(conn)
            elif path == "/api/sessions":
                self._handle_sessions(conn)
            else:
                self._send_json({"error": "Not found"}, 404)
        finally:
            conn.close()

    def do_OPTIONS(self):
        """Handle CORS preflight for PUT/DELETE requests."""
        self.send_response(204)
        self.send_header("Allow", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # Match /api/memories/<id>/<action>
        parts = path.split("/")
        if len(parts) == 5 and parts[1] == "api" and parts[2] == "memories" and parts[4] in ("approve", "reject", "flag"):
            mem_id = parts[3]
            action = parts[4]
            try:
                conn = self._get_db()
            except SystemExit:
                self._send_json({"error": "brain.db not found"}, 500)
                return
            try:
                self._handle_memory_action(conn, mem_id, action)
            finally:
                conn.close()
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        parts = path.split("/")

        # PUT /api/memories/<id>
        if len(parts) == 4 and parts[1] == "api" and parts[2] == "memories":
            mem_id = parts[3]
            try:
                conn = self._get_db()
            except SystemExit:
                self._send_json({"error": "brain.db not found"}, 500)
                return
            try:
                self._handle_update_memory(conn, mem_id)
            finally:
                conn.close()
            return

        # PUT /api/decisions/<id>
        if len(parts) == 4 and parts[1] == "api" and parts[2] == "decisions":
            dec_id = parts[3]
            try:
                conn = self._get_db()
            except SystemExit:
                self._send_json({"error": "brain.db not found"}, 500)
                return
            try:
                self._handle_update_decision(conn, dec_id)
            finally:
                conn.close()
            return

        self._send_json({"error": "Not found"}, 404)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        parts = path.split("/")

        # DELETE /api/memories/<id>
        if len(parts) == 4 and parts[1] == "api" and parts[2] == "memories":
            mem_id = parts[3]
            try:
                conn = self._get_db()
            except SystemExit:
                self._send_json({"error": "brain.db not found"}, 500)
                return
            try:
                self._handle_delete_memory(conn, mem_id)
            finally:
                conn.close()
            return

        # DELETE /api/decisions/<id>
        if len(parts) == 4 and parts[1] == "api" and parts[2] == "decisions":
            dec_id = parts[3]
            try:
                conn = self._get_db()
            except SystemExit:
                self._send_json({"error": "brain.db not found"}, 500)
                return
            try:
                self._handle_delete_decision(conn, dec_id)
            finally:
                conn.close()
            return

        self._send_json({"error": "Not found"}, 404)

    def _safe_count(self, conn, table):
        try:
            row = conn.execute(f"SELECT COUNT(*) as c FROM {table}").fetchone()
            return row["c"] if row else 0
        except sqlite3.OperationalError:
            return 0

    def _handle_stats(self, conn):
        stats = {
            "tasks": self._safe_count(conn, "tasks"),
            "decisions": self._safe_count(conn, "decisions"),
            "runs": self._safe_count(conn, "runs"),
            "files": self._safe_count(conn, "file_index"),
            "conflicts": self._safe_count(conn, "conflicts"),
            "project_dir": self.project_dir,
            "db_path": str(get_db_path(self.project_dir)),
        }
        self._send_json(stats)

    def _handle_memories(self, conn):
        try:
            rows = conn.execute(
                "SELECT id, run_id, task_subject, agent_name, agent_role, "
                "files_touched, decisions, output_summary, completed_at, "
                "confidence, access_count, last_accessed, status "
                "FROM tasks ORDER BY completed_at DESC"
            ).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                # Map role to display name
                role_raw = d.get("agent_role") or ""
                d["role_display"] = ROLE_DISPLAY.get(role_raw.lower(), role_raw.capitalize() if role_raw else "Agent")
                # Derive a useful display subject when subject is generic
                subject = d.get("task_subject") or ""
                summary = (d.get("output_summary") or "")[:200]
                if subject.startswith("Work by ") or not subject:
                    first_line = ""
                    for line in summary.split('\n'):
                        line = line.strip().lstrip('#').lstrip('*').strip().rstrip('*').strip()
                        if len(line) >= 10 and not (line.startswith('/') and ' ' not in line):
                            first_line = line[:100]
                            break
                    d["display_subject"] = first_line or subject
                else:
                    d["display_subject"] = subject
                # Add truncated summary preview
                d["summary_preview"] = summary[:120]
                results.append(d)
            self._send_json(results)
        except sqlite3.OperationalError:
            self._send_json([])

    def _handle_decisions(self, conn):
        try:
            rows = conn.execute(
                "SELECT id, run_id, agent_name, context, decision, rationale, "
                "tags, created_at, status "
                "FROM decisions ORDER BY created_at DESC"
            ).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                agent = d.get("agent_name") or ""
                d["agent_display"] = ROLE_DISPLAY.get(agent.lower(), agent.capitalize() if agent else "Agent")
                results.append(d)
            self._send_json(results)
        except sqlite3.OperationalError:
            self._send_json([])

    def _handle_files(self, conn):
        try:
            rows = conn.execute(
                "SELECT file_path, agent_name, operation, touched_at "
                "FROM file_index ORDER BY touched_at DESC"
            ).fetchall()
        except sqlite3.OperationalError:
            self._send_json([])
            return

        # Group by file_path
        files = {}
        for r in rows:
            fp = r["file_path"]
            if fp not in files:
                files[fp] = {"file_path": fp, "touch_count": 0, "agents": set(), "last_touched": None}
            files[fp]["touch_count"] += 1
            if r["agent_name"]:
                files[fp]["agents"].add(r["agent_name"])
            ts = r["touched_at"]
            if ts and (files[fp]["last_touched"] is None or ts > files[fp]["last_touched"]):
                files[fp]["last_touched"] = ts

        result = []
        for fp, data in sorted(files.items(), key=lambda x: x[1]["touch_count"], reverse=True):
            data["agents"] = sorted(data["agents"])
            result.append(data)
        self._send_json(result)

    def _handle_sessions(self, conn):
        try:
            rows = conn.execute(
                "SELECT id, project_dir, session_id, started_at, ended_at, summary "
                "FROM runs ORDER BY started_at DESC"
            ).fetchall()
            self._send_json([dict(r) for r in rows])
        except sqlite3.OperationalError:
            self._send_json([])

    def _handle_memory_action(self, conn, mem_id, action):
        if action == "approve":
            conn.execute("UPDATE tasks SET confidence='HIGH', status='active' WHERE id=?", (mem_id,))
        elif action == "reject":
            conn.execute("UPDATE tasks SET status='rejected' WHERE id=?", (mem_id,))
        elif action == "flag":
            conn.execute("UPDATE tasks SET status='flagged' WHERE id=?", (mem_id,))
        conn.commit()
        self._send_json({"ok": True, "id": mem_id, "action": action})

    def _read_json_body(self):
        """Safely read and parse JSON request body."""
        content_length = int(self.headers.get('Content-Length') or 0)
        if content_length == 0:
            return {}
        raw = self.rfile.read(content_length)
        if not raw:
            return {}
        return json.loads(raw)

    def _handle_update_memory(self, conn, task_id):
        try:
            body = self._read_json_body()
        except (json.JSONDecodeError, ValueError):
            self._send_json({"error": "Invalid JSON body"}, 400)
            return
        updates = []
        params = []
        if 'subject' in body:
            updates.append('task_subject = ?')
            params.append(body['subject'])
        if 'role' in body:
            updates.append('agent_role = ?')
            params.append(body['role'])
            updates.append('agent_name = ?')
            params.append(body['role'])
        if 'summary' in body:
            updates.append('output_summary = ?')
            params.append(body['summary'])
        if updates:
            params.append(task_id)
            conn.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()
        self._send_json({"status": "ok", "id": task_id})

    def _handle_delete_memory(self, conn, task_id):
        conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        try:
            conn.execute("DELETE FROM file_index WHERE task_id = ?", (task_id,))
        except sqlite3.OperationalError:
            pass  # file_index may not have task_id column
        conn.commit()
        self._send_json({"status": "ok", "id": task_id})

    def _handle_update_decision(self, conn, decision_id):
        try:
            body = self._read_json_body()
        except (json.JSONDecodeError, ValueError):
            self._send_json({"error": "Invalid JSON body"}, 400)
            return
        updates = []
        params = []
        if 'decision' in body:
            updates.append('decision = ?')
            params.append(body['decision'])
        if 'rationale' in body:
            updates.append('rationale = ?')
            params.append(body['rationale'])
        if updates:
            params.append(decision_id)
            conn.execute(f"UPDATE decisions SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()
        self._send_json({"status": "ok", "id": decision_id})

    def _handle_delete_decision(self, conn, decision_id):
        conn.execute("DELETE FROM decisions WHERE id = ?", (decision_id,))
        conn.commit()
        self._send_json({"status": "ok", "id": decision_id})


def main():
    parser = argparse.ArgumentParser(description="claude-teams-brain Dashboard Server")
    parser.add_argument("--project-dir", default=os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()),
                        help="Project directory (default: CLAUDE_PROJECT_DIR or cwd)")
    parser.add_argument("--port", type=int, default=7432, help="Port to listen on (default: 7432)")
    parser.add_argument("--no-open", action="store_true", help="Don't open browser automatically")
    args = parser.parse_args()

    project_dir = str(Path(args.project_dir).resolve())
    db = get_db_path(project_dir)
    if not db.exists():
        print(f"Error: No brain.db found at {db}")
        print(f"  Project dir: {project_dir}")
        print(f"  Project hash: {project_id(project_dir)}")
        print(f"\nMake sure you have run at least one session with claude-teams-brain in this project.")
        sys.exit(1)

    DashboardHandler.project_dir = project_dir

    server = HTTPServer(("127.0.0.1", args.port), DashboardHandler)
    url = f"http://127.0.0.1:{args.port}"
    print(f"claude-teams-brain Dashboard")
    print(f"  Project: {project_dir}")
    print(f"  DB:      {db}")
    print(f"  URL:     {url}")
    print(f"\nPress Ctrl+C to stop.\n")

    if not args.no_open:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
