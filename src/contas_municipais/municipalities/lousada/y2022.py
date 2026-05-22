"""
Parser for fiscal year 2022.

Source: prestacao_contas_2022.pdf (combined, 9.0 MB, native text)
Format: SNC-AP Relatório de Gestão
Validated: 2026-05-18 — all revenue and expenditure values verified against PDF.

Known quirks (handled explicitly here):
- % GLB column is computed incorrectly in the source PDF (subcategory GLBs sum to >100
  for the total row: 96.7 + 24.4 = 121.1 for revenue, 74.2 + 45.3 = 119.5 for expenditure).
  Stored as-is from the PDF — faithful to source.
- saldo_gerencia_anterior: no execution value shown in the PDF table (exec = None).
- Staff: the 2022 document does not contain a "funcionários de quadro" paragraph.
  Staff data unavailable for this year.
- net_result: 6,162,659.33 € — from P&L LEFT column (current year = left in SNC-AP).
  Confirmed via DAPL in same document.
- Quadro 4 ratio columns: "2021  2022" — current (2022) = rightmost = col -1.
"""
from pathlib import Path
from contas_municipais.base import ParseResult, extract_text, find_numbers, slice_section, parse_snc_table

YEAR = 2022

REVENUE_CATEGORIES = {
    "RECEITAS CORRENTES":        ("receitas_correntes",       False),
    "IMPOSTOS DIRECTOS":         ("impostos_diretos",         True),
    "IMPOSTOS INDIRECTOS":       ("impostos_indiretos",       True),
    "TAXAS, MULTAS":             ("taxas_multas",             True),
    "RENDIMENTOS DE PROPRIEDADE":("rendimentos_propriedade",  True),
    "TRANSFERÊNCIAS CORRENTES":  ("transferencias_correntes", True),
    "VENDA DE BENS E SERVIÇOS":  ("venda_bens_servicos",      True),
    "OUTRAS RECEITAS CORRENTES": ("outras_receitas_correntes",True),
    "RECEITAS DE CAPITAL":       ("receitas_capital",         False),
    "VENDAS BENS DE INVESTIMENTO":("vendas_bens_investimento",True),
    "TRANSFERÊNCIAS DE CAPITAL": ("transferencias_capital",   True),
    "PASSIVOS FINANCEIROS":      ("passivos_financeiros_rec", True),
    "OUTRAS RECEITAS DE CAPITAL":("outras_receitas_capital",  True),
    "SALDO DA GERÊNCIA ANTERIOR":("saldo_gerencia_anterior",  False),
    "TOTAL DAS RECEITAS":        ("total_receitas",           False),
}

EXPENDITURE_CATEGORIES = {
    "DESPESAS CORRENTES":           ("despesas_correntes",          False),
    "DESPESAS COM O PESSOAL":       ("despesas_pessoal",            True),
    "AQUISIÇÃO DE BENS E SERVIÇOS": ("aquisicao_bens_servicos",     True),
    "JUROS E OUTROS ENCARGOS":      ("juros_encargos",              True),
    "TRANSFERÊNCIAS CORRENTES":     ("transferencias_correntes_desp",True),
    "SUBSÍDIOS":                    ("subsidios",                   True),
    "OUTRAS DESPESAS CORRENTES":    ("outras_despesas_correntes",   True),
    "DESPESAS DE CAPITAL":          ("despesas_capital",            False),
    "AQUISIÇÃO DE BENS DE CAPITAL": ("aquisicao_bens_capital",      True),
    "TRANSFERÊNCIAS DE CAPITAL":    ("transferencias_capital_desp", True),
    "ACTIVOS FINANCEIROS":          ("activos_financeiros",         True),
    "PASSIVOS FINANCEIROS":         ("passivos_financeiros_desp",   True),
    "TOTAL DAS DESPESAS":           ("total_despesas",              False),
}


def parse(files: dict[str, Path]) -> ParseResult:
    pdf = files["prestacao_contas"]
    text = extract_text(pdf)
    result = ParseResult(year=YEAR)
    result.revenue     = _parse_revenue(text)
    result.expenditure = _parse_expenditure(text)
    result.indicators  = _parse_indicators(text)
    result.staff       = None  # not available in 2022 document
    return result


def _parse_revenue(text: str) -> list[dict]:
    section = slice_section(text, "quadro 1", "1.2 execução da despesa")
    return parse_snc_table(section, REVENUE_CATEGORIES, YEAR)


def _parse_expenditure(text: str) -> list[dict]:
    section = slice_section(text, "quadro 2", "1.3 estrutura")
    return parse_snc_table(section, EXPENDITURE_CATEGORIES, YEAR)


def _parse_indicators(text: str) -> list[dict]:
    ind = []
    section = slice_section(text, "quadro 3", "5. recursos humanos")

    def _find(search_text: str, term: str, excludes: list[str], col: int, key: str, unit: str, label: str):
        for line in search_text.split("\n"):
            if term.lower() not in line.lower():
                continue
            if any(ex.lower() in line.lower() for ex in excludes):
                continue
            nums = find_numbers(line)
            if nums and (col == 0 or len(nums) > abs(col) - (1 if col < 0 else 0)):
                ind.append({"year": YEAR, "indicator_key": key, "label_pt": label, "value": nums[col], "unit": unit})
                return

    # Quadro 4 ratios — "2021  2022" columns; current (2022) = col -1 (rightmost)
    _find(section, "Autonomia financeira",         [],              -1, "financial_autonomy",  "%",     "Autonomia financeira")
    _find(section, "Liquidez geral",               [],              -1, "liquidity_general",   "ratio", "Liquidez geral")
    _find(section, "Liquidez reduzida",            [],              -1, "liquidity_reduced",   "ratio", "Liquidez reduzida")
    _find(section, "Liquidez imediata",            [],              -1, "liquidity_immediate", "ratio", "Liquidez imediata")
    _find(section, "Solvabilidade",                [],              -1, "solvency",            "ratio", "Solvabilidade")

    # Debt section
    _find(section, "Dívida Total",   ["limite", "dgal", "01/01"],   0, "total_debt",          "€",     "Dívida Total")
    _find(section, "Limite Dívida Total DGAL",     [],               0, "debt_limit_dgal",     "€",     "Limite Dívida Total DGAL")
    _find(section, "Margem Absoluta",              [],               0, "debt_headroom",       "€",     "Margem Absoluta")

    # Net result: LEFT column = current year 2022; confirmed via DAPL (6,162,659.33 €)
    _find(text, "Resultado líquido do período", ["resultado líquido/"], 0, "net_result", "€", "Resultado líquido do período")

    return ind
