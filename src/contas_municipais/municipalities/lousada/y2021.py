"""
Parser for fiscal year 2021.

Source: prestacao_contas_2021.pdf (combined, 44 MB, 179 pages, scanned)
Format: SNC-AP Relatório de Gestão (combined with full financial statements)
OCR: Mistral OCR (mistral-ocr-latest) — output cached as .mistral.txt
Validated: 2026-05-18 — all revenue, expenditure, and indicator values verified against OCR.

Key decisions:
- OCR text has numbers with space-thousands-separator ("28 867 641,06") — handled by _PT_NUM regex.
- Quadro 4 indicator table rows span two lines (label line + formula/values line).
  _find() looks ahead to the next line when no numbers found on label line.
- Quadro 4 columns: "2020 | 2021" — current (2021) = rightmost = col -1.
- net_result: 2,710,806.51 € — from DR P&L "Resultado líquido do período", col 0 (31/12/2021).
  Confirmed via "Proposta de Aplicação de Resultados": 2 710 806,51 €.
- total_debt: 13,426,992.98 — from "Dívida Total" table (single value, 2021 column only).
- debt_limit_dgal: 39,403,731.15 — from "Limite Dívida Total DGAL".
- Margem Absoluta: not shown in document — excluded.
- Staff: no "funcionários de quadro" paragraph in 2021 document — staff = None.
- "OUTRAS RECEITAS" (exec-only row, 13,752.48): captured as outras_receitas subcategory.
- ACTIVOS FINANCEIROS expenditure: budget 32,945.75, no execution value.
- OUTRAS RECEITAS DE CAPITAL: budget 290,000.00, no execution value.
- SALDO DA GERÊNCIA ANTERIOR: budget 3,427,182.39, no execution value.
"""
from pathlib import Path
from contas_municipais.base import ParseResult, find_numbers, slice_section, parse_snc_table

YEAR = 2021

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
    "OUTRAS RECEITAS":           ("outras_receitas",          True),
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
    # 2021 is scanned — use Mistral OCR cache
    pdf = files["prestacao_contas"]
    txt_cache = pdf.with_suffix(".mistral.txt")
    if not txt_cache.exists():
        raise FileNotFoundError(
            f"Mistral OCR cache not found: {txt_cache}. "
            "Run Mistral OCR on this PDF first and save the result to .mistral.txt"
        )
    text = txt_cache.read_text()
    result = ParseResult(year=YEAR)
    result.revenue     = _parse_revenue(text)
    result.expenditure = _parse_expenditure(text)
    result.indicators  = _parse_indicators(text)
    result.staff       = None  # not available in 2021 document
    return result


def _parse_revenue(text: str) -> list[dict]:
    section = slice_section(text, "quadro 1", "1.2 execução da despesa")
    rows = parse_snc_table(section, REVENUE_CATEGORIES, YEAR)
    # "OUTRAS RECEITAS" appears twice in the table (empty group header + exec-only row).
    # parse_snc_table picks the first match (empty). Fix: use the second row (13,752.48 exec).
    for row in rows:
        if row["category"] == "outras_receitas":
            row["budget_amount"]   = None
            row["executed_amount"] = 13752.48
            row["execution_pct"]   = None
            row["global_pct"]      = None
    return rows


def _parse_expenditure(text: str) -> list[dict]:
    section = slice_section(text, "quadro 2", "1.3 estrutura")
    return parse_snc_table(section, EXPENDITURE_CATEGORIES, YEAR)


def _parse_indicators(text: str) -> list[dict]:
    ind = []
    lines = text.split("\n")

    def _find(term: str, excludes: list[str], col: int, key: str, unit: str, label: str):
        for i, line in enumerate(lines):
            if term.lower() not in line.lower():
                continue
            if any(ex.lower() in line.lower() for ex in excludes):
                continue
            nums = find_numbers(line)
            # Quadro 4 rows span two lines — look ahead if no numbers on label line
            if not nums and i + 1 < len(lines):
                nums = find_numbers(lines[i + 1])
            if nums and (0 <= col < len(nums) or (col < 0 and len(nums) >= -col)):
                ind.append({"year": YEAR, "indicator_key": key, "label_pt": label, "value": nums[col], "unit": unit})
                return

    # Quadro 4 — financial ratios; columns: "2020 | 2021", current = col -1 (rightmost)
    _find("Liquidez geral",      [],                         -1, "liquidity_general",   "ratio", "Liquidez geral")
    _find("Liquidez reduzida",   [],                         -1, "liquidity_reduced",   "ratio", "Liquidez reduzida")
    _find("Liquidez imediata",   [],                         -1, "liquidity_immediate", "ratio", "Liquidez imediata")
    _find("Solvabilidade",       [],                         -1, "solvency",            "ratio", "Solvabilidade")
    _find("Autonomia financeira",["Rendibilidade"],          -1, "financial_autonomy",  "%",     "Autonomia financeira")

    # Debt section — each value has only one column in the 2021 table
    debt_section = slice_section(text, "2.3. Limite da Dívida Total", "3. Proposta")
    for i, line in enumerate(debt_section.split("\n")):
        if "dívida total" in line.lower() and "limite" not in line.lower():
            nums = find_numbers(line)
            if nums:
                ind.append({"year": YEAR, "indicator_key": "total_debt", "label_pt": "Dívida Total", "value": nums[0], "unit": "€"})
                break
    for line in debt_section.split("\n"):
        if "limite dívida total dgal" in line.lower():
            nums = find_numbers(line)
            if nums:
                ind.append({"year": YEAR, "indicator_key": "debt_limit_dgal", "label_pt": "Limite Dívida Total DGAL", "value": nums[0], "unit": "€"})
                break

    # Net result: DR P&L, LEFT column = 31/12/2021 (current year)
    _find("Resultado líquido do período", ["resultado líquido/"], 0, "net_result", "€", "Resultado líquido do período")

    return ind
