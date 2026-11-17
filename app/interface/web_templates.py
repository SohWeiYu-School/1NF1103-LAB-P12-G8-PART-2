"""The HTML pages of the web app, as Jinja templates. WebApp loads them by name."""

BASE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{% block title %}Orbit{% endblock %}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{
  --bg:#f0f2f5; --surface:#ffffff; --surface-2:#f6f8fa; --ink:#1f2933; --muted:#5f6c7a; --line:#d9dee3; --line-strong:#c4cdd6;
  --accent:#1d4f7a; --accent-ink:#ffffff; --accent-soft:#e8f1f8; --header:#1d4f7a; --header-ink:#ffffff;
  --bad:#a61b1b; --bad-soft:#fdeaea; --warn:#a15c07; --warn-soft:#fef3c7; --ok:#1a7a3f; --ok-soft:#dcf5e7;
  --g-client:#1d4f7a; --g-assessment:#2a9d8f; --g-documents:#c08a2d; --g-system:#7b8794; --g-signin:#b6c2cf;
  --v-pass-bg:#d1fae5; --v-pass-fg:#065f46; --v-manual-bg:#fef3c7; --v-manual-fg:#92400e; --v-risky-bg:#ffedd5; --v-risky-fg:#9a3412; --v-serious-bg:#fee2e2; --v-serious-fg:#991b1b;
  --shadow:0 1px 2px rgba(16,24,40,.05),0 1px 3px rgba(16,24,40,.06);
  color-scheme:light;
  --font:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif; --mono:"IBM Plex Mono",ui-monospace,"SF Mono",Menlo,monospace;
}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--ink);font-family:var(--font);font-size:14.5px;line-height:1.5;margin:0}
a{color:var(--accent)}
button,input,select,textarea{font:inherit;color:inherit}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.wrap{max-width:1120px;margin:0 auto;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
.mono{font-family:var(--mono);font-size:.86em}
.muted{color:var(--muted)}
.num{font-variant-numeric:tabular-nums}
h1{font-size:1.5rem;line-height:1.25;margin:0;font-weight:600;letter-spacing:-.01em;text-wrap:balance}
h2{font-size:1.05rem;margin:0;font-weight:600;text-wrap:balance}
main > h1{margin:0 0 18px}
main > h2{margin:0 0 12px}
.eyebrow{font-size:.72rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);font-weight:600}
header.top{background:var(--header);color:var(--header-ink);position:sticky;top:0;z-index:20}
header.top.admin{background:#232b36}
header.top .wrap{display:flex;align-items:center;gap:18px;min-height:56px;flex-wrap:wrap;padding-block:6px}
.brand{color:var(--header-ink);text-decoration:none;font-weight:700;letter-spacing:.01em;display:flex;gap:10px;align-items:center}
.brand-mark{width:26px;height:26px;border-radius:6px;background:rgba(255,255,255,.14);display:grid;place-items:center;font-size:.72rem;font-weight:700}
.portal-tag{font-size:.66rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;background:#f2c94c;color:#3d2e00;border-radius:4px;padding:2px 6px}
nav.main{display:flex;gap:4px;flex-wrap:nowrap;flex:1 1 auto;min-width:0;overflow-x:auto}
nav.main form{display:contents}
nav.main a,nav.main button{white-space:nowrap;color:rgba(255,255,255,.82);text-decoration:none;padding:6px 11px;border-radius:6px;font-size:.88rem;background:none;border:0;cursor:pointer}
nav.main a:hover,nav.main button:hover{background:rgba(255,255,255,.1);color:#fff}
nav.main a[aria-current="page"]{background:rgba(255,255,255,.16);color:#fff;font-weight:600}
.who{display:flex;gap:10px;align-items:center;font-size:.85rem}
.who form{margin:0}
.avatar{width:28px;height:28px;border-radius:50%;display:inline-grid;place-items:center;font-size:.72rem;font-weight:700;background:var(--accent-soft);color:var(--accent);flex:none}
header .avatar{background:rgba(255,255,255,.18);color:#fff}
.link-btn{background:none;border:0;color:inherit;text-decoration:underline;text-underline-offset:2px;cursor:pointer;padding:0;opacity:.85}
.cta{background:#fff;color:#1d4f7a;border:0;border-radius:6px;padding:6px 12px;font-weight:600;font-size:.86rem;cursor:pointer;text-decoration:none}
main{padding-block:24px 64px}
.stack{display:flex;flex-direction:column;gap:16px}
.row{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.spread{display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap}
.panel{background:var(--surface);border:1px solid var(--line);border-radius:10px;box-shadow:var(--shadow);min-width:0;padding:18px 22px;margin-bottom:16px}
.stack .panel{padding:0;margin-bottom:0}
.panel-pad{padding:18px 20px}
.stack .panel.panel-pad{padding:18px 20px}
.btn{display:inline-flex;gap:6px;align-items:center;border-radius:6px;padding:7px 14px;border:1px solid var(--accent);background:var(--accent);color:var(--accent-ink);cursor:pointer;font-size:.88rem;font-weight:500;text-decoration:none;white-space:nowrap}
.btn.secondary{background:var(--surface);color:var(--accent)}
.btn.ghost{background:transparent;border-color:transparent;color:var(--accent);padding-inline:8px}
.btn.sm{padding:4px 10px;font-size:.82rem}
.btn[aria-disabled="true"]{opacity:.5;pointer-events:none}
.page-head{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap}
.filters{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:12px 14px;display:flex;flex-direction:column;gap:10px;box-shadow:var(--shadow)}
.f-row{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end}
.field{display:flex;flex-direction:column;gap:3px;min-width:0;margin:0}
.field>span{font-size:.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;font-weight:600}
.field input,.field select{border:1px solid var(--line-strong);border-radius:6px;padding:6px 9px;background:var(--surface);min-height:34px;margin:0;width:auto}
.seg{display:inline-flex;border:1px solid var(--line-strong);border-radius:6px;overflow:hidden;min-height:34px}
.seg button{border:0;background:var(--surface);color:var(--ink);padding:6px 10px;cursor:pointer;font-size:.85rem;border-right:1px solid var(--line);border-radius:0}
.seg button:last-child{border-right:0}
.seg button[aria-pressed="true"]{background:var(--accent-soft);color:var(--accent);font-weight:600}
details.multi{position:relative}
details.multi summary{list-style:none;border:1px solid var(--line-strong);border-radius:6px;padding:6px 28px 6px 9px;cursor:pointer;min-height:34px;background:var(--surface);position:relative;white-space:nowrap}
details.multi summary::after{content:"\\25BE";position:absolute;right:9px;color:var(--muted)}
details.multi summary::-webkit-details-marker{display:none}
.multi-pop{position:absolute;z-index:15;top:calc(100% + 4px);left:0;background:var(--surface);border:1px solid var(--line-strong);border-radius:8px;padding:8px;box-shadow:0 8px 24px rgba(0,0,0,.14);min-width:220px}
.multi-pop label{display:flex;gap:8px;align-items:center;padding:5px 6px;border-radius:5px;cursor:pointer;margin:0;color:var(--ink)}
.multi-pop label:hover{background:var(--surface-2)}
.multi-pop input{width:auto;margin:0}
.dot{width:9px;height:9px;border-radius:50%;flex:none;display:inline-block}
.chips{display:flex;gap:6px;flex-wrap:wrap;align-items:center}
.chip{display:inline-flex;gap:6px;align-items:center;background:var(--accent-soft);color:var(--accent);border-radius:20px;padding:3px 6px 3px 11px;font-size:.8rem;font-weight:500}
.chip a{display:inline-grid;place-items:center;color:inherit;text-decoration:none;width:18px;height:18px;border-radius:50%;line-height:1;font-size:.95rem}
.chip a:hover{background:rgba(0,0,0,.08)}
.problem{background:var(--warn-soft);color:var(--warn);border-radius:6px;padding:7px 11px;font-size:.84rem}
.summary{font-size:1rem;line-height:1.55;margin:0}
.summary strong{font-weight:600}
.kv{display:grid;grid-template-columns:110px 1fr;gap:6px 12px;font-size:.88rem;margin:0}
.kv dt{color:var(--muted);font-size:.78rem;text-transform:uppercase;letter-spacing:.05em;font-weight:600;padding-top:2px}
.kv dd{margin:0}
.diff{display:inline-flex;gap:6px;align-items:center;flex-wrap:wrap;font-variant-numeric:tabular-nums}
.diff .b{text-decoration:line-through;color:var(--muted)}
.diff .a{font-weight:600}
.err{color:var(--bad);font-size:.84rem}
.scroll-x{overflow-x:auto;max-width:100%}
.small{font-size:.8rem}
table{width:100%;border-collapse:collapse}
th,td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--line);vertical-align:top;font-size:.88rem}
th{color:var(--muted);font-weight:600;font-size:.72rem;text-transform:uppercase;letter-spacing:.06em;background:var(--surface-2);white-space:nowrap;width:auto}
tbody tr.ev:hover{background:var(--surface-2)}
tr.ev:has(details[open]){background:var(--accent-soft)}
tr.detail td{background:var(--surface-2);padding:12px 16px 14px}
.pill{display:inline-flex;gap:6px;align-items:center;font-size:.8rem;white-space:nowrap}
.res-fail{color:var(--bad);font-weight:600;font-size:.8rem;background:var(--bad-soft);padding:1px 7px;border-radius:4px}
.badge{display:inline-block;font-size:.72rem;font-weight:700;padding:2px 8px;border-radius:12px;letter-spacing:.03em;white-space:nowrap}
.b-PASSED{background:var(--v-pass-bg);color:var(--v-pass-fg)} .b-MANUAL_REVIEW{background:var(--v-manual-bg);color:var(--v-manual-fg)}
.b-RISKY{background:var(--v-risky-bg);color:var(--v-risky-fg)} .b-SERIOUS_RISK{background:var(--v-serious-bg);color:var(--v-serious-fg)}
.pager{display:flex;gap:8px;align-items:center;justify-content:space-between;padding:10px 14px;flex-wrap:wrap;font-size:.85rem}
.empty{padding:36px 20px;text-align:center;color:var(--muted)}
.client-head{display:grid;grid-template-columns:1fr auto;gap:16px;align-items:start}
.facts{display:flex;gap:22px;flex-wrap:wrap;margin-top:10px;font-size:.88rem}
.facts div > span:first-child{display:block;font-size:.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;font-weight:600}
.timeline{list-style:none;margin:0;padding:6px 0}
.day-label{padding:14px 20px 4px;font-size:.75rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.tl{display:grid;grid-template-columns:56px 22px 1fr;gap:10px;padding:8px 20px;position:relative}
.tl time{font-variant-numeric:tabular-nums;color:var(--muted);font-size:.85rem;padding-top:2px}
.tl .node{width:12px;height:12px;border-radius:50%;margin:5px auto 0;border:2px solid var(--surface);box-shadow:0 0 0 2px currentColor;background:currentColor}
.tl .rail{position:absolute;left:calc(20px + 56px + 10px + 10px);top:0;bottom:0;width:2px;background:var(--line)}
.tl .body{min-width:0;display:flex;flex-direction:column;gap:2px;padding-bottom:4px}
.line{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.line .short{min-width:0}
.line .by{margin-left:auto;font-size:.82rem}
details.info summary{display:inline-flex;gap:4px;align-items:center;cursor:pointer;font-size:.78rem;color:var(--accent);list-style:none;padding:1px 0}
details.info summary::-webkit-details-marker{display:none}
details.info summary::before{content:"\\25B8";font-size:.7rem;transition:transform .15s}
details.info[open] summary::before{transform:rotate(90deg)}
details.info[open]{background:var(--surface-2);border:1px solid var(--line);border-radius:8px;padding:6px 10px 10px;margin-top:2px}
details.info .kv{margin-top:6px}
.signin-wrap{max-width:900px;margin:36px auto 0;display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:18px;align-items:start}
.signin{padding:28px}
.signin input{width:100%;border:1px solid var(--line-strong);border-radius:6px;padding:9px 11px;background:var(--surface);margin-top:4px}
.signin label{margin:0;color:var(--ink);font-size:inherit}
.demo-note{border:1px solid #e6cf7a;background:#fdf8e4;border-radius:10px;padding:18px 20px}
.demo-note h2{font-size:1rem;margin:0 0 6px;display:flex;gap:8px;align-items:center}
.demo-note ul{margin:6px 0 0;padding-left:18px}.demo-note li{margin:3px 0}
.demo-pill{font-size:.68rem;font-weight:700;letter-spacing:.06em;background:#7a5c00;color:#fff;border-radius:4px;padding:2px 6px}
.acct{width:100%;font-size:.86rem;margin-top:10px}.acct td{padding:5px 6px;border-top:1px solid #efe3b5;border-bottom:0}.acct th{text-align:left;font-size:.74rem;color:var(--muted);padding:4px 6px;background:none}
.acct button{border:1px solid var(--line-strong);background:var(--surface);color:var(--ink);border-radius:6px;padding:2px 9px;cursor:pointer;font-size:.8rem}
.env{font-family:var(--mono);font-size:.74rem;background:#fff;border:1px solid #efe3b5;border-radius:6px;padding:8px 10px;white-space:pre;overflow-x:auto;margin:6px 0 0}
.ro-pill{font-size:.74rem;border:1px solid var(--line-strong);border-radius:12px;padding:3px 10px;color:var(--muted);background:var(--surface-2);white-space:nowrap}
@media (max-width:1000px){ .who .name{display:none} }
@media (max-width:760px){.signin-wrap{grid-template-columns:1fr}}
@media (max-width:520px){ .client-head{grid-template-columns:1fr} .kv{grid-template-columns:1fr} .tl{grid-template-columns:44px 18px 1fr;padding-inline:12px} .tl .rail{left:calc(12px + 44px + 10px + 8px)} }
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}

/* ===== Audit Phase 2: copied from the mockup (docs/plans/mockup-v21.html) ===== */
[hidden]:not([hidden=until-found i]){display:none!important}
:root{--info:#1d4f7a; --info-soft:#e8f1f8; --g-review:#8e5bb5; --f1:#2a78d6;--f2:#eb6834;--f3:#1baf7a;--f4:#eda100}
.nav-count{display:inline-block;min-width:18px;padding:0 5px;margin-left:5px;border-radius:9px;background:#f8d4d4;color:#7f1414;font-size:.72rem;font-weight:700;text-align:center}
.sev{font-size:.7rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;border-radius:4px;padding:2px 7px}
.sev.alert{background:var(--bad-soft);color:var(--bad)} .sev.warning{background:var(--warn-soft);color:var(--warn)} .sev.info{background:var(--info-soft);color:var(--info)}
.kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.kpi{padding:14px 16px;display:flex;flex-direction:column;gap:4px}
.kpi .v{font-size:1.65rem;font-weight:600;letter-spacing:-.01em;font-variant-numeric:tabular-nums;line-height:1.2}
.kpi{padding:16px 18px;gap:6px}
.kpi .v{font-size:1.9rem}
.chart-card{padding:16px 18px;display:flex;flex-direction:column;gap:10px}
.chart-box{position:relative;height:220px}
.meaning{background:var(--surface-2);border-radius:8px;padding:10px 12px;font-size:.87rem;display:flex;gap:10px}
.meaning .ic{flex:none;width:20px;height:20px;border-radius:50%;background:var(--accent-soft);color:var(--accent);display:grid;place-items:center;font-weight:700;font-size:.75rem}
.meaning .lbl{display:block;font-weight:600;font-size:.72rem;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin-bottom:1px}
details.numbers summary{cursor:pointer;color:var(--accent);font-size:.84rem}
.offline{background:var(--warn-soft);color:var(--warn);border-radius:8px;padding:10px 12px;font-size:.87rem}
.sub{margin:2px 0 0;font-size:.88rem}
.dash{display:grid;grid-template-columns:minmax(0,1.7fr) minmax(0,1fr);gap:16px;align-items:stretch}
.vhead{display:flex;justify-content:space-between;align-items:flex-start;gap:16px}
.vhead h2{margin:0}.vhead .sub{margin:2px 0 0;color:var(--muted);font-size:.84rem}
.hero{text-align:right;line-height:1.1}.hero .n{font-size:1.9rem;font-weight:600;color:var(--ink)}.hero .l{display:block;font-size:.78rem;color:var(--muted);white-space:nowrap}
.vlegend{display:flex;flex-wrap:wrap;gap:6px 18px;margin:0;padding:0;list-style:none;font-size:.82rem;color:var(--muted)}
.vlegend li{display:inline-flex;align-items:center;gap:7px}.vlegend i{width:10px;height:10px;border-radius:3px;display:inline-block}
.vlegend b{color:var(--ink);font-weight:600;font-variant-numeric:tabular-nums}
.vlegend li.zero{opacity:.55}
.sevbar{display:flex;gap:2px;height:10px;border-radius:5px;overflow:hidden;background:var(--surface-2)}
.sevbar span{display:block;height:100%}
.sevkey{display:flex;gap:16px;flex-wrap:wrap;font-size:.82rem;color:var(--muted);margin:0;padding:0;list-style:none}
.sevkey li{display:inline-flex;align-items:center;gap:6px}.sevkey i{width:10px;height:10px;border-radius:50%}.sevkey b{color:var(--ink);font-weight:600}
@media (max-width:900px){ .dash{grid-template-columns:1fr} }
table.mini{width:auto;min-width:100%}
table.mini th,table.mini td{padding:5px 10px;font-size:.84rem;background:var(--surface)}
.kv dd .scroll-x{border:1px solid var(--line);border-radius:6px}
.fd{display:flex;flex-direction:column;gap:10px}
.rule{font-size:.8rem;color:var(--muted)} .rule b{color:var(--ink);font-weight:600}
.flow{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1.4fr) auto minmax(0,1fr);gap:8px;align-items:stretch}
.flow.two{grid-template-columns:minmax(0,1fr) auto minmax(0,1.6fr)}
.flow .arrow{align-self:center;color:var(--muted);font-size:1.1rem}
.card{background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:10px 12px;display:flex;flex-direction:column;gap:5px;min-width:0;font-size:.88rem;align-items:flex-start}
.card .lab{font-size:.66rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);font-weight:700}
.card .dl{display:flex;flex-direction:column}
.card .dl .muted{font-size:.76rem}
.person{display:flex;gap:8px;align-items:center}
.person small{display:block;color:var(--muted);font-size:.74rem;line-height:1.3}
.person b{display:block;line-height:1.3}
.who-bar{display:flex;gap:24px;flex-wrap:wrap;padding:8px 12px;background:var(--surface);border:1px solid var(--line);border-radius:8px}
.who-bar small{display:block;font-size:.66rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);font-weight:700}
.runs{display:flex;gap:8px;flex-wrap:wrap}
.run{text-decoration:none;color:var(--ink);min-width:120px}
a.run:hover{border-color:var(--accent)}
.clock{position:relative;height:22px;width:100%;background:var(--surface-2);border:1px solid var(--line);border-radius:5px;margin-top:16px}
.clock .work{position:absolute;top:0;bottom:0;background:var(--ok-soft)}
.clock .mark{position:absolute;top:-4px;bottom:-4px;width:3px;background:var(--bad);border-radius:2px}
.clock .mark i{position:absolute;bottom:100%;left:50%;transform:translateX(-60%);font-style:normal;font-size:.72rem;font-weight:700;color:var(--bad);white-space:nowrap}
.clock-l{position:relative;height:14px;width:100%;font-size:.7rem;color:var(--muted)}
.clock-l span{position:absolute;transform:translateX(-50%)}
.clock-l span:first-child{transform:none}
.clock-l span:last-child{transform:translateX(-100%)}
.bigstat{display:flex;gap:14px;align-items:baseline;flex-wrap:wrap}
.bigstat .n{font-size:1.6rem;font-weight:600;font-variant-numeric:tabular-nums}
.pillc{background:var(--surface-2);border:1px solid var(--line);border-radius:14px;padding:2px 10px;font-size:.8rem}
@media (max-width:700px){ .flow,.flow.two{grid-template-columns:1fr} .flow .arrow{transform:rotate(90deg);justify-self:center} }
.sec-head{display:flex;justify-content:space-between;align-items:flex-end;gap:12px;flex-wrap:wrap;padding:16px 20px 12px}
table.flags-t{table-layout:fixed}
table.flags-t tbody tr{height:72px}
table.flags-t td{padding-block:8px!important}
table.flags-t .st{flex-wrap:nowrap}
.st.review,.st.open,.st.followup,.st.resolved{flex-direction:row;margin:0;padding:2px 9px;border:1px solid transparent}
table.flags-t td{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
table.flags-t tr.filler td{border-bottom-color:transparent}
.flags-empty td{text-align:center;color:var(--muted);white-space:normal!important}
table.flags-t td{vertical-align:middle;padding-block:12px}
table.flags-t th:first-child,table.flags-t td:first-child{padding-left:20px}
tr.ev[data-sev="alert"] td:first-child{box-shadow:inset 4px 0 0 var(--bad)}
tr.ev[data-sev="warning"] td:first-child{box-shadow:inset 4px 0 0 var(--warn)}
tr.ev[data-sev="info"] td:first-child{box-shadow:inset 4px 0 0 var(--info)}
.integrity-note{margin:0}
.pill{font-size:.76rem;font-weight:600;border-radius:999px;padding:3px 10px;white-space:nowrap}
.pill.good{background:#dcf5e7;color:#14632f}.pill.bad{background:#fde3e3;color:#9b1c1c}.pill.flat{background:#eef1f5;color:var(--muted)}
.flag-ic{color:var(--bad);font-weight:700}
.st{display:inline-flex;align-items:center;gap:5px;font-size:.76rem;font-weight:600;border-radius:12px;padding:2px 9px;white-space:nowrap;border:1px solid transparent}
.st::before{content:"";width:7px;height:7px;border-radius:50%;background:currentColor}
.st.open{background:#fdecec;color:#a61b1b}.st.review{background:#e8f1f8;color:#1d4f7a}.st.followup{background:#fdf3dc;color:#8a5a00}.st.resolved{background:#e6f4ea;color:#1e6b34}
.assignee{display:block;font-size:.76rem;color:var(--muted);margin-top:3px}
.ticket{display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:18px;align-items:start}
.ticket .side{position:sticky;top:76px;display:flex;flex-direction:column;gap:16px}
.ticket h3{font-size:.95rem;margin:0}
.meta-row{display:flex;flex-wrap:wrap;gap:8px 18px;align-items:center;margin-top:10px;font-size:.86rem;color:var(--muted)}
.meta-row b{color:var(--ink);font-weight:600}
.evid{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:6px}
.evid a{display:flex;justify-content:space-between;gap:10px;padding:9px 12px;border:1px solid var(--line);border-radius:8px;text-decoration:none;color:var(--ink)}
.evid a:hover{border-color:var(--accent);background:var(--accent-soft)}
.upd label.field{display:flex;flex-direction:column;gap:4px}
.upd select,.upd textarea{width:100%;border:1px solid var(--line-strong);border-radius:6px;padding:8px 10px;background:var(--surface);font:inherit}
.upd textarea{min-height:92px;resize:vertical}
.radios{display:flex;flex-direction:column;gap:4px}.radios label{display:flex;gap:8px;align-items:flex-start;font-size:.88rem;cursor:pointer;margin:0;color:var(--ink)}
.radios input{width:auto;margin:3px 0 0}
.thist{list-style:none;margin:0;padding:0;display:flex;flex-direction:column}
.thist li{display:grid;grid-template-columns:28px minmax(0,1fr);gap:10px;padding:10px 0;border-top:1px solid var(--line)}
.thist li:first-child{border-top:0}
.thist .note{margin:4px 0 0;font-size:.88rem;background:var(--surface-2);border-radius:6px;padding:6px 9px}
.thist small{color:var(--muted)}
.qtabs{display:flex;gap:4px;flex-wrap:wrap}
.qtabs a{border:1px solid var(--line-strong);background:var(--surface);border-radius:16px;padding:4px 12px;font-size:.84rem;cursor:pointer;text-decoration:none;color:var(--ink)}
.qtabs a[aria-pressed="true"]{background:var(--accent);border-color:var(--accent);color:#fff}
.qtabs b{font-weight:700;margin-left:4px}
@media (max-width:980px){.ticket{grid-template-columns:1fr}.ticket .side{position:static}}
.why-item{display:grid;grid-template-columns:28px minmax(0,1fr);gap:12px;padding:12px 14px;border-radius:8px;background:var(--surface-2);border-left:4px solid var(--info)}
.why-item.alert{border-left-color:var(--bad)} .why-item.warning{border-left-color:var(--warn)}
.why-letter{width:26px;height:26px;border-radius:50%;background:var(--surface);border:1px solid var(--line-strong);display:grid;place-items:center;font-weight:700;font-size:.8rem}
.tl.flagged .body{background:var(--bad-soft);border-radius:8px;padding:8px 10px;margin-left:-10px}
tr.ev.flagged td:first-child{box-shadow:inset 3px 0 0 var(--bad)}
.check{display:inline-flex;gap:6px;align-items:center;cursor:pointer;min-height:34px;font-size:.9rem;margin:0;color:var(--ink)}
.check input{width:auto;margin:0}
.toast{position:fixed;left:50%;transform:translateX(-50%);bottom:calc(20px + env(safe-area-inset-bottom,0px));background:var(--ink);color:var(--bg);padding:10px 16px;border-radius:8px;z-index:50;font-size:.88rem;box-shadow:0 8px 24px rgba(0,0,0,.2);max-width:calc(100% - 32px);animation:toast-out .4s ease 6s forwards}
@keyframes toast-out{to{opacity:0;visibility:hidden}}
.seg a{display:inline-flex;align-items:center;border:0;background:var(--surface);color:var(--ink);padding:6px 10px;cursor:pointer;font-size:.85rem;border-right:1px solid var(--line);text-decoration:none}
.seg a:last-child{border-right:0}
.seg a[aria-pressed="true"]{background:var(--accent-soft);color:var(--accent);font-weight:600}
@media (max-width:860px){ .kpis{grid-template-columns:repeat(2,minmax(0,1fr))} }
@media (max-width:520px){ .kpis{grid-template-columns:1fr 1fr} }

/* Admin overview: soft-card style */
body.admin-portal{background:#eef1f6}
.ov{gap:20px!important}
.ov .panel{border:0;border-radius:18px;box-shadow:0 1px 2px rgba(16,24,40,.04),0 8px 24px rgba(16,24,40,.06)}
.ov-head{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap}
.ov-head h1{margin:0;font-size:1.75rem;letter-spacing:-.02em}
.ov-head .date{color:var(--muted);font-size:.9rem;margin-top:2px}
.ov .seg{border:0;background:#fff;border-radius:999px;padding:4px;gap:2px;box-shadow:0 1px 2px rgba(16,24,40,.06)}
.ov .seg button,.ov .seg a{border:0;border-radius:999px;padding:6px 14px;background:transparent;color:var(--muted)}
.ov .seg button[aria-pressed="true"],.ov .seg a[aria-pressed="true"]{background:var(--accent);color:#fff}
.ov .kpis{gap:16px}
.ov .kpi{padding:18px 20px;gap:0;min-height:150px}
.kt{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:auto}
.kic{width:42px;height:42px;border-radius:12px;background:#f1f4f8;display:grid;place-items:center;color:var(--ink)}
.kic svg{width:20px;height:20px}
.kl{font-size:.88rem;color:var(--ink);margin-top:14px;font-weight:500}
.kval{display:flex;align-items:baseline;gap:10px;margin-top:2px}
.kval .v{font-size:2.1rem!important;font-weight:650;letter-spacing:-.02em;line-height:1.1;font-variant-numeric:normal!important}
.kval .ctx{font-size:.8rem;color:var(--muted);line-height:1.25;max-width:16ch}
.kval .ctx form{display:inline;margin:0}
.kval .ctx .link-btn{color:var(--accent);font-size:.8rem;padding:0}
.ov .kpi.feature{background:linear-gradient(135deg,#1d4f7a,#2b6aa3);color:#fff}
.ov .kpi.feature .kic{background:rgba(255,255,255,.95);color:#1d4f7a}
.ov .kpi.feature .kl,.ov .kpi.feature .v{color:#fff}
.ov .kpi.feature .ctx{color:rgba(255,255,255,.8)}
.ov .kpi.feature .pill{background:rgba(255,255,255,.18);color:#fff}
.ov .chart-card,.ov .dash>.panel{padding:22px 24px}
.ov .vhead h2{font-size:1.15rem;letter-spacing:-.01em}
.ov .vlegend i{border-radius:50%}
.ov .meaning{border-radius:12px;background:#f5f7fa}
.ftypes2{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:14px}
.ftypes2 li{display:grid;grid-template-columns:36px minmax(0,1fr) auto;gap:4px 12px;align-items:center}
.ftypes2 .fic{grid-column:1;grid-row:1/3;width:36px;height:36px;border-radius:10px;display:grid;place-items:center}
.ftypes2 .fic svg{width:18px;height:18px}
.ftypes2 .fic.alert{background:#fde3e3;color:#9b1c1c}.ftypes2 .fic.warning{background:#fdf0d5;color:#8a4b06}.ftypes2 .fic.info{background:#eef1f5;color:#4b5866}
.ftypes2 .nm{grid-column:2;grid-row:1;text-align:left;font-size:.9rem;font-weight:500;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ftypes2 .nm small{display:block;font-weight:400;color:var(--muted);font-size:.75rem}
.ftypes2 .ct{grid-column:3;grid-row:1/3;display:flex;align-items:center;gap:10px}
.ftypes2 .ct b{font-size:1rem;font-variant-numeric:tabular-nums;min-width:1.2em;text-align:right}
.ftypes2 .trk{grid-column:2;grid-row:2;height:4px;border-radius:2px;background:#eef1f5}
.ftypes2 .trk span{display:block;height:100%;border-radius:2px;background:var(--accent)}
.ov .sevbar{height:8px;border-radius:999px;gap:3px;background:transparent}
.ov .sevbar span{border-radius:999px}
.ov .qtabs a{border-radius:999px;border-color:transparent;background:#f1f4f8}
.ov .qtabs a[aria-pressed="true"]{background:var(--accent);color:#fff}
.ov table.flags-t th{background:transparent;border-bottom:1px solid var(--line)}
@media (max-width:860px){.ov .kpi{min-height:0}}

/* The pages that are not redesigned keep their own classes (zero specificity, so the classes above win). */
:where(button,.button){font:inherit;background:var(--accent);color:#fff;border:0;border-radius:5px;padding:7px 16px;cursor:pointer;text-decoration:none;display:inline-block;font-size:.9rem}
button.secondary,.button.secondary{background:#fff;color:var(--accent);border:1px solid var(--accent)}
button.danger{background:#fff;color:var(--bad);border:1px solid var(--bad);padding:4px 10px}
:where(label){display:block;font-size:.88rem;color:var(--muted);margin-bottom:10px}
:where(input,select,textarea){display:block;width:100%;font:inherit;color:var(--ink);padding:7px 10px;margin-top:3px;border:1px solid #c4cdd6;border-radius:5px;background:#fff}
fieldset{border:1px solid var(--line);border-radius:8px;background:#fff;padding:16px 20px;margin:0 0 16px}
legend{font-weight:600;padding:0 6px}
.msg{background:#e8f1f8;border:1px solid #b9d3e6;border-radius:6px;padding:10px 14px;margin-bottom:14px}
.msg-warning{background:#fff8db;border-color:#e9d68f}
.msg-success{background:#e6f6ec;border-color:#a7d9b8}
.errors{background:#fdeaea;border:1px solid #e3b0b0;color:var(--bad);border-radius:6px;padding:10px 14px 10px 30px;margin-bottom:14px}
.actions{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:0 16px}
.wide{grid-column:1 / -1}
.entry{border:1px solid var(--line);border-radius:6px;padding:12px 14px;margin-bottom:12px;background:#fafbfc}
.savebar{position:sticky;bottom:0;background:var(--bg);padding:12px 0;border-top:1px solid var(--line)}
.autofill{border-color:#b9d3e6;background:#f5f9fc}
.autofilled{background:#fff8db !important;border-color:#e0c25a !important}
.notes{background:#fff8db;border:1px solid #e9d68f;border-radius:6px;padding:10px 14px;margin-top:12px;font-size:.88rem}
.notes ul{margin:6px 0 0;padding-left:18px}
.badge-pass{background:#d1fae5;color:#065f46}.badge-warn{background:#fef3c7;color:#92400e}
.badge-risk{background:#ffedd5;color:#9a3412}.badge-bad{background:#fee2e2;color:#991b1b}
</style>
</head>
<body{% if portal == 'admin' %} class="admin-portal"{% endif %}>
<header class="top{% if portal == 'admin' %} admin{% endif %}"><div class="wrap">
  <a class="brand" href="{{ url_for('admin_home' if portal == 'admin' else 'home') }}"><span class="brand-mark">O</span>Orbit{% if portal == 'admin' %} <span class="portal-tag">Admin</span>{% endif %}</a>
  {% if account %}
  {% set here = request.endpoint %}
  {% if portal == 'admin' %}
  <nav class="main">
    {% set open_count = open_flags() %}
    <a href="{{ url_for('admin_home') }}"{% if here in ('admin_home', 'admin_flag') %} aria-current="page"{% endif %}>Overview{% if open_count %}<span class="nav-count" title="{{ open_count }} flag{{ '' if open_count == 1 else 's' }} not resolved yet">{{ open_count }}</span>{% elif open_count is none %}<span class="nav-count" title="Flags can't be counted right now">!</span>{% endif %}</a>
    <a href="{{ url_for('audit_log_view') }}"{% if here == 'audit_log_view' or here == 'audit_verify' %} aria-current="page"{% endif %}>Activity log</a>
    <a href="{{ url_for('admin_clients') }}"{% if here in ('admin_clients', 'admin_view_client', 'admin_view_assessment') %} aria-current="page"{% endif %}>Clients</a>
  </nav>
  <div class="who">
    <span class="avatar" aria-hidden="true">{{ account.name|initials }}</span>
    <span class="name"><strong>{{ account.name }}</strong> &middot; System admin</span>
    <form method="post" action="{{ url_for('admin_signout') }}"><button class="link-btn" type="submit">Sign out</button></form>
  </div>
  {% else %}
  <nav class="main">
    <a href="{{ url_for('home') }}"{% if here in ('home', 'view_client', 'view_assessment', 'edit_client', 'new_client') %} aria-current="page"{% endif %}>Clients</a>
    <a href="{{ url_for('list_assessments_view') }}"{% if here == 'list_assessments_view' %} aria-current="page"{% endif %}>Assessments</a>
    <form method="post" action="{{ url_for('sync_to_cloud') }}"><button type="submit">Sync to Cloud</button></form>
  </nav>
  <div class="who">
    <a class="cta" href="{{ url_for('new_client') }}">+ New client</a>
    <span class="avatar" aria-hidden="true">{{ account.name|initials }}</span>
    <span class="name"><strong>{{ account.name }}</strong> &middot; KYC officer</span>
    <form method="post" action="{{ url_for('signout') }}"><button class="link-btn" type="submit">Sign out</button></form>
  </div>
  {% endif %}
  {% endif %}
</div></header>
<main class="wrap">
  {% for category, message in get_flashed_messages(with_categories=true)|unique(case_sensitive=True) %}{% if category == 'toast' %}<div class="toast" role="status">{{ message }}</div>{% else %}<div class="msg{% if category in ('success', 'warning') %} msg-{{ category }}{% endif %}">{{ message }}</div>{% endif %}{% endfor %}
  {% block content %}{% endblock %}
</main>
</body>
</html>
"""
 
HOME = """{% extends "base.html" %}
{% block title %}Clients — Orbit{% endblock %}
{% block content %}
<div class="stack">
  <div class="page-head">
    <div><div class="eyebrow">Clients</div><h1>Client records</h1></div>
    {% if account.is_admin() %}<span class="ro-pill">Read-only for admins</span>
    {% else %}
    <form action="{{ url_for('find') }}" method="get" class="row" style="gap:8px">
      <input name="ref" placeholder="Search by client reference..." aria-label="Client reference" style="width:260px; margin:0">
      <button class="secondary" type="submit">Find</button>
    </form>
    {% endif %}
  </div>
  {% if activity_error %}<div class="problem" role="alert">{{ activity_error }}</div>{% endif %}
  <div class="panel scroll-x">
  {% if clients is none %}
    <p class="muted" style="padding:20px 22px; margin:0">The list of clients cannot be shown because the client database could not be read.</p>
  {% elif not clients %}
    <p class="muted" style="padding:20px 22px; margin:0">No clients yet{% if not account.is_admin() %} — click <strong>+ New client</strong> in the top right to add the first one{% endif %}.</p>
  {% else %}
  <table>
    <thead><tr><th>Ref</th><th>Name</th><th>Latest verdict</th><th>Last activity</th></tr></thead>
    <tbody>
    {% for c in clients %}
    {% set ref = c.get('client_ref', '') %}
    {% set outcome = c.get('outcome') or '' %}
    <tr>
      <td><a class="mono" href="{{ link('view_client', client_ref=ref) }}">{{ ref }}</a></td>
      <td>{{ c.get('name', '') }}</td>
      <td>{% if outcome %}<span class="badge b-{{ outcome }}">{{ outcome.replace('_', ' ').capitalize() }}</span>{% else %}<span class="muted">Not assessed</span>{% endif %}</td>
      <td class="num">{% set last = activity.get(ref|lower) if activity is not none else none %}{% if last %}{{ last.at|sgt_day }} &middot; {{ last.actor }}{% else %}&mdash;{% endif %}</td>
    </tr>
    {% endfor %}
    </tbody>
  </table>
  <div class="pager"><span class="muted">{{ clients|length }} client{{ 's' if clients|length != 1 else '' }}</span></div>
  {% endif %}
  </div>
  {% if account.is_admin() %}<p class="muted" style="margin:0">Admins can look at any client to check an entry in the activity log, but can't edit clients or run assessments.</p>{% endif %}
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
{% from "audit_rows.html" import info, short %}
{% from "flag_parts.html" import detail, status_pill %}
{% block content %}
<div class="stack" style="margin-bottom:16px">
  <a href="{{ link('home') }}" class="muted" style="text-decoration:none">&larr; All clients</a>
  {% set outcome = record.get('outcome') or '' %}
  <section class="panel panel-pad"><div class="client-head">
    <div>
      <div class="eyebrow mono">{{ record.get('client_ref', '') }}</div>
      <h1 style="margin-top:2px">{{ record.get('name', 'Client') }}</h1>
      <div class="facts">
        <div><span>Nationality</span>{{ record.get('nationality') or '—' }}</div>
        <div><span>Occupation</span>{{ (record.get('career') or {}).get('occupation') or '—' }}</div>
        <div><span>Latest verdict</span>{% if outcome %}<span class="badge b-{{ outcome }}">{{ outcome.replace('_', ' ').capitalize() }}</span>{% if record.get('last_assessed_on') %} <span class="muted">{{ record.get('last_assessed_on') }}</span>{% endif %}{% else %}Not assessed{% endif %}</div>
      </div>
    </div>
    {% if account.is_admin() %}<span class="ro-pill">Read-only</span>
    {% else %}
    <div class="row">
      <a class="btn secondary" href="{{ url_for('edit_client', client_ref=record.get('client_ref', '')) }}">Edit</a>
      <form method="post" action="{{ url_for('assess_client', client_ref=record.get('client_ref', '')) }}" style="margin:0">
        <button class="btn" type="submit">Run assessment</button>
      </form>
    </div>
    {% endif %}
  </div></section>
  {% if flags_error %}<div class="problem" role="alert">{{ flags_error }}</div>{% endif %}
  {% if flag_boxes %}
  <section class="panel panel-pad stack why" style="gap:12px"><div><h2>Why this client is flagged</h2><p class="muted sub">What the rule picked up, and the data behind it.</p></div>
    {% for box in flag_boxes %}{% set f = box.ticket.flag %}
    <div class="why-item {{ box.css }}"><span class="why-letter">{{ 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'[loop.index0] if loop.index0 < 26 else '&bull;'|safe }}</span><div style="min-width:0"><div class="row" style="gap:8px"><span class="sev {{ box.css }}">{{ f.severity_name }}</span>{{ status_pill(box.ticket.status, box.ticket.status_name) }}<strong>{{ f.headline }}</strong><a class="btn secondary sm" href="{{ url_for('admin_flag', flag_id=f.flag_id) }}" style="margin-left:auto">Open ticket &rarr;</a></div>
      {{ detail(box.pic) }}</div></div>
    {% endfor %}
  </section>
  {% endif %}
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
{% elif assessments or archived_count %}
<div class="panel" style="margin-bottom:20px">
  <h2>Assessment History</h2>
  <table style="table-layout:fixed">
    <colgroup><col style="width:14%"><col style="width:11%"><col style="width:25%"><col style="width:8%"><col style="width:42%"></colgroup>
    {% for a in assessments %}
    {% set state = archive_states[loop.index0] if loop.index0 < archive_states|length else 'active' %}
    <tr{% if state != 'active' %} style="opacity:.55"{% endif %}>
      {% set when = a.get('assessed_at', '')|sgt %}
      {% if when != a.get('assessed_at', '') and ' ' in when %}<td>{{ when.rsplit(' ', 1)[0] }}</td><td>{{ when.rsplit(' ', 1)[1] }} SGT</td>
      {% else %}<td>{{ when }}</td><td></td>{% endif %}
      <td>{{ (a.get('outcome') or (a.get('assessment') or {}).get('outcome') or '—').replace('_', ' ') }}{% if state == 'archived' %}{% set last = (a.get('archive_log') or [])[-1] %} (archived) &middot; {{ ('by ' ~ last.get('by')) if last.get('by') else 'Not recorded (before sign-in existed)' }}{% elif state == 'unreadable' %} (archive state unreadable){% endif %}</td>
      <td>
        {% if a.get('assessment_id') %}
        <a href="{{ link('view_assessment', assessment_id=a.get('assessment_id')) }}">View</a>
        {% else %}
        <span class="muted">—</span>
        {% endif %}
      </td>
      <td>
        {% if a.get('assessment_id') and state != 'unreadable' and not account.is_admin() %}
        <form method="post" action="{{ url_for('restore_assessment' if state == 'archived' else 'archive_assessment', assessment_id=a.get('assessment_id')) }}" style="margin:0; display:flex; gap:8px; align-items:center">
          {% if state != 'archived' %}
          <input type="text" name="reason" maxlength="{{ max_reason }}" placeholder="Reason (optional)" aria-label="Reason for archiving (optional)" style="flex:1; min-width:0; margin:0">
          {% endif %}
          <button type="submit" class="secondary">{{ 'Restore' if state == 'archived' else 'Archive' }}</button>
        </form>
        {% endif %}
      </td>
    </tr>
    {% endfor %}
  </table>
  {% if show_archived %}
  <p style="margin:12px 0 0"><a href="{{ link('view_client', client_ref=record.get('client_ref', '')) }}">Hide archived</a></p>
  {% elif archived_count %}
  <p style="margin:12px 0 0"><a href="{{ link('view_client', client_ref=record.get('client_ref', ''), archived='1') }}">Show archived ({{ archived_count }})</a></p>
  {% endif %}
</div>
{% endif %}
 
{% set client_url = link('view_client', client_ref=record.get('client_ref', '')) %}
<div class="stack" style="margin-bottom:20px"><section class="panel" id="history">
  <form method="get" action="{{ client_url }}" id="trail-form">
    <div class="spread panel-pad" style="padding-bottom:8px">
      <div><h2>History</h2><p class="muted" style="margin:2px 0 0; font-size:.86rem">Every change to this client, newest first. Open <b>Info</b> for the details, or click <b>Assessed</b> to open that assessment.</p></div>
      <div class="row" style="gap:10px; align-items:flex-end">
        <button type="submit" tabindex="-1" aria-hidden="true" style="position:absolute; left:-9999px">Apply</button>
        <div class="field"><span>Show</span><div class="seg" role="group" aria-label="Show">
          {% for value, label in trail_shows %}<button type="submit" name="show" value="{{ value }}" aria-pressed="{{ 'true' if trail_filter.show == value else 'false' }}">{{ label }}</button>{% endfor %}
        </div></div>
        <label class="field" for="trail-when"><span>When</span><select id="trail-when" name="when">
          {% for value, label in trail_whens %}<option value="{{ value }}"{{ ' selected' if trail_filter.when == value else '' }}>{{ label }}</option>{% endfor %}
        </select></label>
        {% if trail_filter.when == 'custom' %}
        <label class="field" for="trail-from"><span>From</span><input type="date" id="trail-from" name="from" value="{{ trail_filter.date_from }}" max="{{ today }}"></label>
        <label class="field" for="trail-to"><span>To</span><input type="date" id="trail-to" name="to" value="{{ trail_filter.date_to }}" max="{{ today }}"></label>
        {% endif %}
        <button class="btn sm" type="submit" style="margin-bottom:2px">Apply</button>
      </div>
    </div>
    {% if show_archived %}<input type="hidden" name="archived" value="1">{% endif %}
    <input type="hidden" name="show" value="{{ trail_filter.show }}">
  </form>
  {% for problem in trail_filter.problems() %}<div class="panel-pad" style="padding-top:0"><div class="problem" role="alert">{{ problem }}</div></div>{% endfor %}
  {% if history_error %}
  <p class="muted" style="padding:0 20px 18px; margin:0">{{ history_error }}</p>
  {% else %}
  {% if history_unreadable %}<div class="panel-pad" style="padding-top:0"><div class="problem" role="alert">{{ history_unreadable }} {{ 'entry' if history_unreadable == 1 else 'entries' }} in the audit log can't be read, so this history may be incomplete.</div></div>{% endif %}
  {% if history %}
  <ul class="timeline">
    {% for day, events in history %}
    <li class="day-label">{{ day }}</li>
    {% for e in events %}
    <li class="tl{{ ' flagged' if e.sequence in flagged_sequences else '' }}"><span class="rail"></span><time title="{{ e.at.replace('T', ' ').replace('Z', ' UTC') }}">{{ e.at|sgt_hm }}</time><span class="node" style="color:var({{ GROUP_COLOURS[e.group] }})"></span>
      <div class="body">
        <div class="line"><strong>{% if e.action == 'assessment_run' and e.details.get('assessment_id') %}<a href="{{ link('view_assessment', assessment_id=e.details.get('assessment_id')) }}">{{ e.label }}</a>{% else %}{{ e.label }}{% endif %}</strong>
          <span class="short">{{ short(e) }}</span>{% if e.result == 'failed' %}<span class="res-fail">Failed</span>{% endif %}<span class="by muted">{{ e.actor }}</span></div>
        <details class="info"><summary>Info</summary>{{ info(e) }}</details>
      </div></li>
    {% endfor %}
    {% endfor %}
  </ul>
  {% elif history_total %}
  <div class="empty">Nothing matches these filters. Try &ldquo;All&rdquo; or &ldquo;All time&rdquo;.</div>
  {% else %}
  <div class="empty">No history recorded yet.</div>
  {% endif %}
  <div class="pager" style="border-top:1px solid var(--line)"><span class="muted">{{ history_count }} entr{{ 'y' if history_count == 1 else 'ies' }}</span></div>
  {% endif %}
</section></div>
<script>
(function () {
  var form = document.getElementById('trail-form');
  form.addEventListener('change', function (event) {
    if (event.target.matches('select, input[type=date]')) { form.submit(); }
  });
})();
</script>

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
        - <a href="{{ link('download_document', client_ref=record.get('client_ref', ''), file_id=document.get('file_id')) }}">Download</a>
      {% endif %}
    </p>
  {% else %}
    <p class="muted">No documents uploaded yet.</p>
  {% endfor %}
 
  {% if not account.is_admin() %}
  <form method="post" action="{{ url_for('upload_documents', client_ref=record.get('client_ref', '')) }}"
        enctype="multipart/form-data" style="margin-top:14px">
    <label>Add documents
      <input type="file" name="files" multiple>
    </label>
    <button type="submit">Upload</button>
  </form>
  {% endif %}
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
  <a class="button secondary" href="{{ link('view_client', client_ref=record.get('client_ref', '')) }}">Back to client</a>
</div>

{% if archive_state == 'unreadable' %}
<div class="msg">This assessment's archive record is damaged, so it cannot be archived or restored.</div>
{% elif archive %}
<div class="msg" style="display:flex; justify-content:space-between; align-items:center; gap:12px">
  <span>This assessment is archived{% if archive.get('at') %} (since {{ archive['at'][:10] }}){% endif %}{% if archive.get('reason') %}: {{ archive['reason'] }}{% endif %}. It is hidden from the lists but kept as a record. The client's current outcome is not changed. Archived by: {{ archive.get('by') or 'Not recorded (before sign-in existed)' }}.</span>
  {% if not account.is_admin() %}
  <form method="post" action="{{ url_for('restore_assessment', assessment_id=assessment_id) }}" style="margin:0">
    <button type="submit" class="secondary">Restore</button>
  </form>
  {% endif %}
</div>
{% endif %}

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
    <span style="color:var(--muted)">{{ crime_result.get('match_results', []) | length }} typologies scanned</span>
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
      {% if not typologies_checked %}
      <span style="font-size:.76rem; color:#92400e; background:#fef3c7; padding:1px 7px; border-radius:3px; border:1px solid #fcd34d">not checked against research</span>
      {% endif %}
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
  {% elif not assessments and archived_count %}
    <p class="muted">All {{ archived_count }} assessment(s) are archived. Open a client and click Show archived to see them.</p>
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
{% block title %}Assessing {{ record.get('name', '') }} — Orbit{% endblock %}
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
{% block title %}Error — Orbit{% endblock %}
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
  <a class="button secondary" href="{{ link('home') }}">← Back to home</a>
</div>
{% endblock %}
"""

AUDIT_ROWS = """{% macro short(e) -%}
{%- set d = e.details -%}
{%- if e.action == 'client_created' -%}New client record
{%- elif e.action == 'client_edited' -%}{%- if e.result == 'failed' -%}Change was not saved{%- else -%}{{ (d.get('changes')|short_fields) or 'Fields' }} changed{%- endif -%}
{%- elif e.action == 'assessment_run' -%}{%- set outcome = d.get('outcome') -%}{%- if outcome -%}<span class="badge b-{{ outcome }}">{{ outcome.replace('_', ' ').capitalize() }}</span>{%- else -%}Assessment saved{%- endif -%}
{%- elif e.action == 'assessment_failed' -%}Stopped before finishing
{%- elif e.action in ('document_uploaded', 'document_downloaded') -%}<span class="mono">{{ d.get('file_id') or 'a document' }}</span>
{%- elif e.action == 'autofill_used' -%}Details filled in from documents
{%- else -%}{{ e.summary().replace(' — failed', '') }}
{%- endif -%}
{%- endmacro %}

{% macro info(e, seal=false) %}
{% set d = e.details %}
<dl class="kv">
  {% if e.action == 'client_edited' %}
    {% if e.result == 'failed' %}<dt>Problem</dt><dd>The change could not be saved, so the record stayed as it was.</dd>
    {% else %}<dt>What changed</dt><dd>{% for c in d.get('changes', []) %}<div>{{ c.get('field')|field_label }}: <span class="diff"><span class="b">{{ c.get('before')|shown }}</span>&rarr;<span class="a">{{ c.get('after')|shown }}</span></span></div>{% else %}Nothing was listed.{% endfor %}</dd>{% endif %}
  {% elif e.action == 'assessment_run' %}
    <dt>Result</dt><dd>{% if d.get('outcome') %}<span class="badge b-{{ d.get('outcome') }}">{{ d.get('outcome').replace('_', ' ').capitalize() }}</span>{% else %}Not recorded{% endif %}</dd>
    <dt>Steps</dt><dd>{% if d.get('not_run') %}Not run: {{ d.get('not_run')|join(', ') }}{% else %}All steps ran{% endif %}</dd>
    {% if d.get('assessment_id') %}<dt>Record</dt><dd><a href="{{ link('view_assessment', assessment_id=d.get('assessment_id')) }}">Open assessment {{ d.get('assessment_id') }} &rarr;</a></dd>{% endif %}
  {% elif e.action == 'assessment_failed' %}
    <dt>Stopped at</dt><dd>{{ d.get('step') or 'Not recorded' }}</dd><dt>Saved?</dt><dd>No. Nothing from this run was saved.</dd>
  {% elif e.action in ('document_uploaded', 'document_downloaded') %}
    <dt>File</dt><dd class="mono">{{ d.get('file_id') or 'Not recorded' }}</dd>
  {% elif e.action == 'autofill_used' %}
    <dt>Read</dt><dd>{{ d.get('documents', 0) }} document{{ '' if d.get('documents') == 1 else 's' }}, {{ d.get('fields', 0) }} field{{ '' if d.get('fields') == 1 else 's' }} filled in</dd>
  {% elif e.action in ('assessment_archived', 'assessment_restored') %}
    <dt>Assessment</dt><dd class="mono">{{ d.get('assessment_id') or 'Not recorded' }}</dd>
    {% if d.get('reason') %}<dt>Reason</dt><dd>{{ d.get('reason') }}</dd>{% endif %}
  {% elif e.action == 'cloud_sync' %}
    <dt>Synced</dt><dd>{{ d.get('synced', 0) }} record{{ '' if d.get('synced') == 1 else 's' }}{% if d.get('errors') %}, {{ d.get('errors') }} could not be synced{% endif %}</dd>
  {% elif e.action == 'audit_verified' %}
    <dt>Checked</dt><dd>{{ d.get('entries', 0) }} entries: {{ 'changes found' if e.result == 'failed' else 'no changes found' }}</dd>
  {% elif e.action == 'access_refused' %}
    <dt>Tried to</dt><dd>{{ d.get('what') or 'Not recorded' }}</dd>
  {% elif e.action == 'sign_in_failed' %}
    <dt>Portal</dt><dd>{{ d.get('portal') or 'Not recorded' }}</dd>
  {% endif %}
  <dt>{{ DONE_BY.get(e.action, 'Done by') }}</dt><dd>{{ e.actor }} &middot; {{ e.at|sgt_long }}</dd>
  {% if seal %}<dt>Log entry</dt><dd class="mono small">#{{ e.sequence }} &middot; fingerprint {{ e.hash[:12] }}&hellip; &middot; {% if e.sequence > 1 %}links to #{{ e.sequence - 1 }}{% else %}first entry{% endif %}</dd>{% endif %}
</dl>
{% endmacro %}
"""

AUDIT = """{% extends "base.html" %}
{% from "audit_rows.html" import short, info with context %}
{% block title %}Activity log — Orbit{% endblock %}
{% block content %}
<form method="post" action="{{ url_for('audit_verify', **query) }}" id="verify-form"></form>
<form method="get" action="{{ url_for('audit_log_view') }}" id="filters" class="stack">
  <button type="submit" tabindex="-1" aria-hidden="true" style="position:absolute; left:-9999px">Apply</button>
  <div class="page-head">
    <div><div class="eyebrow">Audit</div><h1>Activity log</h1>
      <p class="muted" style="margin:4px 0 0">Every action anyone took in the app. Use it to answer &ldquo;who did what, and when?&rdquo;</p></div>
    <div class="row">
      <div class="seg" role="group" aria-label="Sort">
        <button type="submit" name="sort" value="desc" aria-pressed="{{ 'true' if audit_filter.sort == 'desc' else 'false' }}">Newest first</button>
        <button type="submit" name="sort" value="asc" aria-pressed="{{ 'true' if audit_filter.sort == 'asc' else 'false' }}">Oldest first</button>
      </div>
      <button class="btn secondary" type="submit" form="verify-form">Verify log</button>
    </div>
  </div>

  <section class="filters" aria-label="Filters">
    <div class="f-row">
      <div class="field"><span>Date range</span><div class="seg" role="group" aria-label="Date range">
        {% for value, label in (('1', 'Today'), ('7', '7 days'), ('30', '30 days'), ('90', '90 days'), ('custom', 'Custom')) %}<button type="submit" name="preset" value="{{ value }}" aria-pressed="{{ 'true' if audit_filter.preset == value else 'false' }}">{{ label }}</button>{% endfor %}
      </div></div>
      {% if audit_filter.preset == 'custom' %}
      <label class="field" for="f-from"><span>From</span><input type="date" id="f-from" name="from" value="{{ audit_filter.date_from }}" max="{{ today }}"></label>
      <label class="field" for="f-to"><span>To</span><input type="date" id="f-to" name="to" value="{{ audit_filter.date_to }}" max="{{ today }}"></label>
      {% endif %}
      <label class="field" for="f-officer"><span>Officer</span><select id="f-officer" name="actor">
        <option value="">Everyone</option>
        {% for name in officers %}<option{{ ' selected' if name.casefold() == audit_filter.actor.casefold() and audit_filter.actor else '' }}>{{ name }}</option>{% endfor %}
      </select></label>
      <div class="field"><span>Actions</span><details class="multi" id="f-groups"><summary>{{ 'All actions' if audit_filter.all_groups() else (audit_filter.groups|length ~ ' of ' ~ groups|length ~ ' groups') }}</summary>
        <div class="multi-pop">{% for name in groups %}<label><input type="checkbox" name="group" value="{{ name }}"{{ ' checked' if name in audit_filter.groups else '' }}><span class="dot" style="background:var({{ GROUP_COLOURS[name] }})"></span>{{ name }}</label>{% endfor %}</div></details></div>
      <div class="field"><span>Result</span><div class="seg" role="group" aria-label="Result">
        {% for value, label in (('all', 'All'), ('ok', 'OK'), ('failed', 'Failed')) %}<button type="submit" name="result" value="{{ value }}" aria-pressed="{{ 'true' if audit_filter.result == value else 'false' }}">{{ label }}</button>{% endfor %}
      </div></div>
    </div>
    <div class="f-row">
      <label class="field" for="f-client" style="width:130px"><span>Client</span><input id="f-client" name="client_ref" maxlength="40" placeholder="C-0007" value="{{ audit_filter.client_ref }}"></label>
      <label class="field" for="f-q" style="flex:1; min-width:180px"><span>Search</span><input id="f-q" name="q" type="search" maxlength="80" placeholder="Name, file, field, officer…" value="{{ audit_filter.query }}"></label>
      <label class="check" for="f-flagged" style="margin-bottom:0"><input type="checkbox" id="f-flagged" name="flagged" value="1"{{ ' checked' if audit_filter.flagged_only else '' }}>Flagged only</label>
      <button class="btn sm" type="submit" style="margin-bottom:2px">Apply</button>
    </div>
    {% for problem in audit_filter.problems() %}<div class="problem" role="alert">{{ problem }}</div>{% endfor %}
    <div class="spread"><div class="chips"><span class="muted" style="font-size:.82rem">{{ range_text }}</span>
      {% for text, remove in chips %}<span class="chip">{{ text }}<a href="{{ remove }}" aria-label="Remove this filter: {{ text }}">&times;</a></span>{% endfor %}</div>
      {% if chips %}<a class="btn ghost sm" href="{{ clear_url }}">Clear all</a>{% endif %}</div>
  </section>
  <input type="hidden" name="preset" value="{{ audit_filter.preset }}">
  <input type="hidden" name="result" value="{{ audit_filter.result }}">
  <input type="hidden" name="sort" value="{{ audit_filter.sort }}">
</form>

<div class="stack" style="margin-top:16px">
{% if log and log.unreadable and not error %}<div class="problem" role="alert">{{ log.unreadable }} {{ 'entry' if log.unreadable == 1 else 'entries' }} in the audit log can't be read. Use Verify log to see which.</div>{% endif %}
{% if log and not log.flags_ok and not error %}<div class="problem" role="alert">The flags could not be worked out right now. The events below are still complete.</div>{% endif %}
{% if log and log.flags_skipped and not error %}<div class="problem" role="alert">{{ log.flags_skipped }} {{ 'flag' if log.flags_skipped == 1 else 'flags' }} could not be worked out, so {{ 'it is' if log.flags_skipped == 1 else 'they are' }} not marked or counted here.</div>{% endif %}
{% if log %}<p class="summary">{{ period }}: <strong>{{ log.total }} event{{ '' if log.total == 1 else 's' }}</strong> by {{ log.officers }} officer{{ '' if log.officers == 1 else 's' }}; <strong>{{ log.failed }} failed</strong>; {% if not log.flags_ok %}flags unknown{% elif log.open_flags %}<a href="{{ url_for('admin_home') }}"><strong>{{ log.open_flags }} open flag{{ '' if log.open_flags == 1 else 's' }}</strong></a>{% else %}no open flags{% endif %}.</p>{% endif %}
<section class="panel">
  {% if error %}
    <p class="muted" style="padding:20px 22px; margin:0">{{ error }}</p>
  {% else %}
  <div class="scroll-x"><table>
    <thead><tr><th>Time (SGT)</th><th>Officer</th><th>Action</th><th>Client</th><th>What happened</th></tr></thead>
    <tbody>
    {% for e in log.events %}
    <tr class="ev{{ ' flagged' if e.sequence in log.flagged else '' }}">
      <td class="num" title="{{ e.at.replace('T', ' ').replace('Z', ' UTC') }}" style="white-space:nowrap">{{ e.at|sgt_day }} <span class="muted">{{ e.at|sgt_hm }}</span></td>
      <td style="white-space:nowrap"><span class="pill"><span class="avatar" style="width:22px;height:22px;font-size:.62rem" aria-hidden="true">{{ e.actor|initials }}</span>{{ e.actor }}</span></td>
      <td style="white-space:nowrap"><span class="pill"><span class="dot" style="background:var({{ GROUP_COLOURS[e.group] }})"></span>{{ e.label }}</span>{% if e.sequence in log.flagged %} <span class="flag-ic" title="Behind a flag that is not resolved yet" aria-label="Behind a flag that is not resolved yet">&#9873;</span>{% endif %}</td>
      <td>{% if e.client_ref %}<a class="mono" href="{{ link('view_client', client_ref=e.client_ref) }}">{{ e.client_ref }}</a>{% else %}<span class="muted">&mdash;</span>{% endif %}</td>
      <td style="min-width:260px">
        <span class="row" style="gap:8px">{{ short(e) }}{% if e.result == 'failed' %}<span class="res-fail">Failed</span>{% endif %}{% if e.event_id in broken_ids %}<span class="badge badge-warn">Changed outside the app</span>{% endif %}</span>
        <details class="info"><summary>Info</summary>{{ info(e, true) }}</details>
      </td>
    </tr>
    {% else %}
    <tr><td colspan="5"><div class="empty">{% if log.everything == 0 and not log.unreadable %}No activity recorded yet.{% elif log.everything == 0 %}No activity can be shown.{% else %}No events match these filters. Try a longer date range or <a href="{{ clear_url }}">clear the filters</a>.{% endif %}</div></td></tr>
    {% endfor %}
    </tbody>
  </table></div>
  <div class="pager"><span class="muted">Showing {{ (page - 1) * page_size + 1 if log.total else 0 }}&ndash;{{ [page * page_size, log.total]|min }} of {{ log.total }} &middot; open <b>Info</b> on a row for details</span>
    <span class="row">
      {% set back_word, on_word = ('Older', 'Newer') if audit_filter.sort == 'asc' else ('Newer', 'Older') %}
      {% if page > 1 %}<a class="btn secondary sm" href="{{ url_for('audit_log_view', **(dict(base_query, page=page - 1) if page > 2 else base_query)) }}">&larr; {{ back_word }}</a>{% else %}<span class="btn secondary sm" aria-disabled="true">&larr; {{ back_word }}</span>{% endif %}
      <span class="num">Page {{ page }} of {{ pages }}</span>
      {% if page < pages %}<a class="btn secondary sm" href="{{ url_for('audit_log_view', **dict(base_query, page=page + 1)) }}">{{ on_word }} &rarr;</a>{% else %}<span class="btn secondary sm" aria-disabled="true">{{ on_word }} &rarr;</span>{% endif %}
    </span></div>
  {% endif %}
</section>
</div>
<script>
(function () {
  var form = document.getElementById('filters');
  form.addEventListener('change', function (event) {
    if (event.target.matches('select, input[type=date], input[name=flagged]')) { form.submit(); }
  });
  var groups = document.getElementById('f-groups'), before = groups.querySelectorAll('input:checked').length;
  groups.addEventListener('toggle', function () {
    if (!groups.open && groups.querySelectorAll('input:checked').length !== before) { form.submit(); }
  });
  document.querySelectorAll('tr.ev').forEach(function (row) {
    row.style.cursor = 'pointer';
    row.addEventListener('click', function (event) {
      if (event.target.closest('a, summary, details dl')) { return; }
      var info = row.querySelector('details.info');
      if (info) { info.open = !info.open; }
    });
  });
})();
</script>
{% endblock %}
"""

SIGNIN = """{% extends "base.html" %}
{% block title %}{{ 'Admin sign-in' if portal == 'admin' else 'Sign in' }} — Orbit{% endblock %}
{% block content %}
<div class="signin-wrap">
  <form class="panel signin stack" method="post" action="{{ url_for('admin_signin' if portal == 'admin' else 'signin') }}" id="signin-form" novalidate>
    <div><div class="eyebrow">{{ 'Admin portal · /admin' if portal == 'admin' else 'Orbit' }}</div>
      <h1 style="margin-top:4px">{{ 'System admin sign-in' if portal == 'admin' else 'Officer sign-in' }}</h1></div>
    <p class="muted" style="margin:0">{{ 'The activity log and a read-only view of clients. For system admins only.' if portal == 'admin' else 'Clients, assessments and client history.' }}</p>
    <label for="signin-name"><span class="eyebrow">Name</span>
      <input id="signin-name" name="name" autocomplete="username" maxlength="{{ max_text }}" placeholder="e.g. {{ demo[0].name if demo else 'Shareen' }}" value="{{ name }}"></label>
    <label for="signin-pw"><span class="eyebrow">Password</span>
      <input id="signin-pw" name="password" type="password" autocomplete="current-password" maxlength="{{ max_text }}"></label>
    {% if problem %}<div class="err" role="alert">{{ problem }}</div>{% endif %}
    <button class="btn" type="submit" style="justify-content:center">Sign in</button>
    <p class="muted" style="margin:0; font-size:.84rem">{% if portal == 'admin' %}Not an admin? <a href="{{ url_for('signin') }}">Officer sign-in is at /</a>{% else %}System admin? <a href="{{ url_for('admin_signin') }}">Admin sign-in is at /admin</a>{% endif %}</p>
  </form>
  <aside class="demo-note">
    <h2><span class="demo-pill">DEMO ONLY</span> This login is for demonstration</h2>
    <p style="margin:0">It shows <b>who did what</b> in the activity log and keeps the admin pages separate. It is not how a real bank would do login.</p>
    <ul>
      <li><b>No sign-up.</b> Accounts are set up by whoever runs the app, in the <span class="mono">config/accounts.json</span> file.</li>
      <li><b>No password reset.</b> To change a password, put a new hash in <span class="mono">config/accounts.json</span> and restart.</li>
      <li>Passwords are stored <b>hashed</b>, never as plain text.</li>
      <li>A real system would add single sign-on, a second factor (MFA), lockout after failed tries and self-service reset.</li>
    </ul>
    <table class="acct"><thead><tr><th>Demo account</th><th>Password</th><th></th></tr></thead><tbody>
      {% for a in demo %}
      <tr><td>{{ a.name }}</td><td class="mono">{{ a.password }}</td><td style="text-align:right"><button type="button" data-name="{{ a.name }}" data-password="{{ a.password }}">Use</button></td></tr>
      {% endfor %}
    </tbody></table>
    <details style="margin-top:10px"><summary style="cursor:pointer; font-size:.86rem">How accounts look in <span class="mono">config/accounts.json</span></summary>
      <div class="env">{"email": "shareen@orbit.local", "name": "Shareen", "role": "officer",
 "password_hash": "scrypt:32768:8:1$…"}</div>
      <p class="muted small" style="margin:6px 0 0">Make a hash with <span class="mono">python3 -c "from werkzeug.security import generate_password_hash as g; print(g('a-password'))"</span>.</p></details>
  </aside>
</div>
<script>
document.querySelectorAll('.acct button[data-name]').forEach(function (button) {
  button.addEventListener('click', function () {
    document.getElementById('signin-name').value = button.dataset.name;
    document.getElementById('signin-pw').value = button.dataset.password;
    document.getElementById('signin-pw').focus();
  });
});
</script>
{% endblock %}
"""

FORBIDDEN = """{% extends "base.html" %}
{% block title %}Not allowed — Orbit{% endblock %}
{% block content %}
<div class="panel" style="text-align:center; padding:40px 22px">
  <h1 style="color:var(--bad); margin-bottom:10px">Not allowed</h1>
  <p style="color:var(--muted); margin:0 auto 24px">{{ message }}</p>
  <a class="button secondary" href="{{ url_for('home') }}">← Back to the officer portal</a>
</div>
{% endblock %}
"""

FLAG_PARTS = """{% macro icon(name) -%}
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
{%- if name == 'activity' %}<path d="M3 12h4l3-8 4 16 3-8h4"/>
{%- elif name == 'alert' %}<path d="M12 3 2 20h20L12 3z"/><path d="M12 10v4"/><path d="M12 17h.01"/>
{%- elif name == 'shield' %}<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6l-8-3z"/><path d="m9 12 2 2 4-4"/>
{%- elif name == 'shieldx' %}<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6l-8-3z"/><path d="m10 10 4 4M14 10l-4 4"/>
{%- elif name == 'shop' %}<path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/>
{%- elif name == 'other' %}<circle cx="9" cy="8" r="3.5"/><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6"/><path d="M17 11l4-4M19 7h2v2"/>
{%- elif name == 'repeat' %}<path d="M4 12a8 8 0 0 1 14-5.3L20 9"/><path d="M20 4v5h-5"/><path d="M20 12a8 8 0 0 1-14 5.3L4 15"/><path d="M4 20v-5h5"/>
{%- elif name == 'hours' %}<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/>
{%- elif name == 'spike' %}<path d="M13 2 4 14h7l-1 8 9-12h-7l1-8z"/>
{%- elif name == 'integrity' %}<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6l-8-3z"/><path d="M12 9v4"/><path d="M12 16h.01"/>
{%- else %}<path d="M5 21V4"/><path d="M5 4h11l-2 4 2 4H5"/>
{%- endif %}</svg>
{%- endmacro %}

{% macro badge(e) -%}
{%- set o = e.details.get('outcome') -%}
{%- if o %}<span class="badge b-{{ o }}">{{ o.replace('_', ' ').capitalize() }}</span>{% else %}<span class="muted">Assessment saved</span>{% endif -%}
{%- endmacro %}

{% macro alink(e) -%}
{%- set aid = e.details.get('assessment_id') -%}
{%- if aid %}<a href="{{ link('view_assessment', assessment_id=aid) }}" class="mono small">{{ aid }}</a>{% endif -%}
{%- endmacro %}

{% macro person(name, role, sub) -%}
<span class="person"><span class="avatar">{{ name|initials }}</span><span><small>{{ role }}</small><b>{{ name }}</b>{% if sub %}<small>{{ sub }}</small>{% endif %}</span></span>
{%- endmacro %}

{% macro diffs(changes) -%}
{% for c in changes %}<div class="dl"><span class="muted">{{ c.get('field')|flag_field }}</span><span class="diff"><span class="b">{{ c.get('before')|shown }}</span>&rarr;<span class="a">{{ c.get('after')|shown }}</span></span></div>{% endfor %}
{%- endmacro %}

{% macro change_pill(has_previous, percent, diff, bad_up) -%}
{% if not has_previous %}<span class="pill flat">No earlier data</span>
{%- elif diff == 0 and percent is none %}<span class="pill flat">No change</span>
{%- else %}{% set kind = 'flat' if diff == 0 else ('bad' if (diff > 0) == bad_up else 'good') %}<span class="pill {{ kind }}">{{ '+' if diff > 0 else ('&minus;' if diff < 0 else '&plusmn;')|safe }}{% if percent is none %}{{ diff|abs }}{% else %}{{ percent|abs }}%{% endif %}</span>{% endif %}
{%- endmacro %}

{% macro status_pill(key, name) -%}<span class="st {{ key }}">{{ name }}</span>{%- endmacro %}

{% macro detail(pic) %}
{% set f = pic.flag %}
<div class="fd"><span class="rule">Rule &middot; <b>{{ pic.rule }}</b></span>
  <div class="who-bar">
  {% if f.client_ref %}<span><small>Client</small><b>{{ pic.client_name or f.client_ref }}</b>{% if pic.client_name %} <span class="mono small muted">{{ f.client_ref }}</span>{% endif %}</span>{% if f.owner %}<span><small>Owner officer</small><b>{{ f.owner }}</b></span>{% endif %}
  {% else %}<span><small>Client</small><b>None</b> <span class="muted small">(affects the whole system)</span></span>{% endif %}
  </div>
  {% if f.kind == 'integrity' %}
  <div class="card"><div class="bigstat"><span>Entry <span class="n">#{{ f.broken_at }}</span></span><span class="muted">{{ pic.entries - f.broken_at }} {{ 'entry' if pic.entries - f.broken_at == 1 else 'entries' }} after it can't be trusted</span></div><span class="small muted">Edited or deleted directly in the file, so the app can't tell which officer did it.</span></div>
  {% elif not pic.complete %}
  <div class="problem" role="alert">Some of the log entries behind this flag can't be read, so the picture is incomplete.</div>
  {% elif f.kind == 'shop' %}
  {% set a, e, b = pic.ordered %}
  <div class="flow"><div class="card"><span class="lab">Before</span>{{ badge(a) }}{{ person(a.actor, 'Assessed by', a.at|sgt_when) }}{{ alink(a) }}</div><span class="arrow">&rarr;</span>
    <div class="card"><span class="lab">Edit</span>{{ diffs(f.changes) }}{{ person(e.actor, 'Edited by', e.at|sgt_when) }}</div><span class="arrow">&rarr;</span>
    <div class="card"><span class="lab">After</span>{{ badge(b) }}{{ person(b.actor, 'Assessed by', b.at|sgt_when) }}{{ alink(b) }}</div></div>
  {% elif f.kind == 'other' %}
  {% set e = pic.ordered[0] %}
  <div class="flow two"><div class="card"><span class="lab">Owner officer</span>{{ person(f.owner, 'Created the client', pic.created.at|sgt_when if pic.created else '') }}</div><span class="arrow">&rarr;</span>
    <div class="card"><span class="lab">Edit by another officer</span>{{ person(e.actor, 'Edited by', e.at|sgt_when) }}{{ diffs(f.changes) }}</div></div>
  {% elif f.kind == 'repeat' %}
  <div class="runs">{% for e in pic.ordered %}{% set aid = e.details.get('assessment_id') %}<{{ 'a' if aid else 'div' }} class="card run"{% if aid %} href="{{ link('view_assessment', assessment_id=aid) }}"{% endif %}><span class="lab">Run {{ loop.index }} &middot; {{ e.at|sgt_when(false) }}</span>{{ badge(e) }}{{ person(e.actor, 'Assessed by', '') }}</{{ 'a' if aid else 'div' }}>{% endfor %}</div>
  {% elif f.kind == 'hours' %}
  {% set e = pic.ordered[0] %}
  <div class="card" style="gap:8px">{{ person(e.actor, 'Edited by' if e.action == 'client_edited' else 'Assessed by', e.at|sgt_when) }}
    <div class="clock" role="img" aria-label="Done at {{ pic.clock.time }}; working hours {{ pic.rule_hours }}"><span class="work" style="left:{{ pic.clock.work_left }}%;width:{{ pic.clock.work_width }}%"></span><span class="mark" style="left:calc({{ pic.clock.at }}% - 1px)"><i>{{ pic.clock.time }}</i></span></div>
    <div class="clock-l">{% for left, text in pic.clock.ticks %}<span style="left:{{ left }}%">{{ text }}</span>{% endfor %}</div>
    {% if e.action == 'client_edited' %}<span class="lab">What changed</span>{{ diffs(e.details.get('changes', [])) }}{% else %}<div>{{ badge(e) }} {{ alink(e) }}</div>{% endif %}</div>
  {% elif f.kind == 'spike' %}
  <div class="card"><div class="bigstat"><span><span class="n">{{ pic.ordered|length }}</span> failures</span><span class="muted">{{ f.day|day_when }} &middot; usual {{ f.usual|plain_number }} a day</span></div>
    <div class="row" style="gap:6px">{% for kind, count in pic.kinds %}<span class="pillc">{{ kind }} <b>{{ count }}</b></span>{% endfor %}</div>
    <details class="numbers"><summary>Show all {{ pic.ordered|length }}</summary><div class="scroll-x" style="margin-top:6px"><table class="mini"><thead><tr><th>Time</th><th>Client</th><th>Officer</th><th>What failed</th></tr></thead><tbody>
      {% for e in pic.ordered %}<tr><td class="num">{{ e.at|sgt_hm }}</td><td>{% if e.client_ref %}<a class="mono" href="{{ link('view_client', client_ref=e.client_ref) }}">{{ e.client_ref }}</a>{% else %}&mdash;{% endif %}</td><td>{{ e.actor }}</td><td>{{ pic.what[e.sequence] }}</td></tr>{% endfor %}
    </tbody></table></div></details></div>
  {% endif %}
</div>
{% endmacro %}
"""

OVERVIEW = """{% extends "base.html" %}
{% from "flag_parts.html" import icon, status_pill, change_pill %}
{% block title %}Overview — Orbit{% endblock %}
{% block content %}
{% if error %}
<div class="stack ov">
  <div class="ov-head"><div><h1>Overview</h1><div class="date">{{ today_long }}</div></div></div>
  <section class="panel"><p class="muted" style="padding:20px 22px; margin:0" role="alert">{{ error }}</p></section>
</div>
{% else %}
{% set days = (view.day_to - view.day_from).days + 1 %}
<div class="stack ov">
  <div class="ov-head"><div><h1>Overview</h1><div class="date">{{ today_long }}</div></div>
    <div class="seg" role="group" aria-label="Date range">
      {% for value, text in ranges %}<a href="{{ url_for('admin_home', range=value, tab=view.tab) }}" aria-pressed="{{ 'true' if view.preset == value else 'false' }}">{{ text }}</a>{% endfor %}
    </div></div>
  {% for problem in problems %}<div class="problem" role="alert">{{ problem }}</div>{% endfor %}
  {% if view.unreadable %}<div class="problem" role="alert">{{ view.unreadable }} log {{ 'entry' if view.unreadable == 1 else 'entries' }} could not be read, so the numbers below may be missing {{ 'it' if view.unreadable == 1 else 'them' }}. Use Verify log on the Activity log page to see which.</div>{% endif %}
  {% if view.flags_skipped %}<div class="problem" role="alert">{{ view.flags_skipped }} {{ 'flag' if view.flags_skipped == 1 else 'flags' }} could not be worked out, so {{ 'it is' if view.flags_skipped == 1 else 'they are' }} left out of the numbers and the table below.</div>{% endif %}
  {% if not view.intact %}<div class="problem" role="alert">Entry #{{ view.broken_at }} was changed outside the app, so the numbers from that entry on can't be trusted.</div>{% endif %}
  <div class="kpis">
    <div class="panel kpi feature"><div class="kt"><span class="kic">{{ icon('flag') }}</span><span class="pill">{{ view.not_started }} not started</span></div>
      <span class="kl">Flags to handle</span><div class="kval"><span class="v">{{ view.to_handle }}</span><span class="ctx">{{ view.in_progress }} in progress</span></div></div>
    <div class="panel kpi"><div class="kt"><span class="kic">{{ icon('activity') }}</span>{{ change_pill(view.has_previous, view.actions_change, view.actions_diff, false) }}</div>
      <span class="kl">Actions</span><div class="kval"><span class="v">{{ '{:,}'.format(view.actions) }}</span><span class="ctx">vs previous {{ days }} day{{ '' if days == 1 else 's' }}</span></div></div>
    <div class="panel kpi"><div class="kt"><span class="kic">{{ icon('alert') }}</span>{{ change_pill(view.has_previous, view.failures_change, view.failures_diff, true) }}</div>
      <span class="kl">Failures</span><div class="kval"><span class="v">{{ view.failures }}</span><span class="ctx">vs previous {{ days }} day{{ '' if days == 1 else 's' }}</span></div></div>
    <div class="panel kpi"><div class="kt"><span class="kic" style="color:var({{ '--ok' if view.intact else '--bad' }})">{{ icon('shield' if view.intact else 'shieldx') }}</span><span class="pill {{ 'good' if view.intact else 'bad' }}">{{ 'Intact' if view.intact else 'Broken' }}</span></div>
      <span class="kl">Log integrity</span><div class="kval"><span class="v" style="color:var({{ '--ok' if view.intact else '--bad' }})">{{ '&check;'|safe if view.intact else '#' ~ view.broken_at }}</span><span class="ctx">{{ ('{:,}'.format(view.entries) ~ ' entries verified') if view.intact else 'entry changed outside the app' }} &middot; <form method="post" action="{{ url_for('audit_verify') }}"><button class="link-btn" type="submit">Check again</button></form></span></div></div>
  </div>
  <div class="dash">
    <section class="panel chart-card" style="gap:14px">
      <div class="vhead"><div><h2>Failures over time</h2><p class="sub">Each bar is one {{ chart.unit }}: AI steps, saves, reads and syncs that didn't work</p></div>
        <div class="hero"><span class="n">{{ view.failures }}</span><span class="l">failure{{ '' if view.failures == 1 else 's' }} in this range</span></div></div>
      <ul class="vlegend" aria-label="Failure kinds">{% for kind in chart.kinds %}<li class="{{ '' if chart.totals[kind] else 'zero' }}"><i style="background:var(--f{{ loop.index }})"></i>{{ kind }} <b>{{ chart.totals[kind] }}</b></li>{% endfor %}</ul>
      <div class="offline" id="chart-offline" role="alert">Chart can't load. The table below has the same numbers.</div>
      <div class="chart-box" id="chart-box" style="height:240px" hidden><canvas id="c-hl" role="img" aria-label="Failures over time, one bar per {{ chart.unit }}"></canvas></div>
      <div class="meaning"><span class="ic">i</span><div><span class="lbl">What this means</span>{{ chart.caption }}</div></div>
      <details class="numbers" id="chart-numbers" open><summary>Show the numbers</summary><div class="scroll-x" style="margin-top:8px"><table>
        <thead><tr><th>{{ chart.unit|capitalize }}</th>{% for kind in chart.kinds %}<th>{{ kind }}</th>{% endfor %}<th>Total</th></tr></thead>
        <tbody>{% for long in chart.longs %}{% set i = loop.index0 %}<tr><td>{{ long }}</td>{% for kind in chart.kinds %}<td class="num">{{ chart.data[kind][i] }}</td>{% endfor %}<td class="num">{{ chart.sums[i] }}</td></tr>{% endfor %}</tbody></table></div></details>
      <script type="application/json" id="chart-data">{{ chart.json|tojson }}</script>
    </section>
    <section class="panel panel-pad stack" style="gap:14px; min-width:0">
      <div class="vhead"><div><h2>Flags by type</h2><p class="sub">Not resolved, raised in this range</p></div>
        <div class="hero"><span class="n">{{ open_in_range }}</span><span class="l">open flag{{ '' if open_in_range == 1 else 's' }}</span></div></div>
      {% if open_in_range %}
      <div class="stack" style="gap:8px"><div class="sevbar" role="img" aria-label="By priority: {% for key, name, count, colour in severities %}{{ name }} {{ count }}{{ ', ' if not loop.last }}{% endfor %}">{% for key, name, count, colour in severities if count %}<span style="width:{{ count / open_in_range * 100 }}%; background:{{ colour }}" title="{{ name }}: {{ count }}"></span>{% endfor %}</div>
        <ul class="sevkey">{% for key, name, count, colour in severities %}<li><i style="background:{{ colour }}"></i>{{ name }} <b>{{ count }}</b></li>{% endfor %}</ul></div>
      <ul class="ftypes2">{% for t in types %}<li><span class="fic {{ t.css }}" title="{{ t.priority }} priority">{{ icon(t.kind) }}</span><span class="nm">{{ t.name }}<small>{{ t.priority }} priority</small></span><span class="ct"><b>{{ t.count }}</b><span class="pill flat">{{ t.percent }}%</span></span><span class="trk"><span style="width:{{ t.count / types[0].count * 100 }}%"></span></span></li>{% endfor %}</ul>
      {% else %}<p class="muted" style="margin:0">No open flags in this range.</p>{% endif %}
    </section>
  </div>
  <section class="panel" style="min-width:0">
    <div class="sec-head"><div><h2>Flags</h2><p class="muted small" style="margin:2px 0 0">Each flag is a ticket. Click a row to investigate it and update its status. Flags stay here until resolved, whatever the date range.</p></div></div>
    <div class="panel-pad" style="padding-top:0; padding-bottom:10px"><div class="qtabs" role="group" aria-label="Show flags">{% for key, text in tabs %}<a href="{{ url_for('admin_home', range=view.preset, tab=key) }}" aria-pressed="{{ 'true' if view.tab == key else 'false' }}">{{ text }}<b>{{ view.tab_counts[key] }}</b></a>{% endfor %}</div></div>
    <div class="scroll-x"><table class="flags-t"><thead><tr><th style="width:96px">Priority</th><th style="width:20%">Type</th><th style="width:14%">Client</th><th>Detail</th><th style="width:140px">Status</th><th style="width:100px">Raised</th></tr></thead>
      <tbody>
      {% for row in rows %}{% set f = row.ticket.flag %}
      <tr class="ev" data-href="{{ url_for('admin_flag', flag_id=f.flag_id) }}" data-sev="{{ row.css }}">
        <td><span class="sev {{ row.css }}">{{ f.severity_name }}</span></td>
        <td><strong><a href="{{ url_for('admin_flag', flag_id=f.flag_id) }}" style="color:inherit; text-decoration:none">{{ f.name }}</a></strong><span class="assignee mono">{{ f.flag_id }}</span></td>
        <td style="white-space:nowrap">{% if f.client_ref %}{{ row.client or f.client_ref }}{% else %}<span class="muted">System</span>{% endif %}</td>
        <td>{{ row.detail }}</td>
        <td>{{ status_pill(row.ticket.status, row.ticket.status_name) }}</td>
        <td class="num muted" style="white-space:nowrap">{{ f.raised_at|sgt_day }}<span class="assignee">{{ f.raised_at|sgt_ago }}</span></td></tr>
      {% endfor %}
      {% if rows %}{% for n in range(page_size - rows|length) %}<tr class="filler" aria-hidden="true"><td colspan="6"></td></tr>{% endfor %}
      {% else %}<tr class="flags-empty"><td colspan="6" style="height:{{ page_size * 72 }}px">{{ 'Nothing resolved yet. Open a flag and set it to Resolved with a note.' if view.tab == 'resolved' else 'No flags here.' }}</td></tr>{% endif %}
      </tbody></table></div>
    <div class="pager" style="border-top:1px solid var(--line)"><span class="muted">{% if shown_total %}Showing {{ (view.page - 1) * page_size + 1 }}&ndash;{{ [view.page * page_size, shown_total]|min }} of {{ shown_total }}{% else %}0 flags{% endif %}</span>
      <span class="row">
        {% if view.page > 1 %}<a class="btn secondary sm" href="{{ url_for('admin_home', range=view.preset, tab=view.tab, page=view.page - 1) }}">&larr; Prev</a>{% else %}<span class="btn secondary sm" aria-disabled="true">&larr; Prev</span>{% endif %}
        <span class="num">Page {{ view.page }} of {{ view.page_count }}</span>
        {% if view.page < view.page_count %}<a class="btn secondary sm" href="{{ url_for('admin_home', range=view.preset, tab=view.tab, page=view.page + 1) }}">Next &rarr;</a>{% else %}<span class="btn secondary sm" aria-disabled="true">Next &rarr;</span>{% endif %}
      </span></div></section>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js" integrity="sha384-bs/nf9FbdNouRbMiFcrcZfLXYPKiPaGVGplVbv7dLGECccEXDW+S3zjqSKR5ZEaD sha512-CQBWl4fJHWbryGE+Pc7UAxWMUMNMWzWxF4SQo9CgkJIN1kx6djDQZjh3Y8SZ1d+6I+1zze6Z7kHXO7q3UyZAWw==" crossorigin="anonymous"></script>
<script>
(function () {
  document.querySelectorAll('tr.ev[data-href]').forEach(function (row) {
    row.style.cursor = 'pointer';
    row.addEventListener('click', function (event) {
      if (!event.target.closest('a')) { window.location = row.dataset.href; }
    });
  });
  var box = document.getElementById('chart-box'), note = document.getElementById('chart-offline'),
      numbers = document.getElementById('chart-numbers');
  if (!window.Chart || !box) { return; }
  note.hidden = true; box.hidden = false; numbers.open = false;
  var cfg = JSON.parse(document.getElementById('chart-data').textContent);
  var style = getComputedStyle(document.documentElement);
  function css(name) { return style.getPropertyValue(name).trim(); }
  Chart.defaults.font.family = css('--font') || 'system-ui';
  Chart.defaults.color = css('--muted');
  var colours = [css('--f1'), css('--f2'), css('--f3'), css('--f4')];
  var topIndex = cfg.labels.map(function (_, j) {
    var top = -1;
    cfg.kinds.forEach(function (kind, i) { if (cfg.data[kind][j]) { top = i; } });
    return top;
  });
  new Chart(document.getElementById('c-hl'), {
    type: 'bar',
    data: { labels: cfg.labels, datasets: cfg.kinds.map(function (kind, i) {
      return { label: kind, data: cfg.data[kind], backgroundColor: colours[i], borderColor: css('--surface'),
        borderWidth: { top: 2, bottom: 0, left: 0, right: 0 }, borderSkipped: false,
        borderRadius: function (c) { return topIndex[c.dataIndex] === i ? { topLeft: 6, topRight: 6, bottomLeft: 0, bottomRight: 0 } : 0; },
        maxBarThickness: 22, categoryPercentage: .7, barPercentage: .9 };
    }) },
    options: { responsive: true, maintainAspectRatio: false, animation: false,
      interaction: { mode: 'index', intersect: false },
      plugins: { legend: { display: false },
        tooltip: { backgroundColor: '#151a21', titleColor: '#fff', bodyColor: '#e6e9ee', footerColor: '#fff', cornerRadius: 12,
          padding: 12, boxPadding: 6, usePointStyle: true, caretSize: 6,
          filter: function (item) { return item.raw > 0; },
          callbacks: { title: function (items) { return cfg.longs[items[0].dataIndex]; },
            labelPointStyle: function () { return { pointStyle: 'circle', rotation: 0 }; },
            footer: function (items) {
              var j = items[0].dataIndex, total = 0;
              cfg.kinds.forEach(function (kind) { total += cfg.data[kind][j]; });
              return total ? 'Total ' + total : 'No failures';
            } } } },
      scales: { x: { stacked: true, grid: { display: false }, border: { color: css('--line') },
          ticks: { color: css('--muted'), maxRotation: 0, autoSkip: true, maxTicksLimit: 7, font: { size: 11 } } },
        y: { stacked: true, beginAtZero: true, grace: '10%', grid: { color: css('--line'), lineWidth: 1 }, border: { display: false },
          ticks: { precision: 0, color: css('--muted'), font: { size: 11 }, maxTicksLimit: 5 } } } }
  });
})();
</script>
{% endif %}
{% endblock %}
"""

FLAG = """{% extends "base.html" %}
{% from "flag_parts.html" import detail, status_pill, badge, alink %}
{% block title %}{{ ticket.flag.flag_id ~ ' — ' if ticket }}Flag — Orbit{% endblock %}
{% block content %}
<div class="stack">
  <a href="{{ url_for('admin_home') }}" class="muted" style="text-decoration:none">&larr; All flags</a>
  {% if error %}
  <div class="panel empty" role="alert">{{ error }}</div>
  {% elif not ticket %}
  <div class="panel empty">{{ gone }}</div>
  {% else %}
  {% set f = ticket.flag %}
  {% set draft = draft_status or ticket.status %}
  <div class="ticket"><div class="stack" style="min-width:0">
    <section class="panel panel-pad"><div class="eyebrow mono">{{ f.flag_id }} &middot; {{ f.name }}</div><h1 style="margin-top:4px">{{ f.headline }}</h1>
      <div class="meta-row"><span class="sev {{ sev_css }}">{{ f.severity_name }}</span>{{ status_pill(ticket.status, ticket.status_name) }}<span>Raised <b>{{ f.raised_at|sgt_day }} {{ f.raised_at|sgt_hm }}</b> ({{ f.raised_at|sgt_ago }})</span></div></section>
    <section class="panel panel-pad stack" style="gap:10px"><h2>What happened</h2>{{ detail(pic) }}{% if f.meaning %}<p class="muted" style="margin:0; font-size:.9rem">{{ f.meaning }}</p>{% endif %}</section>
    {% if evidence %}<section class="panel panel-pad stack" style="gap:10px"><h2>Evidence</h2><ul class="evid">{% for item in evidence %}<li><a href="{{ item.href }}"><span>{{ item.text }}</span>{% if item.badge %}<span>{{ badge(item.badge) }}</span>{% else %}<span class="muted{{ ' mono' if item.mono }}">{{ item.side }}</span>{% endif %}</a></li>{% endfor %}</ul></section>{% endif %}
  </div>
  <aside class="side">
    <form class="panel panel-pad stack upd" id="ticket-form" method="post" action="{{ url_for('admin_flag', flag_id=f.flag_id) }}" style="gap:12px" novalidate data-current="{{ ticket.status }}">
      <h2>Update this flag</h2>
      <label class="field" for="t-status"><span class="eyebrow">Status</span><select id="t-status" name="status">{% for key, name in statuses %}<option value="{{ key }}" data-name="{{ name }}"{{ ' selected' if draft == key }}>{{ name }}{{ ' (current)' if key == ticket.status }}</option>{% endfor %}</select></label>
      <label class="field" for="t-wait" id="wait-block"{{ '' if draft == 'followup' else ' hidden' }}><span class="eyebrow">Waiting on</span><select id="t-wait" name="waiting_on"><option value="">Choose&hellip;</option>{% for who in waiting_on_choices %}<option{{ ' selected' if draft_wait == who }}>{{ who }}</option>{% endfor %}</select></label>
      <fieldset id="outcome-block" style="border:0; padding:0; margin:0"{{ '' if draft == 'resolved' and ticket.status != 'resolved' else ' hidden' }}><legend class="eyebrow" style="margin-bottom:6px">Outcome</legend><div class="radios">{% for key, name in outcomes %}<label><input type="radio" name="outcome" value="{{ key }}"{{ ' checked' if draft_outcome == key }}><span>{{ name }}</span></label>{% endfor %}</div></fieldset>
      <label class="field" for="t-note"><span class="eyebrow" id="note-label">{{ 'Note' if draft == ticket.status else 'Why' }} (required)</span><textarea id="t-note" name="note" maxlength="500" placeholder="{{ 'What you found and why it can be closed' if draft == 'resolved' else ('What you asked, and whom' if draft == 'followup' else 'What you are doing next') }}">{{ draft_note }}</textarea></label>
      {% for message in errors %}<div class="err" role="alert">{{ message }}</div>{% endfor %}
      <button class="btn" type="submit" id="t-save" style="justify-content:center">{{ 'Add note' if draft == ticket.status else ('Reopen flag' if ticket.status == 'resolved' else 'Save: ' ~ statuses_by_key[draft]) }}</button>
      <p class="muted small" style="margin:0">Every update is saved in the audit log, so it can't be quietly changed later.</p>
    </form>
    <section class="panel panel-pad stack" style="gap:6px"><h2>Activity</h2><ul class="thist">
      {% for h in history %}<li><span class="avatar">{{ '&#9881;'|safe if h.by == 'System' else h.by|initials }}</span><div><div class="row" style="gap:6px"><b>{{ h.by }}</b>{% if h.get('from') and h['from'] != h['to'] %}{{ status_pill(h['from'], statuses_by_key[h['from']]) }}&rarr;{{ status_pill(h['to'], statuses_by_key[h['to']]) }}{% elif h.get('from') %}<small>added a note</small>{% else %}<small>opened the flag</small>{% endif %}</div>
        <small>{{ h.at|sgt_day }} {{ h.at|sgt_hm }}{% if h.get('waiting_on') %} &middot; waiting on {{ h.waiting_on }}{% endif %}</small>{% if h.get('outcome') %}<div style="margin-top:4px; font-size:.86rem"><b>Outcome:</b> {{ outcomes_by_key.get(h.outcome, h.outcome) }}</div>{% endif %}{% if h.note %}<p class="note">{{ h.note }}</p>{% endif %}</div></li>{% endfor %}
    </ul></section>
  </aside></div>
  <script>
  (function () {
    var form = document.getElementById('ticket-form'), select = document.getElementById('t-status');
    var wait = document.getElementById('wait-block'), outcome = document.getElementById('outcome-block');
    var label = document.getElementById('note-label'), note = document.getElementById('t-note'), save = document.getElementById('t-save');
    var current = form.dataset.current;
    function update() {
      var draft = select.value, name = select.options[select.selectedIndex].dataset.name;
      wait.hidden = draft !== 'followup';
      outcome.hidden = !(draft === 'resolved' && current !== 'resolved');
      label.textContent = (draft === current ? 'Note' : 'Why') + ' (required)';
      note.placeholder = draft === 'resolved' ? 'What you found and why it can be closed'
        : (draft === 'followup' ? 'What you asked, and whom' : 'What you are doing next');
      save.textContent = draft === current ? 'Add note' : (current === 'resolved' ? 'Reopen flag' : 'Save: ' + name);
    }
    select.addEventListener('change', update);
  })();
  </script>
  {% endif %}
</div>
{% endblock %}
"""

TEMPLATES: dict[str, str] = {
    "audit_rows.html": AUDIT_ROWS,
    "flag_parts.html": FLAG_PARTS,
    "overview.html": OVERVIEW,
    "flag.html": FLAG,
    "audit.html": AUDIT,
    "signin.html": SIGNIN,
    "forbidden.html": FORBIDDEN,
    "base.html": BASE,
    "home.html": HOME,
    "client_form.html": FORM,
    "client_view.html": VIEW,
    "assess_loading.html": ASSESS_LOADING,
    "assess_result.html": ASSESS_RESULT,
    "assessments.html": ASSESSMENTS,
    "error.html": ERROR,
}
