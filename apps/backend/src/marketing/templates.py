"""Copies de prospecção por nicho + montagem do email (assunto, corpo).

O CONTEÚDO vive em nichos.json (raiz), fonte única compartilhada com o mailer/.
Este módulo só carrega o JSON e monta o email de cada lead.
"""

import json
import re
from pathlib import Path

_DATA = json.loads((Path(__file__).parent.parent.parent / "nichos.json").read_text("utf-8"))
NICHOS: dict[str, dict] = _DATA["nichos"]
ASSUNTOS = {slug: n["assunto"] for slug, n in NICHOS.items()}
ASSINATURA = _DATA["assinatura"]
OPT_OUT = _DATA["opt_out"]

_PREFIXO_SLUG = {p: slug for slug, n in NICHOS.items() for p in n["prefixos"]}
_CONECT = {"de", "da", "do", "das", "dos", "e"}
_SUFIXOS = {"ltda", "me", "epp", "eireli", "eirl", "mei", "ss"}


def nicho_do_cnae(cnae: str) -> str:
    div = (cnae or "").zfill(7)[:2]
    if div in _PREFIXO_SLUG:
        return _PREFIXO_SLUG[div]
    if div.isdigit() and 10 <= int(div) <= 33:
        return "industria"
    return "geral"


def nome_empresa(razao_social: str = "", nome_fantasia: str = "") -> str:
    s = (razao_social or nome_fantasia or "").strip()
    if not s:
        return ""
    s = re.sub(r"\bs[./]?a\b", " ", s, flags=re.I)
    s = re.sub(r"[-–—]", " ", s)
    s = re.sub(r"\d[\d./-]*", " ", s)  # números e CPF/CNPJ do MEI
    tokens = [t for t in s.split() if t]
    while len(tokens) > 1 and tokens[-1].lower().replace(".", "") in _SUFIXOS:
        tokens.pop()
    if not tokens:
        return ""
    out = []
    for i, w in enumerate(tokens):
        low = w.lower()
        out.append(low if i > 0 and low in _CONECT else low[:1].upper() + low[1:])
    return " ".join(out)


def primeiro_nome(nome: str) -> str:
    return nome.split(" ")[0] if nome else ""


def montar_email(lead: dict, slug: str | None = None) -> dict:
    """Monta o email de um lead: escolhe o nicho, preenche nome e assinatura."""
    slug = slug or nicho_do_cnae(lead.get("cnae_fiscal_principal", ""))
    n = NICHOS.get(slug, NICHOS["geral"])
    nome = nome_empresa(lead.get("razao_social", ""), lead.get("nome_fantasia", ""))
    pnome = primeiro_nome(nome)
    saud = f"Oi, {pnome}" if pnome else "Oi"

    def fill(t: str) -> str:
        return t.replace("{saudacao}", saud).replace("{nome}", nome or "sua empresa")

    corpo = "\n\n".join(fill(p) for p in n["paragrafos"])
    corpo = f"{corpo}\n\n{ASSINATURA}\n\n{OPT_OUT}"
    assunto = ASSUNTOS.get(slug, ASSUNTOS["geral"]).replace("{nome}", pnome or "você")
    return {"nicho": slug, "assunto": assunto, "corpo": corpo}


def corpo_para_html(corpo: str) -> str:
    """Texto simples -> HTML simples (parágrafos), pra enviar no Brevo."""
    paras = corpo.split("\n\n")
    html = "".join(
        f'<p style="margin:0 0 14px">{p.replace(chr(10), "<br>")}</p>' for p in paras
    )
    return (
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:15px;'
        f'line-height:1.55;color:#222">{html}</div>'
    )
