"""
Parser for fiscal year 2016.

Source: 3188_original.pdf (144 KB, ~8 pages, native digital PDF), POCAL format
Format: POCAL Mapa do Controlo Orçamental da Receita + Despesa (economic classification only)
Text extraction: pdftotext -layout (no OCR needed — native text PDF)
Validated: 2026-05-18 — all revenue and expenditure values verified against extracted text.

Key decisions:
- POCAL format (not SNC-AP): data is in "MAPA DO CONTROLO ORÇAMENTAL DA RECEITA/DESPESA".
  Numbers use dot-thousands, comma-decimal (e.g. "22.938.755,19").
- Text extraction: uses extract_text() from _base (pdftotext -layout), no Mistral OCR.
- Revenue executed value: cobrada_líquida (col 10 = col 7 - col 9) always repeats 2+ times
  in each row (equals cobradas_brutas when no reembolsos). _rev_executed() returns mode of
  nums[1:] after stripping the pct.
- Expenditure executed value: same futuros-detection logic as 2017.
  No futuros (nums[1]==nums[2]): despesa_paga=nums[3].
  Futuros present (nums[1]!=nums[2] and nums[2]>100): despesa_paga=nums[4].
- Pct column uses period-decimal ("102.2", "90.77") — not matched by the comma-decimal
  _PT_NUM regex. Captured via _PCT_PERIOD_END fallback in _row().
- Code matching: space-based regex (r"^\s{0,4}0*CODE\s{2,}") — not pipe-based like 2017,
  because pdftotext produces fixed-width columns, not markdown tables.
- SALDO DA GERÊNCIA ANTERIOR (code 16): single number on the line (budget only).
  _rev_executed returns None (len<2) — no special casing needed.
- No indicators: document contains only the budget execution maps, not the full
  Relatório de Gestão. Indicators are unavailable for 2016.
- Document has no organic classification section — only economic classification.
"""
import re
from pathlib import Path
from contas_municipais.base import ParseResult, find_numbers, slice_section, extract_text

YEAR = 2016

# Pct values use period-decimal ("102.2", "90.77") at line end — not matched by _PT_NUM.
_PCT_PERIOD_END = re.compile(r"(\d{1,3})\.(\d{1,2})\s*$")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rev_executed(nums: list[float]) -> float | None:
    """Return cobrada_líquida (executed) from a POCAL revenue row.

    The executed value repeats 2+ times in nums[1:] (cols 5-11 minus pct).
    Returns the most-frequent value; None if no value repeats.
    """
    if len(nums) < 2:
        return None
    pct = nums[-1] if nums[-1] < 300 else None
    candidates = nums[1:-1] if pct is not None else nums[1:]
    if not candidates:
        return None
    freq: dict[float, int] = {}
    for v in candidates:
        freq[v] = freq.get(v, 0) + 1
    max_count = max(freq.values())
    if max_count < 2:
        return None
    return max((k for k, c in freq.items() if c == max_count), key=lambda x: freq[x])


def _exp_executed(nums: list[float]) -> float | None:
    """Return despesa_paga from a POCAL expenditure row.

    Detects futuros by checking nums[1] != nums[2] and nums[2] > 100.
    No futuros → paga = nums[3]. Futuros present → paga = nums[4].
    """
    if len(nums) < 4:
        return None
    futuros = len(nums) >= 3 and nums[2] != nums[1] and nums[2] > 100
    idx = 4 if futuros else 3
    return nums[idx] if len(nums) > idx else None


def _row(line: str | None, year: int, slug: str, label: str, is_current: bool,
         mode: str = "rev") -> dict | None:
    """Build a row dict from a matched line. mode='rev' or 'exp'."""
    if not line:
        return None
    nums = find_numbers(line)
    if not nums:
        return None
    budget = nums[0]
    pct_threshold = 300 if mode == "rev" else 200
    # Period-decimal pct at line end takes priority (all pct values in 2016 use this format).
    # Fallback to nums[-1] for any comma-decimal pct (none expected in 2016).
    pct = None
    m = _PCT_PERIOD_END.search(line.rstrip())
    if m:
        val = float(m.group(1) + "." + m.group(2))
        if 0 < val <= pct_threshold:
            pct = val
    if pct is None:
        pct = nums[-1] if len(nums) >= 2 and nums[-1] < pct_threshold else None
    if mode == "rev":
        executed = _rev_executed(nums)
    else:
        executed = _exp_executed(nums)
    return {
        "year": year,
        "category": slug,
        "label_pt": label,
        "is_current": is_current,
        "budget_amount": budget,
        "executed_amount": executed,
        "execution_pct": pct,
        "global_pct": None,
    }


def _find_kw(section: str, keyword: str, exclude: list[str] = ()) -> str | None:
    """First line containing keyword (case-insensitive), skipping lines with any exclude term."""
    kw = keyword.upper()
    for line in section.split("\n"):
        upper = line.upper()
        if kw in upper and not any(ex.upper() in upper for ex in exclude):
            return line
    return None


def _find_code(section: str, code: str) -> str | None:
    """First POCAL row for this 2-digit economic code in the section.

    Matches lines where the code appears at line-start (after ≤4 spaces), e.g.:
      "01                 IMPOSTOS DIRECTOS   4.534.145,29 ..."
      "  07             AQUISIÇÃO DE BENS DE CAPITAL ..."
    Does NOT match sub-codes (0101, 020206, etc.) because those are longer.
    """
    stripped = code.lstrip("0") or "0"
    pat = re.compile(r"^\s{0,4}0*" + re.escape(stripped) + r"\s{2,}", re.MULTILINE)
    for line in section.split("\n"):
        if pat.match(line):
            return line
    return None


