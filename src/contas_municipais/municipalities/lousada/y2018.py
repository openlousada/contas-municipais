"""
Parser for fiscal year 2018.

Source: prestacao_de_contas.pdf (scanned), POCAL format
OCR: Mistral OCR — output cached as .mistral.txt
"""
from pathlib import Path

from contas_municipais.base import ParseResult, find_numbers, slice_section

YEAR = 2018

_REVENUE = [
    (25_322_046.85, "receitas_correntes",        "Receitas Correntes",         False),
    ( 4_703_013.69, "impostos_diretos",           "Impostos Directos",          True),
    (   313_237.90, "impostos_indiretos",         "Impostos Indirectos",        True),
    ( 1_597_815.08, "taxas_multas",               "Taxas, Multas E Penalidades",True),
    (       838.79, "rendimentos_propriedade",    "Rendimentos De Propriedade", True),
    (13_362_561.22, "transferencias_correntes",   "Transferências Correntes",   True),
    ( 4_670_600.62, "venda_bens_servicos",        "Venda De Bens E Serviços",   True),
    (   673_979.55, "outras_receitas_correntes",  "Outras Receitas Correntes",  True),
    ( 6_592_663.75, "receitas_capital",           "Receitas De Capital",        False),
    (   264_286.16, "vendas_bens_investimento",   "Vendas Bens De Investimento",True),
    ( 4_007_114.47, "transferencias_capital",     "Transferências De Capital",  True),
    ( 2_251_263.12, "passivos_financeiros_rec",   "Passivos Financeiros",       True),
    (    70_000.00, "outras_receitas_capital",    "Outras Receitas De Capital", True),
    ( 2_127_319.82, "saldo_gerencia_anterior",    "Saldo Da Gerência Anterior", False),
    (34_072_030.42, "total_receitas",             "Total Das Receitas",         False),
]

_EXPENDITURE = [
    (23_563_708.47, "despesas_correntes",           "Despesas Correntes",           False),
    (10_862_837.49, "despesas_pessoal",             "Despesas Com O Pessoal",       True),
    ( 9_951_530.51, "aquisicao_bens_servicos",      "Aquisição De Bens E Serviços", True),
    (   146_650.00, "juros_encargos",               "Juros E Outros Encargos",      True),
    ( 3_074_286.51, "transferencias_correntes_desp","Transferências Correntes",     True),
    (   140_800.00, "subsidios",                    "Subsídios",                    True),
    (   188_483.96, "outras_despesas_correntes",    "Outras Despesas Correntes",    True),
    (10_500_321.95, "despesas_capital",             "Despesas De Capital",          False),
    ( 7_644_046.84, "aquisicao_bens_capital",       "Aquisição De Bens De Capital", True),
    (   912_242.69, "transferencias_capital_desp",  "Transferências De Capital",    True),
    (   131_785.00, "activos_financeiros",           "Activos Financeiros",          True),
    ( 1_408_087.68, "passivos_financeiros_desp",    "Passivos Financeiros",         True),
    (   412_159.74, "outras_despesas_capital",      "Outras Despesas De Capital",   True),
    (34_072_030.42, "total_despesas",               "Total Das Despesas",           False),
]


# ── Portuguese number formatting ─────────────────────────────────────────────

def _pt(n: float) -> str:
    """Format a float as a Portuguese-style number string for text search.

    e.g. 24_949_465.02 → "24.949.465,02"
    """
    cents = round(n * 100)
    integer_part = cents // 100
    decimal_part = cents % 100
    return f"{integer_part:,}".replace(",", ".") + f",{decimal_part:02d}"


# ── Pct extraction from table cell ───────────────────────────────────────────

def _last_pct(line: str) -> float | None:
    """Extract percentage from the last non-empty pipe-separated cell.

    Handles both Portuguese comma-decimal ("99,93") and period-decimal ("92.43",
    "101.3") formats. Values > 1000 (e.g. pct=3367.2) are returned as None.
    """
    parts = [p.strip() for p in line.split("|")]
    last = next((p for p in reversed(parts) if p), None)
    if last is None:
        return None
    for candidate in (last, last.replace(",", ".")):
        try:
            val = float(candidate)
            if 0 < val <= 1000:
                return round(val, 2)
        except ValueError:
            pass
    return None


# ── POCAL row extraction heuristics ──────────────────────────────────────────

def _rev_exec(line: str) -> float | None:
    """Return executed amount from a POCAL revenue row.

    Executed = first pair of consecutive equal values in find_numbers(line)[1:],
    i.e. RECEITAS COBRADAS BRUTAS == RECEITA COBRADA LÍQUIDA when reembolsos = 0.
    """
    nums = find_numbers(line)
    tail = nums[1:]
    for i in range(len(tail) - 1):
        if tail[i] == tail[i + 1]:
            return tail[i]
    return None


