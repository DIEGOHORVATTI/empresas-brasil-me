import csv
import io
import zipfile
from collections.abc import Generator
from pathlib import Path

from src.models import Empresa, Estabelecimento, Simples, Socio

# Mapeamento: tipo -> (classe, nº campos esperado)
_PARSERS: dict[str, tuple[type, int]] = {
    "empresas": (Empresa, 7),
    "estabelecimentos": (Estabelecimento, 30),
    "socios": (Socio, 11),
    "simples": (Simples, 7),
}


def parse_zip(zip_path: Path, tipo: str) -> Generator[dict, None, None]:
    """Extrai registros de um ZIP da RF.

    Yields dicts com os campos do modelo correspondente.
    """
    model_cls, expected_fields = _PARSERS[tipo]
    field_names = [f.name for f in model_cls.__dataclass_fields__.values()]

    with zipfile.ZipFile(zip_path) as zf:
        for entry in zf.namelist():
            if not entry.endswith(".csv") and not entry.endswith(".CSV"):
                # Tenta de qualquer forma (RF às vezes muda extensão)
                pass

            with zf.open(entry) as raw:
                text = io.TextIOWrapper(raw, encoding="latin-1")
                reader = csv.reader(text, delimiter=";")

                for row in reader:
                    if len(row) < expected_fields:
                        continue

                    # Strip de todos os campos
                    values = [v.strip().strip('"') for v in row[:expected_fields]]
                    yield dict(zip(field_names, values))


def parse_reference_zip(zip_path: Path) -> Generator[tuple[str, str], None, None]:
    """Extrai tabelas de referência (código, descrição) de ZIPs simples."""
    with zipfile.ZipFile(zip_path) as zf:
        for entry in zf.namelist():
            with zf.open(entry) as raw:
                text = io.TextIOWrapper(raw, encoding="latin-1")
                reader = csv.reader(text, delimiter=";")
                for row in reader:
                    if len(row) >= 2:
                        yield row[0].strip(), row[1].strip()
