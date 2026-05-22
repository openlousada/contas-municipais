"""
Suporte ao formato POCAL (Plano Oficial de Contabilidade das Autarquias Locais).

O POCAL foi o sistema contabilístico obrigatório para as autarquias portuguesas
de 1999 até 2017. Foi substituído pelo SNC-AP a partir de 2018.

Os documentos POCAL organizam a execução orçamental no:

- **Mapa do Controlo Orçamental da Receita**
- **Mapa do Controlo Orçamental da Despesa**

Âncoras típicas para slice_section()::

    # Receita
    slice_section(text, "CONTROLO ORÇAMENTAL DA RECEITA",
                        "CONTROLO ORÇAMENTAL DA DESPESA")

    # Despesa
    slice_section(text, "CONTROLO ORÇAMENTAL DA DESPESA", <âncora_fim>)

Estrutura das colunas POCAL — ATENÇÃO: difere do SNC-AP.

A receita e a despesa têm layouts de colunas diferentes, e a posição
exacta do valor executado varia entre municípios e versões de software.
Consulte os parsers de referência em municipalities/lousada/ para ver
como lidar com estas variações (modo de calcular cobrada_líquida,
detecção de "futuros" na despesa, etc.).

Colunas típicas da **receita** POCAL::

    col 0 — Previsão inicial
    col 1 — Cobrada líquida (executado) — pode repetir-se no PDF
    col N — % de execução (usa separador decimal de ponto, não vírgula)

Colunas típicas da **despesa** POCAL::

    col 0 — Dotação inicial
    col 1 — Dotação corrigida
    col 2 — Compromissos assumidos / Despesa paga
    col 3 — Despesa paga (quando há "compromissos futuros")
    col N — % de execução

Dado este layout variável, parse_budget_table() pode não funcionar
directamente para POCAL — os parsers de referência implementam lógica
própria de extracção de colunas.
"""
from .categories import REVENUE_CATEGORIES, EXPENDITURE_CATEGORIES

__all__ = ["REVENUE_CATEGORIES", "EXPENDITURE_CATEGORIES"]
