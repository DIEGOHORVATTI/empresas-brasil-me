"""API + frontend para consultar empresas do SQLite com filtros.

Rodar:  uvicorn src.api.web:app --reload
Depois: http://localhost:8000
"""

import sqlite3
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import Body, FastAPI, Query
from fastapi.staticfiles import StaticFiles

from src.config import DB_PATH
from src.etl.database import get_connection as get_write_conn
from src.etl.database import init_db
from src.marketing import brevo
from src.marketing.templates import NICHOS, corpo_para_html, montar_email, nome_empresa

app = FastAPI(title="Empresas Brasil")
HERE = Path(__file__).parent

# Garante tabelas novas (ex: maps_empresas) em bancos criados antes do schema atual.
_c = get_write_conn(); init_db(_c); _c.close()


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/api/empresas")
def empresas(
    uf: list[str] = Query(default=[]),
    situacao: list[str] = Query(default=[]),
    cnae: list[str] = Query(default=[]),  # códigos CNAE (7 dígitos)
    porte: list[str] = Query(default=[]),
    q: str = "",  # busca em razão social / nome fantasia
    data_inicio_min: str = "",  # YYYYMMDD
    data_inicio_max: str = "",
    tem_email: bool = False,
    mei: str = "",  # S / N
    nicho: list[str] = Query(default=[]),  # slugs de nicho (filtra por divisão CNAE)
    capital_min: float = 0,
    capital_max: float = 0,
    sort: str = "data_inicio_atividade",
    order: str = "desc",
    limit: int = Query(50, le=500),
    offset: int = 0,
):
    where, params = [], []

    def add_in(col: str, vals: list[str]):
        where.append(f"{col} IN ({','.join('?' * len(vals))})")
        params.extend(vals)

    if uf:
        add_in("e.uf", [u.upper() for u in uf])
    if situacao:
        add_in("e.situacao_cadastral", situacao)
    if cnae:
        add_in("e.cnae_fiscal_principal", cnae)
    if porte:
        add_in("emp.porte_empresa", porte)
    if data_inicio_min:
        where.append("e.data_inicio_atividade >= ?"); params.append(data_inicio_min)
    if data_inicio_max:
        where.append("e.data_inicio_atividade <= ?"); params.append(data_inicio_max)
    if tem_email:
        where.append("e.email != ''")
    if q:
        where.append("(emp.razao_social LIKE ? OR e.nome_fantasia LIKE ?)")
        params += [f"%{q.upper()}%", f"%{q.upper()}%"]
    if mei:
        where.append("s.opcao_mei = ?"); params.append(mei.upper())
    if nicho:
        # cada nicho vira suas divisões CNAE; indústria é a faixa 10 a 33
        divs = [d for s in nicho for d in NICHOS.get(s, {}).get("prefixos", [])]
        conds = []
        if divs:
            conds.append(f"substr(e.cnae_fiscal_principal, 1, 2) IN ({','.join('?' * len(divs))})")
            params.extend(divs)
        if "industria" in nicho:
            conds.append("CAST(substr(e.cnae_fiscal_principal, 1, 2) AS INT) BETWEEN 10 AND 33")
        if conds:
            where.append("(" + " OR ".join(conds) + ")")
    cap = "CAST(REPLACE(emp.capital_social, ',', '.') AS REAL)"
    if capital_min:
        where.append(f"{cap} >= ?"); params.append(capital_min)
    if capital_max:
        where.append(f"{cap} <= ?"); params.append(capital_max)

    clause = ("WHERE " + " AND ".join(where)) if where else ""

    # ORDER BY com whitelist (evita SQL injection na coluna)
    sort_cols = {
        "razao_social": "emp.razao_social",
        "uf": "e.uf",
        "data_inicio_atividade": "e.data_inicio_atividade",
        "capital_social": "CAST(REPLACE(emp.capital_social, ',', '.') AS REAL)",
        "porte_empresa": "emp.porte_empresa",
        "situacao_cadastral": "e.situacao_cadastral",
        "email": "e.email",
        "envio_status": "ev.status",
    }
    col = sort_cols.get(sort, "e.data_inicio_atividade")
    direction = "ASC" if order.lower() == "asc" else "DESC"

    sql = f"""
        SELECT e.cnpj_basico, e.cnpj_ordem, e.cnpj_dv, e.nome_fantasia,
               e.uf, e.municipio, e.email, e.telefone_1, e.ddd_1,
               e.data_inicio_atividade, e.situacao_cadastral,
               e.cnae_fiscal_principal, c.descricao AS cnae_desc,
               emp.razao_social, emp.porte_empresa, emp.capital_social, s.opcao_mei,
               ev.status AS envio_status, ev.template AS envio_template,
               ev.provider AS envio_provider, ev.enviado_em
        FROM estabelecimentos e
        LEFT JOIN empresas emp ON emp.cnpj_basico = e.cnpj_basico
        LEFT JOIN cnaes c ON c.codigo = e.cnae_fiscal_principal
        LEFT JOIN simples s ON s.cnpj_basico = e.cnpj_basico
        LEFT JOIN envios ev ON ev.cnpj = e.cnpj_basico || e.cnpj_ordem || e.cnpj_dv
        {clause}
        ORDER BY {col} {direction}
        LIMIT ? OFFSET ?
    """
    # Total do filtro (pra paginação saber quantas páginas/itens existem).
    count_sql = f"""
        SELECT COUNT(*) FROM estabelecimentos e
        LEFT JOIN empresas emp ON emp.cnpj_basico = e.cnpj_basico
        LEFT JOIN simples s ON s.cnpj_basico = e.cnpj_basico
        {clause}
    """
    with _conn() as conn:
        rows = conn.execute(sql, params + [limit, offset]).fetchall()
        total = conn.execute(count_sql, params).fetchone()[0]
    results = [dict(r) for r in rows]
    for x in results:  # nome do dono limpo (sem CPF do MEI, sem CAPS, sem LTDA)
        x["razao_limpa"] = nome_empresa(x.get("razao_social") or "", x.get("nome_fantasia") or "")
    return {"count": len(rows), "total": total, "results": results}


