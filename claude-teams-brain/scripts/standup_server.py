#!/usr/bin/env python3
"""
Standup Meeting Server — claude-teams-brain
Mission Control holographic briefing UI for agent team standup reports.

Pure Python stdlib. Launch:
  python3 standup_server.py --project-dir /path/to/project [--port 7433]
"""

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

# ── Config ───────────────────────────────────────────────────────────────────

BRAIN_HOME = Path(os.environ.get("CLAUDE_BRAIN_HOME", Path.home() / ".claude-teams-brain"))
ROLE_COLORS = ['#4e9fff', '#00e5a0', '#ff6b6b', '#ffd43b', '#c084fc', '#fb923c']

# Map Claude Code system agent types to readable role names
ROLE_DISPLAY = {
    'general-purpose': 'Backend',
    'explore': 'Researcher',
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


def role_color(role: str) -> str:
    return ROLE_COLORS[hash(role) % len(ROLE_COLORS)]


def role_initials(role: str) -> str:
    parts = role.replace('-', ' ').replace('_', ' ').split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return role[:2].upper()


# ── Data Queries ─────────────────────────────────────────────────────────────

def query_standup(db_file: Path) -> list:
    if not db_file.exists():
        return []

    conn = sqlite3.connect(str(db_file), timeout=5)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT DISTINCT agent_role FROM tasks WHERE agent_role IS NOT NULL AND agent_role != '' ORDER BY agent_role")
    raw_roles = [r[0] for r in cur.fetchall()]
    roles = []
    for r in raw_roles:
        display = ROLE_DISPLAY.get(r.lower(), r.capitalize() if r else 'Agent')
        if display not in [rr[1] for rr in roles]:
            roles.append((r, display))

    reports = []
    for raw_role, display_role in roles:
        role = raw_role
        report = {"role": display_role, "color": role_color(display_role), "initials": role_initials(display_role)}

        cur.execute(
            "SELECT output_summary FROM tasks WHERE agent_role = ? AND output_summary IS NOT NULL "
            "ORDER BY completed_at DESC LIMIT 1", (role,))
        row = cur.fetchone()
        if row and row[0]:
            text = row[0]
            clean_lines = []
            for line in text.split('\n'):
                line = line.strip().lstrip('#').lstrip('*').lstrip('-').strip().rstrip('*').strip()
                if len(line) < 10 or line.startswith('```') or line.startswith('|'):
                    continue
                clean_lines.append(line)
                if len(' '.join(clean_lines)) > 280:
                    break
            result = ' '.join(clean_lines)[:300] if clean_lines else text[:300]
            if len(result) >= 300 and '.' in result[200:]:
                result = result[:result.rindex('.', 200) + 1]
            report["yesterday"] = result
        else:
            report["yesterday"] = "No previous work recorded."

        cur.execute(
            "SELECT task_subject FROM tasks WHERE agent_role = ? AND task_subject IS NOT NULL "
            "ORDER BY completed_at DESC LIMIT 1", (role,))
        row = cur.fetchone()
        today_text = row[0] if row else "No current task."
        if today_text.startswith("Work by "):
            today_text = report["yesterday"][:100] if report["yesterday"] != "No previous work recorded." else "Continuing previous work."
        report["today"] = today_text

        cur.execute(
            "SELECT decision FROM decisions WHERE agent_name = ? AND "
            "(tags LIKE '%%blocked%%' OR tags LIKE '%%waiting%%') "
            "ORDER BY created_at DESC LIMIT 3", (role,))
        blockers = [r[0] for r in cur.fetchall()]
        report["blockers"] = blockers if blockers else ["None"]

        cur.execute(
            "SELECT DISTINCT file_path FROM file_index WHERE agent_name = ? "
            "ORDER BY touched_at DESC LIMIT 5", (role,))
        report["files"] = [r[0] for r in cur.fetchall()] or ["No files tracked."]

        cur.execute(
            "SELECT decision FROM decisions WHERE agent_name = ? "
            "ORDER BY created_at DESC LIMIT 2", (role,))
        report["decisions"] = [r[0] for r in cur.fetchall()] or ["No recent decisions."]

        reports.append(report)

    conn.close()
    return reports


# ── HTML Page ────────────────────────────────────────────────────────────────

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mission Briefing — claude-teams-brain</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;700&family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg: #05080f;
  --surface: rgba(12,20,40,0.85);
  --glass: rgba(25,45,85,0.35);
  --border: rgba(78,159,255,0.12);
  --glow: rgba(78,159,255,0.25);
  --accent: #4e9fff;
  --green: #00e5a0;
  --red: #ff6b6b;
  --yellow: #ffd43b;
  --purple: #c084fc;
  --text: #c0cfe0;
  --dim: #4a5568;
  --bright: #f0f4ff;
  --heading: 'Outfit', -apple-system, sans-serif;
  --mono: 'JetBrains Mono', 'Fira Code', monospace;
}

