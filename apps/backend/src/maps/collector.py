"""Cola: cidade -> coordenadas (Nominatim) -> scraper -> grava em maps_empresas."""

import httpx

from src.etl.database import get_connection, init_db
from src.maps.scraper import buscar

_COLS = ["place_id", "nome", "categoria", "endereco", "telefone", "website",
         "rating", "reviews", "latitude", "longitude", "cidade", "uf",
         "query", "maps_url", "coletado_em"]


def geocode(cidade: str, uf: str = "") -> tuple[float, float]:
    """Centro da cidade via OpenStreetMap Nominatim (grátis, sem key)."""
    q = ", ".join(x for x in [cidade, uf, "Brasil"] if x)
    r = httpx.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": q, "format": "json", "limit": 1},
        headers={"User-Agent": "empresas-brasil-me/1.0"},
        timeout=20,
    )
    r.raise_for_status()
    dados = r.json()
    if not dados:
        raise ValueError(f"Cidade não encontrada: {q}")
    return float(dados[0]["lat"]), float(dados[0]["lon"])


def reverse(lat: float, lng: float) -> dict:
    """Coordenadas -> cidade/UF (reverse geocoding do Nominatim)."""
    r = httpx.get(
        "https://nominatim.openstreetmap.org/reverse",
        params={"lat": lat, "lon": lng, "format": "json", "zoom": 10},
        headers={"User-Agent": "empresas-brasil-me/1.0"},
        timeout=20,
    )
    r.raise_for_status()
    a = r.json().get("address", {})
    cidade = a.get("city") or a.get("town") or a.get("municipality") or a.get("village") or ""
    uf = (a.get("ISO3166-2-lvl4") or "").replace("BR-", "")  # ex: BR-SP -> SP
    return {"cidade": cidade, "uf": uf}


def coletar(query: str, cidade: str, uf: str = "", zoom: int = 14,
            max_resultados: int = 20,
            lat: float | None = None, lng: float | None = None) -> dict:
    """Roda a busca e faz upsert. Devolve os registros gravados.
    Se lat/lng vierem (centro escolhido no mapa) usa direto; senão geocoda a cidade."""
    if lat is None or lng is None:
        lat, lng = geocode(cidade, uf)
    lugares = buscar(query, lat, lng, zoom, max_resultados)
    for x in lugares:
        x["cidade"], x["uf"] = cidade, uf.upper()

    conn = get_connection()
    init_db(conn)  # garante a tabela em bancos antigos
    ph = ", ".join("?" * len(_COLS))
    conn.executemany(
        f"INSERT OR REPLACE INTO maps_empresas ({', '.join(_COLS)}) VALUES ({ph})",
        [tuple(x.get(c) for c in _COLS) for x in lugares],
    )
    conn.commit()
    conn.close()
    return {"count": len(lugares), "cidade": cidade, "uf": uf, "results": lugares}
