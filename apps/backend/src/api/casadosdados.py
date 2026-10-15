import time

import httpx


class CasaDosDadosClient:
    """Cliente para a API pública Casa dos Dados (busca avançada de CNPJ)."""

    BASE_URL = "https://api.casadosdados.com.br/v2/public/cnpj/search"

    def __init__(self, timeout: int = 30) -> None:
        self.client = httpx.Client(
            timeout=timeout,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Origin": "https://casadosdados.com.br",
                "Referer": "https://casadosdados.com.br/",
            },
        )

    def busca(
        self,
        data_abertura_gte: str | None = None,
        data_abertura_lte: str | None = None,
        uf: list[str] | None = None,
        cnae: list[str] | None = None,
        situacao_cadastral: str = "ATIVA",
        termo: list[str] | None = None,
        somente_mei: bool = False,
        excluir_mei: bool = False,
        com_email: bool = False,
        com_contato_telefonico: bool = False,
        somente_matriz: bool = False,
        page: int = 1,
    ) -> dict:
        """Busca empresas com filtros avançados (data de abertura, UF, CNAE, etc.)."""
        payload = {
            "query": {
                "termo": termo or [],
                "atividade_principal": cnae or [],
                "natureza_juridica": [],
                "uf": uf or [],
                "municipio": [],
                "situacao_cadastral": situacao_cadastral,
                "cep": [],
                "ddd": [],
            },
            "range_query": {
                "data_abertura": {
                    "gte": data_abertura_gte,
                    "lte": data_abertura_lte,
                },
                "capital_social": {
                    "lte": None,
                    "gte": None,
                },
            },
            "extras": {
                "somente_mei": somente_mei,
                "excluir_mei": excluir_mei,
                "com_email": com_email,
                "incluir_atividade_secundaria": False,
                "com_contato_telefonico": com_contato_telefonico,
                "somente_fixo": False,
                "somente_celular": False,
                "somente_matriz": somente_matriz,
                "somente_filial": False,
            },
            "page": page,
        }

        resp = self.client.post(self.BASE_URL, json=payload)
        resp.raise_for_status()
        return resp.json()

    def busca_todas_paginas(
        self,
        max_paginas: int = 100,
        delay: float = 1.0,
        **kwargs,
    ) -> list[dict]:
        """Busca todas as páginas de resultados com rate limiting."""
        todas_empresas: list[dict] = []

        for page in range(1, max_paginas + 1):
            resultado = self.busca(page=page, **kwargs)
            empresas = resultado.get("data", {}).get("cnpj", [])

            if not empresas:
                break

            todas_empresas.extend(empresas)

            # Rate limiting
            if page < max_paginas:
                time.sleep(delay)

        return todas_empresas

    def close(self) -> None:
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
