import asyncio
import re
from pathlib import Path

import httpx
from tqdm import tqdm

from src.config import RAW_DIR, RF_BASE_URL, RF_INDEX_URL


async def discover_latest_period(client: httpx.AsyncClient) -> str:
    """Descobre o período mais recente disponível no mirror Casa dos Dados."""
    resp = await client.get(RF_INDEX_URL, follow_redirects=True)
    resp.raise_for_status()
    # Busca padrões YYYY-MM-DD apenas em links href (diretórios reais)
    periods = re.findall(r'href="(\d{4}-\d{2}-\d{2})/?"', resp.text)
    if periods:
        return sorted(set(periods))[-1]
    raise RuntimeError(
        "Não foi possível descobrir o período mais recente. "
        f"Verifique manualmente: {RF_INDEX_URL}"
    )


async def download_file(
    client: httpx.AsyncClient,
    url: str,
    dest: Path,
    chunk_size: int = 1024 * 1024,
) -> Path:
    """Baixa um arquivo com barra de progresso e suporte a resume."""
    dest.parent.mkdir(parents=True, exist_ok=True)

    headers = {}
    existing_size = dest.stat().st_size if dest.exists() else 0

    # Checa tamanho total com HEAD
    head = await client.head(url, follow_redirects=True)
    total_size = int(head.headers.get("content-length", 0))

    if existing_size and existing_size >= total_size and total_size > 0:
        return dest  # Já baixado

    if existing_size:
        headers["Range"] = f"bytes={existing_size}-"

    async with client.stream("GET", url, headers=headers, follow_redirects=True) as resp:
        resp.raise_for_status()
        mode = "ab" if existing_size else "wb"
        with (
            open(dest, mode) as f,
            tqdm(
                total=total_size,
                initial=existing_size,
                unit="B",
                unit_scale=True,
                desc=dest.name,
            ) as pbar,
        ):
            async for chunk in resp.aiter_bytes(chunk_size):
                f.write(chunk)
                pbar.update(len(chunk))

    return dest


async def download_all(
    file_names: list[str],
    period: str | None = None,
    max_concurrent: int = 3,
) -> list[Path]:
    """Baixa todos os arquivos da RF com concorrência limitada."""
    semaphore = asyncio.Semaphore(max_concurrent)
    downloaded: list[Path] = []

    async with httpx.AsyncClient(timeout=httpx.Timeout(30, read=300)) as client:
        if not period:
            period = await discover_latest_period(client)
            print(f"Período mais recente: {period}")

        base_url = f"{RF_BASE_URL}/{period}"

        async def _download(name: str) -> Path:
            async with semaphore:
                url = f"{base_url}/{name}"
                dest = RAW_DIR / period / name
                return await download_file(client, url, dest)

        tasks = [_download(name) for name in file_names]
        for coro in asyncio.as_completed(tasks):
            path = await coro
            downloaded.append(path)

    return downloaded
