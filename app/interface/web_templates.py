"""The HTML pages of the web app, as Jinja templates. WebApp loads them by name."""

BASE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{% block title %}Source of Wealth Screening{% endblock %}</title>
<style>
  :root { --ink:#1f2933; --muted:#616e7c; --line:#d9dee3; --bg:#f0f2f5; --accent:#1d4f7a; --bad:#a61b1b; }
  * { box-sizing: border-box; }
  body { margin:0; font-family: system-ui, -apple-system, "Segoe UI", sans-serif; color:var(--ink); background:var(--bg); line-height:1.5; }
  header { background:var(--accent); padding:0 28px; display:flex; align-items:center; justify-content:space-between; height:54px; }
  .brand { color:#fff; font-weight:700; font-size:1rem; text-decoration:none; letter-spacing:.02em; }
  nav { display:flex; gap:8px; align-items:center; }
  .nav-link { color:rgba(255,255,255,.85); font-size:.875rem; text-decoration:none; padding:5px 11px; border-radius:4px; border:1px solid rgba(255,255,255,.3); transition:background .15s; }
  .nav-link:hover { background:rgba(255,255,255,.12); }
  .nav-cta { background:#fff; color:var(--accent); font-size:.875rem; font-weight:600; text-decoration:none; padding:5px 13px; border-radius:4px; border:none; cursor:pointer; font:inherit; }
  .nav-cta:hover { background:#e8edf2; }
  main { max-width:960px; margin:0 auto; padding:28px 24px; }
  h1 { font-size:1.45rem; margin:0 0 18px; }
  h2 { font-size:1.05rem; margin:0 0 12px; color:var(--ink); }
  a { color:var(--accent); }
  .panel { background:#fff; border:1px solid var(--line); border-radius:8px; padding:18px 22px; margin-bottom:16px; box-shadow:0 1px 3px rgba(0,0,0,.04); }
  .msg { background:#e8f1f8; border:1px solid #b9d3e6; border-radius:6px; padding:10px 14px; margin-bottom:14px; }
  .errors { background:#fdeaea; border:1px solid #e3b0b0; color:var(--bad); border-radius:6px; padding:10px 14px 10px 30px; margin-bottom:14px; }
  .actions { display:flex; gap:10px; flex-wrap:wrap; align-items:center; }
  button, .button { font:inherit; background:var(--accent); color:#fff; border:0; border-radius:5px; padding:7px 16px; cursor:pointer; text-decoration:none; display:inline-block; font-size:.9rem; }
  button.secondary, .button.secondary { background:#fff; color:var(--accent); border:1px solid var(--accent); }
  button.danger { background:#fff; color:var(--bad); border:1px solid var(--bad); padding:4px 10px; }
  button:focus-visible, input:focus-visible, select:focus-visible, textarea:focus-visible, a:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
  label { display:block; font-size:.88rem; color:var(--muted); margin-bottom:10px; }
  input, select, textarea { display:block; width:100%; font:inherit; color:var(--ink); padding:7px 10px; margin-top:3px; border:1px solid #c4cdd6; border-radius:5px; background:#fff; }
  fieldset { border:1px solid var(--line); border-radius:8px; background:#fff; padding:16px 20px; margin:0 0 16px; }
  legend { font-weight:600; padding:0 6px; }
  .grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(240px, 1fr)); gap:0 16px; }
  .wide { grid-column:1 / -1; }
  .entry { border:1px solid var(--line); border-radius:6px; padding:12px 14px; margin-bottom:12px; background:#fafbfc; }
  table { width:100%; border-collapse:collapse; }
  th, td { text-align:left; padding:9px 12px; border-bottom:1px solid var(--line); vertical-align:middle; font-size:.9rem; }
  th { color:var(--muted); font-weight:500; font-size:.8rem; text-transform:uppercase; letter-spacing:.04em; width:auto; }
  .muted { color:var(--muted); }
  .savebar { position:sticky; bottom:0; background:var(--bg); padding:12px 0; border-top:1px solid var(--line); }
  .autofill { border-color:#b9d3e6; background:#f5f9fc; }
  .autofilled { background:#fff8db !important; border-color:#e0c25a !important; }
  .notes { background:#fff8db; border:1px solid #e9d68f; border-radius:6px; padding:10px 14px; margin-top:12px; font-size:.88rem; }
  .notes ul { margin:6px 0 0; padding-left:18px; }
  .badge { display:inline-block; font-size:.75rem; font-weight:700; padding:2px 8px; border-radius:12px; letter-spacing:.03em; }
  .badge-pass { background:#d1fae5; color:#065f46; }
  .badge-warn { background:#fef3c7; color:#92400e; }
  .badge-risk { background:#ffedd5; color:#9a3412; }
  .badge-bad  { background:#fee2e2; color:#991b1b; }
</style>
</head>
<body>
<header>
  <a class="brand" href="{{ url_for('home') }}">Source of Wealth Screening</a>
  <nav>
    <a class="nav-link" href="{{ url_for('list_assessments_view') }}">Assessments</a>
    <form method="post" action="{{ url_for('sync_to_cloud') }}" style="margin:0">
      <button class="nav-link" type="submit" style="cursor:pointer">Sync to Cloud</button>
    </form>
    <a class="nav-cta" href="{{ url_for('new_client') }}">+ New client</a>
  </nav>
</header>
<main>
  {% for message in get_flashed_messages() %}<div class="msg">{{ message }}</div>{% endfor %}
  {% block content %}{% endblock %}
</main>
</body>
</html>
"""
 
HOME = """{% extends "base.html" %}
{% block content %}
<div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:18px; gap:16px">
  <h1 style="margin:0">Clients</h1>
  <form action="{{ url_for('find') }}" method="get" style="display:flex; gap:8px; align-items:center">
    <input name="ref" placeholder="Search by client reference..." aria-label="Client reference"
           style="width:280px; margin:0; padding:7px 10px">
    <button class="secondary" type="submit" style="white-space:nowrap">Find</button>
  </form>
</div>

<div class="panel" style="padding:0; overflow:hidden">
  {% if clients is none %}
    <p class="muted" style="padding:20px 22px; margin:0">The list of clients cannot be shown because the client database could not be read.</p>
  {% elif not clients %}
    <p class="muted" style="padding:20px 22px; margin:0">No clients yet — click <strong>+ New client</strong> in the top right to add the first one.</p>
  {% else %}
  <table>
    <thead>
      <tr style="background:#fafbfc">
        <th>Reference</th>
        <th>Name</th>
        <th>Occupation</th>
        <th>Industry</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
    {% for c in clients %}
    <tr style="transition:background .1s" onmouseover="this.style.background='#f5f7fa'" onmouseout="this.style.background=''">
      <td><code style="font-size:.82rem; color:var(--muted)">{{ c.get('client_ref', '') }}</code></td>
      <td><strong>{{ c.get('name', '') }}</strong></td>
      <td>{{ (c.get('career') or {}).get('occupation', '') }}</td>
      <td>{{ (c.get('career') or {}).get('industry', '') }}</td>
      <td style="text-align:right; padding-right:14px">
        <a class="button" href="{{ url_for('view_client', client_ref=c.get('client_ref', '')) }}"
           style="padding:4px 12px; font-size:.82rem">Open →</a>
      </td>
    </tr>
    {% endfor %}
    </tbody>
  </table>
  <div style="padding:10px 22px; color:var(--muted); font-size:.82rem; border-top:1px solid var(--line)">
    {{ clients|length }} client{{ 's' if clients|length != 1 else '' }}
  </div>
  {% endif %}
</div>
{% endblock %}
"""
 
FORM = """{% extends "base.html" %}
{% macro box(prefix, field, value) %}
  <label {% if field[2] == 'textarea' %}class="wide"{% endif %}>{{ field[1] }}
    {% if field[2] == 'textarea' %}
      <textarea name="{{ prefix }}.{{ field[0] }}" rows="6">{{ value }}</textarea>
    {% elif field[2] == 'pep' %}
      <select name="{{ prefix }}.{{ field[0] }}">
        <option value="">Choose</option>
        {% for option in PEP_OPTIONS %}<option {{ 'selected' if value == option else '' }}>{{ option }}</option>{% endfor %}
        {% if value and value not in PEP_OPTIONS %}<option selected>{{ value }}</option>{% endif %}
      </select>
    {% elif field[2] == 'payment' %}
      <select name="{{ prefix }}.{{ field[0] }}">
        <option value="">Choose</option>
        {% for option in PAYMENT_OPTIONS %}<option {{ 'selected' if value == option else '' }}>{{ option }}</option>{% endfor %}
      </select>
    {% else %}
      <input name="{{ prefix }}.{{ field[0] }}" type="{{ 'date' if field[2] == 'date' else 'text' }}" value="{{ value }}">
    {% endif %}
  </label>
{% endmacro %}
 
{% macro entry(prefix, fields, item) %}
  <div class="entry">
    <div class="grid">
      {% for field in fields %}{{ box(prefix, field, item.get(field[0], '')) }}{% endfor %}
    </div>
    <button type="button" class="danger" onclick="this.parentElement.remove()">Remove entry</button>
  </div>
{% endmacro %}
 
{% block content %}
<h1>{{ heading }}</h1>
 
{% if problems %}
<div class="errors" style="padding:10px 14px; border-radius:6px">
  <strong>{{ problems|length }} issue{{ 's' if problems|length != 1 else '' }} found</strong>
  — fix the fields highlighted below.
  {% set _general = [] %}
  {% for p in problems %}{% if p not in field_errors.values() %}{% if _general.append(p) %}{% endif %}{% endif %}{% endfor %}
  {% if _general %}<ul style="margin:6px 0 0; padding-left:18px">{% for p in _general %}<li>{{ p }}</li>{% endfor %}</ul>{% endif %}
</div>
{% endif %}
 
{% if request.endpoint in ('new_client', 'new_client_autofill') %}
  {% set autofill_url = url_for('new_client_autofill') %}
  {% set save_url = url_for('new_client') %}
{% else %}
  {% set autofill_url = url_for('edit_client_autofill', client_ref=request.view_args.get('client_ref', '')) %}
  {% set save_url = url_for('edit_client', client_ref=request.view_args.get('client_ref', '')) %}
{% endif %}

<form method="post" action="{{ save_url }}" enctype="multipart/form-data" id="client-form">
  <fieldset class="autofill">
    <legend>Fill in from documents</legend>
    <p class="muted" style="margin:0 0 10px">
      Upload the client's documents (CV, payslips, employment letters, tax notices, property deeds,
      bank or brokerage statements, KYC forms). The AI reads them and fills in the empty boxes below.
      Nothing you've typed is overwritten, and every filled box is highlighted for you to check.
    </p>
    <div class="actions">
      <input type="file" name="autofill_files" id="autofill-files" multiple
             accept=".pdf,.docx,.xlsx,.xlsm,.txt,.csv,.md,.json,.png,.jpg,.jpeg,.webp,.gif"
             style="flex:1; min-width:240px; margin:0">
      <button type="submit" id="autofill-button" formaction="{{ autofill_url }}" formnovalidate>
        Read documents &amp; fill in
      </button>
    </div>
    <p id="autofill-status" class="muted" style="display:none; margin:10px 0 0">
      Reading documents... this can take up to a minute.
    </p>
    {% if documents %}
    <p style="margin:12px 0 4px; font-size:.88rem"><strong>Attached to this client when saved:</strong></p>
    <ul style="margin:0; padding-left:18px; font-size:.88rem">
      {% for d in documents %}
      <li>{{ d.file_name }}
        <input type="hidden" name="doc.file_name" value="{{ d.file_name }}">
        <input type="hidden" name="doc.file_id" value="{{ d.file_id }}"></li>
      {% endfor %}
    </ul>
    {% endif %}
    {% if notes %}
    <div class="notes">
      <strong>{{ notes_title or 'Notes from reading the documents' }}</strong>
      <ul>{% for n in notes %}<li>{{ n }}</li>{% endfor %}</ul>
    </div>
    {% endif %}
  </fieldset>

  {% for prefix, title, fields, kind in SECTIONS %}
  <fieldset>
    <legend>{{ title }}</legend>
    {% if kind == 'dict' %}
      {% set data = values[prefix] %}
      <div class="grid">
        {% for field in fields %}{{ box(prefix, field, data.get(field[0], '')) }}{% endfor %}
      </div>
    {% else %}
      <div id="list-{{ prefix }}">
        {% for item in (values[prefix] or [{}]) %}{{ entry(prefix, fields, item) }}{% endfor %}
      </div>
      <button type="button" class="secondary" onclick="addEntry('{{ prefix }}')">Add entry</button>
      <template id="tpl-{{ prefix }}">{{ entry(prefix, fields, {}) }}</template>
    {% endif %}
  </fieldset>
  {% endfor %}
 
  <p class="muted">Files chosen above are kept as supporting documents when you save. More can be added on the client page later.</p>
  <div class="savebar actions">
    <button type="submit">Save client</button>
    <a class="button secondary" href="{{ url_for('home') }}">Cancel</a>
  </div>
</form>
 
<script>
(function () {
  var fe = {{ field_errors | tojson }};
  Object.keys(fe).forEach(function (key) {
    var msg = fe[key];
    var parts = key.split(".");
    var input;
    if (parts.length === 3 && /^\\d+$/.test(parts[1])) {
      var name = parts[0] + "." + parts[2];
      var idx  = parseInt(parts[1], 10);
      var all  = document.querySelectorAll('[name="' + name + '"]');
      input = all[idx] || null;
    } else {
      input = document.querySelector('[name="' + key + '"]');
    }
    if (!input) return;
    input.style.borderColor = "#e3b0b0";
    input.style.background  = "#fff5f5";
    var lbl = input.closest("label");
    if (!lbl) return;
    var span = document.createElement("span");
    span.style.cssText = "color:#a61b1b;font-size:.79rem;display:block;margin-top:3px";
    span.textContent = msg;
    lbl.appendChild(span);
  });
})();
</script>
<script>
(function () {
  // Highlight the boxes the documents filled in; the highlight clears once the officer edits the box.
  var filled = {{ autofilled | tojson }};
  filled.forEach(function (key) {
    var parts = key.split("."), input;
    if (parts.length === 3 && /^\\d+$/.test(parts[1])) {
      input = document.querySelectorAll('[name="' + parts[0] + "." + parts[2] + '"]')[parseInt(parts[1], 10)];
    } else {
      input = document.querySelector('[name="' + key + '"]');
    }
    if (!input) return;
    input.classList.add("autofilled");
    input.title = "Filled in from the uploaded documents - please check";
    input.addEventListener("input", function () { input.classList.remove("autofilled"); });
    input.addEventListener("change", function () { input.classList.remove("autofilled"); });
  });

  var button = document.getElementById("autofill-button");
  var files = document.getElementById("autofill-files");
  document.getElementById("client-form").addEventListener("submit", function (event) {
    if (event.submitter !== button) return;
    if (!files.files.length) { event.preventDefault(); alert("Choose at least one document first."); return; }
    button.disabled = true;
    button.textContent = "Reading...";
    document.getElementById("autofill-status").style.display = "block";
    // a disabled submitter isn't sent, so submit through the form action ourselves
    event.preventDefault();
    var form = event.target;
    form.action = button.getAttribute("formaction");
    form.submit();
  });
})();
</script>
<script>
  function addEntry(prefix) {
    var template = document.getElementById("tpl-" + prefix);
    document.getElementById("list-" + prefix).appendChild(template.content.cloneNode(true));
  }
</script>
{% endblock %}
"""
 
VIEW = """{% extends "base.html" %}
{% block content %}
<h1>{{ record.get('name', 'Client') }}
  <span class="muted" style="font-size:1rem">{{ record.get('client_ref', '') }}</span></h1>
 
<div style="display:flex; gap:8px; flex-wrap:wrap; align-items:center; margin-bottom:20px; padding-bottom:16px; border-bottom:1px solid var(--line)">
  <a class="button secondary" href="{{ url_for('edit_client', client_ref=record.get('client_ref', '')) }}">Edit</a>
  <form method="post" action="{{ url_for('assess_client', client_ref=record.get('client_ref', '')) }}" style="margin:0">
    <button type="submit">Run Assessment</button>
  </form>
  <span style="flex:1"></span>
  <a class="button secondary" href="{{ url_for('home') }}" style="color:var(--muted); border-color:var(--line)">← Back</a>
</div>

{% if problems %}
<div class="notes" style="margin-bottom:20px">
  <strong>To complete or check (use Edit)</strong>
  <ul>{% for p in problems %}<li>{{ p }}</li>{% endfor %}</ul>
</div>
{% endif %}

{% if assessments is none %}
<div class="panel" style="margin-bottom:20px">
  <h2>Assessment History</h2>
  <p class="muted">The assessment history cannot be shown because the saved assessments could not be read.</p>
</div>
{% elif assessments %}
<div class="panel" style="margin-bottom:20px">
  <h2>Assessment History</h2>
  <table>
    {% for a in assessments %}
    <tr>
      <td>{{ a.get('assessed_at', '')[:10] }}</td>
      <td>{{ a.get('assessed_at', '')[11:16] }} UTC</td>
      <td>{{ (a.get('outcome') or (a.get('assessment') or {}).get('outcome') or '—').replace('_', ' ') }}</td>
      <td>
        {% if a.get('assessment_id') %}
        <a href="{{ url_for('view_assessment', assessment_id=a.get('assessment_id')) }}">View</a>
        {% else %}
        <span class="muted">—</span>
        {% endif %}
      </td>
    </tr>
    {% endfor %}
  </table>
</div>
{% endif %}
 
{% for prefix, title, fields, kind in SECTIONS %}
<div class="panel">
  <h2>{{ title }}</h2>
  {% if kind == 'dict' %}
    {% set data = values[prefix] %}
    <table>
      {% for field in fields %}
      <tr><th>{{ field[1] }}</th><td>{{ data.get(field[0], '') }}</td></tr>
      {% endfor %}
    </table>
  {% else %}
    {% for item in values[prefix] %}
      <table style="margin-bottom:12px">
        {% for field in fields %}
        <tr><th>{{ field[1] }}</th><td>{{ item.get(field[0], '') }}</td></tr>
        {% endfor %}
      </table>
    {% else %}
      <p class="muted">Nothing entered.</p>
    {% endfor %}
  {% endif %}
</div>
{% endfor %}
 
<div class="panel">
  <h2>Supporting documents</h2>
  {% for document in record.get('supporting_documents', []) %}
    <p style="margin:4px 0">
      {{ document.get('file_name', 'Unknown file') }}
      {% if document.get('file_id') %}
        - <a href="{{ url_for('download_document', client_ref=record.get('client_ref', ''), file_id=document.get('file_id')) }}">Download</a>
      {% endif %}
    </p>
  {% else %}
    <p class="muted">No documents uploaded yet.</p>
  {% endfor %}
 
  <form method="post" action="{{ url_for('upload_documents', client_ref=record.get('client_ref', '')) }}"
        enctype="multipart/form-data" style="margin-top:14px">
    <label>Add documents
      <input type="file" name="files" multiple>
    </label>
    <button type="submit">Upload</button>
  </form>
</div>
{% endblock %}
"""
 
ASSESS_RESULT = """{% extends "base.html" %}
{% set COLORS = {"PASSED": "#1a7a3f", "MANUAL_REVIEW": "#b45309", "RISKY": "#c2410c", "SERIOUS_RISK": "#b91c1c"} %}
{% set MARK_COLORS = {"fail": "#b91c1c", "explained": "#1d4f7a", "weak": "#b45309", "pass": "#1a7a3f", "skip": "#616e7c", "info": "#616e7c"} %}
{% block title %}Assessment — {{ record.get('name', '') }}{% endblock %}
{% block content %}
<style>
  .report-items { list-style:none; margin:0; padding:0; }
  .report-items li { display:flex; gap:10px; padding:8px 0; border-bottom:1px solid var(--line); font-size:.92rem; }
  .report-items li:last-child { border-bottom:0; }
  .mark { width:18px; flex-shrink:0; text-align:center; font-weight:700; }
  .sub { color:var(--muted); font-size:.85rem; margin-top:3px; }
  .legend { display:flex; flex-wrap:wrap; gap:6px 16px; font-size:.8rem; color:var(--muted); margin-top:12px; }
  details { border-top:1px solid var(--line); padding:8px 0; }
  details:first-of-type { border-top:0; }
  summary { cursor:pointer; font-weight:600; font-size:.92rem; }
  .evidence { margin:8px 0 0; padding-left:18px; font-size:.86rem; }
  .evidence li { white-space:pre-wrap; padding:2px 0; }
</style>
<h1>Assessment — {{ record.get('name', '') }}
  <span class="muted" style="font-size:1rem">{{ record.get('client_ref', '') }}</span>
</h1>
<div class="actions" style="margin-bottom:16px">
  <a class="button secondary" href="{{ url_for('view_client', client_ref=record.get('client_ref', '')) }}">Back to client</a>
</div>

{% if report %}
{% set h = report['header'] %}
{% set colour = COLORS.get(h['verdict'], '#333') %}
<div class="panel" style="border-left:6px solid {{ colour }}">
  <div class="muted" style="font-size:.78rem; text-transform:uppercase; letter-spacing:.06em">Verdict</div>
  <div style="font-size:1.7rem; font-weight:700; color:{{ colour }}; margin:2px 0 10px">{{ h['verdict_label'] }}</div>
  <table>
    <tr><th>Next step</th><td>{{ h['next_step'] }}</td></tr>
    <tr><th>Next review</th><td>{{ h['next_review_date'] }}</td></tr>
    <tr><th>Assessed on</th><td>{{ h['assessed_on'] }} (policy {{ h['policy_version'] }})</td></tr>
  </table>
  <p style="margin:12px 0 0">{{ h['summary'] }}</p>
  <div class="legend">
    {% for entry in report['legend'] %}
    <span><strong style="color:{{ MARK_COLORS[entry['mark']] }}">{{ entry['symbol'] }}</strong> {{ entry['meaning'] }}</span>
    {% endfor %}
  </div>
</div>

{% set INDICATOR_LABELS = {
  "counterparty_unnamed": "Money from unnamed counterparty",
  "gift_or_inheritance_unnamed": "Gift or inheritance from unnamed person",
  "source_contradicts_occupation": "Source of wealth contradicts occupation",
  "unvalued_source_present": "Source with no declared amount",
  "related_party_transaction": "Related party transaction"
} %}
{% set CAT_BG    = {"critical":"#fef2f2","high":"#fff7ed","medium":"#fffbeb","partial":"#eff6ff","weak_signal":"#f9fafb","no_match":"#f9fafb"} %}
{% set CAT_BORDER= {"critical":"#b91c1c","high":"#c2410c","medium":"#b45309","partial":"#1d4f7a","weak_signal":"#9ca3af","no_match":"#d1d5db"} %}
{% set CAT_LABEL = {"critical":"CRITICAL MATCH","high":"HIGH MATCH","medium":"MEDIUM MATCH","partial":"PARTIAL MATCH","weak_signal":"WEAK SIGNAL","no_match":"NO MATCH"} %}

{% for section in report['sections'] %}
{% if section['title'] == "Crime - known patterns for his industry" and crime_result %}
<div class="panel">
  <h2>{{ section['title'] }}</h2>
  <div style="display:flex; gap:16px; margin-bottom:18px; font-size:.85rem; border-bottom:1px solid var(--line); padding-bottom:12px">
    <span style="color:var(--muted)">{{ crime_result.get('match_results', []) | length }} typologies checked</span>
    <span style="color:#b91c1c; font-weight:600">{{ crime_result.get('match_count', 0) }} matched</span>
    <span style="color:var(--muted)">{{ (crime_result.get('match_results', []) | length) - crime_result.get('match_count', 0) }} no match</span>
  </div>
  {% for m in crime_result.get('match_results', []) %}
  {% set cat = m.get('category', 'no_match') %}
  {% set typo = typologies_by_id.get(m.get('typology_id'), {}) %}
  <div style="padding:14px 16px; border-radius:6px; margin-bottom:10px;
              background:{{ CAT_BG.get(cat,'#f9fafb') }};
              border-left:4px solid {{ CAT_BORDER.get(cat,'#d1d5db') }}">
    <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:6px">
      <span style="font-size:.7rem; font-weight:700; letter-spacing:.06em; padding:2px 8px; border-radius:3px;
                   background:{{ CAT_BORDER.get(cat,'#9ca3af') }}; color:#fff">{{ CAT_LABEL.get(cat, cat.upper()) }}</span>
      <strong style="font-size:.97rem; color:#111">{{ m.get('name', m.get('typology_id')) }}</strong>
      {% if typo.get('crime_category') %}
      <span style="font-size:.76rem; color:#6b7280; background:#f3f4f6; padding:1px 7px; border-radius:3px; border:1px solid #e5e7eb">{{ typo['crime_category'].replace('_', ' ') }}</span>
      {% endif %}
    </div>
    {% if typo.get('description') %}
    <p style="margin:0 0 10px; font-size:.83rem; color:#4a5568; line-height:1.5">{{ typo['description'] }}</p>
    {% endif %}
    <div style="display:flex; gap:28px; flex-wrap:wrap">
      {% if m.get('core_indicators') %}
      <div>
        <div style="font-size:.72rem; font-weight:700; text-transform:uppercase; letter-spacing:.05em; color:#6b7280; margin-bottom:5px">Core</div>
        {% for ind in m['core_indicators'] %}
        {% if ind in m.get('core_fired', []) %}
        <div style="font-size:.83rem; display:flex; gap:7px; align-items:baseline; padding:2px 0; color:#111"><span style="color:#b91c1c; font-weight:700; flex-shrink:0">✓</span> {{ INDICATOR_LABELS.get(ind, ind.replace('_',' ')) }}</div>
        {% else %}
        <div style="font-size:.83rem; display:flex; gap:7px; align-items:baseline; padding:2px 0; color:#9ca3af"><span style="flex-shrink:0">—</span> {{ INDICATOR_LABELS.get(ind, ind.replace('_',' ')) }}</div>
        {% endif %}
        {% endfor %}
      </div>
      {% endif %}
      {% if m.get('supporting_indicators') %}
      <div>
        <div style="font-size:.72rem; font-weight:700; text-transform:uppercase; letter-spacing:.05em; color:#6b7280; margin-bottom:5px">Supporting</div>
        {% for ind in m['supporting_indicators'] %}
        {% if ind in m.get('supporting_fired', []) %}
        <div style="font-size:.83rem; display:flex; gap:7px; align-items:baseline; padding:2px 0; color:#111"><span style="color:#b45309; font-weight:700; flex-shrink:0">✓</span> {{ INDICATOR_LABELS.get(ind, ind.replace('_',' ')) }}</div>
        {% else %}
        <div style="font-size:.83rem; display:flex; gap:7px; align-items:baseline; padding:2px 0; color:#9ca3af"><span style="flex-shrink:0">—</span> {{ INDICATOR_LABELS.get(ind, ind.replace('_',' ')) }}</div>
        {% endif %}
        {% endfor %}
      </div>
      {% endif %}
    </div>
    {% if typo.get('source_quotes') %}{% set q = typo['source_quotes'][0] %}{% if q.get('quote') %}
    <blockquote style="margin:10px 0 0; padding:8px 12px; border-left:3px solid {{ CAT_BORDER.get(cat,'#d1d5db') }}; background:rgba(255,255,255,.55); font-size:.8rem; color:#4a5568; font-style:italic; line-height:1.5">"{{ q['quote'] }}"{% if q.get('report_id') %}<footer style="margin-top:3px; font-style:normal; font-size:.74rem; color:#9ca3af">[{{ q['report_id'] }}]</footer>{% endif %}</blockquote>
    {% endif %}{% endif %}
  </div>
  {% endfor %}
  {% if not crime_result.get('match_results') %}<p class="muted">No typologies were checked.</p>{% endif %}
</div>
{% else %}
<div class="panel">
  <h2>{{ section['title'] }}</h2>
  <ul class="report-items">
    {% for item in section['items'] %}
    <li>
      <span class="mark" style="color:{{ MARK_COLORS[item['mark']] }}">{{ symbols[item['mark']] }}</span>
      <div>{{ item['text'] }}
        {% for sub in item['sub'] %}<div class="sub">{{ sub }}</div>{% endfor %}
      </div>
    </li>
    {% endfor %}
  </ul>
</div>
{% endif %}
{% endfor %}
{% endif %}

{% if benchmark %}
<div class="panel">
  <h2>Full evidence</h2>
  {% for part in report['evidence'] %}
  <details>
    <summary>{{ part['title'] }}</summary>
    <ul class="evidence">{% for line in part['lines'] %}<li>{{ line }}</li>{% endfor %}</ul>
  </details>
  {% endfor %}
</div>
{% else %}
<div class="panel">
  <p class="muted" style="margin:0">This assessment was saved before the combined verdict. Run the assessment
  again to get one verdict with its reasons.</p>
</div>
{% endif %}
{% endblock %}
"""

ASSESSMENTS = """{% extends "base.html" %}
{% block content %}
<h1>Saved Assessments</h1>
<div class="actions" style="margin-bottom:16px">
  <a class="button secondary" href="{{ url_for('home') }}">Back to clients</a>
</div>
<div class="panel">
  {% if assessments is none %}
    <p class="muted">The saved assessments cannot be shown because they could not be read.</p>
  {% elif not assessments %}
    <p class="muted">No assessments saved yet. Open a client and click Run Assessment.</p>
  {% else %}
  <table>
    <tr>
      <th style="width:auto">Client</th>
      <th style="width:auto">Date</th>
      <th style="width:auto">Kind</th>
      <th style="width:auto">Outcome</th>
      <th style="width:auto"></th>
    </tr>
    {% for a in assessments %}
    {% set outcome = a.get('outcome') or (a.get('assessment') or {}).get('outcome', '') %}
    <tr>
      <td>{{ a.get('client_ref', '') }}</td>
      <td>{{ (a.get('assessed_at') or a.get('assessment', {}).get('assessed_on', ''))[:10] }}</td>
      <td>{{ 'combined assessment' if a.get('verdict') else a.get('kind', 'crime scan + benchmark') }}</td>
      <td>{{ outcome.replace('_', ' ') if outcome else '—' }}</td>
      <td style="display:flex; gap:10px">
        <a href="{{ url_for('view_client', client_ref=a.get('client_ref', '')) }}">Open client</a>
        {% if a.get('assessment_id') %}
        <a href="{{ url_for('view_assessment', assessment_id=a.get('assessment_id')) }}">View result</a>
        {% endif %}
      </td>
    </tr>
    {% endfor %}
  </table>
  {% endif %}
</div>
{% endblock %}
"""

ASSESS_LOADING = """{% extends "base.html" %}
{% block title %}Assessing {{ record.get('name', '') }} — Source of Wealth Screening{% endblock %}
{% block content %}
<h1>Assessing {{ record.get('name', '') }}
  <span class="muted" style="font-size:1rem">{{ record.get('client_ref', '') }}</span>
</h1>
<div class="panel">
  <p style="color:var(--muted); margin:0 0 18px">The crime scan, forecast and benchmark run together as one assessment in the background. A first run can take a few minutes; saved AI replies make reruns quick.</p>
  <ol id="step-list" style="list-style:none; padding:0; margin:0">
    {% for s in ASSESS_STEPS %}
    <li id="step-{{ loop.index }}" style="display:flex; align-items:center; gap:10px; padding:9px 0; border-bottom:1px solid var(--line)">
      <span class="step-icon" style="width:22px; text-align:center; flex-shrink:0">
        <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--line)"></span>
      </span>
      <span class="step-label" style="font-size:.9rem; color:var(--muted)">{{ s }}</span>
    </li>
    {% endfor %}
  </ol>
  <div id="error-box" style="display:none; margin-top:18px; padding:12px 14px; background:#fdeaea; border:1px solid #e3b0b0; border-radius:6px; color:#a61b1b; font-size:.9rem"></div>
  <div style="margin-top:20px">
    <button class="button secondary" onclick="cancel()">Cancel</button>
  </div>
</div>

<style>
  @keyframes spin { to { transform: rotate(360deg); } }
  .spinner { display:inline-block; width:14px; height:14px; border:2px solid #d0d7de; border-top-color:var(--accent); border-radius:50%; animation:spin .7s linear infinite; vertical-align:middle; }
</style>

<script>
  var pollUrl   = {{ url_for('assess_poll',   job_id=job_id) | tojson }};
  var resultUrl = {{ url_for('assess_result', job_id=job_id) | tojson }};
  var cancelUrl = {{ url_for('view_client',   client_ref=record.get('client_ref', '')) | tojson }};
  var total = {{ ASSESS_STEPS | length }};
  var timer;

  function cancel() {
    clearInterval(timer);
    window.location.href = cancelUrl;
  }

  function updateUI(data) {
    var n = data.step_num || 0;
    for (var i = 1; i <= total; i++) {
      var li    = document.getElementById("step-" + i);
      var icon  = li.querySelector(".step-icon");
      var label = li.querySelector(".step-label");
      if (data.status === "done" || i < n) {
        icon.innerHTML         = '<span style="color:#1a7a3f;font-size:1rem;line-height:1">✓</span>';
        label.style.color      = "var(--ink)";
        label.style.fontWeight = "";
      } else if (i === n) {
        icon.innerHTML         = '<span class="spinner"></span>';
        label.style.color      = "var(--ink)";
        label.style.fontWeight = "600";
      } else {
        icon.innerHTML         = '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--line)"></span>';
        label.style.color      = "var(--muted)";
        label.style.fontWeight = "";
      }
    }
    if (data.status === "done") {
      clearInterval(timer);
      window.location.href = resultUrl;
    } else if (data.status === "error") {
      clearInterval(timer);
      var box = document.getElementById("error-box");
      box.style.display = "block";
      box.textContent = "Assessment failed: " + (data.error || "Unknown error");
    }
  }

  function poll() {
    fetch(pollUrl)
      .then(function(r) { return r.json(); })
      .then(updateUI)
      .catch(function() {});
  }

  timer = setInterval(poll, 2000);
  poll();
</script>
{% endblock %}
"""


ERROR = """{% extends "base.html" %}
{% block title %}Error — Source of Wealth Screening{% endblock %}
{% block content %}
<div class="panel" style="text-align:center; padding:40px 22px">
  <div style="font-size:2.5rem; margin-bottom:12px; color:var(--bad)">&#9888;</div>
  <h1 style="color:var(--bad); margin-bottom:10px">Something went wrong</h1>
  <p style="color:var(--muted); max-width:440px; margin:0 auto 24px">
    An unexpected error occurred. Please go back and try again.
    If the problem persists, contact your system administrator.
  </p>
  {% if error_detail %}
  <p style="font-size:.8rem; color:var(--muted); font-family:monospace; max-width:600px; margin:0 auto 24px; word-break:break-all">{{ error_detail }}</p>
  {% endif %}
  <a class="button secondary" href="{{ url_for('home') }}">← Back to home</a>
</div>
{% endblock %}
"""

TEMPLATES: dict[str, str] = {
    "base.html": BASE,
    "home.html": HOME,
    "client_form.html": FORM,
    "client_view.html": VIEW,
    "assess_loading.html": ASSESS_LOADING,
    "assess_result.html": ASSESS_RESULT,
    "assessments.html": ASSESSMENTS,
    "error.html": ERROR,
}
