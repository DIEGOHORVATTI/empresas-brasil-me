"""Scraper do Google Maps por raio (o que o omkarcloud fazia, em ~150 linhas de Playwright).

Fluxo: abre a busca em lat,lng,zoom → faz scroll no painel de resultados até esgotar
→ visita cada lugar e lê o painel de detalhes (telefone/site/endereço são estáveis via
data-item-id). Devolve dicts prontos pra tabela `maps_empresas`.

Requer:  uv pip install playwright && playwright install chromium
Teste:   python -m src.maps.scraper   (só valida os helpers puros, não abre browser)
"""

import re
from datetime import datetime

# Selectors do painel de resultados/detalhe. Os data-item-id são estáveis;
# as classes ofuscadas (hfpxzc) mudam de vez em quando — por isso há fallback.
_FEED = 'div[role="feed"]'
_LINK = 'a[href*="/maps/place/"]'


def search_url(query: str, lat: float, lng: float, zoom: int = 14) -> str:
    q = query.strip().replace(" ", "+")
    return f"https://www.google.com/maps/search/{q}/@{lat},{lng},{zoom}z?hl=pt-BR"


def parse_place_id(href: str) -> str:
    """Id único do lugar a partir do href (hex `0x..:0x..`); fallback = caminho da URL."""
    m = re.search(r"!1s(0x[0-9a-f]+:0x[0-9a-f]+)", href)
    if m:
        return m.group(1)
    m = re.search(r"/maps/place/([^/@]+)", href)
    return m.group(1) if m else href[:200]


def parse_latlng(href: str) -> tuple[float | None, float | None]:
    """Coordenadas do lugar: prefere `!3d..!4d..`, senão o `/@lat,lng`."""
    m = re.search(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", href)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.search(r"/@(-?\d+\.\d+),(-?\d+\.\d+)", href)
    if m:
        return float(m.group(1)), float(m.group(2))
    return None, None


def _strip_label(v: str | None, prefixo: str) -> str:
    """aria-label vem como 'Telefone: (11) 1234-5678' → devolve só o valor."""
    if not v:
        return ""
    return v.split(":", 1)[1].strip() if ":" in v else v.replace(prefixo, "").strip()


def clean_rating(v: str | None) -> float | None:
    if not v:
        return None
    m = re.search(r"(\d+[.,]\d+)", v)
    return float(m.group(1).replace(",", ".")) if m else None


def clean_int(v: str | None) -> int | None:
    if not v:
        return None
    d = re.sub(r"\D", "", v)
    return int(d) if d else None


def buscar(
    query: str,
    lat: float,
    lng: float,
    zoom: int = 14,
    max_resultados: int = 20,
    headless: bool = True,
) -> list[dict]:
    """Coleta lugares do Maps no raio dado. Import do Playwright é lazy (só quando roda)."""
    from playwright.sync_api import sync_playwright

    coletado_em = datetime.now().isoformat(timespec="seconds")
    resultados: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        ctx = browser.new_context(
            locale="pt-BR",
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
            ),
        )
        page = ctx.new_page()
        try:
            page.goto(search_url(query, lat, lng, zoom), timeout=45_000)
            _consentir(page)
            hrefs = _coletar_links(page, max_resultados)
            for href in hrefs:
                try:
                    resultados.append(_detalhar(page, href, query, coletado_em))
                except Exception:
                    continue  # um lugar que falha não derruba o lote
        finally:
            browser.close()
    return resultados


def _consentir(page) -> None:
    """Fecha o banner de cookies do Google, se aparecer (varia por região)."""
    for sel in ['button[aria-label*="Aceitar"]', 'button[aria-label*="Accept"]',
                'form[action*="consent"] button']:
        try:
            page.locator(sel).first.click(timeout=2_000)
            return
        except Exception:
            pass


def _coletar_links(page, alvo: int) -> list[str]:
    page.wait_for_selector(_FEED, timeout=30_000)
    feed = page.locator(_FEED)
    vistos: dict[str, None] = {}  # dict preserva ordem e deduplica
    estagnado = 0
    while len(vistos) < alvo and estagnado < 4:
        for h in page.locator(f"{_FEED} {_LINK}").evaluate_all(
            "els => els.map(e => e.href)"
        ):
            vistos.setdefault(h, None)
        antes = len(vistos)
        feed.evaluate("el => el.scrollBy(0, el.scrollHeight)")
        page.wait_for_timeout(1_500)
        estagnado = estagnado + 1 if len(vistos) == antes else 0
    return list(vistos)[:alvo]


def _texto(page, sel: str, attr: str | None = None) -> str | None:
    try:
        loc = page.locator(sel).first
        return loc.get_attribute(attr) if attr else loc.inner_text(timeout=2_000)
    except Exception:
        return None


def _detalhar(page, href: str, query: str, coletado_em: str) -> dict:
    page.goto(href, timeout=30_000)
    page.wait_for_selector("h1", timeout=15_000)
    lat, lng = parse_latlng(page.url)
    return {
        "place_id": parse_place_id(page.url),
        "nome": _texto(page, "h1"),
        "categoria": _texto(page, 'button[jsaction*="category"]'),
        "endereco": _strip_label(
            _texto(page, 'button[data-item-id="address"]', "aria-label"), "Endereço"),
        "telefone": _strip_label(
            _texto(page, 'button[data-item-id^="phone"]', "aria-label"), "Telefone"),
        "website": _texto(page, 'a[data-item-id="authority"]', "href"),
        "rating": clean_rating(_texto(page, "div.F7nice")),
        "reviews": clean_int(_texto(page, 'div.F7nice span[aria-label*="avaliaç"]', "aria-label")),
        "latitude": lat,
        "longitude": lng,
        "query": query,
        "maps_url": page.url,
        "coletado_em": coletado_em,
    }


def _demo() -> None:
    assert search_url("padaria centro", -23.55, -46.63, 15).endswith(
        "/@-23.55,-46.63,15z?hl=pt-BR")
    href = ("https://www.google.com/maps/place/Padaria/@-23.5,-46.6,17z/"
            "data=!3d-23.5501!4d-46.6333!1s0x94ce59:0xa4969e07ce3108de")
    assert parse_place_id(href) == "0x94ce59:0xa4969e07ce3108de"
    assert parse_latlng(href) == (-23.5501, -46.6333)
    assert parse_latlng("https://x/@-23.5,-46.6,17z") == (-23.5, -46.6)
    assert _strip_label("Telefone: (11) 1234-5678", "Telefone") == "(11) 1234-5678"
    assert clean_rating("4,5 estrelas") == 4.5
    assert clean_int("1.234 avaliações") == 1234
    print("ok")


if __name__ == "__main__":
    _demo()
