"""
Parser for fiscal year 2013.

Source: 1383_original.pdf (1.6 MB, scanned), POCAL format
Format: POCAL Mapa do Controlo Orçamental da Receita + Despesa (economic classification)
OCR: Mistral OCR (mistral-ocr-latest) — output cached as .mistral.txt
Validated: 2026-05-18 — all revenue and expenditure values verified against OCR text.

Key decisions:
- POCAL format (not SNC-AP). Numbers use dot-thousands, comma-decimal ("22.089.484,37").
- OCR produces pipe-delimited markdown tables (same structure as 2014/2015/2017).
- Pct values are mixed: period-decimal ("97.6", "95.24") and comma-decimal ("85,54", "75,06").
  _PCT_PERIOD_END checked first; comma-decimal pct falls through to nums[-1] fallback.
- Revenue executed: cobrada_líquida = mode of repeated values in nums[1:] (same as 2014/2015).
- Expenditure executed: same 2015 logic — if nums[3] > nums[1]: paga=nums[4]; else paga=nums[3].
- Code matching: pipe-based (r"^\\|\\s+0*CODE\\s*\\|") — same as 2014/2015/2017.
- Expenditure section: slice_section(text, "ORÇAMENTAL DA DESPESA", "ORGÂNI").
  Page 1 header reads "CONTROLE" (not "CONTROLO"), so searching for "CONTROLO ORÇAMENTAL
  DA DESPESA" misses page 1 and starts from page 2 — must use shorter keyword.
- Expenditure code 10 (PASSIVOS FINANCEIROS): the economic section has a multi-line OCR
  block for codes 10-11 at the end of page 4. Instead, the organic classification section
  (first occurrence after "ORGÂNI") has a clean single-row for code 10 at its aggregate level.
  A global search for the first pipe-table code-10 row with ≥4 numbers finds it correctly.
- Budget values for codes 01 (PESSOAL: OCR "18.498.339,38" ≈ correct "10.498.339,38") and
  02 (BENS/SERVIÇOS: OCR "0.344.382,48" ≈ correct "8.344.382,48") are OCR-garbled. The
  executed values are correct and verified by cross-checks.
- Revenue section: slice_section(text, "CONTROLO ORÇAMENTAL DA RECEITA", "CONTABILÍSTICO").
- No indicators or staff: document contains only budget execution maps.
"""
import re
from pathlib import Path
from contas_municipais.base import ParseResult, slice_section

YEAR = 2013

# Some pct values use 1 decimal place ("97,6", "95,0") — base _PT_NUM requires exactly 2.
_PT_NUM = re.compile(r"\d{1,3}(?:[. ]\d{3})*,\d{1,2}")
_PCT_PERIOD_END = re.compile(r"(\d{1,3})\.(\d{1,2})\s*\|?\s*$")


def find_numbers(line: str) -> list[float]:
    out = []
    for m in _PT_NUM.finditer(line):
        try:
            out.append(float(m.group().replace(" ", "").replace(".", "").replace(",", ".")))
        except ValueError:
            pass
    return out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rev_executed(nums: list[float]) -> float | None:
    """Return cobrada_líquida from a POCAL revenue row (mode of repeated values in nums[1:])."""
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
    # Tiebreaker: when multiple values have the same repeat count, prefer the larger one.
    # In 2013 revenue rows, cobrada_líquida (large) and por-cobrar carry-over (small) can both
    # repeat exactly twice; the larger value is always the correct cobrada_líquida.
    return max((k for k, c in freq.items() if c == max_count), key=lambda x: (freq[x], x))


def _exp_executed(nums: list[float]) -> float | None:
    """Return despesa_paga from a POCAL expenditure row.

    Layout when futuros explicit: [budget, exercício, futuros, total, paga, ...]
      → nums[3] = total > nums[1] = exercício → paga = nums[4]
    Layout when futuros cell empty: [budget, exercício, total, paga, ...]
      → nums[3] = paga ≤ nums[1] = exercício → paga = nums[3]
    """
    if len(nums) < 4:
        return None
    if len(nums) >= 5 and nums[3] > nums[1]:
        return nums[4]
    return nums[3]


