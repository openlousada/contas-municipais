"""
Parser for fiscal year 2017.

Source: 3466_original.pdf (168 pages, scanned), POCAL format
OCR: Mistral OCR — output cached as .mistral.txt
"""
import re
from pathlib import Path
from contas_municipais.base import ParseResult, slice_section

YEAR = 2017

# POCAL execution-% values use 1 decimal place ("109,8") — the base _PT_NUM requires exactly 2.
# Override locally to capture both 1- and 2-decimal numbers.
_PT_NUM = re.compile(r"\d{1,3}(?:[. ]\d{3})*,\d{1,2}")

# Some OCR lines use period-decimal for pct at end of line ("94.9", "103.3") — fallback pattern.
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
    """Return the 'cobrada_liquida' (executed) value from a POCAL revenue row.

    The executed value repeats 2+ times in nums[1:] between budget and pct.
    Returns the most-frequent value; None if no value repeats (e.g. OUTRAS RECEITAS DE CAPITAL).
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

    Detects futuros by checking nums[1] != nums[2].
    No futuros → paga = nums[3]. Futuros present → paga = nums[4].
    """
    if len(nums) < 4:
        return None
    futuros = len(nums) >= 3 and nums[2] != nums[1] and nums[2] > 100
    idx = 4 if futuros else 3
    return nums[idx] if len(nums) > idx else None


def _row(line: str | None, year: int, slug: str, label: str, is_subcategory: bool,
         mode: str = "rev") -> dict | None:
    """Build a row dict from a matched OCR line. mode='rev' or 'exp'."""
    if not line:
        return None
    nums = find_numbers(line)
    if not nums:
        return None
    budget = nums[0]
    pct_threshold = 300 if mode == "rev" else 200
    pct = nums[-1] if len(nums) >= 2 and nums[-1] < pct_threshold else None
    if pct is None:
        m = _PCT_PERIOD_END.search(line.rstrip())
        if m:
            val = float(m.group(1) + "." + m.group(2))
            if 0 < val <= pct_threshold:
                pct = val
    if mode == "rev":
        executed = _rev_executed(nums)
    else:
        executed = _exp_executed(nums)
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
    """First line containing keyword (case-insensitive), skipping any exclude terms."""
    kw = keyword.upper()
    for line in section.split("\n"):
        upper = line.upper()
        if kw in upper and not any(ex.upper() in upper for ex in exclude):
            return line
    return None


def _find_code(section: str, code: str) -> str | None:
    """First POCAL row with exactly this 1-2 digit code (e.g. '01', '8')."""
    pat = re.compile(r"\|\s*0*" + re.escape(code.lstrip("0") or "0") + r"\s*\|")
    for line in section.split("\n"):
        if pat.search(line):
            return line
    return None


def _parse_revenue(text: str) -> list[dict]:
    sec = slice_section(text, "CONTROLO ORÇAMENTAL DA RECEITA", "ORÇAMENTAL DA DESPESA")
    rows = []

    def add(line, slug, label, is_subcategory):
        r = _row(line, YEAR, slug, label, is_subcategory, mode="rev")
        if r:
            rows.append(r)

    add(_find_kw(sec, "RECEITAS CORRENTES", exclude=["OUTRAS"]),
        "receitas_correntes", "Receitas Correntes", False)

    add(_find_code(sec, "01"), "impostos_diretos",          "Impostos Directos",                    True)
    add(_find_code(sec, "02"), "impostos_indiretos",         "Impostos Indirectos",                  True)
    add(_find_code(sec, "04"), "taxas_multas",               "Taxas, Multas e Outras Penalidades",   True)
    add(_find_code(sec, "05"), "rendimentos_propriedade",    "Rendimentos de Propriedade",           True)
    add(_find_code(sec, "06"), "transferencias_correntes",   "Transferências Correntes",             True)
    add(_find_code(sec, "07"), "venda_bens_servicos",        "Venda de Bens e Serviços Correntes",   True)
    add(_find_code(sec, "08"), "outras_receitas_correntes",  "Outras Receitas Correntes",            True)

    add(_find_kw(sec, "RECEITAS DE CAPITAL", exclude=["OUTRAS"]),
        "receitas_capital", "Receitas de Capital", False)

    add(_find_code(sec, "09"), "vendas_bens_investimento",   "Vendas de Bens de Investimento",       True)
    add(_find_code(sec, "10"), "transferencias_capital",     "Transferências de Capital",             True)
    add(_find_code(sec, "12"), "passivos_financeiros_rec",   "Passivos Financeiros",                 True)

    # OUTRAS RECEITAS DE CAPITAL — cobrada_liquida is empty (nothing collected)
    outras_cap_line = _find_code(sec, "13")
    if outras_cap_line:
        nums = find_numbers(outras_cap_line)
        rows.append({
            "year": YEAR, "category": "outras_receitas_capital",
            "label_pt": "Outras Receitas de Capital", "is_subcategory": True,
            "budget_amount": nums[0] if nums else None,
            "executed_amount": None, "execution_pct": None, "global_pct": None,
        })

    # SALDO DA GERÊNCIA ANTERIOR — budget only, nothing collected
    saldo_line = _find_code(sec, "16")
    if saldo_line:
        nums = find_numbers(saldo_line)
        rows.append({
            "year": YEAR, "category": "saldo_gerencia_anterior",
            "label_pt": "Saldo da Gerência Anterior", "is_subcategory": False,
            "budget_amount": nums[0] if nums else None,
            "executed_amount": None, "execution_pct": None, "global_pct": None,
        })

    # Total
    total_line = _find_kw(sec, "TOTAL")
    if total_line:
        r = _row(total_line, YEAR, "total_receitas", "Total das Receitas", False, mode="rev")
        if r:
            rows.append(r)

    return rows


