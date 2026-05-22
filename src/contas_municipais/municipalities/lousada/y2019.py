"""
Parser for fiscal year 2019.

Source: prestacao_contas_2019.pdf (177 pages, scanned)
Format: POCAL (pre-SNC-AP reform) — "Mapa do Controlo Orçamental" format
OCR: Mistral OCR (mistral-ocr-latest) — output cached as .mistral.txt
Validated: 2026-05-18 — all values verified against OCR.

Key differences from 2020+ (SNC-AP):
- Uses POCAL Mapa format; parse_snc_table() does not apply.
- Revenue columns: PREVISÕES CORRIGIDAS | ... | RECEITAS COBRADAS BRUTAS |
  (empty reembolsos) | RECEITA COBRADA LÍQUIDA | RECEITAS POR COBRAR FINAL | GRAU EXEC
  When reembolsos = 0 (normal), cobradas brutas == cobrada líquida, so the executed
  value appears twice consecutively in the row's number list. We find that first
  repeated consecutive pair as the executed amount.
- Expenditure columns: DOTAÇÕES CORRIGIDAS | COMPROMISSOS EXERCÍCIO | FUTUROS |
  TOTAL | DESPESA PAGA | ... | GRAU EXEC
  When futuros = 0, nums[1] == nums[2] (exercício == total); exec = nums[3].
  When futuros > 0, nums[1] != nums[2]; exec = nums[4].
- Pct: some pages use period-decimal ("92.43", "101.3") instead of comma-decimal
  ("99,93"). _PT_NUM can only parse comma-decimal, so pct is extracted from the
  last pipe-separated cell of the row directly (_last_pct).
- Rows are found by matching the budget amount string (Portuguese dot-comma format)
  within the consolidated mapa section, immune to OCR label typos (e.g. "DESPESSAS").
- Indicators: from "RÁCIOS DE LIQUIDEZ E SOLVABILIDADE" (columns: 2018 | 2019).
  Current year (2019) = col -1 (rightmost).
  net_result from Demonstração de Resultados, col 0 = N = current year.
- Staff: no headcount paragraph in POCAL format — staff = None.
"""
from pathlib import Path

from contas_municipais.base import ParseResult, find_numbers, slice_section

YEAR = 2019

# ── Category definitions ─────────────────────────────────────────────────────
# (budget_amount, category_key, label_pt, is_current)
# Rows are located by their unique budget string within the sliced section.

_REVENUE = [
    (26_205_830.62, "receitas_correntes",        "Receitas Correntes",         False),
    ( 5_183_283.50, "impostos_diretos",           "Impostos Directos",          True),
    (   427_518.22, "impostos_indiretos",         "Impostos Indirectos",        True),
    ( 1_769_489.23, "taxas_multas",               "Taxas, Multas E Penalidades",True),
    (    13_847.36, "rendimentos_propriedade",    "Rendimentos De Propriedade", True),
    (13_499_895.66, "transferencias_correntes",   "Transferências Correntes",   True),
    ( 4_731_154.38, "venda_bens_servicos",        "Venda De Bens E Serviços",   True),
    (   580_642.27, "outras_receitas_correntes",  "Outras Receitas Correntes",  True),
    ( 9_921_285.43, "receitas_capital",           "Receitas De Capital",        False),
    (   101_400.00, "vendas_bens_investimento",   "Vendas Bens De Investimento",True),
    ( 5_503_848.27, "transferencias_capital",     "Transferências De Capital",  True),
    ( 3_686_037.16, "passivos_financeiros_rec",   "Passivos Financeiros",       True),
    (   630_000.00, "outras_receitas_capital",    "Outras Receitas De Capital", True),
    ( 1_767_507.20, "saldo_gerencia_anterior",    "Saldo Da Gerência Anterior", False),
    (37_894_623.25, "total_receitas",             "Total Das Receitas",         False),
]

_EXPENDITURE = [
    (24_949_465.02, "despesas_correntes",           "Despesas Correntes",           False),
    (11_064_567.05, "despesas_pessoal",             "Despesas Com O Pessoal",       True),
    (10_438_485.17, "aquisicao_bens_servicos",      "Aquisição De Bens E Serviços", True),
    (    95_427.54, "juros_encargos",               "Juros E Outros Encargos",      True),
    ( 2_638_530.91, "transferencias_correntes_desp","Transferências Correntes",     True),
    (   152_500.00, "subsidios",                    "Subsídios",                    True),
    (   570_171.82, "outras_despesas_correntes",    "Outras Despesas Correntes",    True),
    (12_945_158.23, "despesas_capital",             "Despesas De Capital",          False),
    (10_540_600.96, "aquisicao_bens_capital",       "Aquisição De Bens De Capital", True),
    ( 1_039_040.00, "transferencias_capital_desp",  "Transferências De Capital",    True),
    (    82_414.50, "activos_financeiros",           "Activos Financeiros",          True),
    ( 1_283_102.77, "passivos_financeiros_desp",    "Passivos Financeiros",         True),
    (37_894_623.25, "total_despesas",               "Total Das Despesas",           False),
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
    "101.3") formats, which both appear in the 2019 POCAL OCR depending on the page.
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
    section = slice_section(text, "mapa do controlo orçamental da receita", "resumo dos fluxos")
    lines = section.split("\n")
    rows = []
    for budget, key, label_pt, is_current in _REVENUE:
        line = _find_row(lines, budget)
        if line is None:
            print(f"[y2019] WARNING: no row found for revenue '{key}' (budget={budget})")
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
            "is_current": is_current,
            "budget_amount": budget,
            "executed_amount": exec_,
            "execution_pct": pct,
            "global_pct": None,
        })
    return rows


def _parse_expenditure(text: str) -> list[dict]:
    # Consolidated mapa ends where the per-organic-unit mapa begins ("por classificação").
    section = slice_section(text, "controlo orçamental da des", "por classificação")
    lines = section.split("\n")
    rows = []
    for budget, key, label_pt, is_current in _EXPENDITURE:
        line = _find_row(lines, budget)
        if line is None:
            print(f"[y2019] WARNING: no row found for expenditure '{key}' (budget={budget})")
            continue
        exec_ = _exp_exec(line)
        pct = _last_pct(line)
        rows.append({
            "year": YEAR,
            "category": key,
            "label_pt": label_pt,
            "is_current": is_current,
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

    # "RÁCIOS DE LIQUIDEZ E SOLVABILIDADE" — columns: 2018 | 2019 → col=-1 for 2019.
    # Values are on the continuation line (formula), so look-ahead in _find covers them.
    _find("Liquidez geral",      -1, "liquidity_general",   "ratio", "Liquidez geral")
    _find("Liquidez reduzida",   -1, "liquidity_reduced",   "ratio", "Liquidez reduzida")
    _find("Liquidez imediata",   -1, "liquidity_immediate", "ratio", "Liquidez imediata")
    _find("Solvabilidade",       -1, "solvency",            "ratio", "Solvabilidade")
    _find("Autonomia financeira",-1, "financial_autonomy",  "%",     "Autonomia financeira",
          excludes=["Rendibilidade"])

    # V - LIMITE DÍVIDA TOTAL (single-column table, col 0)
    _find("Dívida Total",        0, "total_debt",       "€", "Dívida Total",
          excludes=["Limite"])
    _find("Limite Dívida Total", 0, "debt_limit_dgal",  "€", "Limite Dívida Total DGAL")

    # Demonstração de Resultados — col 0 = N (current year = 2019), col 1 = N-1 (2018).
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
    result.staff = None  # POCAL format has no headcount paragraph
    return result
