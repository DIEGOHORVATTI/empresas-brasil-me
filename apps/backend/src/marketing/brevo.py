"""Envio de email transacional via API REST do Brevo."""

from pathlib import Path

import httpx

ENV_PATH = Path(__file__).parent.parent.parent / "mailer" / ".env"
BREVO_URL = "https://api.brevo.com/v3/smtp/email"


def _env() -> dict[str, str]:
    """Lê o mailer/.env (chave, remetente) sem depender de lib externa."""
    out: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    return out


def config_ok() -> tuple[bool, str]:
    env = _env()
    if not env.get("BREVO_API_KEY"):
        return False, "BREVO_API_KEY ausente no mailer/.env"
    if not env.get("BREVO_REMETENTE_EMAIL"):
        return False, "BREVO_REMETENTE_EMAIL ausente (remetente verificado no Brevo)"
    return True, ""


def enviar(destinatario: str, assunto: str, corpo_texto: str, corpo_html: str) -> tuple[bool, str]:
    """Envia um email. Retorna (ok, mensagem/erro). Inclui List-Unsubscribe."""
    env = _env()
    remetente = env["BREVO_REMETENTE_EMAIL"]
    payload = {
        "sender": {"email": remetente, "name": env.get("BREVO_REMETENTE_NOME", "")},
        "to": [{"email": destinatario}],
        "subject": assunto,
        "textContent": corpo_texto,
        "htmlContent": corpo_html,
        "headers": {"List-Unsubscribe": f"<mailto:{remetente}?subject=unsubscribe>"},
    }
    headers = {"api-key": env["BREVO_API_KEY"], "content-type": "application/json"}
    try:
        r = httpx.post(BREVO_URL, json=payload, headers=headers, timeout=30)
    except httpx.HTTPError as e:
        return False, f"falha de rede: {e}"
    if r.status_code in (200, 201):
        return True, r.json().get("messageId", "ok")
    return False, f"HTTP {r.status_code}: {r.text[:200]}"
