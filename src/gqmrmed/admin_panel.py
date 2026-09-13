"""Minimal private browser panel for operations; API remains protected by ADMIN_SECRET."""

# The embedded HTML/JavaScript is intentionally kept readable as one browser document.
# Ruff's Python line-length rule is not meaningful for the embedded markup.
# ruff: noqa: E501

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["admin-panel"])

_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>GQMRMed Admin</title><style>body{font-family:system-ui,sans-serif;max-width:900px;margin:40px auto;padding:0 16px}input,button{padding:9px;margin:4px}section{border:1px solid #ddd;border-radius:12px;padding:16px;margin:16px 0}pre{white-space:pre-wrap}</style></head>
<body><h1>GQMRMed Admin</h1><p>Private operations panel. Keep the admin secret private.</p>
<section><label>Admin secret <input id="secret" type="password" size="40"></label><button onclick="overview()">Load overview</button><pre id="out"></pre></section>
<section><h2>Activation codes</h2><input id="plan" value="PLUS"><input id="days" type="number" value="30" min="1"><input id="count" type="number" value="1" min="1" max="100"><button onclick="codes()">Generate</button><pre id="codesout"></pre></section>
<section><h2>Pending payments</h2><button onclick="payments()">Refresh</button><pre id="paymentsout"></pre></section>
<script>
const h=()=>({'X-Admin-Secret':document.getElementById('secret').value});
async function overview(){const r=await fetch('/admin/overview',{headers:h()});document.getElementById('out').textContent=JSON.stringify(await r.json(),null,2)}
async function codes(){const body={plan:document.getElementById('plan').value,duration_days:+document.getElementById('days').value,count:+document.getElementById('count').value};const r=await fetch('/admin/activation-codes',{method:'POST',headers:{...h(),'Content-Type':'application/json'},body:JSON.stringify(body)});document.getElementById('codesout').textContent=JSON.stringify(await r.json(),null,2)}
async function payments(){const r=await fetch('/admin/payments',{headers:h()});document.getElementById('paymentsout').textContent=JSON.stringify(await r.json(),null,2)}
</script></body></html>"""


@router.get("/admin/panel", response_class=HTMLResponse, include_in_schema=False)
async def admin_panel() -> HTMLResponse:
    """Serve the operator UI; every data action still requires the API secret."""
    return HTMLResponse(_HTML)