def _find_total_data(section: str) -> str | None:
    """Last line containing 'TOTAL' that also has numbers (skips column-header lines)."""
    result = None
    for line in section.split("\n"):
        if "total" in line.lower() and find_numbers(line):
            result = line
    return result


# ---------------------------------------------------------------------------
# Revenue
# ---------------------------------------------------------------------------

def _parse_revenue(text: str) -> list[dict]:
    sec = slice_section(text, "CONTROLO ORÇAMENTAL DA RECEITA", "CONTROLO ORÇAMENTAL DA DESPESA")
    rows = []

    def add(line, slug, label, is_current):
        r = _row(line, YEAR, slug, label, is_current, mode="rev")
        if r:
            rows.append(r)

    add(_find_kw(sec, "RECEITAS CORRENTES", exclude=["OUTRAS"]),
        "receitas_correntes", "Receitas Correntes", False)

    add(_find_code(sec, "01"), "impostos_diretos",          "Impostos Directos",                  True)
    add(_find_code(sec, "02"), "impostos_indiretos",         "Impostos Indirectos",                True)
    add(_find_code(sec, "04"), "taxas_multas",               "Taxas, Multas e Outras Penalidades", True)
    add(_find_code(sec, "05"), "rendimentos_propriedade",    "Rendimentos de Propriedade",         True)
    add(_find_code(sec, "06"), "transferencias_correntes",   "Transferências Correntes",           True)
    add(_find_code(sec, "07"), "venda_bens_servicos",        "Venda de Bens e Serviços Correntes", True)
    add(_find_code(sec, "08"), "outras_receitas_correntes",  "Outras Receitas Correntes",          True)

    add(_find_kw(sec, "RECEITAS DE CAPITAL", exclude=["OUTRAS"]),
        "receitas_capital", "Receitas de Capital", False)

    add(_find_code(sec, "09"), "vendas_bens_investimento",   "Vendas de Bens de Investimento",     True)
    add(_find_code(sec, "10"), "transferencias_capital",     "Transferências de Capital",           True)
    add(_find_code(sec, "12"), "passivos_financeiros_rec",   "Passivos Financeiros",               True)
    add(_find_code(sec, "13"), "outras_receitas_capital",    "Outras Receitas de Capital",         True)

    # SALDO DA GERÊNCIA ANTERIOR (code 16): budget only, single number on the line.
    add(_find_code(sec, "16"), "saldo_gerencia_anterior",    "Saldo da Gerência Anterior",         False)

    total_line = _find_total_data(sec)
    if total_line:
        r = _row(total_line, YEAR, "total_receitas", "Total das Receitas", False, mode="rev")
        if r:
            rows.append(r)

    return rows


# ---------------------------------------------------------------------------
# Expenditure
# ---------------------------------------------------------------------------

def _parse_expenditure(text: str) -> list[dict]:
    sec = slice_section(text, "CONTROLO ORÇAMENTAL DA DESPESA", "Orgão Deliberativo")
    rows = []

    def add(line, slug, label, is_current):
        r = _row(line, YEAR, slug, label, is_current, mode="exp")
        if r:
            rows.append(r)

    add(_find_kw(sec, "DESPESAS CORRENTES", exclude=["COM O", "OUTRAS"]),
        "despesas_correntes", "Despesas Correntes", False)

    add(_find_code(sec, "01"), "despesas_pessoal",              "Despesas com o Pessoal",        True)
    add(_find_code(sec, "02"), "aquisicao_bens_servicos",       "Aquisição de Bens e Serviços",  True)
    add(_find_code(sec, "03"), "juros_encargos",                "Juros e Outros Encargos",       True)
    add(_find_code(sec, "04"), "transferencias_correntes_desp", "Transferências Correntes",      True)
    add(_find_code(sec, "05"), "subsidios",                     "Subsídios",                     True)
    add(_find_code(sec, "06"), "outras_despesas_correntes",     "Outras Despesas Correntes",     True)

    add(_find_kw(sec, "DESPESAS DE CAPITAL"),
        "despesas_capital", "Despesas de Capital", False)

    add(_find_code(sec, "07"), "aquisicao_bens_capital",        "Aquisição de Bens de Capital",  True)
    add(_find_code(sec, "08"), "transferencias_capital_desp",   "Transferências de Capital",     True)
    add(_find_code(sec, "09"), "activos_financeiros",           "Activos Financeiros",           True)
    add(_find_code(sec, "10"), "passivos_financeiros_desp",     "Passivos Financeiros",          True)

    total_line = _find_total_data(sec)
    if total_line:
        r = _row(total_line, YEAR, "total_despesas", "Total das Despesas", False, mode="exp")
        if r:
            rows.append(r)

    return rows


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse(files: dict[str, Path]) -> ParseResult:
    pdf = files.get("pocal_orcamental") or files.get("prestacao_contas") or files.get("other")
    if pdf is None:
        raise FileNotFoundError("No PDF found for 2016 (expected key 'pocal_orcamental' or 'other')")
    text = extract_text(pdf)
    result = ParseResult(year=YEAR)
    result.revenue     = _parse_revenue(text)
    result.expenditure = _parse_expenditure(text)
    result.indicators  = []
    result.staff       = None
    return result
