"use strict";

const COLORS = {
  User: "#5b7ca8", Group: "#9070bf", Computer: "#57a08a", Domain: "#b0563f", Base: "#4a5266",
  goal: "#ff4d6d", thread: "#f5b83d", arcane: "#37e0c9", broken: "#ff4d6d", faint: "#26324a",
};
const HOP_COLOR = { edge: COLORS.thread, inferred: COLORS.arcane, broken: COLORS.broken };
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const $ = (id) => document.getElementById(id);
const short = (n) => (n || "").split("@")[0];
let cy = null;

function setStatus(kind, text) {
  $("statusDot").className = "dot " + kind;
  $("statusText").textContent = text;
}

// -------------------------------------------------------------------------
// Boot
// -------------------------------------------------------------------------
async function boot() {
  try {
    const starts = await (await fetch("/api/starts")).json();
    const sel = $("startSelect");
    const group = (label, names) => {
      if (!names.length) return;
      const og = document.createElement("optgroup");
      og.label = label;
      for (const n of names) og.append(new Option(short(n), short(n)));
      sel.append(og);
    };
    group("Planted footholds (known answers)", starts.planted);
    group("Random users", starts.random);

    const checks = await (await fetch("/api/checks")).json();
    const list = $("checkList");
    for (const c of checks) {
      // Plain-text label only (no nested count span) — the nested inline element
      // tripped a Chrome rasterizer quirk under the full page; the finding count
      // is appended to the text after the check runs.
      const b = document.createElement("div");
      b.className = "check-btn empty";
      b.setAttribute("role", "button");
      b.tabIndex = 0;
      b.dataset.name = c.name;
      b.dataset.label = c.name.replace(/_/g, " ");
      b.title = c.description;
      b.textContent = b.dataset.label;
      const run = () => runCheck(c.name, b);
      b.onclick = run;
      b.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); run(); } };
      list.append(b);
    }
    setStatus("ok", "ready");
  } catch (e) {
    setStatus("err", "no backend — is it running?");
    $("railHint").textContent = "Could not reach the server. Start it with: python -m ariadne.web.app";
  }
}

// -------------------------------------------------------------------------
// Run the agent
// -------------------------------------------------------------------------
$("traceBtn").onclick = trace;

async function trace() {
  const start = $("startSelect").value;
  if (!start) return;
  $("traceBtn").disabled = true;
  setStatus("busy", `tracing from ${start}…`);
  $("empty").hidden = true;
  $("verdict").hidden = true;
  $("steps").innerHTML = "";
  $("telemetry").hidden = true;

  try {
    const res = await fetch("/api/run", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ start }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "run failed");
    render(data);
    setStatus("ok", "done");
  } catch (e) {
    setStatus("err", e.message);
    $("empty").hidden = false;
    $("empty").querySelector("p").textContent = "Run failed: " + e.message;
  } finally {
    $("traceBtn").disabled = false;
  }
}

// -------------------------------------------------------------------------
// Render graph + thread
// -------------------------------------------------------------------------
function render(data) {
  const pathIds = new Set();
  data.path.forEach((h) => { if (h.from) pathIds.add(h.from); if (h.to) pathIds.add(h.to); });

  const els = [];
  for (const n of data.nodes) {
    els.push({ data: { id: n.id, label: short(n.name), type: n.type, goal: n.goal,
                       onpath: pathIds.has(n.id), start: n.id === data.start_oid } });
  }
  const seen = new Set(data.nodes.map((n) => n.id));
  for (const e of data.edges) {
    if (seen.has(e.source) && seen.has(e.target))
      els.push({ data: { id: `r-${e.source}-${e.target}-${e.type}`, source: e.source, target: e.target, kind: "real" } });
  }
  // thread edges (may overlay a real edge, or stand alone for an inferred hop)
  data.path.forEach((h, i) => {
    if (h.from && h.to && seen.has(h.from) && seen.has(h.to))
      els.push({ data: { id: `t-${i}`, source: h.from, target: h.to, kind: h.kind, label: h.label, step: i },
                 classes: "thread-edge" });
  });

  if (cy) cy.destroy();
  cy = cytoscape({
    container: $("cy"),
    elements: els,
    minZoom: 0.2, maxZoom: 2.5,
    style: cyStyle(),
    layout: { name: "cose", animate: !reduceMotion, animationDuration: 500,
              nodeRepulsion: 9000, idealEdgeLength: 90, padding: 40 },
  });

  cy.edges(".thread-edge").style("opacity", 0);      // hide until drawn
  cy.one("layoutstop", () => setTimeout(() => drawThread(data, pathIds), reduceMotion ? 0 : 250));
  buildLog(data);
}

