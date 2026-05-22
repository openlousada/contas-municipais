"""
Parser de referência para o Município de Lousada (NIF 505279460).

Cobre os exercícios fiscais de 2012 a 2024, com dois formatos:

- **POCAL** (2012–2017): Mapa do Controlo Orçamental da Receita/Despesa
- **SNC-AP** (2018–2024): Quadro 1 (receita) e Quadro 2 (despesa)

Utilização::

    from pathlib import Path
    from contas_municipais.municipalities.lousada import parse

    result = parse(year=2023, files={
        "relatorio_gestao": Path("relatorio_gestao_2023.pdf"),
        "prestacao_contas": Path("prestacao_contas_2023.pdf"),
    })

Os ficheiros necessários variam por ano — consulte o docstring de cada
módulo yYYYY.py para saber quais as chaves obrigatórias.

Este módulo serve como implementação de referência para contribuidores
que queiram adicionar o seu próprio município. Consulte CONTRIBUTING.md.
"""
from pathlib import Path
from contas_municipais.base import ParseResult

from . import y2012, y2013, y2014, y2015, y2016, y2017, y2018, y2019, y2020, y2021, y2022, y2023, y2024

_REGISTRY: dict[int, object] = {
    2012: y2012,
    2013: y2013,
    2014: y2014,
    2015: y2015,
    2016: y2016,
    2017: y2017,
    2018: y2018,
    2019: y2019,
    2020: y2020,
    2021: y2021,
    2022: y2022,
    2023: y2023,
    2024: y2024,
}


def parse(year: int, files: dict[str, Path]) -> ParseResult:
    parser = _REGISTRY.get(year)
    if parser is None:
        raise NotImplementedError(f"No validated parser for year {year}. Add parsers/years/y{year}.py.")
    return parser.parse(files)


def supported_years() -> list[int]:
    return sorted(_REGISTRY.keys())
