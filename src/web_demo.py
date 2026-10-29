"""
web_demo.py — Job Application Screener web demo.

FastAPI + SSE: streams each agent step in real time.

Run:
    # Start the three A2A services first (or let run_demo start them)
    python -m src.agents.compliance_agent --port 9101
    python -m src.agents.specialist_agents --agent recruiter --port 9102
    python -m src.agents.specialist_agents --agent culture --port 9103

    # Then start the web demo
    python -m src.web_demo
    # Open http://127.0.0.1:8000
"""
from __future__ import annotations
import asyncio, json, os, sys, time
from pathlib import Path
from typing import AsyncIterator

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, StreamingResponse
from starlette.routing import Route

sys.path.insert(0, str(Path(__file__).parent.parent))

# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CS239 Job Application Screener</title>
<style>
:root {
  --bg:#F8F9FA; --surface:#FFFFFF; --border:#E9ECEF;
  --text:#111827; --dim:#6B7280;
  --navy:#3D5A80; --blue:#4895EF; --green:#52B788;
  --purple:#9B72CF; --amber:#E9A84C; --red:#E07A7A;
  --lblue:#EAF4FD; --lgreen:#EBF7F1; --lpurp:#F3EEFB;
  --lamber:#FEF6E4; --lred:#FDEAEA;
}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--text);font-family:'Inter',system-ui,sans-serif;
  display:flex;flex-direction:column;height:100vh;overflow:hidden;}