function cyStyle() {
  const hop = (e) => HOP_COLOR[e.data("kind")] || COLORS.thread;
  return [
    { selector: "node", style: {
        "background-color": (n) => COLORS[n.data("type")] || COLORS.Base,
        "label": "data(label)", "color": "#cfd4e0", "font-size": 8, "font-family": "JetBrains Mono",
        "text-valign": "bottom", "text-margin-y": 4, "width": 18, "height": 18,
        "border-width": 1.5, "border-color": "#0b0e14",
        "text-opacity": 0.55, "min-zoomed-font-size": 7 } },
    { selector: "node[?onpath]", style: { "text-opacity": 1, "width": 24, "height": 24, "font-size": 10 } },
    { selector: "node[?start]", style: { "border-color": "#ece8dd", "border-width": 2 } },
    { selector: "node[?goal]", style: {
        "background-color": COLORS.goal, "width": 30, "height": 30, "font-size": 11,
        "text-opacity": 1, "border-color": COLORS.goal, "border-width": 2, "border-opacity": 0.4 } },
    { selector: "node.dim", style: { "opacity": 0.28 } },
    { selector: "edge", style: { "curve-style": "bezier", "width": 1,
        "line-color": COLORS.faint, "target-arrow-color": COLORS.faint,
        "target-arrow-shape": "triangle", "arrow-scale": 0.6, "opacity": 0.55 } },
    { selector: "edge.dim", style: { "opacity": 0.12 } },
    { selector: "edge.thread-edge", style: {
        "width": 3.5, "line-color": hop, "target-arrow-color": hop,
        "arrow-scale": 0.9, "opacity": 1, "z-index": 20, "line-dash-pattern": [7, 6] } },
    { selector: 'edge.thread-edge[kind = "inferred"]', style: { "line-style": "dashed" } },
    { selector: 'edge.thread-edge[kind = "broken"]', style: { "line-style": "dotted", "line-dash-pattern": [3, 4] } },
  ];
}

function drawThread(data, pathIds) {
  // Dim everything not on the path, then light the thread hop by hop.
  cy.nodes().forEach((n) => { if (!pathIds.has(n.id())) n.addClass("dim"); });
  cy.edges().forEach((e) => { if (e.data("kind") === "real") e.addClass("dim"); });
  cy.animate({ fit: { eles: cy.nodes().filter((n) => pathIds.has(n.id())), padding: 70 } },
             { duration: reduceMotion ? 0 : 500 });

  const hops = cy.edges(".thread-edge").sort((a, b) => a.data("step") - b.data("step")).toArray();
  const step = (i) => {
    if (i >= hops.length) { finale(data); return; }
    const e = hops[i];
    const color = HOP_COLOR[e.data("kind")] || COLORS.thread;
    e.style("opacity", 1);
    if (!reduceMotion) {
      e.style("line-dash-offset", 26);
      e.animate({ style: { "line-dash-offset": 0 } }, { duration: 360 });
      const t = e.target();
      t.animate({ style: { "overlay-color": color, "overlay-opacity": 0.35, "overlay-padding": 8 } }, { duration: 160 })
       .animate({ style: { "overlay-opacity": 0 } }, { duration: 420 });
    }
    setTimeout(() => step(i + 1), reduceMotion ? 0 : 430);
  };
  step(0);
}

function finale(data) {
  const goal = cy.nodes("[?goal]");
  if (goal.nonempty() && !reduceMotion) {
    goal.animate({ style: { "overlay-color": COLORS.goal, "overlay-opacity": 0.5, "overlay-padding": 14 } }, { duration: 220 })
        .animate({ style: { "overlay-opacity": 0 } }, { duration: 600 });
  }
  showVerdict(data);
}

