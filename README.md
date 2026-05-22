# contas-municipais

![banner](https://raw.githubusercontent.com/openlousada/contas-municipais/main/banner.png)

Framework Python para extração e parsing de relatórios financeiros de municípios portugueses.

Suporta os dois sistemas contabilísticos usados pelas autarquias locais:

- **POCAL** — Plano Oficial de Contabilidade das Autarquias Locais (até 2017)
- **SNC-AP** — Sistema de Normalização Contabilística para as Administrações Públicas (desde 2018)

---

## Instalação

```bash
pip install contas-municipais
```

Recomenda-se também instalar `poppler` para melhor extração de texto (pdftotext):

```bash
# macOS
brew install poppler

# Ubuntu/Debian
apt-get install poppler-utils
```

---

## Utilização rápida

```python
from pathlib import Path
from contas_municipais import extract_text, slice_section, parse_budget_table
from contas_municipais.sncap import REVENUE_CATEGORIES, EXPENDITURE_CATEGORIES

text = extract_text(Path("relatorio_gestao_2023.pdf"))

rev_section = slice_section(text, "quadro 1", "1.2 execução da despesa")
exp_section = slice_section(text, "1.2 execução da despesa", "2.")

receita = parse_budget_table(rev_section, REVENUE_CATEGORIES, year=2023)
despesa = parse_budget_table(exp_section, EXPENDITURE_CATEGORIES, year=2023)

for row in receita:
    print(row["label_pt"], row["executed_amount"])
```

---

## Município de referência

O pacote inclui um parser validado para **Lousada** (NIF 505279460), com cobertura de **2012 a 2024**:

```python
from pathlib import Path
from contas_municipais.municipalities.lousada import parse

result = parse(year=2023, files={
    "relatorio_gestao": Path("relatorio_gestao_2023.pdf"),
    "prestacao_contas": Path("prestacao_contas_2023.pdf"),
})

print(result.revenue)
print(result.expenditure)
```

Os ficheiros necessários variam por ano. Consulte o docstring de cada módulo `y20XX.py` para os detalhes.

---

## Estrutura do pacote

```
contas_municipais/
├── base.py                  # Utilitários de extração e parsing
├── sncap/
│   ├── __init__.py          # Documentação do formato SNC-AP
│   └── categories.py        # Mapas de categorias (receita e despesa)
├── pocal/
│   ├── __init__.py          # Documentação do formato POCAL
│   └── categories.py        # Mapas de categorias (receita e despesa)
└── municipalities/
    └── lousada/             # Parser de referência (2012–2024)
```

---

## API principal

### `extract_text(pdf_path: Path) -> str`

Extrai texto de um PDF com fallback automático entre `pdftotext -layout` e `pdfplumber`.

### `slice_section(text, start, end) -> str`

Isola uma secção do texto entre dois marcadores (case-insensitive).

### `parse_budget_table(section_text, category_map, year, ...) -> list[dict]`

Faz o parsing de uma tabela orçamental (receita ou despesa). Devolve uma lista de dicts com os campos `year`, `category`, `label_pt`, `is_subcategory`, `budget_amount`, `executed_amount`, `execution_pct`, `global_pct`.

Os índices de coluna são configuráveis via `col_budget`, `col_executed`, `col_exec_pct`, `col_global_pct` para acomodar diferenças entre formatos.

### `find_numbers(line: str) -> list[float]`

Extrai números em formato português (`1.234.567,89`) de uma linha de texto.

---

## Adicionar o seu município

Consulte [CONTRIBUTING.md](CONTRIBUTING.md) para um guia passo a passo.

---

## Licença

MIT © [Open Lousada](https://github.com/openlousada)
