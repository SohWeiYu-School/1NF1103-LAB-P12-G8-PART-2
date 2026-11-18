"""The new split-screen sign-in page, as the string WebApp's TEMPLATES dictionary holds for "signin.html".

Use it in app/interface/web_templates.py:

    from app.interface.signin_template import SIGNIN_HTML
    TEMPLATES["signin.html"] = SIGNIN_HTML      # after TEMPLATES is built (or put it in the dict itself)

It is a whole page (it does not extend your base layout) and reads what WebApp.signin() already passes:
problem, name, demo (a list of {"name", "password"}), max_text, and the context's portal.
The logo is app/interface/static/logo.png (Flask serves the static folder next to web_app.py).
"""

SIGNIN_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ 'Admin' if portal == 'admin' else 'Officer' }} sign-in · Orbit</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono&display=swap" rel="stylesheet">
<style>
:root{--navy:#1f4e79;--ring:rgba(255,255,255,.22);--page:#f0f2f6;--ink:#17283b;--muted:#5a6b7e;
--border:#d9dee6;--gold:#e6a21e;--demo-bg:#fdf5e0;--demo-line:#efdfb0;--badge:#7a5200;--error:#b42318;
--font:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",Arial,sans-serif;
--mono:"IBM Plex Mono",ui-monospace,Consolas,monospace}
*{box-sizing:border-box}html,body{height:100%;margin:0}
body{font-family:var(--font);color:var(--ink);background:var(--page)}
.split{display:grid;grid-template-columns:5fr 6fr;min-height:100%}
.brand{position:relative;overflow:hidden;background:var(--navy);color:#fff;padding:40px 48px;display:flex;flex-direction:column}
.logo{display:flex;align-items:center;gap:12px;font-weight:700;font-size:1.25rem}
.logo img{width:40px;height:40px;border-radius:10px;object-fit:contain}
.pitch{margin-top:auto;margin-bottom:18%;position:relative;z-index:1;max-width:26rem}
.pitch h1{font-size:clamp(1.8rem,2.8vw,2.5rem);line-height:1.18;margin:0 0 18px}
.pitch p{margin:0;font-size:.95rem;line-height:1.5;color:#d6e4f2}
.pitch p.kicker{color:var(--gold);font-size:.72rem;font-weight:600;letter-spacing:.14em;text-transform:uppercase;margin:0 0 16px}
.rings{position:absolute;left:-10%;bottom:-26%;width:120%;height:auto;pointer-events:none}
.rings circle{fill:none;stroke:var(--ring);stroke-width:1.5}.rings .dot{fill:var(--gold);stroke:none}
.side{display:flex;align-items:center;justify-content:center;padding:40px 24px}
.stack{width:100%;max-width:350px;display:grid;gap:16px}
.card{background:#fff;border-radius:14px;padding:26px 28px 22px;box-shadow:0 1px 2px rgba(23,40,59,.06),0 6px 20px rgba(23,40,59,.05)}
.card h2{margin:0;font-size:1.35rem}
.card h2::after{content:"";display:block;width:38px;height:3px;background:var(--gold);border-radius:2px;margin:8px 0 20px}
label{display:block;font-size:.68rem;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin:0 0 6px}
input{width:100%;font:inherit;font-size:.9rem;padding:11px 12px;margin-bottom:16px;border:1px solid var(--border);border-radius:8px;color:var(--ink);background:#fff}
input:focus{outline:none;border-color:var(--gold);box-shadow:0 0 0 2px rgba(230,162,30,.25)}
button{width:100%;font:inherit;font-weight:600;font-size:.85rem;padding:12px;border:0;border-radius:8px;background:var(--navy);color:#fff;cursor:pointer}
button:hover{background:#18405f}button:focus-visible{outline:3px solid var(--gold);outline-offset:2px}
.error{background:#fdecea;color:var(--error);border-radius:8px;padding:10px 12px;font-size:.85rem;margin:0 0 16px}
.alt{margin:16px 0 0;font-size:.75rem;color:var(--muted)}.alt a{color:var(--navy)}
.demo{background:var(--demo-bg);border:1px solid var(--demo-line);border-radius:12px;padding:14px 18px 8px;font-size:.78rem}
.demo header{display:flex;align-items:center;gap:10px;margin-bottom:8px;font-weight:600;font-size:.85rem}
.badge{background:var(--badge);color:#fff;font-size:.6rem;font-weight:700;letter-spacing:.08em;padding:4px 7px;border-radius:4px}
.demo table{width:100%;border-collapse:collapse}.demo td{padding:6px 0;border-top:1px solid var(--demo-line)}
.demo td:nth-child(2){font-family:var(--mono);font-size:.75rem}
.demo td:last-child{text-align:right;width:1%}
.demo button.use{width:auto;padding:3px 12px;font-size:.78rem;font-weight:500;background:#fff;color:var(--ink);border:1px solid var(--border)}
.demo button.use:hover{background:var(--page)}
@media(max-width:820px){.split{grid-template-columns:1fr}.brand{padding:24px}
.pitch{margin:28px 0 8px}.pitch h1{font-size:1.5rem}.rings{display:none}}
</style>
</head>
<body>
<div class="split">

  <section class="brand">
    <div class="logo"><img src="{{ url_for('static', filename='logo.svg') }}" alt="">Orbit</div>
    <div class="pitch">
      <p class="kicker">Source of wealth screening</p>
      <h1>Crime scan, forecast and benchmark in one verdict.</h1>
      <p>Clients, assessments and client history for compliance officers.</p>
    </div>
    <svg class="rings" viewBox="0 0 600 600" aria-hidden="true">
      <circle cx="300" cy="300" r="290"/><circle cx="300" cy="300" r="225"/>
      <circle cx="300" cy="300" r="160"/><circle cx="300" cy="300" r="95"/>
      <circle class="dot" cx="212" cy="365" r="9"/>
    </svg>
  </section>

  <main class="side">
    <div class="stack">
      <form class="card" method="post" action="">
        <h2>{{ 'Admin' if portal == 'admin' else 'Officer' }} sign-in</h2>

        {% for message in get_flashed_messages() %}<p class="error" role="alert">{{ message }}</p>{% endfor %}
        {% if problem %}<p class="error" role="alert">{{ problem }}</p>{% endif %}

        <label for="name">Name</label>
        <input id="name" name="name" type="text" value="{{ name }}" placeholder="e.g. Shareen"
               maxlength="{{ max_text }}" autocomplete="username" autofocus>

        <label for="password">Password</label>
        <input id="password" name="password" type="password" maxlength="{{ max_text }}"
               autocomplete="current-password">

        <button type="submit">Sign in</button>
        <p class="alt">
          {% if portal == 'admin' %}Officer? <a href="{{ url_for('signin') }}">Officer sign-in is at /signin</a>
          {% else %}System admin? <a href="{{ url_for('admin_signin') }}">Admin sign-in is at /admin</a>{% endif %}
        </p>
      </form>

      {% if demo %}
      <aside class="demo">
        <header><span class="badge">DEMO ONLY</span> Demo accounts</header>
        <table>{% for account in demo %}<tr><td>{{ account.name }}</td><td>{{ account.password }}</td><td><button type="button" class="use" data-name="{{ account.name }}" data-password="{{ account.password }}">Use</button></td></tr>{% endfor %}</table>
      </aside>
      {% endif %}
    </div>
  </main>

</div>
<script>
document.querySelectorAll('.demo button.use').forEach(function (button) {
  button.addEventListener('click', function () {
    document.getElementById('name').value = button.dataset.name;
    document.getElementById('password').value = button.dataset.password;
    document.getElementById('password').focus();
  });
});
</script>
</body>
</html>
"""
