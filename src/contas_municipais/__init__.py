"""
contas-municipais — Framework para parsing de relatórios financeiros de municípios portugueses.

Fornece utilitários de extração de texto e parsing de tabelas orçamentais
compatíveis com os dois sistemas contabilísticos usados pelas autarquias:

- **POCAL** (Plano Oficial de Contabilidade das Autarquias Locais) — até 2017
- **SNC-AP** (Sistema de Normalização Contabilística para as AP) — desde 2018

Utilização rápida::

    from contas_municipais.base import extract_text, slice_section, parse_budget_table
    from contas_municipais.sncap import REVENUE_CATEGORIES, EXPENDITURE_CATEGORIES

    text = extract_text(Path("relatorio_gestao_2023.pdf"))
    section = slice_section(text, "quadro 1", "1.2 execução da despesa")
    rows = parse_budget_table(section, REVENUE_CATEGORIES, year=2023)

Para ver uma implementação completa com tratamento de anos e quirks
específicos de um município, consulte municipalities/lousada/.
"""
from .base import (
    ParseResult,
    extract_text,
    find_numbers,
    slice_section,
    parse_budget_table,
)

__all__ = [
    "ParseResult",
    "extract_text",
    "find_numbers",
    "slice_section",
    "parse_budget_table",
]