# --- WhatsApp: proxy pro serviço Baileys (mailer/whatsapp.mjs na porta 3001) ---
WA_BASE = "http://localhost:3001"


@app.get("/api/whatsapp/status")
def whatsapp_status():
    """Retorna {connected, qr} — o QR é data-URL pra vincular o WhatsApp."""
    try:
        return httpx.get(f"{WA_BASE}/status", timeout=10).json()
    except httpx.HTTPError:
        return {"connected": False, "qr": None, "offline": True}


@app.get("/api/whatsapp/check")
def whatsapp_check(ddd: str = "", telefone: str = ""):
    """Confere se o número tem WhatsApp. Retorna {exists: bool} ou {error}."""
    numero = f"{ddd}{telefone}"
    try:
        return httpx.get(f"{WA_BASE}/check", params={"n": numero}, timeout=30).json()
    except httpx.HTTPError:
        return {"error": "serviço whatsapp offline"}


@app.post("/api/maps/buscar")
def maps_buscar(body: dict = Body(...)):
    """Coleta empresas do Google Maps num raio da cidade e grava em maps_empresas.
    Body: {query, cidade, uf?, zoom?, max?}. Bloqueante (abre o browser) — pode levar
    minutos; o front mostra spinner."""
    from src.maps.collector import coletar
    try:
        return coletar(
            query=(body.get("query") or "").strip(),
            cidade=(body.get("cidade") or "").strip(),
            uf=(body.get("uf") or "").strip(),
            zoom=int(body.get("zoom") or 14),
            max_resultados=int(body.get("max") or 20),
            lat=body.get("lat"), lng=body.get("lng"),  # centro do mapa, se houver
        )
    except Exception as e:  # cidade não achada, Playwright ausente, etc.
        return {"erro": str(e), "count": 0, "results": []}


@app.get("/api/maps/geocode")
def maps_geocode(cidade: str, uf: str = ""):
    from src.maps.collector import geocode
    try:
        lat, lng = geocode(cidade, uf)
        return {"lat": lat, "lng": lng}
    except Exception as e:
        return {"erro": str(e)}


@app.get("/api/maps/reverse")
def maps_reverse(lat: float, lng: float):
    from src.maps.collector import reverse
    try:
        return reverse(lat, lng)
    except Exception as e:
        return {"erro": str(e)}


