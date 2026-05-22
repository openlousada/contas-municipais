"""
Utilitários de extração de texto e parsing de tabelas orçamentais.

Estas funções são independentes do formato contabilístico (POCAL ou SNC-AP)
e funcionam com qualquer PDF de prestação de contas municipal português.
"""

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pdfplumber

# Números no formato português: 1.234.567,89 ou 1 234 567,89
_PT_NUM = re.compile(r"\d{1,3}(?:[. ]\d{3})*,\d{2}")


@dataclass
class ParseResult:
    """Resultado estruturado do parsing de um documento de prestação de contas."""

    year: int
    revenue: list[dict] = field(default_factory=list)
    """Linhas da execução da receita. Cada dict inclui 'category', 'label_pt',
    'budget_amount', 'executed_amount', 'execution_pct'."""

    expenditure: list[dict] = field(default_factory=list)
    """Linhas da execução da despesa. Mesma estrutura que revenue."""

    indicators: list[dict] = field(default_factory=list)
    """Indicadores financeiros (dívida total, resultado líquido, etc.)."""

    staff: Optional[dict] = None
    """Resumo de recursos humanos: total, entradas, saídas."""


def extract_text(pdf_path: Path) -> str:
    """
    Extrai texto de um PDF, com fallback automático entre ferramentas.

    Tenta primeiro pdftotext -layout (preserva colunas), que produz os melhores
    resultados para tabelas orçamentais. Se não estiver disponível ou falhar,
    usa pdfplumber como alternativa.

    Args:
        pdf_path: Caminho para o ficheiro PDF.

    Returns:
        Texto extraído como string. PDFs digitalizados (sem camada de texto)
        devolvem texto vazio ou com muito ruído — ver ocr.py para esses casos.
    """
    pdftotext = shutil.which("pdftotext")
    if pdftotext:
        r = subprocess.run(
            [pdftotext, "-layout", str(pdf_path), "-"],
            capture_output=True, text=True, timeout=60,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout
    with pdfplumber.open(pdf_path) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages)


def find_numbers(line: str) -> list[float]:
    """
    Devolve todos os números em formato português encontrados numa linha.

    Reconhece separadores de milhar com ponto ou espaço, e vírgula decimal.
    Exemplos reconhecidos: "1.234.567,89", "1 234 567,89", "45,00".

    Args:
        line: Uma linha de texto extraída do PDF.

    Returns:
        Lista de floats pela ordem em que aparecem na linha.
    """
    out = []
    for m in _PT_NUM.finditer(line):
        try:
            out.append(float(m.group().replace(" ", "").replace(".", "").replace(",", ".")))
        except ValueError:
            pass
    return out


def slice_section(text: str, start: str, end: str) -> str:
    """
    Devolve o texto entre a primeira linha que contém `start` e a primeira
    linha após essa que contém `end`.

    A comparação é insensível a maiúsculas/minúsculas. Útil para isolar
    secções de tabelas orçamentais (ex: receita vs despesa).

    Args:
        text:  Texto completo extraído do PDF.
        start: Marcador de início da secção (substring, case-insensitive).
        end:   Marcador de fim da secção (substring, case-insensitive).

    Returns:
        Texto da secção, incluindo a linha de início. String vazia se não
        encontrado.

    Exemplo::

        # SNC-AP
        rev_section = slice_section(text, "quadro 1", "1.2 execução da despesa")

        # POCAL
        rev_section = slice_section(text,
                                    "CONTROLO ORÇAMENTAL DA RECEITA",
                                    "CONTROLO ORÇAMENTAL DA DESPESA")
    """
    lines = text.split("\n")
    capturing, result = False, []
    for line in lines:
        if not capturing and start.lower() in line.lower():
            capturing = True
        if capturing and result and end.lower() in line.lower():
            break
        if capturing:
            result.append(line)
    return "\n".join(result)


def parse_budget_table(
    section_text: str,
    category_map: dict[str, tuple[str, bool]],
    year: int,
    col_budget: int = 0,
    col_executed: int = 1,
    col_exec_pct: int = 2,
    col_global_pct: int = 3,
) -> list[dict]:
    """
    Faz o parsing de uma tabela orçamental (receita ou despesa).

    Percorre as linhas da secção e, para cada linha cujo início corresponda
    a uma chave do `category_map`, extrai os valores numéricos nas posições
    de coluna especificadas.

    Args:
        section_text:  Texto da secção já isolada com slice_section().
        category_map:  Dicionário ``{PREFIXO_MAIÚSCULAS: (slug, is_subcategory)}``.
                       O prefixo é comparado ao início de cada linha (após
                       remoção de espaços e pipe ``|``).
                       ``slug`` é o identificador normalizado da categoria.
                       ``is_subcategory`` indica se é subcategoria (True) ou
                       categoria agregada (False).
        year:          Ano fiscal — incluído em cada registo devolvido.
        col_budget:    Índice (0-based) do número que representa a dotação/orçamento.
                       SNC-AP: 0. POCAL receita: 0.
        col_executed:  Índice do número que representa o valor executado/cobrado.
                       SNC-AP: 1. POCAL despesa: varia — ver parsers de referência.
        col_exec_pct:  Índice da percentagem de execução. SNC-AP: 2.
        col_global_pct: Índice da percentagem global. SNC-AP: 3. Pode ser None.

    Returns:
        Lista de dicts com os campos:
        ``year``, ``category``, ``label_pt``, ``is_subcategory``,
        ``budget_amount``, ``executed_amount``, ``execution_pct``, ``global_pct``.

    Nota:
        Cada chave do ``category_map`` só é extraída uma vez (a primeira
        ocorrência). Categorias duplicadas no PDF são ignoradas.

    Exemplo::

        from contas_municipais.sncap.categories import REVENUE_CATEGORIES
        rows = parse_budget_table(section, REVENUE_CATEGORIES, year=2023)
    """
    rows, seen = [], set()
    for line in section_text.split("\n"):
        upper = line.strip().lstrip("|").strip().upper()
        matched = next((k for k in category_map if upper.startswith(k)), None)
        if not matched or matched in seen:
            continue
        seen.add(matched)
        slug, is_sub = category_map[matched]
        nums = find_numbers(line)
        rows.append({
            "year": year,
            "category": slug,
            "label_pt": matched.title(),
            "is_subcategory": is_sub,
            "budget_amount":   nums[col_budget]    if len(nums) > col_budget    else None,
            "executed_amount": nums[col_executed]  if len(nums) > col_executed  else None,
            "execution_pct":   nums[col_exec_pct]  if len(nums) > col_exec_pct  else None,
            "global_pct":      nums[col_global_pct] if col_global_pct is not None and len(nums) > col_global_pct else None,
        })
    return rows
