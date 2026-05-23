"""
Parser for fiscal year 2013.

Source: 1383_original.pdf (1.6 MB, scanned), POCAL format
OCR: Mistral OCR — output cached as .mistral.txt
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

    # Code 10 has a multi-line OCR block in the economic section; organic section has the clean row.
    add(_find_exp_code10(text), "passivos_financeiros_desp",    "Passivos Financeiros",          True)

    total_line = _find_total_data(sec)
    if total_line:
        r = _row(total_line, YEAR, "total_despesas", "Total das Despesas", False, mode="exp")
        if r:
            rows.append(r)

    return rows


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
    result.staff = None
    return result