// -------------------------------------------------------------------------
// Step log + verdict
// -------------------------------------------------------------------------
function buildLog(data) {
  const ol = $("steps");
  $("stepCount").textContent = `${data.steps.length} steps`;
  data.steps.forEach((s, i) => {
    const li = document.createElement("li");
    const inferred = /inferred step available/.test(s.summary);
    li.className = "step " + (s.action === "finish" ? "finish" : inferred ? "infer act" : "act");
    li.style.animationDelay = (reduceMotion ? 0 : i * 80) + "ms";
    const arg = s.input ? `<div class="arg">${short(String(s.input))}</div>` : "";
    li.innerHTML =
      `<div class="head"><b>${s.action}</b></div>${arg}` +
      `<div class="sum${inferred ? " hot" : ""}">${s.summary}</div>`;
    ol.append(li);
  });

  const t = data.telemetry;
  const tel = $("telemetry");
  tel.innerHTML =
    `<div>tool calls<b>${t.tool_calls}</b></div><div>steps<b>${t.steps}</b></div>` +
    `<div>time<b>${t.seconds}s</b></div><div>cost<b>$${t.cost_usd}</b></div>`;
  tel.hidden = false;
}

function showVerdict(data) {
  const v = data.verdict || {};
  const el = $("verdict");
  let cls, sigil, title, sub;
  if (v.beats_bloodhound) {
    cls = "win"; sigil = "✧";
    title = "Beats BloodHound";
    sub = "Found a real path through an inferred step the canonical query can't see.";
  } else if (v.correct && v.path_valid) {
    cls = "ok"; sigil = "✓"; title = "Reached Domain Admins";
    sub = `A verified ${v.agent_hops}-hop path to Domain Admins.`;
  } else if (v.correct && v.declared_no_path) {
    cls = "none"; sigil = "∅"; title = "No path — correctly";
    sub = "The agent gave up, and there truly is no route from here.";
  } else if (v.hallucinated_edge) {
    cls = "bad"; sigil = "✗"; title = "Lost the thread";
    sub = "The proposed path includes a step that doesn't exist — a hallucination.";
  } else if (v.incomplete) {
    cls = "bad"; sigil = "⋯"; title = "Ran out of thread";
    sub = "The agent didn't finish within its step budget.";
  } else if (v.declared_no_path) {
    cls = "bad"; sigil = "✗"; title = "Gave up — a path existed";
    sub = "The agent declared no path, but one was reachable.";
  } else {
    cls = "bad"; sigil = "✗"; title = "No valid path"; sub = data.answer || "";
  }
  el.className = "verdict " + cls;
  el.innerHTML = `<div class="sigil">${sigil}</div><div><h3>${title}</h3><p>${sub}</p></div>`;
  el.hidden = false;
}

// -------------------------------------------------------------------------
// Vulnerability checks
// -------------------------------------------------------------------------
async function runCheck(name, btn) {
  const label = btn.dataset.label;
  btn.textContent = label + "  ·  …";
  try {
    const data = await (await fetch(`/api/check/${name}`)).json();
    const n = data.findings.length;
    btn.classList.toggle("empty", n === 0);
    btn.textContent = `${label}  ·  ${n} finding${n === 1 ? "" : "s"}`;
    if (cy) {
      cy.nodes().removeClass("dim");
      const hits = data.findings.map((f) => f.oid).filter(Boolean);
      if (hits.length) {
        cy.nodes().addClass("dim");
        hits.forEach((oid) => {
          const node = cy.getElementById(oid);
          if (node.nonempty()) {
            node.removeClass("dim");
            if (!reduceMotion)
              node.animate({ style: { "overlay-color": COLORS.arcane, "overlay-opacity": 0.4, "overlay-padding": 10 } }, { duration: 250 })
                  .animate({ style: { "overlay-opacity": 0 } }, { duration: 700 });
          }
        });
      }
    }
  } catch (e) {
    btn.textContent = label + "  ·  error";
  }
}

boot();
