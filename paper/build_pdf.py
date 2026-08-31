"""Render paper.md's content into a typeset academic-style PDF via xhtml2pdf.

Pure-Python (xhtml2pdf sits on reportlab), so it needs no LaTeX/pandoc/Pango
toolchain, only `pip install xhtml2pdf`. Content is transcribed by hand from
paper.md into styled HTML (xhtml2pdf's CSS support is a 2.1-era subset, not
enough for a markdown-to-HTML library's output to be trusted blind), figures
are embedded as base64 data URIs so there is no image-path resolution to get
wrong.

    .venv/Scripts/python.exe paper/build_pdf.py
"""
import base64
from pathlib import Path

from xhtml2pdf import pisa

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


def img_data_uri(path: Path) -> str:
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{data}"


FIG1 = img_data_uri(RESULTS / "model_comparison.png")
FIG2 = img_data_uri(RESULTS / "failure_modes.png")

CSS = """
@page {
    size: A4;
    margin: 2.4cm 2.2cm 2.6cm 2.2cm;
    @frame footer_frame {
        -pdf-frame-content: footer_content;
        bottom: 1.1cm; margin-left: 2.2cm; margin-right: 2.2cm; height: 1cm;
    }
}
body { font-family: "Times New Roman", Times, serif; font-size: 10.3pt; line-height: 1.32; color: #111; }
#footer_content { text-align: center; font-size: 9pt; color: #444; }
h1.title { font-size: 15.5pt; text-align: center; margin: 0 0 4pt 0; line-height: 1.25; }
p.subtitle { text-align: center; font-style: italic; font-size: 10pt; margin: 0 0 4pt 0; }
p.status { text-align: center; font-size: 8.7pt; color: #333; margin: 0 0 14pt 0; }
h2.abstract-h { font-size: 11pt; text-align: center; margin: 10pt 0 6pt 0; }
div.abstract p { text-align: justify; font-size: 9.6pt; margin: 0 0 8pt 0; }
h2.section { font-size: 12pt; margin: 15pt 0 6pt 0; border-bottom: 0.6pt solid #000; padding-bottom: 2pt; }
h3.subsection { font-size: 10.6pt; margin: 10pt 0 4pt 0; font-style: italic; }
p { text-align: justify; margin: 0 0 7pt 0; text-indent: 0; }
ul { margin: 4pt 0 8pt 0; padding-left: 16pt; }
li { text-align: justify; margin: 0 0 5pt 0; }
b.lead { font-weight: bold; }
code, span.code { font-family: "Courier New", monospace; font-size: 9.3pt; }
table.datatable td span.code, table.datatable th span.code { font-size: 7.6pt; }
table.datatable { border-collapse: collapse; width: 100%; margin: 4pt 0 10pt 0; font-size: 9.2pt; }
table.datatable td, table.datatable th { word-wrap: break-word; overflow-wrap: break-word; }
table.datatable th { border-top: 1pt solid #000; border-bottom: 0.6pt solid #000; padding: 3pt 9pt 3pt 5pt; text-align: left; background-color: #f0f0f0; }
table.datatable td { border-bottom: 0.3pt solid #ccc; padding: 3pt 9pt 3pt 5pt; }
table.datatable tr.lastrow td { border-bottom: 1pt solid #000; }
p.tablecap { font-size: 9.3pt; font-weight: bold; margin: 8pt 0 2pt 0; }
p.figcap { font-size: 9.3pt; font-weight: bold; text-align: center; margin: 4pt 0 12pt 0; }
div.figwrap { text-align: center; margin: 10pt 0 2pt 0; }
img.fig { width: 13cm; }
a { color: #000; text-decoration: underline; }
p.refs { font-size: 9.3pt; text-indent: -14pt; padding-left: 14pt; margin: 0 0 5pt 0; }
h2.refs-h { font-size: 11pt; margin: 15pt 0 6pt 0; }
"""