def _exp_exec(line: str) -> float | None:
    """Return executed amount (DESPESA PAGA) from a POCAL expenditure row.

    When COMPROMISSOS FUTUROS = 0, nums[1] == nums[2] (exercício == total);
    exec = nums[3].
    When futuros > 0, nums[1] != nums[2]; exec = nums[4].
    """
    nums = find_numbers(line)
    if len(nums) < 4:
        return None
    if nums[1] == nums[2]:
        return nums[3]
    return nums[4] if len(nums) > 4 else nums[3]


# ── Row finder ───────────────────────────────────────────────────────────────

def _find_row(lines: list[str], budget: float) -> str | None:
    """Return the first table line in `lines` that contains the budget string."""
    target = _pt(budget)
    for line in lines:
        if target in line and "|" in line:
            if find_numbers(line):
                return line
    return None


# ── Section parsers ───────────────────────────────────────────────────────────

def _parse_revenue(text: str) -> list[dict]:
    section = slice_section(text, "previsões corrigidas", "urgão exec")
    lines = section.split("\n")
    rows = []
    for budget, key, label_pt, is_subcategory in _REVENUE:
        line = _find_row(lines, budget)
        if line is None:
            print(f"[y2018] WARNING: no row found for revenue '{key}' (budget={budget})")
            continue
        if key == "saldo_gerencia_anterior":
            exec_, pct = None, None
        else:
            exec_ = _rev_exec(line)
            pct = _last_pct(line)
        rows.append({
            "year": YEAR,
            "category": key,
            "label_pt": label_pt,
            "is_subcategory": is_subcategory,
            "budget_amount": budget,
            "executed_amount": exec_,
            "execution_pct": pct,
            "global_pct": None,
        })
    return rows


def _parse_expenditure(text: str) -> list[dict]:
    # OCR heading: "CONTROLE" (not "CONTROLO").
    section = slice_section(text, "controle orçamental da des", "por classificação")
    lines = section.split("\n")
    rows = []
    for budget, key, label_pt, is_subcategory in _EXPENDITURE:
        line = _find_row(lines, budget)
        if line is None:
            print(f"[y2018] WARNING: no row found for expenditure '{key}' (budget={budget})")
            continue
        exec_ = _exp_exec(line)
        pct = _last_pct(line)
        # OCR error on correntes aggregate pct — recompute from executed/budget.
        if key == "despesas_correntes" and pct == 96.53:
            pct = round(exec_ / budget * 100, 2) if exec_ else pct
        rows.append({
            "year": YEAR,
            "category": key,
            "label_pt": label_pt,
            "is_subcategory": is_subcategory,
            "budget_amount": budget,
            "executed_amount": exec_,
            "execution_pct": pct,
            "global_pct": None,
        })
    return rows


def _parse_indicators(text: str) -> list[dict]:
    ind: list[dict] = []
    lines = text.split("\n")

    def _find(term: str, col: int, key: str, unit: str, label: str,
              excludes: list[str] | None = None) -> None:
        for i, line in enumerate(lines):
            if term.lower() not in line.lower():
                continue
            if excludes and any(ex.lower() in line.lower() for ex in excludes):
                continue
            nums = find_numbers(line)
            if not nums and i + 1 < len(lines):
                nums = find_numbers(lines[i + 1])
            if nums and len(nums) >= abs(col):
                ind.append({
                    "year": YEAR,
                    "indicator_key": key,
                    "label_pt": label,
                    "value": nums[col],
                    "unit": unit,
                })
                return

    # Columns: prior | current; current year = col -1.
    _find("Liquidez geral",      -1, "liquidity_general",   "ratio", "Liquidez geral")
    _find("Liquidez reduzida",   -1, "liquidity_reduced",   "ratio", "Liquidez reduzida")
    _find("Liquidez imediata",   -1, "liquidity_immediate", "ratio", "Liquidez imediata")
    _find("Solvabilidade",       -1, "solvency",            "ratio", "Solvabilidade")
    _find("Autonomia financeira",-1, "financial_autonomy",  "%",     "Autonomia financeira",
          excludes=["Rendibilidade"])

    _find("Dívida Total",        0, "total_debt",       "€", "Dívida Total",
          excludes=["Limite"])
    _find("Limite Dívida Total", 0, "debt_limit_dgal",  "€", "Limite Dívida Total DGAL")

    # P&L: col 0 = current year.
    _find("Resultado Líquido do Exercício", 0, "net_result", "€",
          "Resultado Líquido do Exercício")

    return ind


# ── Public API ────────────────────────────────────────────────────────────────

def parse(files: dict[str, Path]) -> ParseResult:
    pdf = files["prestacao_contas"]
    txt_cache = pdf.with_suffix(".mistral.txt")
    if not txt_cache.exists():
        raise FileNotFoundError(
            f"Mistral OCR cache not found: {txt_cache}. "
            "Run Mistral OCR on this PDF first and save output to .mistral.txt"
        )
    text = txt_cache.read_text()
    result = ParseResult(year=YEAR)
    result.revenue = _parse_revenue(text)
    result.expenditure = _parse_expenditure(text)
    result.indicators = _parse_indicators(text)
    result.staff = None  # POCAL format has no headcount section
    return result