/* Header */
header{background:var(--navy);padding:12px 24px;display:flex;align-items:center;gap:16px;flex-shrink:0;}
header h1{font-size:15px;font-weight:600;color:#fff;}
header p{font-size:11px;color:#8BAFD4;}
.badge{padding:3px 9px;border-radius:4px;font-size:10px;font-weight:700;color:#fff;}
.b-blue{background:var(--blue);} .b-green{background:var(--green);}
.b-purple{background:var(--purple);} .b-amber{background:var(--amber);}

/* Layout */
main{display:flex;flex:1;overflow:hidden;}

/* Left panel */
.left{width:300px;border-right:1px solid var(--border);display:flex;
  flex-direction:column;overflow-y:auto;flex-shrink:0;background:var(--surface);}
.panel-title{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;
  color:var(--dim);padding:14px 16px 6px;}

/* Architecture */
.arch{padding:0 14px 12px;}
.arch-box{border:1px solid var(--border);border-radius:6px;padding:9px 11px;
  margin-bottom:6px;font-size:11px;background:var(--surface);}
.arch-box.coord{border-color:var(--blue);}
.arch-box.comp{border-color:var(--amber);}
.arch-box.rec{border-color:var(--purple);}
.arch-box.cult{border-color:var(--green);}
.arch-box.mcp{border-color:var(--green);background:var(--lgreen);}
.arch-label{font-weight:700;margin-bottom:2px;}
.arch-sub{color:var(--dim);font-size:10px;}
.arch-arrow{text-align:center;font-size:10px;color:var(--dim);margin:2px 0;}
.proto{font-size:9px;font-weight:700;padding:1px 5px;border-radius:3px;}
.proto-mcp{background:var(--lgreen);color:var(--green);}
.proto-a2a{background:var(--lblue);color:var(--blue);}

/* Scenarios */
.scenarios{padding:0 14px 12px;display:flex;flex-direction:column;gap:7px;}
.sc-btn{background:var(--bg);border:1px solid var(--border);border-radius:7px;
  padding:9px 11px;text-align:left;cursor:pointer;transition:all .15s;color:var(--text);font-size:12px;}
.sc-btn:hover{border-color:var(--blue);}
.sc-btn.active{border-color:var(--blue);background:var(--lblue);}
.sc-btn .s-title{font-weight:600;margin-bottom:2px;}
.sc-btn .s-sub{color:var(--dim);font-size:10px;}

/* Custom */
.custom{padding:0 14px 14px;}
.custom input,.custom textarea,.custom select{width:100%;background:var(--bg);
  border:1px solid var(--border);border-radius:5px;color:var(--text);
  font-size:11px;padding:6px 8px;font-family:inherit;margin-bottom:5px;}
.custom textarea{resize:vertical;min-height:100px;}
.run-btn{width:100%;padding:8px;background:var(--navy);color:#fff;border:none;
  border-radius:6px;font-weight:600;font-size:13px;cursor:pointer;}
.run-btn:disabled{opacity:.5;cursor:default;}

/* Right panel */
.right{flex:1;display:flex;flex-direction:column;overflow:hidden;}
.trace-area{flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:7px;}

/* Step cards */
.step-card{border-radius:7px;padding:9px 13px;border:1px solid transparent;
  font-size:12px;animation:fadeIn .2s ease;}
@keyframes fadeIn{from{opacity:0;transform:translateY(3px)}to{opacity:1;transform:translateY(0)}}
.step-card.user_request{border-color:var(--amber);background:var(--lamber);}
.step-card.mcp_connect{border-color:var(--green);background:var(--lgreen);}
.step-card.tool_call{border-color:var(--green);background:var(--lgreen);}
.step-card.tool_result{border-color:var(--border);background:var(--bg);}
.step-card.thought{border-color:var(--border);background:var(--surface);}
.step-card.a2a_send{border-color:var(--blue);background:var(--lblue);}
.step-card.a2a_receive{border-color:var(--purple);background:var(--lpurp);}
.step-card.final_response{border-color:var(--green);background:var(--lgreen);}
.step-card.final_response_fallback{border-color:var(--amber);background:var(--lamber);}
.step-card.error{border-color:var(--red);background:var(--lred);}

.step-header{display:flex;align-items:center;gap:7px;margin-bottom:5px;}
.step-num{font-size:9px;color:var(--dim);min-width:22px;}
.step-role{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;}
.step-time{font-size:9px;color:var(--dim);margin-left:auto;}
.step-body{font-size:11px;color:var(--text);line-height:1.6;}
.step-body pre{background:rgba(0,0,0,.04);border-radius:4px;padding:7px;
  overflow-x:auto;font-size:10px;margin-top:5px;white-space:pre-wrap;}

/* Role colors */
.role-applicant{color:var(--amber);}
.role-mcp{color:var(--green);}
.role-coordinator{color:var(--blue);}
.role-compliance{color:var(--amber);}
.role-recruiter{color:var(--purple);}
.role-culture{color:var(--green);}

/* Decision tags */
.tag{display:inline-block;padding:1px 7px;border-radius:3px;font-size:9px;font-weight:700;margin-right:4px;}
.tag-pass{background:var(--lgreen);color:var(--green);}
.tag-fail{background:var(--lred);color:var(--red);}
.tag-advance{background:var(--lgreen);color:var(--green);}
.tag-hold{background:var(--lamber);color:var(--amber);}
.tag-reject{background:var(--lred);color:var(--red);}

/* Final answer */
.answer-box{border-top:1px solid var(--border);padding:14px;flex-shrink:0;
  background:var(--surface);min-height:80px;}
.answer-box h3{font-size:10px;font-weight:700;text-transform:uppercase;
  letter-spacing:.08em;color:var(--dim);margin-bottom:6px;}
.answer-box p{font-size:12px;line-height:1.7;color:var(--text);}
.spinner{display:inline-block;width:11px;height:11px;border:2px solid var(--border);
  border-top-color:var(--blue);border-radius:50%;animation:spin .7s linear infinite;}
@keyframes spin{to{transform:rotate(360deg)}}
</style>
</head>
<body>
<header>
  <div>
    <h1>🧑‍💼 Job Application Screener — Multi-Agent System</h1>
    <p>CS239 · 4 agents · MCP / stdio · A2A / JSONRPC · PII isolation enforced in code</p>
  </div>
  <span class="badge b-green">MCP / stdio</span>
  <span class="badge b-blue">A2A / JSONRPC</span>
  <span class="badge b-purple">3 LLM Agents</span>
  <span class="badge b-amber">PII Isolation</span>
</header>

<main>
<div class="left">
  <div class="panel-title">Architecture</div>
  <div class="arch">
    <div class="arch-box" style="border-color:var(--dim);font-size:10px;color:var(--dim);">
      🧑 Applicant (you)</div>
    <div class="arch-arrow">↕ HTTP / SSE</div>
    <div class="arch-box coord">
      <div class="arch-label" style="color:var(--blue)">🤖 Coordinator Agent</div>
      <div class="arch-sub">LLM · Qwen3 via SiliconFlow</div>
    </div>
    <div class="arch-arrow">↕ <span class="proto proto-mcp">MCP/stdio</span></div>
    <div class="arch-box mcp">
      <div class="arch-label" style="color:var(--green)">🗄 job_db</div>
      <div class="arch-sub">MCP subprocess · 4 tools</div>
    </div>
    <div class="arch-arrow">↕ <span class="proto proto-a2a">A2A/JSONRPC</span></div>
    <div class="arch-box comp">
      <div class="arch-label" style="color:var(--amber)">⚖️ Compliance Agent</div>
      <div class="arch-sub">Deterministic · port 9101</div>
    </div>
    <div class="arch-arrow">↕ <span class="proto proto-a2a">A2A/JSONRPC</span></div>
    <div class="arch-box rec">
      <div class="arch-label" style="color:var(--purple)">🔍 Recruiter Agent</div>
      <div class="arch-sub">LLM · port 9102 · PII stripped</div>
    </div>
    <div class="arch-arrow">↕ <span class="proto proto-a2a">A2A/JSONRPC</span></div>
    <div class="arch-box cult">
      <div class="arch-label" style="color:var(--green)">🤝 Culture Fit Agent</div>
      <div class="arch-sub">LLM · port 9103 · PII stripped</div>
    </div>
  </div>

  <div class="panel-title">Scenarios</div>
  <div class="scenarios">
    <button class="sc-btn" onclick="runScenario(0)">
      <div class="s-title">✅ Strong Candidate</div>
      <div class="s-sub">Jordan Kim · SWE-001 · US citizen · all skills match</div>
    </button>
    <button class="sc-btn" onclick="runScenario(1)">
      <div class="s-title">🚫 Sponsorship Required</div>
      <div class="s-sub">Priya Sharma · SWE-001 · needs H-1B · compliance blocks</div>
    </button>
    <button class="sc-btn" onclick="runScenario(2)">
      <div class="s-title">⚠️ Career Changer</div>
      <div class="s-sub">Alex Rivera · DS-003 · partial skills · 1.5yr experience</div>
    </button>
  </div>

  <div class="panel-title">Custom Application</div>
  <div class="custom">
    <select id="job-id">
      <option value="SWE-001">SWE-001 — Software Engineer, Backend</option>
      <option value="PM-002">PM-002 — Product Manager</option>
      <option value="DS-003">DS-003 — Data Scientist</option>
    </select>
    <textarea id="app-text" placeholder="Paste application here..."></textarea>
    <button class="run-btn" id="run-btn" onclick="runCustom()">▶ Screen Application</button>
  </div>
</div>

<div class="right">
  <div class="trace-area" id="trace"></div>
  <div class="answer-box">
    <h3>Final Recommendation</h3>
    <p id="final-answer" style="color:var(--dim)">Run a scenario to see the hiring recommendation.</p>
  </div>
</div>
</main>

<script>
const SCENARIOS = [
  { job_id: "SWE-001", request: `Name: Jordan Kim\nEmail: jordan.kim@email.com\nSchool: UC Berkeley, BS Computer Science, graduated 2021\nGPA: 3.7\nYears of experience: 3\nSkills: Python, SQL, REST APIs, PostgreSQL, Kubernetes\nExpected salary: $135,000\nWork authorization: US citizen (no sponsorship needed)\nCover letter: I am excited to apply for this backend engineering role. I have 3 years of experience building scalable Python microservices at my current company, where I led the migration of our monolith to a Kubernetes-based architecture. I thrive in collaborative environments and enjoy mentoring junior engineers.\nSummary: Experienced backend engineer with strong Python and cloud infrastructure skills.` },
  { job_id: "SWE-001", request: `Name: Priya Sharma\nEmail: priya.sharma@email.com\nSchool: IIT Bombay, BTech Computer Science, graduated 2022\nGPA: 3.9\nYears of experience: 2.5\nSkills: Python, SQL, REST APIs, Go, PostgreSQL\nExpected salary: $128,000\nWork authorization: Indian citizen, requires H-1B sponsorship\nCover letter: I am applying for the backend engineer position. During my 2.5 years at my current employer I have shipped multiple high-availability services in Python and Go, handling millions of requests per day. I am detail-oriented and communicate clearly with both engineering and product teams.\nSummary: Strong technical background with experience in Python and distributed systems.` },
  { job_id: "DS-003", request: `Name: Alex Rivera\nEmail: alex.rivera@email.com\nSchool: UCLA, MS Statistics, graduated 2023\nGPA: 3.5\nYears of experience: 1.5\nSkills: Python, statistics, R, data visualization, SQL\nExpected salary: $118,000\nWork authorization: US citizen\nCover letter: I am transitioning from academic research into industry data science. My MS thesis applied Bayesian methods to epidemiological data, and I am eager to apply similar techniques to product recommendation problems. I learn quickly and adapt well to fast-paced environments. While I have not yet worked with PyTorch in a production setting, I have completed several personal projects using it.\nSummary: Quantitative researcher transitioning to industry, strong stats background.` },
];

const ICONS = {
  user_request:'🧑', mcp_connect:'🔌', tool_call:'🔧', tool_result:'📦',
  thought:'💭', a2a_send:'📤', a2a_receive:'📥',
  final_response:'✅', final_response_fallback:'⚠️', error:'❌',
};

const ROLES = {
  applicant:'Applicant', mcp_connect:'MCP Connect',
  coordinator:'Coordinator Agent', tool_result:'Tool Result',
  'coordinator→compliance':'→ Compliance Agent',
  'coordinator→recruiter':'→ Recruiter Agent',
  'coordinator→culture':'→ Culture Fit Agent',
  'compliance→coordinator':'← Compliance',
  'recruiter→coordinator':'← Recruiter',
  'culture→coordinator':'← Culture Fit',
};

const ROLE_CLASS = {
  applicant:'role-applicant', mcp_connect:'role-mcp',
  coordinator:'role-coordinator', tool_result:'role-mcp',
  'coordinator→compliance':'role-compliance',
  'coordinator→recruiter':'role-recruiter',
  'coordinator→culture':'role-culture',
  'compliance→coordinator':'role-compliance',
  'recruiter→coordinator':'role-recruiter',
  'culture→coordinator':'role-culture',
};

let running = false;

function setRunning(v) {
  running = v;
  document.getElementById('run-btn').disabled = v;
  document.querySelectorAll('.sc-btn').forEach(b => b.disabled = v);
}

function clearTrace() {
  document.getElementById('trace').innerHTML = '';
  document.getElementById('final-answer').textContent = 'Running…';
  document.getElementById('final-answer').style.color = 'var(--dim)';
}

function decisionTag(text) {
  if (!text) return '';
  const t = text.toLowerCase();
  if (t.includes('advance')) return '<span class="tag tag-advance">ADVANCE</span>';
  if (t.includes('reject')) return '<span class="tag tag-reject">REJECT</span>';
  if (t.includes('hold')) return '<span class="tag tag-hold">HOLD</span>';
  if (t.includes('pass') || t.includes('eligible: true')) return '<span class="tag tag-pass">PASS</span>';
  if (t.includes('fail') || t.includes('eligible: false')) return '<span class="tag tag-fail">FAIL</span>';
  return '';
}

let _detailId = 0;
function collapsible(summary, detail) {
  const id = 'det-' + (++_detailId);
  return `<div style="display:flex;align-items:center;gap:6px;cursor:pointer"
    onclick="document.getElementById('${id}').style.display=
      document.getElementById('${id}').style.display==='none'?'block':'none'">
    <span style="font-size:10px;color:var(--dim)">▶ ${summary}</span>
  </div>
  <div id="${id}" style="display:none;margin-top:6px">
    <pre>${detail}</pre>
  </div>`;
}

function renderBody(type, content) {
  if (typeof content === 'string') return `<div style="white-space:pre-wrap">${content}</div>`;

  if (type === 'mcp_connect') {
    return `<div>Connected to <strong>${content.server}</strong> · <strong>${content.transport}</strong></div>
      <div style="color:var(--dim);margin-top:3px;font-size:10px">Tools: ${(content.tools_discovered||[]).join(', ')} + delegate_to_specialists</div>`;
  }

  if (type === 'tool_call') {
    const args = JSON.stringify(content.input);
    return `<div><strong>${content.tool}</strong><span style="color:var(--dim)">(${args})</span>
      <em style="color:var(--dim);font-size:10px"> via ${content.via||'MCP'}</em></div>`;
  }

  if (type === 'tool_result') {
    const r = content.result || {};
    // Show key values inline, hide full JSON behind toggle
    const keys = Object.keys(r).filter(k => !Array.isArray(r[k]) && typeof r[k] !== 'object');
    const summary = keys.slice(0,4).map(k => `${k}: ${r[k]}`).join(' · ');
    return `<div style="color:var(--dim);font-size:10px">${content.tool}</div>
      <div style="margin:3px 0">${summary}</div>
      ${collapsible('show full result', JSON.stringify(r, null, 2))}`;
  }

  if (type === 'a2a_send') {
    const stripped = content.stripped || [];
    const p = content.payload || {};
    // Show only non-object fields inline
    const inline = Object.entries(p)
      .filter(([k,v]) => !Array.isArray(v) && typeof v !== 'object')
      .slice(0,5).map(([k,v]) => `${k}: ${v}`).join(' · ');
    return `<div>→ <strong>${(content.to||'').replace('http://127.0.0.1:','port ')}</strong></div>
      ${stripped.length ? `<div style="color:var(--red);margin-top:3px;font-size:10px">🔒 PII stripped: ${stripped.join(', ')}</div>` : ''}
      <div style="color:var(--dim);font-size:10px;margin-top:3px">${inline}</div>
      ${collapsible('show full payload', JSON.stringify(p, null, 2))}`;
  }

  if (type === 'a2a_receive') {
    const eligible = content.eligible;
    const flags = content.flags || [];
    const rules = (content.triggered_rules||[]).join(', ');
    const assessment = content.assessment || '';

    if (eligible !== undefined) {
      // Compliance: show result clearly, no big JSON
      return `<div style="display:flex;align-items:center;gap:8px">
        ${eligible
          ? '<span class="tag tag-pass">ELIGIBLE</span>'
          : '<span class="tag tag-fail">NOT ELIGIBLE</span>'}
        <span style="font-size:10px;color:var(--dim)">${rules}</span>
      </div>
      ${flags.map(f=>`<div style="color:var(--red);font-size:10px;margin-top:3px">${f}</div>`).join('')}`;
    }

    // LLM agent: show assessment lines clearly, hide payload
    const lines = assessment.trim().split('\n').filter(l=>l.trim());
    const keyLines = lines.filter(l => /^(SKILL_MATCH|EXPERIENCE|COMMUNICATION|MOTIVATION|COLLABORATION|SCORE|RECOMMENDATION|NOTES)/i.test(l));
    const rec = lines.find(l=>/^RECOMMENDATION/i.test(l)) || '';
    const recTag = rec.toLowerCase().includes('advance') ? 'tag-advance'
      : rec.toLowerCase().includes('reject') ? 'tag-reject' : 'tag-hold';
    return `<div><strong style="font-size:10px;color:var(--dim)">${content.agent||''}</strong></div>
      <div style="margin-top:5px;display:flex;flex-direction:column;gap:3px">
        ${keyLines.map(l => {
          const isRec = /^RECOMMENDATION/i.test(l);
          return `<div style="font-size:11px${isRec?';font-weight:700':''}">
            ${isRec ? `<span class="tag ${recTag}">${l.split(':')[1]?.trim()||''}</span>` : l}
          </div>`;
        }).join('')}
      </div>
      ${collapsible('show full assessment', assessment)}`;
  }

  return collapsible('show detail', JSON.stringify(content, null, 2));
}

function addStep(step) {
  const area = document.getElementById('trace');
  const card = document.createElement('div');
  card.className = `step-card ${step.type}`;
  const icon = ICONS[step.type] || '•';
  const roleLabel = ROLES[step.role] || step.role;
  const roleClass = ROLE_CLASS[step.role] || '';
  const t = step.t != null ? `${step.t.toFixed(1)}s` : '';
  card.innerHTML = `
    <div class="step-header">
      <span class="step-num">#${step.step}</span>
      <span style="font-size:13px">${icon}</span>
      <span class="step-role ${roleClass}">${roleLabel}</span>
      <span class="step-time">${t}</span>
    </div>
    <div class="step-body">${renderBody(step.type, step.content)}</div>`;
  area.appendChild(card);
  area.scrollTop = area.scrollHeight;
}

function addStatus(msg) {
  removeStatus();
  const area = document.getElementById('trace');
  const el = document.createElement('div');
  el.id = 'status-line';
  el.style.cssText = 'display:flex;align-items:center;gap:8px;color:var(--dim);font-size:11px;padding:4px 0';
  el.innerHTML = `<span class="spinner"></span> ${msg}`;
  area.appendChild(el);
  area.scrollTop = area.scrollHeight;
}

function removeStatus() {
  const el = document.getElementById('status-line');
  if (el) el.remove();
}

async function runRequest(job_id, request) {
  if (running) return;
  setRunning(true);
  clearTrace();

  const res = await fetch('/run', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ job_id, request }),
  });

  if (!res.ok || !res.body) {
    document.getElementById('final-answer').textContent = 'Server error — is the web demo running?';
    setRunning(false);
    return;
  }

  addStatus('Starting MCP subprocess…');
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const lines = buf.split('\n');
    buf = lines.pop();
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      const raw = line.slice(6).trim();
      if (!raw) continue;
      try {
        const msg = JSON.parse(raw);
        removeStatus();
        if (msg.type === 'step') {
          addStep(msg.step);
          const t = msg.step.type;
          if (t === 'mcp_connect') addStatus('Coordinator calling MCP tools…');
          else if (t === 'tool_call') addStatus(`MCP: ${msg.step.content.tool}…`);
          else if (t === 'a2a_send') {
            const role = msg.step.role || '';
            const who = role.includes('compliance') ? 'Compliance'
              : role.includes('recruiter') ? 'Recruiter'
              : role.includes('culture') ? 'Culture Fit' : 'Specialist';
            addStatus(`Waiting for ${who} Agent (LLM)…`);
          }
        } else if (msg.type === 'done') {
          const fa = document.getElementById('final-answer');
          fa.textContent = msg.final_response || '(no response)';
          fa.style.color = 'var(--text)';
        } else if (msg.type === 'error') {
          document.getElementById('final-answer').textContent = '⚠ ' + msg.message;
        }
      } catch {}
    }
  }
  removeStatus();
  setRunning(false);
}