html, body { height: 100%; overflow: hidden; }

body {
  background: var(--bg);
  color: var(--text);
  font-family: var(--heading);
  position: relative;
}

/* ── Animated background ───────────────────────────────── */
canvas#stars {
  position: fixed; top: 0; left: 0; width: 100%; height: 100%;
  z-index: 0; pointer-events: none;
}

/* Gradient mesh overlay */
body::before {
  content: '';
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background:
    radial-gradient(ellipse at 20% 50%, rgba(78,159,255,0.06) 0%, transparent 50%),
    radial-gradient(ellipse at 80% 20%, rgba(0,229,160,0.04) 0%, transparent 40%),
    radial-gradient(ellipse at 60% 80%, rgba(192,132,252,0.04) 0%, transparent 40%);
  z-index: 1; pointer-events: none;
}

/* Subtle grid lines */
body::after {
  content: '';
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background-image:
    linear-gradient(rgba(78,159,255,0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(78,159,255,0.03) 1px, transparent 1px);
  background-size: 60px 60px;
  z-index: 1; pointer-events: none;
}

/* ── Layout ────────────────────────────────────────────── */
.screen {
  position: fixed; top: 0; left: 0; width: 100%; height: 100%;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  z-index: 10; opacity: 0; pointer-events: none;
  transition: opacity 0.6s cubic-bezier(0.16, 1, 0.3, 1);
}
.screen.active { opacity: 1; pointer-events: auto; }

/* ── HUD frame ─────────────────────────────────────────── */
.hud-top, .hud-bottom {
  position: fixed; left: 0; right: 0; z-index: 100;
  padding: 12px 24px;
  background: linear-gradient(180deg, rgba(5,8,15,0.95) 0%, transparent 100%);
  display: flex; align-items: center; justify-content: space-between;
  font-family: var(--mono); font-size: 11px; letter-spacing: 0.5px;
  color: var(--dim);
}
.hud-top { top: 0; }
.hud-bottom {
  bottom: 0;
  background: linear-gradient(0deg, rgba(5,8,15,0.95) 0%, transparent 100%);
  padding: 16px 24px;
}
.hud-label { color: var(--accent); text-transform: uppercase; letter-spacing: 1.5px; font-size: 10px; }
.hud-value { color: var(--text); margin-left: 8px; }

/* ── Intro screen ──────────────────────────────────────── */
.intro-content {
  text-align: center;
  animation: fadeUp 1s cubic-bezier(0.16, 1, 0.3, 1) both;
}
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(30px); }
  to { opacity: 1; transform: translateY(0); }
}

.intro-badge {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 6px 16px; border-radius: 20px;
  background: var(--glass); border: 1px solid var(--border);
  font-family: var(--mono); font-size: 11px; color: var(--accent);
  letter-spacing: 1px; text-transform: uppercase;
  margin-bottom: 32px;
  animation: fadeUp 0.8s 0.2s both;
}
.intro-badge::before {
  content: ''; width: 6px; height: 6px; border-radius: 50%;
  background: var(--green); box-shadow: 0 0 8px var(--green);
  animation: pulse 2s infinite;
}
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }

.intro-title {
  font-family: var(--heading); font-weight: 800; font-size: clamp(36px, 6vw, 72px);
  color: var(--bright);
  line-height: 1.1; margin-bottom: 8px;
  animation: fadeUp 0.8s 0.3s both;
}
.intro-title span { color: var(--accent); }

.intro-subtitle {
  font-family: var(--heading); font-weight: 300; font-size: clamp(14px, 2vw, 20px);
  color: var(--dim); margin-bottom: 48px;
  animation: fadeUp 0.8s 0.4s both;
}