def _parse_expenditure(text: str) -> list[dict]:
    # Economic classification only — stop before the organic section
    sec = slice_section(text, "ORÇAMENTAL DA DESPESA", "CLASSIFICAÇÃO ORGÂNICA")
    rows = []

    def add(line, slug, label, is_subcategory):
        r = _row(line, YEAR, slug, label, is_subcategory, mode="exp")
        if r:
            rows.append(r)

    add(_find_kw(sec, "DESPESAS CORRENTES", exclude=["COM O", "OUTRAS"]),
        "despesas_correntes", "Despesas Correntes", False)

    add(_find_code(sec, "01"), "despesas_pessoal",           "Despesas com o Pessoal",              True)
    add(_find_code(sec, "02"), "aquisicao_bens_servicos",    "Aquisição de Bens e Serviços",        True)
    add(_find_code(sec, "03"), "juros_encargos",             "Juros e Outros Encargos",             True)
    add(_find_code(sec, "04"), "transferencias_correntes_desp", "Transferências Correntes",         True)
    add(_find_code(sec, "05"), "subsidios",                  "Subsídios",                           True)
    add(_find_code(sec, "06"), "outras_despesas_correntes",  "Outras Despesas Correntes",           True)

    add(_find_kw(sec, "DESPESAS DE CAPITAL"),
        "despesas_capital", "Despesas de Capital", False)

    # OCR garbles code 07 budget; corrected below by deriving from capital total minus other codes.
    add(_find_code(sec, "07"), "aquisicao_bens_capital",     "Aquisição de Bens de Capital",        True)
    add(_find_code(sec, "08"), "transferencias_capital_desp","Transferências de Capital",            True)
    add(_find_code(sec, "09"), "activos_financeiros",        "Activos Financeiros",                  True)
    add(_find_code(sec, "10"), "passivos_financeiros_desp",  "Passivos Financeiros",                True)

    # Derive code 07 budget from capital total minus other capital codes.
    by_cat = {r["category"]: r for r in rows}
    cap_row = by_cat.get("despesas_capital")
    cap_07  = by_cat.get("aquisicao_bens_capital")
    if cap_row and cap_07 and cap_row.get("budget_amount"):
        other = sum(
            by_cat.get(c, {}).get("budget_amount") or 0
            for c in ("transferencias_capital_desp", "activos_financeiros", "passivos_financeiros_desp")
        )
        cap_07["budget_amount"] = round(cap_row["budget_amount"] - other, 2)

    # Match data row — avoids "TOTAL (6)" column-header lines.
    _total_pat = re.compile(r"\|\s+TOTAL\s+\|")
    for line in sec.split("\n"):
        if _total_pat.search(line) and find_numbers(line):
            r = _row(line, YEAR, "total_despesas", "Total das Despesas", False, mode="exp")
            if r:
                rows.append(r)
            break

    return rows


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
            if not nums and i + 1 < len(lines):
                nums = find_numbers(lines[i + 1])
            if nums and (0 <= col < len(nums) or (col < 0 and len(nums) >= -col)):
                ind.append({
                    "year": YEAR, "indicator_key": key,
                    "label_pt": label, "value": nums[col], "unit": unit,
                })
                return

    # Columns: prior | current; current year = nums[-1]
    _find("Liquidez geral",      [],               -1, "liquidity_general",   "ratio", "Liquidez geral")
    _find("Liquidez reduzida",   [],               -1, "liquidity_reduced",   "ratio", "Liquidez reduzida")
    _find("Liquidez imediata",   [],               -1, "liquidity_immediate", "ratio", "Liquidez imediata")
    _find("Solvabilidade",       [],               -1, "solvency",            "ratio", "Solvabilidade")
    _find("Autonomia financeira",["Rendibilidade"],-1, "financial_autonomy",  "%",     "Autonomia financeira")

    # Debt section
    debt_sec = slice_section(text, "LIMITE DÍVIDA TOTAL", "PESSOAL")
    for line in debt_sec.split("\n"):
        if "limite dívida total dgal" in line.lower():
            nums = find_numbers(line)
            if nums:
                ind.append({"year": YEAR, "indicator_key": "debt_limit_dgal",
                            "label_pt": "Limite Dívida Total DGAL", "value": nums[0], "unit": "€"})
                break
    for line in debt_sec.split("\n"):
        if "dívida total" in line.lower() and "limite" not in line.lower():
            nums = find_numbers(line)
            if nums:
                ind.append({"year": YEAR, "indicator_key": "total_debt",
                            "label_pt": "Dívida Total", "value": nums[0], "unit": "€"})
                break

    # LEFT column = current year
    _find("Resultado Líquido do Exercício", ["proposta", "aplicação", "reserva"],
          0, "net_result", "€", "Resultado líquido do exercício")

    return ind


def parse(files: dict[str, Path]) -> ParseResult:
    pdf = files.get("prestacao_contas") or files.get("other")
    if pdf is None:
        raise FileNotFoundError("No PDF found for 2017 (expected key 'prestacao_contas' or 'other')")
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
    result.indicators  = _parse_indicators(text)
    result.staff = None
    return result