@app.get("/api/maps/empresas")
def maps_empresas(cidade: str = "", q: str = "", limit: int = Query(200, le=1000),
                  offset: int = 0):
    where, params = [], []
    if cidade:
        where.append("cidade = ?"); params.append(cidade)
    if q:
        where.append("(nome LIKE ? OR categoria LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    with _conn() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM maps_empresas {clause}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM maps_empresas {clause} ORDER BY coletado_em DESC "
            f"LIMIT ? OFFSET ?", params + [limit, offset]).fetchall()
    return {"total": total, "results": [dict(r) for r in rows]}


@app.get("/api/cnaes")
def cnaes():
    with _conn() as conn:
        rows = conn.execute(
            "SELECT codigo, descricao FROM cnaes ORDER BY codigo"
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/ufs")
def ufs():
    with _conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT uf FROM estabelecimentos WHERE uf != '' ORDER BY uf"
        ).fetchall()
    return [r["uf"] for r in rows]


@app.get("/api/campanha/config")
def campanha_config():
    ok, msg = brevo.config_ok()
    return {"ok": ok, "msg": msg}


@app.get("/api/campanha/modelos")
def campanha_modelos():
    """Todos os modelos de email salvos, um por nicho (com exemplo preenchido)."""
    exemplo = {"razao_social": "PADARIA DO JOAO LTDA", "nome_fantasia": ""}
    out = []
    for slug in NICHOS:
        e = montar_email({**exemplo, "cnae_fiscal_principal": ""}, slug=slug)
        out.append({"nicho": slug, "assunto": e["assunto"], "corpo": e["corpo"]})
    return out


@app.get("/api/campanha/stats")
def campanha_stats():
    """Envios de hoje (pra acompanhar a cota diária do Brevo) + total."""
    hoje_sql = "substr(enviado_em, 1, 10) = date('now', 'localtime')"
    with _conn() as conn:
        hoje = conn.execute(f"SELECT count(*) FROM envios WHERE {hoje_sql}").fetchone()[0]
        total = conn.execute("SELECT count(*) FROM envios").fetchone()[0]
        rows = conn.execute(
            f"SELECT email, template, status, enviado_em FROM envios "
            f"WHERE {hoje_sql} ORDER BY enviado_em DESC LIMIT 300"
        ).fetchall()
    return {"hoje": hoje, "total": total, "limite_dia": 300,
            "enviados": [dict(r) for r in rows]}


@app.post("/api/campanha/preview")
def campanha_preview(leads: list[dict] = Body(...)):
    """Monta o email (assunto + corpo) de cada lead selecionado, pra revisar."""
    out = []
    for lead in leads:
        email = montar_email(lead)
        email["cnpj"] = lead.get("cnpj", "")
        email["email"] = lead.get("email", "")
        email["razao_social"] = lead.get("razao_social", "")
        out.append(email)
    return out


@app.post("/api/campanha/enviar")
def campanha_enviar(emails: list[dict] = Body(...)):
    """Envia os emails (já revisados/editados) via Brevo e registra em `envios`."""
    ok, msg = brevo.config_ok()
    if not ok:
        return {"erro": msg, "resultados": []}

    conn = get_write_conn()
    resultados = []
    for e in emails:
        if not e.get("email"):
            resultados.append({"cnpj": e.get("cnpj", ""), "ok": False, "msg": "sem email"})
            continue
        html = corpo_para_html(e["corpo"])
        sucesso, info = brevo.enviar(e["email"], e["assunto"], e["corpo"], html)
        if sucesso:
            conn.execute(
                "INSERT OR REPLACE INTO envios VALUES (?,?,?,?,?,?)",
                (e.get("cnpj", ""), e["email"], e.get("nicho", ""),
                 "enviado", "brevo", datetime.now().isoformat(timespec="seconds")),
            )
        resultados.append({"cnpj": e.get("cnpj", ""), "email": e["email"], "ok": sucesso, "msg": info})
    conn.commit()
    conn.close()
    return {"resultados": resultados}


# Serve o build do Vite (frontend/). Rode `cd frontend && npm run build`.
# Mount por último para não capturar as rotas /api acima.
DIST = HERE / "dist"
if DIST.exists():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="app")
