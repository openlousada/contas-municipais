# Guia de Contribuição

Este documento explica como adicionar o parser do seu município ao pacote `contas-municipais`.

O município de **Lousada** serve como implementação de referência. Leia o código em `src/contas_municipais/municipalities/lousada/` antes de começar.

---

## Pré-requisitos

- Python 3.11+
- `poppler-utils` instalado no sistema (para `pdftotext -layout`)
- PDFs de prestação de contas do seu município (Relatório de Gestão e/ou Prestação de Contas)

---

## Estrutura a criar

```
src/contas_municipais/municipalities/
└── <nome_municipio>/          # ex: sintra, porto, braga
    ├── __init__.py            # dispatcher parse(year, files) -> ParseResult
    ├── y2018.py               # um módulo por ano suportado
    ├── y2019.py
    └── ...
```

---

## Passo 1 — Identificar o formato

Abra os PDFs do seu município e determine:

- **SNC-AP** (2018 em diante): procure "Quadro 1" para receita e "Quadro 2" para despesa.
- **POCAL** (até 2017): procure "Mapa do Controlo Orçamental da Receita" e "Mapa do Controlo Orçamental da Despesa".

Use `extract_text()` para ver o texto extraído:

```python
from pathlib import Path
from contas_municipais import extract_text

text = extract_text(Path("relatorio_gestao_2023.pdf"))
print(text[:5000])
```

---

## Passo 2 — Identificar os marcadores de secção

Localize as strings exatas que delimitam as tabelas de receita e despesa.

Para SNC-AP, os marcadores típicos são:

```python
start_receita = "quadro 1"          # ou "1.1 execução da receita"
end_receita   = "1.2 execução da despesa"
start_despesa = "1.2 execução da despesa"
end_despesa   = "2."                # ou o título da secção seguinte
```

Para POCAL:

```python
start_receita = "CONTROLO ORÇAMENTAL DA RECEITA"
end_receita   = "CONTROLO ORÇAMENTAL DA DESPESA"
start_despesa = "CONTROLO ORÇAMENTAL DA DESPESA"
end_despesa   = "MAPA DE FLUXOS DE CAIXA"       # ou similar
```

Verifique com `slice_section()`:

```python
from contas_municipais import slice_section

section = slice_section(text, "quadro 1", "1.2 execução da despesa")
print(section[:2000])
```

---

## Passo 3 — Verificar o layout de colunas

Execute `find_numbers()` em algumas linhas da tabela para confirmar a ordem dos valores:

```python
from contas_municipais import find_numbers

for line in section.split("\n"):
    nums = find_numbers(line)
    if nums:
        print(repr(line[:60]), "->", nums)
```

O layout típico do SNC-AP é `[dotação, executado, % execução, % global]`.

O POCAL pode variar — compare com os parsers de referência em `lousada/y2012.py` a `y2017.py`.

Se o layout coincidir com o padrão SNC-AP, use os índices por defeito. Caso contrário, ajuste os parâmetros `col_budget`, `col_executed`, etc.

---

## Passo 4 — Criar o módulo do ano

Crie `src/contas_municipais/municipalities/<nome>/y<ano>.py`:

```python
"""
Parser para <Município>, ano <AAAA>.

Formato: SNC-AP
Ficheiros necessários:
  - relatorio_gestao: Relatório de Gestão <AAAA>.pdf
"""
from pathlib import Path
from contas_municipais.base import ParseResult, extract_text, slice_section, parse_budget_table
from contas_municipais.sncap.categories import REVENUE_CATEGORIES, EXPENDITURE_CATEGORIES


def parse(files: dict[str, Path]) -> ParseResult:
    text = extract_text(files["relatorio_gestao"])

    rev = slice_section(text, "quadro 1", "1.2 execução da despesa")
    exp = slice_section(text, "1.2 execução da despesa", "2.")

    return ParseResult(
        year=<AAAA>,
        revenue=parse_budget_table(rev, REVENUE_CATEGORIES, year=<AAAA>),
        expenditure=parse_budget_table(exp, EXPENDITURE_CATEGORIES, year=<AAAA>),
    )
```

Para POCAL, importe de `contas_municipais.pocal.categories` em vez de `sncap.categories`.

---

## Passo 5 — Criar o dispatcher `__init__.py`

```python
"""
Parser para o Município de <Nome> (NIF <NIF>).

Cobre os exercícios fiscais de <início> a <fim>.
"""
from pathlib import Path
from contas_municipais.base import ParseResult
from . import y2018, y2019  # adicione os anos suportados

_REGISTRY = {
    2018: y2018,
    2019: y2019,
}


def parse(year: int, files: dict[str, Path]) -> ParseResult:
    parser = _REGISTRY.get(year)
    if parser is None:
        raise NotImplementedError(f"Sem parser validado para o ano {year}.")
    return parser.parse(files)


def supported_years() -> list[int]:
    return sorted(_REGISTRY.keys())
```

---

## Passo 6 — Testar

```python
from pathlib import Path
from contas_municipais.municipalities.<nome> import parse

result = parse(year=2023, files={
    "relatorio_gestao": Path("relatorio_gestao_2023.pdf"),
})

assert result.revenue, "Receita vazia — verifique os marcadores de secção"
assert result.expenditure, "Despesa vazia — verifique os marcadores de secção"

for row in result.revenue:
    print(row["label_pt"], row["executed_amount"])
```

---

## Dicas e problemas comuns

**Rubricas não reconhecidas**

Se `parse_budget_table()` devolver uma lista vazia, imprima as linhas da secção e compare os prefixos com as chaves de `REVENUE_CATEGORIES` / `EXPENDITURE_CATEGORIES`. Alguns municípios usam variantes ortográficas (ex: "DIRETOS" vs "DIRECTOS") — adicione-as ao mapa de categorias.

**Percentagem de execução POCAL**

O formato POCAL usa ponto como separador decimal (`90.77`) em vez de vírgula, pelo que `find_numbers()` não o apanha. Use um regex adicional para essa coluna (veja os parsers de Lousada como exemplo).

**PDFs digitalizados**

`extract_text()` devolve texto vazio ou com muito ruído em PDFs sem camada de texto. Nesse caso é necessário OCR — `tesseract` ou `ocrmypdf` são opções comuns.

**Tabelas fragmentadas em múltiplas páginas**

Alguns municípios têm quebras de página dentro da tabela. Use `slice_section()` com marcadores mais amplos e filtre as linhas de cabeçalho repetidas.

---

## Enviar um pull request

1. Crie um fork do repositório.
2. Adicione o seu município em `src/contas_municipais/municipalities/<nome>/`.
3. Documente o NIF e os anos suportados no `__init__.py`.
4. Abra um pull request com a descrição: quais anos cobertos, quais ficheiros necessários, e quaisquer quirks específicos do município.