.intro-agents {
  display: flex; gap: 16px; justify-content: center; flex-wrap: wrap;
  margin-bottom: 48px;
  animation: fadeUp 0.8s 0.5s both;
}
.intro-agent {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 18px; border-radius: 12px;
  background: var(--surface); border: 1px solid var(--border);
  backdrop-filter: blur(20px);
  transition: transform 0.2s, border-color 0.3s;
}
.intro-agent:hover { transform: translateY(-2px); border-color: var(--accent); }
.intro-agent-dot {
  width: 32px; height: 32px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  font-family: var(--mono); font-weight: 700; font-size: 12px; color: #fff;
}
.intro-agent-name { font-weight: 600; font-size: 14px; color: var(--bright); }
.intro-agent-role { font-size: 11px; color: var(--dim); font-family: var(--mono); }

.btn-start {
  display: inline-flex; align-items: center; gap: 10px;
  padding: 14px 36px; border-radius: 12px;
  background: linear-gradient(135deg, var(--accent), #3b82f6);
  color: #fff; font-family: var(--heading); font-weight: 600; font-size: 16px;
  border: none; cursor: pointer;
  box-shadow: 0 0 30px rgba(78,159,255,0.3), 0 4px 20px rgba(0,0,0,0.3);
  transition: transform 0.2s, box-shadow 0.3s;
  animation: fadeUp 0.8s 0.6s both;
  letter-spacing: 0.5px;
}
.btn-start:hover {
  transform: translateY(-2px);
  box-shadow: 0 0 50px rgba(78,159,255,0.5), 0 8px 30px rgba(0,0,0,0.4);
}
.btn-start svg { width: 18px; height: 18px; }

/* ── Card screen ───────────────────────────────────────── */
.card-container {
  width: 100%; max-width: 800px; padding: 0 24px;
  margin-top: 40px;
}

.agent-header {
  display: flex; align-items: center; gap: 20px;
  margin-bottom: 28px;
  animation: slideIn 0.5s cubic-bezier(0.16, 1, 0.3, 1) both;
}
@keyframes slideIn {
  from { opacity: 0; transform: translateX(-20px); }
  to { opacity: 1; transform: translateX(0); }
}

.agent-avatar {
  width: 56px; height: 56px; border-radius: 14px;
  display: flex; align-items: center; justify-content: center;
  font-family: var(--mono); font-weight: 700; font-size: 20px; color: #fff;
  box-shadow: 0 0 25px var(--glow);
  position: relative;
  flex-shrink: 0;
}
.agent-avatar::after {
  content: ''; position: absolute; inset: -3px; border-radius: 17px;
  border: 1px solid currentColor; opacity: 0.3;
}

.agent-info h2 {
  font-family: var(--heading); font-weight: 700; font-size: 28px;
  color: var(--bright); line-height: 1.2;
}
.agent-info .agent-role-tag {
  font-family: var(--mono); font-size: 11px; color: var(--dim);
  text-transform: uppercase; letter-spacing: 1.5px; margin-top: 2px;
}

/* Report sections */
.report-sections {
  display: flex; flex-direction: column; gap: 12px;
  animation: fadeUp 0.5s 0.15s both;
}

.report-section {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 16px 20px;
  backdrop-filter: blur(20px);
  transition: border-color 0.3s;
}
.report-section:hover { border-color: rgba(78,159,255,0.25); }
.report-section.active-type { border-left: 2px solid var(--accent); }

.section-label {
  font-family: var(--mono); font-size: 10px; font-weight: 500;
  text-transform: uppercase; letter-spacing: 1.5px;
  margin-bottom: 8px; display: flex; align-items: center; gap: 8px;
}
.section-label .dot {
  width: 5px; height: 5px; border-radius: 50%;
  display: inline-block;
}

.section-content {
  font-size: 14px; line-height: 1.7; color: var(--text);
}
.section-content.typewriter-target { min-height: 20px; }
.section-content code {
  font-family: var(--mono); font-size: 12px;
  background: rgba(78,159,255,0.08); padding: 2px 6px; border-radius: 4px;
  color: var(--accent);
}
.section-content .file-path {
  font-family: var(--mono); font-size: 12px; color: var(--accent);
  display: block; padding: 2px 0;
}

/* ── Navigation ────────────────────────────────────────── */
.nav-bar {
  position: fixed; bottom: 0; left: 0; right: 0; z-index: 200;
  display: flex; align-items: center; justify-content: center; gap: 20px;
  padding: 20px 24px 28px;
  background: linear-gradient(0deg, rgba(5,8,15,0.98) 30%, transparent 100%);
}

.nav-dots {
  display: flex; gap: 8px; align-items: center;
}
.nav-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--dim); transition: all 0.3s;
  cursor: pointer;
}
.nav-dot.active { background: var(--accent); box-shadow: 0 0 10px var(--accent); transform: scale(1.3); }
.nav-dot.visited { background: rgba(78,159,255,0.4); }