def T(rows_html: str, header_cells: list[str], widths_cm: list[float] | None = None) -> str:
    """Build a <table class=datatable> from a header list and pre-built <tr> rows.
    `widths_cm` (absolute cm, one per column) forces a <colgroup> with explicit
    widths: percentage <col> widths were not reliably honoured by xhtml2pdf's
    table layout (long wrapped cell content bled into the neighbouring column),
    but reportlab's underlying Table flowable respects absolute colWidths."""
    ths = "".join(f"<th>{h}</th>" for h in header_cells)
    colgroup = ""
    if widths_cm:
        colgroup = "<colgroup>" + "".join(f'<col style="width:{w}cm"/>' for w in widths_cm) + "</colgroup>"
    return f'<table class="datatable">{colgroup}<tr>{ths}</tr>{rows_html}</table>'


HTML = f"""<html><head><meta charset="utf-8"><style>{CSS}</style></head>
<body>
<div id="footer_content"><pdf:pagenumber /></div>

<h1 class="title">Autonomous LLM Agents for Active Directory Attack-Path Discovery: A Live-Collected BloodHound Benchmark</h1>
<p class="subtitle">Evaluated on a real, live-collected Active Directory forest, not synthetic data.</p>
<p class="status">Working draft. Results regenerate from <span class="code">experiments/run_real.py</span> against an ingested BloodHound/SharpHound export.</p>

<h2 class="abstract-h">Abstract</h2>
<div class="abstract">
<p>Active Directory (AD) attack paths, chains of individually-benign misconfigurations that
escalate a low-privilege account to Domain Admin, are today surfaced by BloodHound's
<i>rule-based</i> Cypher queries, which find exactly the shapes their queries encode. This
paper asks whether a modern LLM agent can perform the human analyst's role instead:
exploring the AD graph step by step, through a small set of query tools, and proposing a
valid attack path on its own, with a mandatory self-verification step before it may answer.
Unlike prior work on this codebase, which relied on a synthetic generator, every result here
is measured against a <b>real, live-collected AD forest</b>: a two-domain Windows
environment (GOAD-Light, deployed on disposable cloud VMs and destroyed after collection)
enumerated with SharpHound, BloodHound-CE, and Certipy exactly as an operator would collect
it in the field. Four models across three vendors (Google, OpenAI, Anthropic) are evaluated,
spanning a roughly 100&times; price range, with real metered API cost recorded per run. The
central finding is that cost and correctness are inversely related on this data: the free
model achieves the highest correctness of the four (66.7%); the two most expensive models
tested tie for the lowest (16.7% each, at up to 100&times;+ the cost of the mid-priced model
that beats them); correctness across all four models is substantially lower than prior
synthetic-graph results on the same architecture (16.7 to 66.7% versus 76 to 100%); and
hallucination holds at 0% across all 24 runs and all three vendors. Every rate is reported
with a 95% Wilson interval given how small the per-model samples are, and this paper
discusses explicitly where its design (a rule-based-query baseline with no equivalent
verification pass, a self-referential verifier, a fixed step budget on a graph an order of
magnitude denser than earlier synthetic graphs) should and should not be trusted.</p>
</div>

<h2 class="section">1. Introduction</h2>
<p>BloodHound maps an AD forest into a graph of principals (users, groups, computers) and
control edges (<span class="code">MemberOf</span>, <span class="code">AdminTo</span>,
<span class="code">GenericAll</span>, <span class="code">ForceChangePassword</span>, and
others), then runs pre-written queries such as &ldquo;shortest path to Domain
Admins.&rdquo; Because it is rule-based, it finds exactly the patterns its queries encode;
unusual-shaped chains still require a human to reason over the graph. This work measures
whether an LLM agent can do that reasoning on <b>genuine collected data</b>, not a synthetic
stand-in, and how it compares to the rule-based baseline and to itself across models of very
different price.</p>
<p>A benchmark on synthetic, generator-planted graphs can show an agent is <i>capable</i> of
attack-path reasoning under controlled conditions. It cannot show how that capability holds
up against the messier structure of a real, ACL-dense AD forest, where GenericAll,
WriteDacl, WriteOwner, and DCSync edges number in the hundreds and the shortest real path is
rarely the only plausible-looking one. This paper reports what happens when the same agent
architecture is pointed at data collected from an actual Windows Active Directory lab.</p>

<h2 class="section">2. Background</h2>
<h3 class="subsection">2.1 Active Directory Attack Paths</h3>
<p>An adversary who holds one low-privilege foothold typically escalates by discovering that
the compromised principal can, directly or through group membership, control some other
object, which in turn controls another, until a member of Domain Admins is reached. Each
individual permission may be legitimate; the composition is what is dangerous.</p>
<h3 class="subsection">2.2 BloodHound and Rule-Based Path Discovery</h3>
<p>BloodHound collects the AD graph with SharpHound (or the BloodHound-CE collector) and
stores it in Neo4j, then evaluates canned Cypher queries over control edges, canonically,
shortest path to Domain Admins. Its recall is bounded by the edge types collected and the
query patterns written; it is silent on anything outside that. This canonical shortest-path
query, over canonical edges only, is used as the rule-based baseline throughout this
paper.</p>
<h3 class="subsection">2.3 LLM Agents and the ReAct Loop</h3>
<p>An LLM agent interleaves natural-language reasoning with tool calls, observing each
result before deciding the next action: the reason, act, observe pattern known as ReAct.
Given only a foothold and a goal, the agent must query a node's neighbours, read its
properties, form a hypothesis about the next hop, and verify. This closely resembles manual
BloodHound analysis, which is why it is adopted as the architecture under test.</p>

<h2 class="section">3. Live Data Collection</h2>
<h3 class="subsection">3.1 The Lab</h3>
<p><b>GOAD-Light</b> (Orange Cyberdefense's open-source Active Directory range, commit
<span class="code">992307a</span>) was built as a two-domain forest,
<span class="code">sevenkingdoms.local</span> (parent, with ADCS) and
<span class="code">north.sevenkingdoms.local</span> (child, with a member server running
IIS and MSSQL), on five disposable Vultr cloud VMs (a domain controller per domain, one
member server, one workstation-capable box, and one Linux control node running Ansible).
The build ran GOAD's own Ansible playbooks staged against pre-existing cloud VMs rather than
Vagrant-provisioned ones, which surfaced several real integration issues undocumented for
this deployment path: DNS self-registration on a freshly promoted child DC, a stale local
Administrator credential surviving domain promotion, and API-gateway compatibility quirks
across three different LLM providers (Section 5). None of these are benchmark artefacts;
they are the ordinary friction of running this tooling against real infrastructure, and they
are mentioned here because a paper claiming &ldquo;real data&rdquo; should be honest about
how it was obtained.</p>
<p>The entire lab was destroyed (after a disk snapshot) at the end of collection. No part of
it persists as running infrastructure, and no live or third-party network was touched at any
point.</p>
<h3 class="subsection">3.2 Collection</h3>
<p>SharpHound, BloodHound-CE, and Certipy were run from a compromised-account vantage point,
producing the standard collector JSON (users, groups, computers, domains, GPOs, containers,
OUs, plus ADCS templates). The two domains' collections were merged into one graph and
ingested through the same schema-normalising pipeline this codebase already used for
synthetic data, so the agent, tools, and scorer are unchanged between synthetic and real
runs; only the data source differs. The resulting graph has <b>147 nodes</b> (3 computers, 2
domains, 110 groups, 33 users) and <b>1,259 canonical edges</b>, dominated by ACL-style
control edges (<span class="code">GenericAll</span> 325,
<span class="code">WriteDacl</span>/<span class="code">WriteOwner</span> 206 each,
<span class="code">GenericWrite</span> 202, <span class="code">AllExtendedRights</span> 57,
<span class="code">DCSync</span> 4): roughly 6&times; denser per node than the synthetic
graphs used in earlier development of this codebase, and structured very differently, almost
entirely canonical ACL abuse rather than the inference-only tradecraft (Kerberoasting,
unconstrained delegation, ADCS ESC1, credential exposure) that a synthetic generator can
plant deliberately and evenly.</p>

<h2 class="section">4. Agent, Verifier, and Scoring</h2>
<p>The agent is a minimal ReAct loop over six tools, <span class="code">search_node</span>,
<span class="code">query_outbound_edges</span>, <span class="code">query_inbound_edges</span>,
<span class="code">get_node_properties</span>, <span class="code">check_path_exists</span>,
and <span class="code">verify_path</span>, which it must call to self-check its proposed
path before finishing; a rejected hop sends it back to repair the path rather than ship an
invalid one. It is never shown the whole graph.</p>
<p>Verification means one thing everywhere in this codebase. Each consecutive pair of nodes
on a proposed path must be a real edge in the collected graph (or, where applicable, a
property-justified inference step), and the final node must be a Domain Admins group. A hop
that is neither counts as a <b>hallucination</b>. This verifier is explicitly
<b>internal to the system under test</b>: it checks a proposed path against the same graph
the agent queried, using the same code path for both the agent's own self-check and the
scorer's final judgement. This is a meaningful check for internal consistency, catching a
model asserting an edge that is not in the collected data, but it is not an independent,
external validation of the verifier's own logic, and it cannot detect an error common to
both (Section 8).</p>

<h2 class="section">5. Experimental Setup</h2>
<p><b class="lead">Models.</b> Four models across three vendors were chosen to span a
roughly 100&times; price range on identical hardware access to the same graph, listed in
Table 1.</p>
<p class="tablecap">Table 1. Models evaluated, by vendor, access route, and list price.</p>
{T('''
<tr><td><i>gemini-flash-lite-latest</i></td><td>Google</td><td>native, free tier</td><td>$0 (rate-limited)</td></tr>
<tr><td><i>gpt-4o-mini</i></td><td>OpenAI</td><td>direct billing</td><td>$0.15 / $0.60</td></tr>
<tr><td><i>claude-haiku-4-5</i></td><td>Anthropic</td><td>direct billing</td><td>$1.00 / $5.00</td></tr>
<tr class="lastrow"><td><i>gpt-4o</i></td><td>OpenAI</td><td>direct billing</td><td>$2.50 / $10.00</td></tr>
''', ["Model", "Vendor", "Route", "List price (per M tok, in/out)"],
   widths_cm=[6.0, 2.6, 3.2, 4.8])}
<p><b class="lead">Start users (6, deliberately chosen, not randomly sampled).</b> Four real
path cases, <span class="code">lord.varys</span> (a one-hop
<span class="code">GenericAll</span> to Domain Admins privilege-escalation),
<span class="code">catelyn.stark</span> and <span class="code">robb.stark</span> (multi-hop
routes into the child domain's Domain Admins), and two no-path controls,
<span class="code">jaime.lannister</span> (whose ACL chain reaches a domain-controller
computer object, not the Domain Admins group) and <span class="code">hodor</span> (a
low-privilege account with no path at all), were used to test whether a model asserts a path
where none exists. This deliberate selection, rather than random sampling, is itself a
limitation discussed in Section 8.</p>
<p><b class="lead">Step budget.</b> 35 reasoning steps, raised from an initial 15 after the
denser real graph caused premature &ldquo;ran out of steps&rdquo; failures at the lower
budget on cases every model could solve at 30+ steps. This adjustment is reported rather
than silently tuned away.</p>
<p><b class="lead">Cost.</b> OpenAI and Anthropic costs are real metered API billing
(verified against each provider's own token-price table where the gateway does not echo
cost directly); Gemini's free tier is $0 with a request-rate ceiling. Total spend across all
reported runs was <b>$3.96</b>.</p>

<h2 class="section">6. Results</h2>
<p class="tablecap">Table 2. Overall results, 24 scored runs of 25 attempted (one attempt was
dropped to a transient rate-limit).</p>
{T('''
<tr><td>Runs scored</td><td>24 (of 25 attempted)</td></tr>
<tr><td>Correctness</td><td>37.5% [21.2 to 57.3]</td></tr>
<tr><td>Valid-path rate</td><td>8.3% [2.3 to 25.8]</td></tr>
<tr><td>Hallucination rate</td><td><b>0.0% [0.0 to 13.8]</b></td></tr>
<tr><td>Optimal of paths found</td><td>100.0% (2 of 2 found)</td></tr>
<tr><td>Beats rule-based baseline</td><td>0 of 8 advanced-required</td></tr>
<tr><td>Avg tool calls (solved)</td><td>14.9</td></tr>
<tr><td>Avg runtime (s)</td><td>117.9</td></tr>
<tr class="lastrow"><td>Cost (USD)</td><td>$0.165/run avg, $3.96 total</td></tr>
''', ["Metric", "Value"])}

<p class="tablecap">Table 3. Results by model.</p>
{T('''
<tr><td style="font-size:7pt"><i>gemini-flash-lite-latest</i></td><td>6</td><td><b>66.7% [30.0 to 90.3]</b></td><td>0.0%</td><td>25.2</td><td>124.8</td><td>$0.000</td></tr>
<tr><td style="font-size:7pt"><i>gpt-4o-mini</i></td><td>6</td><td>50.0% [18.8 to 81.2]</td><td>0.0%</td><td>6.5</td><td>14.3</td><td>$0.003</td></tr>
<tr><td style="font-size:7pt"><i>claude-haiku-4-5</i></td><td>6</td><td><b>16.7% [3.0 to 56.4]</b></td><td>0.0%</td><td>19.7</td><td>88.1</td><td>$0.305</td></tr>
<tr class="lastrow"><td style="font-size:7pt"><i>gpt-4o</i></td><td>6</td><td><b>16.7% [3.0 to 56.4]</b></td><td>0.0%</td><td>16.7</td><td>244.4</td><td>$0.352</td></tr>
''', ["Model", "Runs", "Correctness (95% CI)", "Halluc.", "Avg tools", "Avg time (s)", "Avg cost"])}

<p class="tablecap">Table 4. Failure-mode breakdown, 24 runs against one graph.</p>
{T('''
<tr class="lastrow"><td>9</td><td>0</td><td>7</td><td>6</td><td>2</td></tr>
''', ["Correct", "Hallucinated", "Gave up (path existed)", "Ran out of steps", "Wrong path"])}

<div class="figwrap"><img class="fig" src="{FIG1}"/></div>
<p class="figcap">Figure 1. Correctness and hallucination rate by model.</p>

<div class="figwrap"><img class="fig" src="{FIG2}"/></div>
<p class="figcap">Figure 2. Outcome breakdown across all runs.</p>

<h3 class="subsection">6.1 Reading it</h3>
<p><b>Cost and correctness are inversely related on this data.</b> The free model
(<span class="code">gemini-flash-lite-latest</span>) scored highest of the four (66.7%,
Table 3); the two most expensive models tested,
<span class="code">gpt-4o</span> ($2.50/$10.00 per M) and
<span class="code">claude-haiku-4-5</span> ($1.00/$5.00 per M), tied for lowest (16.7%
each), both scoring well below the far cheaper <span class="code">gpt-4o-mini</span>
($0.15/$0.60 per M, 50.0%). <span class="code">gpt-4o</span>, specifically, took
<b>17&times; longer per run on average</b> (244.4s versus 14.3s for
<span class="code">gpt-4o-mini</span>) while scoring worse, repeatedly re-querying the same
region of the graph before giving up. This is read as a genuine signal on this data and this
task, not a general claim about these vendors' models across all tasks: the sample per model
is 6 runs, and the correctness intervals for the three non-Gemini models overlap
substantially (Section 8).</p>
<p><b>Hallucination held at 0% across every model and every run.</b> All 24 runs, across 3
vendors and a 100&times; price spread, produced zero hallucinated hops (Table 2); no model
in this sample asserted a path the collected graph does not support. This is the result
reported with the most confidence: even where a model failed to find a real path (the
dominant outcome at every price point, Table 4), it failed by giving up or running out of
budget, not by inventing one.</p>
<p><b>Correctness is substantially lower than prior synthetic-graph work on this same
agent/verifier architecture.</b> Earlier synthetic benchmarks reported 76 to 100%
correctness on generator-planted graphs of comparable node count. Here, on a real,
ACL-dense collected forest, correctness ranges 16.7 to 66.7% across models: roughly half or
less. The overall hallucination rate (0.0% [0.0 to 13.8]) and the prior synthetic rate (0%
[0.0 to 9.0], from an earlier, differently-scoped sweep) are consistent with each other;
correctness is where the real-versus-synthetic gap actually shows up.</p>
<p><b>The rule-based baseline was never beaten.</b> 0 of 8 cases the true-reachability
search flagged as requiring an inferred (non-canonical) step were solved by any model,
versus 10 of 12 on prior synthetic graphs. The real GOAD-Light collection is overwhelmingly
canonical-ACL-shaped rather than inference-shaped (Section 3.2); this is consistent with,
and does not contradict, the synthetic finding: it says the opportunity to demonstrate this
specific capability was much rarer on this real forest, not that the capability regressed.
There were too few inference-eligible real cases in this collection to measure it properly
here, which is listed as a concrete direction for future collection (Section 10).</p>
<p><b>The dominant failure mode shifted from &ldquo;gave up on a benign miss&rdquo; to
&ldquo;ran out of steps.&rdquo;</b> 6 of 24 runs exhausted the 35-step budget without
concluding, a failure mode that was near-zero on the smaller, sparser synthetic graphs this
architecture was originally tuned against. This is the clearest evidence in this data that
step budget is not a free-standing tuning knob but scales with graph density in a way not
yet characterised (Section 8).</p>

<h2 class="section">7. Discussion</h2>
<p>A minimal LLM agent, given only query tools and no view of the graph, found real,
graph-confirmed attack paths on a genuine collected AD forest, without a single hallucinated
hop across 24 runs, 4 models, and 3 vendors, at price points from $0 to over a third of a
dollar per run. That is the finding reported with the most confidence. Everything else in
this dataset, which model is &ldquo;best,&rdquo; whether cost buys correctness, how the step
budget should scale, is a <i>directional</i> signal from a small sample on one real
topology, discussed below along with why it should be read that way rather than as a settled
result.</p>

<h2 class="section">8. Threats to Validity and Limitations</h2>
<p>These are listed as specific, not generic, caveats; each ties to a concrete number
above.</p>
<ul>
<li><b>The verifier is not independently validated.</b> <span class="code">verify_path</span>
and the scorer share one implementation, checking a proposed path against the same collected
graph the agent queried. This catches a model asserting an edge absent from the data, but it
cannot catch an error the ingest pipeline and the verifier share (for example, a control edge
the BloodHound parser mis-typed), nor does &ldquo;graph-confirmed&rdquo; mean
&ldquo;confirmed against the live domain&rdquo;: no proposed path was re-tested against the
actual GOAD-Light forest before it was destroyed. Every &ldquo;correct&rdquo; and
&ldquo;hallucination&rdquo; figure in this paper should be read as <i>internally consistent
with the collected data</i>, not as independently ground-truthed.</li>
<li><b>The rule-based baseline has no equivalent verification stage.</b> The agent must pass
its own proposed path through a self-check before answering; the canonical shortest-path
query it is compared against has no analogous second pass. This is not a fabricated
advantage, a rule-based query has no natural &ldquo;self-check&rdquo; step to add, but it
does mean the comparison is not between two methods at matched levels of engineering.</li>
<li><b>Correctness intervals overlap substantially across models.</b>
<span class="code">gpt-4o-mini</span> (50.0% [18.8 to 81.2]),
<span class="code">claude-haiku-4-5</span> (16.7% [3.0 to 56.4]), and
<span class="code">gpt-4o</span> (16.7% [3.0 to 56.4]) all overlap at the 95% level; only
<span class="code">gemini-flash-lite-latest</span>'s interval is clearly separated from the
two lowest. The point estimates are reported because they are the actual observed rates, but
a reader should not treat every ranking in Section 6.1 as statistically distinguishable: 6
runs per model is enough to see a pattern, not enough to certify one.</li>
<li><b>Step-budget scaling is an open question, not a solved lever.</b> 6 of 24 real-data
runs hit the 35-step cap, versus near-zero on earlier, sparser synthetic graphs. Whether the
budget a given graph needs scales linearly, sub-linearly, or worse with edge density is not
known; the raised budget (15 to 35) is reported as a fix for a specific observed failure, not
as evidence the relationship is understood.</li>
<li><b>Temperature 0.</b> All runs are deterministic-mode where the API supports it. This
favours reproducibility over measuring run-to-run robustness; a variance sweep at non-zero
temperature is future work, not something this dataset speaks to.</li>
<li><b>&ldquo;Correctness&rdquo; is graph-reachability correctness, not operational
feasibility.</b> A path scored correct here is one the collected graph and its properties
support; whether the access it assumes is actually still held at execution time, detection
risk, and credential/ticket validity windows are not modelled. This is a narrower claim than
&ldquo;this path is exploitable in practice.&rdquo;</li>
<li><b>Deliberately chosen, not randomly sampled, start users.</b> The 6 starts (Section 5)
were picked to cover known path/no-path cases rather than sampled at random, which controls
for a specific failure mode (hallucinating a path where none exists) at the cost of not
being a representative draw over the graph's 33 real users.</li>
<li><b>One real topology, one collection pass per model.</b> All 24 runs are against a
single GOAD-Light forest collected once; how much of the real-versus-synthetic gap in
Section 6.1 is intrinsic to real AD structure, versus specific to this one topology, is not
yet known.</li>
<li><b>Wide intervals throughout.</b> Every rate in Section 6 carries a 95% Wilson interval
because the samples are small (6 runs per model); point estimates are reported with
intervals precisely so a reader does not mistake, for example, 66.7% [30.0 to 90.3] for a
precisely known rate.</li>
</ul>

<h2 class="section">9. Ethics</h2>
<p>All experiments run against a lab that was built, owned, and destroyed for this purpose:
five disposable cloud VMs running GOAD-Light, collected with SharpHound, BloodHound-CE, and
Certipy, then torn down (after a disk snapshot) at the end of data collection. No live,
third-party, or production network was touched at any point, and the collected data,
credentials, hostnames, and topology, belongs entirely to a lab built for this purpose, not
to any real organisation. The chat assistant and vulnerability checks built on the same
verifier are read-only over the graph and refuse to assert anything the graph does not
confirm. Any future live-collection work would run only against systems one owns or is
explicitly authorised to test.</p>

<h2 class="section">10. Conclusion and Future Work</h2>
<p>An LLM attack-path agent was evaluated against a real, live-collected Active Directory
forest, not synthetic data, across four models spanning three vendors and a roughly
100&times; price range. The agent found real, graph-confirmed paths with zero hallucinated
hops across all 24 runs. Beyond that, the central finding is that the two most expensive
models tested did not outperform a free one on this data (both tied for the lowest
correctness observed), and that correctness dropped substantially relative to prior
synthetic-graph results, which is attributed in part to the real forest's markedly denser,
more ACL-heavy structure. Future work includes: a second real topology, to separate
&ldquo;real AD is different&rdquo; from &ldquo;this one topology is different&rdquo;; enough
inference-eligible real cases (Kerberoastable accounts, ADCS misconfigurations,
unconstrained delegation) to properly re-measure advanced-case recall on real data, which
this collection had too few of; a temperature greater than 0 variance sweep; and a
principled study of how step budget should scale with graph density rather than the single
manual adjustment reported here.</p>

<h2 class="section">Data and Code Availability</h2>
<p>The agent, shared verifier, evaluation harness, real-data collection manifest, and raw
per-run logs (each archived with its git commit, model set, and timestamp) are released as
open source at <a href="https://github.com/Crepco/Ariadne">github.com/Crepco/Ariadne</a>
under the MIT license. All tables and figures in this paper regenerate from the benchmark
runner against the ingested real-data graph.</p>

</body></html>
"""

out_path = ROOT / "paper" / "Ariadne_paper.pdf"
with open(out_path, "wb") as f:
    result = pisa.CreatePDF(HTML, dest=f)

print("errors:", result.err)
print("wrote:", out_path, out_path.stat().st_size, "bytes")
