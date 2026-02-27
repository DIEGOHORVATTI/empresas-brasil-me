import httpx

from src.config import MINHARECEITA_BASE_URL


class MinhaReceitaClient:
    """Cliente para a API pública Minha Receita (sem autenticação)."""

    def __init__(self, base_url: str = MINHARECEITA_BASE_URL) -> None:
        self.base_url = base_url
        self.client = httpx.Client(base_url=base_url, timeout=30)

    def consulta(self, cnpj: str) -> dict:
        """Consulta dados completos de uma empresa pelo CNPJ."""
        cnpj_limpo = cnpj.replace(".", "").replace("/", "").replace("-", "")
        resp = self.client.get(f"/{cnpj_limpo}")
        resp.raise_for_status()
        return resp.json()

    def busca(
        self,
        uf: str | None = None,
        cnae: str | None = None,
        limit: int = 100,
        cursor: str | None = None,
    ) -> dict:
        """Busca empresas com filtros (paginação por cursor)."""
        params: dict[str, str | int] = {"limit": limit}
        if uf:
            params["uf"] = uf
        if cnae:
            params["cnae"] = cnae
        if cursor:
            params["cursor"] = cursor

        resp = self.client.get("/", params=params)
        resp.raise_for_status()
        return resp.json()

    def updated(self) -> dict:
        """Retorna timestamp da última atualização dos dados."""
        resp = self.client.get("/updated")
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