.nav-counter {
  font-family: var(--mono); font-size: 12px; color: var(--dim);
  min-width: 60px; text-align: center;
}

.nav-btn {
  padding: 10px 24px; border-radius: 10px;
  font-family: var(--heading); font-weight: 600; font-size: 13px;
  border: 1px solid var(--border); cursor: pointer;
  background: var(--surface); color: var(--text);
  backdrop-filter: blur(10px);
  transition: all 0.2s;
  display: flex; align-items: center; gap: 6px;
}
.nav-btn:hover { background: var(--glass); border-color: var(--accent); color: var(--bright); }
.nav-btn:disabled { opacity: 0.3; cursor: default; }
.nav-btn:disabled:hover { background: var(--surface); border-color: var(--border); color: var(--text); }
.nav-btn.primary {
  background: linear-gradient(135deg, var(--accent), #3b82f6);
  border-color: transparent; color: #fff;
}
.nav-btn.primary:hover { box-shadow: 0 0 20px rgba(78,159,255,0.4); }

.btn-skip {
  padding: 6px 14px; border-radius: 6px;
  font-family: var(--mono); font-size: 10px;
  background: transparent; border: 1px solid var(--border);
  color: var(--dim); cursor: pointer;
  text-transform: uppercase; letter-spacing: 1px;
  transition: all 0.2s;
}
.btn-skip:hover { color: var(--text); border-color: var(--dim); }

/* ── Summary screen ────────────────────────────────────── */
.summary-content {
  text-align: center;
  animation: fadeUp 0.8s both;
}
.summary-title {
  font-family: var(--heading); font-weight: 800; font-size: clamp(28px, 5vw, 52px);
  color: var(--bright); margin-bottom: 12px;
}
.summary-title span { color: var(--green); }
.summary-subtitle {
  color: var(--dim); font-size: 16px; margin-bottom: 40px; font-weight: 300;
}

.summary-stats {
  display: flex; gap: 32px; justify-content: center; margin-bottom: 48px;
  animation: fadeUp 0.8s 0.2s both;
}
.summary-stat {
  text-align: center; padding: 20px 28px; border-radius: 16px;
  background: var(--surface); border: 1px solid var(--border);
  backdrop-filter: blur(20px); min-width: 120px;
}
.summary-stat .stat-val {
  font-family: var(--heading); font-weight: 800; font-size: 36px;
  color: var(--bright); line-height: 1;
}
.summary-stat .stat-label {
  font-family: var(--mono); font-size: 10px; color: var(--dim);
  text-transform: uppercase; letter-spacing: 1.5px; margin-top: 8px;
}

.btn-replay {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 12px 28px; border-radius: 10px;
  background: var(--surface); border: 1px solid var(--border);
  color: var(--text); font-family: var(--heading); font-weight: 600;
  font-size: 14px; cursor: pointer;
  transition: all 0.2s;
  animation: fadeUp 0.8s 0.4s both;
}
.btn-replay:hover { border-color: var(--accent); color: var(--bright); }

/* ── Typewriter cursor ─────────────────────────────────── */
.tw-cursor {
  display: inline-block; width: 2px; height: 1em;
  background: var(--accent); margin-left: 2px;
  animation: blink 0.8s steps(2) infinite;
  vertical-align: text-bottom;
}
@keyframes blink { 0% { opacity: 1; } 50% { opacity: 0; } }

/* ── Responsive ────────────────────────────────────────── */
@media (max-width: 640px) {
  .intro-agents { gap: 8px; }
  .intro-agent { padding: 8px 12px; }
  .summary-stats { flex-direction: column; gap: 12px; align-items: center; }
  .card-container { padding: 0 16px; }
  .nav-bar { gap: 12px; padding: 16px 16px 24px; }
}
</style>
</head>
<body>

<canvas id="stars"></canvas>

<!-- HUD top bar -->
<div class="hud-top">
  <div><span class="hud-label">System</span><span class="hud-value">claude-teams-brain</span></div>
  <div><span class="hud-label">Status</span><span class="hud-value" style="color:var(--green);">● Online</span></div>
</div>

<!-- ── INTRO ──────────────────────────────────────────── -->
<div class="screen active" id="intro-screen">
  <div class="intro-content">
    <div class="intro-badge">Mission Briefing</div>
    <div class="intro-title">Team <span>Standup</span></div>
    <div class="intro-subtitle" id="intro-date"></div>
    <div class="intro-agents" id="intro-agents"></div>
    <button class="btn-start" id="btn-begin" disabled>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
      Begin Briefing
    </button>
  </div>
</div>

<!-- ── AGENT CARD ─────────────────────────────────────── -->
<div class="screen" id="card-screen">
  <div class="card-container">
    <div class="agent-header" id="agent-header"></div>
    <div class="report-sections" id="report-sections"></div>
  </div>
</div>

<!-- ── SUMMARY ────────────────────────────────────────── -->
<div class="screen" id="summary-screen">
  <div class="summary-content">
    <div class="summary-title">Briefing <span>Complete</span></div>
    <div class="summary-subtitle">All agents have reported in.</div>
    <div class="summary-stats" id="summary-stats"></div>
    <button class="btn-replay" id="btn-replay">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 4v6h6"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/></svg>
      Replay Briefing
    </button>
  </div>
</div>

<!-- ── NAV BAR ────────────────────────────────────────── -->
<div class="nav-bar" id="nav-bar" style="display:none;">
  <button class="nav-btn" id="btn-prev" disabled>
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M19 12H5m7-7l-7 7 7 7"/></svg>
    Prev
  </button>
  <div class="nav-dots" id="nav-dots"></div>
  <div class="nav-counter" id="nav-counter"></div>
  <button class="btn-skip" id="btn-skip">Skip ⎵</button>
  <button class="nav-btn primary" id="btn-next">
    Next
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
  </button>
</div>

<script>
(function() {
  // ── Star field background ──────────────────────────────
  const canvas = document.getElementById('stars');
  const ctx = canvas.getContext('2d');
  let stars = [];

  function resizeCanvas() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  }

  function initStars() {
    stars = [];
    for (let i = 0; i < 120; i++) {
      stars.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        r: Math.random() * 1.2 + 0.3,
        a: Math.random() * 0.6 + 0.2,
        speed: Math.random() * 0.15 + 0.02,
        phase: Math.random() * Math.PI * 2,
      });
    }
  }

  function drawStars() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const t = Date.now() * 0.001;
    stars.forEach(s => {
      const flicker = 0.5 + 0.5 * Math.sin(t * s.speed * 10 + s.phase);
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(180,210,255,${s.a * flicker})`;
      ctx.fill();
    });
    requestAnimationFrame(drawStars);
  }

  resizeCanvas();
  initStars();
  drawStars();
  window.addEventListener('resize', () => { resizeCanvas(); initStars(); });

  // ── Data + state ───────────────────────────────────────
  let agents = [];
  let current = 0;
  let typewriterTimer = null;
  let typewriterDone = false;

  const introScreen = document.getElementById('intro-screen');
  const cardScreen = document.getElementById('card-screen');
  const summaryScreen = document.getElementById('summary-screen');
  const navBar = document.getElementById('nav-bar');
  const btnBegin = document.getElementById('btn-begin');
  const btnPrev = document.getElementById('btn-prev');
  const btnNext = document.getElementById('btn-next');
  const btnSkip = document.getElementById('btn-skip');
  const btnReplay = document.getElementById('btn-replay');

  // Set date
  document.getElementById('intro-date').textContent =
    new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });

  // ── Fetch data ─────────────────────────────────────────
  fetch('/api/standup')
    .then(r => r.json())
    .then(data => {
      agents = data || [];
      renderIntro();
      btnBegin.disabled = agents.length === 0;
    })
    .catch(() => { agents = []; renderIntro(); });

  function renderIntro() {
    const el = document.getElementById('intro-agents');
    if (agents.length === 0) {
      el.innerHTML = '<div style="color:var(--dim);font-size:14px;">No agents have reported yet.</div>';
      return;
    }
    el.innerHTML = agents.map(a => `
      <div class="intro-agent">
        <div class="intro-agent-dot" style="background:${a.color};">${a.initials}</div>
        <div>
          <div class="intro-agent-name">${esc(a.role)}</div>
        </div>
      </div>
    `).join('');
  }

  // ── Screen transitions ─────────────────────────────────
  function showScreen(screen) {
    [introScreen, cardScreen, summaryScreen].forEach(s => s.classList.remove('active'));
    screen.classList.add('active');
    navBar.style.display = screen === cardScreen ? 'flex' : 'none';
  }

  // ── Begin ──────────────────────────────────────────────
  btnBegin.addEventListener('click', () => {
    if (agents.length === 0) return;
    current = 0;
    showScreen(cardScreen);
    renderDots();
    renderAgent(current);
  });

  // ── Render agent card ──────────────────────────────────
  function renderAgent(idx) {
    const a = agents[idx];
    if (!a) return;

    // Header
    document.getElementById('agent-header').innerHTML = `
      <div class="agent-avatar" style="background:${a.color};color:#fff;">
        ${a.initials}
      </div>
      <div class="agent-info">
        <h2>${esc(a.role)}</h2>
        <div class="agent-role-tag">Agent ${idx + 1} of ${agents.length}</div>
      </div>
    `;

    // Sections
    const sections = [
      { label: 'Completed', color: 'var(--green)', content: a.yesterday, active: true },
      { label: 'Working On', color: 'var(--accent)', content: a.today },
      { label: 'Blockers', color: 'var(--red)', content: a.blockers.join(' · ') },
      { label: 'Files', color: 'var(--purple)', content: a.files.map(f => f.replace(/.*\//, '')).join(', '), raw: a.files },
      { label: 'Decisions', color: 'var(--yellow)', content: a.decisions.join(' | ') },
    ];

    document.getElementById('report-sections').innerHTML = sections.map((s, i) => `
      <div class="report-section${s.active ? ' active-type' : ''}" style="animation-delay:${i * 0.08}s;">
        <div class="section-label" style="color:${s.color};">
          <span class="dot" style="background:${s.color};"></span>
          ${s.label}
        </div>
        <div class="section-content typewriter-target" data-full="${escAttr(s.content)}" id="sec-${i}"></div>
      </div>
    `).join('');

    // Update nav
    updateNav();
    startTypewriter();
  }

  // ── Typewriter ─────────────────────────────────────────
  function startTypewriter() {
    typewriterDone = false;
    if (typewriterTimer) clearInterval(typewriterTimer);

    const targets = document.querySelectorAll('.typewriter-target');
    let targetIdx = 0;
    let charIdx = 0;

    function tick() {
      if (targetIdx >= targets.length) {
        typewriterDone = true;
        clearInterval(typewriterTimer);
        // Remove cursors
        document.querySelectorAll('.tw-cursor').forEach(c => c.remove());
        return;
      }

      const el = targets[targetIdx];
      const full = el.dataset.full || '';

      if (charIdx === 0) {
        el.innerHTML = '<span class="tw-cursor"></span>';
      }

      if (charIdx < full.length) {
        // Add chars in chunks for speed
        const chunk = Math.min(3, full.length - charIdx);
        const text = full.substring(0, charIdx + chunk);
        el.innerHTML = esc(text) + '<span class="tw-cursor"></span>';
        charIdx += chunk;
      } else {
        // Remove cursor from completed section
        const cursor = el.querySelector('.tw-cursor');
        if (cursor) cursor.remove();
        targetIdx++;
        charIdx = 0;
      }
    }

    typewriterTimer = setInterval(tick, 18);
  }

  function skipTypewriter() {
    if (typewriterDone) return;
    if (typewriterTimer) clearInterval(typewriterTimer);
    typewriterDone = true;
    document.querySelectorAll('.typewriter-target').forEach(el => {
      el.textContent = el.dataset.full || '';
    });
  }

  // ── Nav controls ───────────────────────────────────────
  function updateNav() {
    btnPrev.disabled = current === 0;
    btnNext.textContent = current === agents.length - 1 ? 'Finish' : 'Next';
    if (current < agents.length - 1) {
      btnNext.innerHTML = 'Next <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg>';
    } else {
      btnNext.innerHTML = 'Finish <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg>';
    }
    document.getElementById('nav-counter').textContent = `${current + 1} / ${agents.length}`;
    renderDots();
  }

  function renderDots() {
    const el = document.getElementById('nav-dots');
    el.innerHTML = agents.map((_, i) => {
      let cls = 'nav-dot';
      if (i === current) cls += ' active';
      else if (i < current) cls += ' visited';
      return `<div class="${cls}" data-idx="${i}"></div>`;
    }).join('');
    el.querySelectorAll('.nav-dot').forEach(dot => {
      dot.addEventListener('click', () => {
        current = parseInt(dot.dataset.idx);
        renderAgent(current);
      });
    });
  }

  btnPrev.addEventListener('click', () => {
    if (current > 0) { current--; renderAgent(current); }
  });

  btnNext.addEventListener('click', () => {
    skipTypewriter();
    if (current < agents.length - 1) {
      current++;
      renderAgent(current);
    } else {
      showSummary();
    }
  });

  btnSkip.addEventListener('click', skipTypewriter);

  // ── Summary ────────────────────────────────────────────
  function showSummary() {
    showScreen(summaryScreen);
    const totalFiles = new Set(agents.flatMap(a => a.files.filter(f => f !== 'No files tracked.'))).size;
    const totalDecs = agents.reduce((sum, a) => sum + a.decisions.filter(d => d !== 'No recent decisions.').length, 0);
    document.getElementById('summary-stats').innerHTML = `
      <div class="summary-stat">
        <div class="stat-val">${agents.length}</div>
        <div class="stat-label">Agents</div>
      </div>
      <div class="summary-stat">
        <div class="stat-val">${totalFiles}</div>
        <div class="stat-label">Files</div>
      </div>
      <div class="summary-stat">
        <div class="stat-val">${totalDecs}</div>
        <div class="stat-label">Decisions</div>
      </div>
    `;
  }

  btnReplay.addEventListener('click', () => {
    current = 0;
    showScreen(introScreen);
  });

  // ── Keyboard ───────────────────────────────────────────
  document.addEventListener('keydown', (e) => {
    if (cardScreen.classList.contains('active')) {
      if (e.key === 'ArrowLeft') btnPrev.click();
      else if (e.key === 'ArrowRight') btnNext.click();
      else if (e.key === ' ') { e.preventDefault(); skipTypewriter(); }
    } else {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        if (introScreen.classList.contains('active') && agents.length > 0) btnBegin.click();
        if (summaryScreen.classList.contains('active')) btnReplay.click();
      }
    }
  });

  // ── Helpers ────────────────────────────────────────────
  function esc(s) {
    const d = document.createElement('div');
    d.textContent = s || '';
    return d.innerHTML;
  }
  function escAttr(s) {
    return esc(s).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
})();
</script>
</body>
</html>"""


# ── HTTP Handler ─────────────────────────────────────────────────────────────

class StandupHandler(BaseHTTPRequestHandler):
    db_file = None

    def log_message(self, fmt, *args):
        pass  # quiet

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/':
            self._serve_html()
        elif parsed.path == '/api/standup':
            self._serve_json()
        else:
            self.send_error(404)

    def _serve_html(self):
        body = HTML_PAGE.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_json(self):
        reports = query_standup(self.db_file)
        body = json.dumps(reports, indent=2).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='claude-teams-brain standup meeting server')
    parser.add_argument('--project-dir', default=os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()),
                        help='Project directory (default: CLAUDE_PROJECT_DIR or cwd)')
    parser.add_argument('--port', type=int, default=7433, help='Port (default: 7433)')
    parser.add_argument('--no-open', action='store_true', help='Do not open browser automatically')
    args = parser.parse_args()

    db_file = get_db_path(args.project_dir)
    if not db_file.exists():
        print(f"Warning: No brain.db found at {db_file}")
        print(f"  Project dir: {args.project_dir}")
        print(f"  Project hash: {project_id(args.project_dir)}")
        print("  The standup will show empty data. Run some agent sessions first.")

    StandupHandler.db_file = db_file

    server = HTTPServer(('127.0.0.1', args.port), StandupHandler)
    url = f'http://127.0.0.1:{args.port}'
    print(f"Standup server running at {url}")
    print(f"Project: {args.project_dir}")
    print(f"Brain DB: {db_file}")
    print("Press Ctrl+C to stop.\n")

    if not args.no_open:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStandup server stopped.")
        server.server_close()


if __name__ == '__main__':
    main()
