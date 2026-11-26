from html import escape


def render_not_found_page(alias: str) -> str:
    safe_alias = escape(alias)
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Enlace no encontrado · MochoLink</title>
  <style>
    :root {{ --bg: #f6f7fb; --card: #ffffff; --text: #1f2330; --muted: #646b7e; --accent: #4f5bd5; }}
    @media (prefers-color-scheme: dark) {{
      :root {{ --bg: #12141b; --card: #1c1f2a; --text: #e8eaf2; --muted: #9aa1b5; --accent: #8b94ff; }}
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; min-height: 100vh; display: grid; place-items: center; padding: 16px;
           background: var(--bg); color: var(--text);
           font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }}
    main {{ max-width: 440px; width: 100%; background: var(--card); border-radius: 16px;
           padding: 40px 32px; text-align: center; box-shadow: 0 8px 30px rgba(0,0,0,.08); }}
    .code {{ font-size: 64px; font-weight: 800; color: var(--accent); margin: 0; letter-spacing: -2px; }}
    h1 {{ font-size: 20px; margin: 8px 0 12px; }}
    p {{ color: var(--muted); line-height: 1.5; margin: 0 0 24px; }}
    code {{ background: var(--bg); padding: 2px 6px; border-radius: 6px; word-break: break-all; }}
    .actions {{ display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; }}
    a, button {{ font: inherit; font-weight: 600; padding: 10px 18px; border-radius: 10px;
                cursor: pointer; text-decoration: none; border: 2px solid var(--accent); }}
    .primary {{ background: var(--accent); color: #fff; }}
    .secondary {{ background: transparent; color: var(--accent); }}
  </style>
</head>
<body>
  <main>
    <p class="code">404</p>
    <h1>Este enlace no existe o ha expirado</h1>
    <p>No encontramos ningún enlace activo para <code>/{safe_alias}</code>.
       Revisa que esté bien escrito o pide a quien te lo compartió uno nuevo.</p>
    <div class="actions">
      <button class="secondary" type="button" onclick="history.length > 1 ? history.back() : location.assign('/')">Volver</button>
      <a class="primary" href="/docs">Crear un enlace</a>
    </div>
  </main>
</body>
</html>"""