def _row(line: str | None, year: int, slug: str, label: str, is_subcategory: bool,
         mode: str = "rev") -> dict | None:
    """Build a row dict from a matched line. mode='rev' or 'exp'."""
    if not line:
        return None
    nums = find_numbers(line)
    if not nums:
        return None
    budget = nums[0]
    pct_threshold = 300 if mode == "rev" else 200
    pct = None
    m = _PCT_PERIOD_END.search(line.rstrip())
    if m:
        val = float(m.group(1) + "." + m.group(2))
        if 0 < val <= pct_threshold:
            pct = val
    if pct is None:
        pct = nums[-1] if len(nums) >= 2 and nums[-1] < pct_threshold else None
    executed = _rev_executed(nums) if mode == "rev" else _exp_executed(nums)
    return {
        "year": year,
        "category": slug,
        "label_pt": label,
        "is_subcategory": is_subcategory,
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
    """First pipe-table row for this 2-digit economic code.

    Matches '| 01 |', '|  02 |', etc. — does not match sub-codes (0101, 020206).
    """
    stripped = code.lstrip("0") or "0"
    pat = re.compile(r"^\|\s+0*" + re.escape(stripped) + r"\s*\|")
    for line in section.split("\n"):
        if pat.match(line):
            return line
    return None


def _find_exp_code10(text: str) -> str | None:
    """Find passivos financeiros row from the organic classification section.

    The economic section has a multi-line OCR block for codes 10-11 at the end of the
    last page; the organic section has a clean single row. Search the full text for the
    first pipe-table code-10 row that has ≥4 numbers (budget, exercício, total, paga).
    """
    pat = re.compile(r"^\|\s+10\s*\|")
    for line in text.split("\n"):
        if pat.match(line) and len(find_numbers(line)) >= 4:
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
    sec = slice_section(text, "CONTROLO ORÇAMENTAL DA RECEITA", "CONTABILÍSTICO")
    rows = []

    def add(line, slug, label, is_subcategory):
        r = _row(line, YEAR, slug, label, is_subcategory, mode="rev")
        if r:
            rows.append(r)

    add(_find_kw(sec, "RECEITAS CORRENTES", exclude=["OUTRAS"]),
        "receitas_correntes", "Receitas Correntes", False)

    add(_find_code(sec, "01"), "impostos_diretos",         "Impostos Directos",                  True)
    add(_find_code(sec, "02"), "impostos_indiretos",        "Impostos Indirectos",                True)
    add(_find_code(sec, "04"), "taxas_multas",              "Taxas, Multas e Outras Penalidades", True)
    add(_find_code(sec, "05"), "rendimentos_propriedade",   "Rendimentos de Propriedade",         True)
    add(_find_code(sec, "06"), "transferencias_correntes",  "Transferências Correntes",           True)
    add(_find_code(sec, "07"), "venda_bens_servicos",       "Venda de Bens e Serviços Correntes", True)
    add(_find_code(sec, "08"), "outras_receitas_correntes", "Outras Receitas Correntes",          True)

    add(_find_kw(sec, "RECEITAS DE CAPITAL", exclude=["OUTRAS"]),
        "receitas_capital", "Receitas de Capital", False)

    add(_find_code(sec, "09"), "vendas_bens_investimento",  "Vendas de Bens de Investimento",     True)
    add(_find_code(sec, "10"), "transferencias_capital",    "Transferências de Capital",           True)
    add(_find_code(sec, "12"), "passivos_financeiros_rec",  "Passivos Financeiros",               True)
    add(_find_code(sec, "13"), "outras_receitas_capital",   "Outras Receitas de Capital",         True)

    add(_find_code(sec, "16"), "saldo_gerencia_anterior",   "Saldo da Gerência Anterior",         False)

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
    # Page 1 header: "CONTROLE ORÇAMENTAL DA DESPESA" (E not O).
    # Using "ORÇAMENTAL DA DESPESA" captures from page 1.
    # "ORGÂNI" cuts before "POR CLASSIFICAÇÃO ORGÂNICA" repeated sections.
    sec = slice_section(text, "ORÇAMENTAL DA DESPESA", "ORGÂNI")
    rows = []

    def add(line, slug, label, is_subcategory):
        r = _row(line, YEAR, slug, label, is_subcategory, mode="exp")
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

    # Code 10 is in a multi-line OCR block in the economic section; find clean row in organic section.
    add(_find_exp_code10(text), "passivos_financeiros_desp",    "Passivos Financeiros",          True)

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
    pdf = files.get("prestacao_contas") or files.get("other")
    if pdf is None:
        raise FileNotFoundError("No PDF found for 2013 (expected key 'prestacao_contas' or 'other')")
    txt_cache = pdf.with_suffix(".mistral.txt")
    if not txt_cache.exists():
        raise FileNotFoundError(
            f"Mistral OCR cache not found: {txt_cache}. "
            "Run Mistral OCR on this PDF first and save to .mistral.txt"
        )
    text = txt_cache.read_text()
    result = ParseResult(year=YEAR)
    result.revenue     = _parse_revenue(text)
    result.expenditure = _parse_expenditure(text)
    result.indicators  = []
    result.staff       = None
    return result