function runScenario(i) {
  document.querySelectorAll('.sc-btn').forEach((b,j) => b.classList.toggle('active', i===j));
  const s = SCENARIOS[i];
  runRequest(s.job_id, s.request);
}

function runCustom() {
  const job_id = document.getElementById('job-id').value;
  const request = document.getElementById('app-text').value.trim();
  if (!request) return;
  document.querySelectorAll('.sc-btn').forEach(b => b.classList.remove('active'));
  runRequest(job_id, request);
}
</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# SSE streaming endpoint
# ---------------------------------------------------------------------------

async def sse_run(job_id: str, request: str) -> AsyncIterator[str]:
    def emit(obj: dict) -> str:
        return f"data: {json.dumps(obj)}\n\n"

    from src.agents.coordinator_agent import (
        mcp_session, discover_tools, call_mcp_tool,
        call_compliance, call_recruiter, call_culture,
        sanitize_for_compliance, sanitize_for_recruiter, sanitize_for_culture,
        RECRUITER_STRIP, CULTURE_STRIP, COMPLIANCE_STRIP,
        DELEGATE_TOOL, SILICONFLOW_MODEL, SILICONFLOW_BASE,
        COMPLIANCE_URL, RECRUITER_URL, CULTURE_URL,
        SYSTEM_PROMPT, _repair_json,
    )
    from openai import OpenAI

    api_key = os.environ.get("SILICONFLOW_API_KEY", "")
    if not api_key:
        yield emit({"type": "error", "message": "SILICONFLOW_API_KEY not set."})
        return

    llm = OpenAI(api_key=api_key, base_url=SILICONFLOW_BASE)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Job ID: {job_id}\n\nApplication:\n{request}"},
    ]

    step_n = [0]
    t0 = time.time()

    def make_step(type_, role, content):
        step_n[0] += 1
        return {"step": step_n[0], "type": type_, "role": role,
                "content": content, "t": round(time.time()-t0, 2)}

    def send(type_, role, content):
        return emit({"type": "step", "step": make_step(type_, role, content)})

    yield send("user_request", "applicant", request)

    try:
        async with mcp_session() as mcp:
            mcp_tools = await discover_tools(mcp)
            mcp_names = {t["function"]["name"] for t in mcp_tools}
            all_tools = mcp_tools + [DELEGATE_TOOL]

            yield send("mcp_connect", "mcp_connect", {
                "server": "src.tools.job_db", "transport": "MCP / stdio",
                "tools_discovered": sorted(mcp_names),
                "delegate_tool": "delegate_to_specialists (OpenAI tool_use)",
            })

            delegated = False
            last_call = None
            repeat_count = 0
            total_counts: dict = {}
            final_response = ""

            for _turn in range(20):
                response = await asyncio.to_thread(
                    llm.chat.completions.create,
                    model=SILICONFLOW_MODEL,
                    max_tokens=2048,
                    tools=all_tools,
                    messages=messages,
                )
                msg = response.choices[0].message
                text = msg.content or ""
                tool_calls = msg.tool_calls or []

                if text and not tool_calls:
                    yield send("thought", "coordinator", text)

                if tool_calls:
                    messages.append(msg.model_dump(exclude_none=True))
                    for tc in tool_calls:
                        name = tc.function.name
                        raw = tc.function.arguments or "{}"
                        try:
                            inp = json.loads(raw)
                        except json.JSONDecodeError:
                            try:
                                inp = json.loads(_repair_json(raw))
                            except:
                                inp = {}
                        if not isinstance(inp, dict):
                            inp = {}

                        ck = (name, json.dumps(inp, sort_keys=True))
                        total_counts[name] = total_counts.get(name, 0) + 1
                        repeat_count = repeat_count+1 if ck==last_call else 1
                        last_call = ck

                        if repeat_count > 2 or total_counts[name] > 3:
                            result = {"error": f"{name} called too many times."}

                        elif name == "delegate_to_specialists":
                            if delegated:
                                result = {"error": "Already delegated."}
                            else:
                                stripped_c = list(COMPLIANCE_STRIP & set(inp.keys()))
                                stripped_r = list(RECRUITER_STRIP & set(inp.keys()))
                                stripped_k = list(CULTURE_STRIP & set(inp.keys()))

                                yield send("a2a_send", "coordinator→compliance", {
                                    "to": COMPLIANCE_URL, "protocol": "A2A / JSONRPC",
                                    "payload": sanitize_for_compliance(inp),
                                    "stripped": stripped_c,
                                })
                                compliance_r = await call_compliance(inp)
                                yield send("a2a_receive", "compliance→coordinator", compliance_r)

                                yield send("a2a_send", "coordinator→recruiter", {
                                    "to": RECRUITER_URL, "protocol": "A2A / JSONRPC",
                                    "payload": sanitize_for_recruiter(inp),
                                    "stripped": stripped_r,
                                })
                                recruiter_r = await call_recruiter(inp)
                                yield send("a2a_receive", "recruiter→coordinator", recruiter_r)

                                yield send("a2a_send", "coordinator→culture", {
                                    "to": CULTURE_URL, "protocol": "A2A / JSONRPC",
                                    "payload": sanitize_for_culture(inp),
                                    "stripped": stripped_k,
                                })
                                culture_r = await call_culture(inp)
                                yield send("a2a_receive", "culture→coordinator", culture_r)

                                delegated = True
                                result = {
                                    "compliance": compliance_r,
                                    "recruiter": recruiter_r,
                                    "culture_fit": culture_r,
                                }

                        elif name in mcp_names:
                            yield send("tool_call", "coordinator",
                                {"tool": name, "input": inp, "via": "MCP / stdio"})
                            result = await call_mcp_tool(mcp, name, inp)
                            yield send("tool_result", "tool_result",
                                {"tool": name, "result": result})
                        else:
                            result = {"error": f"Unknown tool: {name}"}

                        messages.append({"role": "tool", "tool_call_id": tc.id,
                                         "content": json.dumps(result)})
                    continue

                if response.choices[0].finish_reason in ("stop", "end"):
                    if not delegated and text:
                        messages.append({"role": "assistant", "content": text})
                        messages.append({"role": "user", "content":
                            "You have not yet called delegate_to_specialists. Please call it now."})
                        continue
                    if text:
                        messages.append({"role": "assistant", "content": text})
                        final_response = text
                        yield send("final_response", "coordinator", text)
                    break

            if not final_response:
                final_response = "[Max turns — see specialist assessments above.]"
                yield send("final_response_fallback", "coordinator", final_response)

            yield emit({"type": "done", "final_response": final_response})

    except Exception as exc:
        yield emit({"type": "error", "message": str(exc)})


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

async def homepage(request: Request) -> HTMLResponse:
    return HTMLResponse(HTML)

async def run_endpoint(request: Request) -> StreamingResponse:
    body = await request.json()
    async def stream():
        async for chunk in sse_run(body.get("job_id","SWE-001"), body.get("request","")):
            yield chunk
    return StreamingResponse(stream(), media_type="text/event-stream",
        headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

app = Starlette(routes=[Route("/", homepage), Route("/run", run_endpoint, methods=["POST"])])

if __name__ == "__main__":
    port = int(os.environ.get("WEB_PORT", "8000"))
    print(f"\nCS239 Job Screener — Web Demo")
    print(f"Open: http://127.0.0.1:{port}")
    print(f"Requires: SILICONFLOW_API_KEY, A2A services on ports 9101/9102/9103")
    print(f"Start services first: python -m src.run_demo  (or 3 separate terminals)\n")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info",
                timeout_keep_alive=600)
