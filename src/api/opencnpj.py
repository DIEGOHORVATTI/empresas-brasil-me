import httpx

from src.config import OPENCNPJ_BASE_URL


class OpenCNPJClient:
    """Cliente para a API pública OpenCNPJ (sem autenticação, 50 req/s)."""

    def __init__(self, base_url: str = OPENCNPJ_BASE_URL) -> None:
        self.base_url = base_url
        self.client = httpx.Client(base_url=base_url, timeout=30)

    def consulta(self, cnpj: str) -> dict:
        """Consulta dados de uma empresa pelo CNPJ."""
        cnpj_limpo = cnpj.replace(".", "").replace("/", "").replace("-", "")
        resp = self.client.get(f"/{cnpj_limpo}")
        resp.raise_for_status()
        return resp.json()

    def info(self) -> dict:
        """Retorna info sobre a base de dados (data, URL do ZIP, MD5)."""
        resp = self.client.get("/info")
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
