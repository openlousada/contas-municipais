"""
Parser for fiscal year 2023.

Sources:
  - relatorio_gestao_2023.pdf (native text) — revenue, expenditure, indicators, staff
  - prestacao_contas_2023.pdf (native text) — net_result (relatorio_gestao has a typo)
SNC-AP format.
"""
from pathlib import Path
from contas_municipais.base import ParseResult, extract_text, find_numbers, slice_section, parse_snc_table

YEAR = 2023

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
    rg_text = extract_text(files["relatorio_gestao"])
    pc_text = extract_text(files["prestacao_contas"])
    result = ParseResult(year=YEAR)
    result.revenue     = _parse_revenue(rg_text)
    result.expenditure = _parse_expenditure(rg_text)
    result.indicators  = _parse_indicators(rg_text, pc_text)
    result.staff       = _parse_staff(rg_text)
    return result


def _parse_revenue(text: str) -> list[dict]:
    section = slice_section(text, "quadro 1", "1.2 execução da despesa")
    return parse_snc_table(section, REVENUE_CATEGORIES, YEAR)


def _parse_expenditure(text: str) -> list[dict]:
    section = slice_section(text, "quadro 2", "1.3 estrutura")
    return parse_snc_table(section, EXPENDITURE_CATEGORIES, YEAR)


def _parse_indicators(rg_text: str, pc_text: str) -> list[dict]:
    ind = []
    section = slice_section(rg_text, "quadro 3", "5. recursos humanos")

    def _find(search_text: str, term: str, excludes: list[str], col: int, key: str, unit: str, label: str):
        for line in search_text.split("\n"):
            if term.lower() not in line.lower():
                continue
            if any(ex.lower() in line.lower() for ex in excludes):
                continue
            nums = find_numbers(line)
            if nums and (0 <= col < len(nums) or (col < 0 and len(nums) >= -col)):
                ind.append({"year": YEAR, "indicator_key": key, "label_pt": label, "value": nums[col], "unit": unit})
                return

    # Columns: prior | current; current year = col -1
    _find(section, "Autonomia financeira",         [],              -1, "financial_autonomy",  "%",     "Autonomia financeira")
    _find(section, "Liquidez geral",               [],              -1, "liquidity_general",   "ratio", "Liquidez geral")
    _find(section, "Liquidez reduzida",            [],              -1, "liquidity_reduced",   "ratio", "Liquidez reduzida")
    _find(section, "Liquidez imediata",            [],              -1, "liquidity_immediate", "ratio", "Liquidez imediata")
    _find(section, "Solvabilidade",                [],              -1, "solvency",            "ratio", "Solvabilidade")

    # 2023 uses bare "Dívida Total" label (not "Montante Dívida Total a 31/12")
    _find(section, "Dívida Total",   ["limite", "dgal", "01/01"],   0, "total_debt",          "€",     "Dívida Total")
    _find(section, "Limite Dívida Total DGAL",     [],               0, "debt_limit_dgal",     "€",     "Limite Dívida Total DGAL")
    _find(section, "Margem Absoluta",              [],               0, "debt_headroom",       "€",     "Margem Absoluta")

    # net_result from prestacao_contas — relatorio_gestao has a typo; LEFT column = current year.
    _find(pc_text, "Resultado líquido do período", ["resultado líquido/"], 0, "net_result", "€", "Resultado líquido do período")

    return ind


def _parse_staff(text: str) -> dict | None:
    import re
    m_perm    = re.search(r"(\d+)\s+funcionários de quadro", text)
    m_other   = re.search(r"e\s+(\d+)\s+funcionários em outra situação", text)
    m_entries = re.search(r"(\d+)\s+entradas", text)
    m_exits   = re.search(r"(\d+)\s+saídas", text)
    if not m_perm:
        return None
    permanent = int(m_perm.group(1))
    other     = int(m_other.group(1)) if m_other else 0
    return {
        "year": YEAR,
        "total_staff":     permanent + other,
        "permanent_staff": permanent,
        "executive_count": None,
        "entries": int(m_entries.group(1)) if m_entries else None,
        "exits":   int(m_exits.group(1))   if m_exits   else None,
    }
