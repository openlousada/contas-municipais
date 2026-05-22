"""
Suporte ao formato SNC-AP (Sistema de Normalização Contabilística
para as Administrações Públicas).

Vigente em Portugal desde 2018, o SNC-AP substituiu o POCAL como
sistema contabilístico obrigatório para as autarquias locais.

Os documentos SNC-AP organizam a execução orçamental em dois quadros:

- **Quadro 1** — Execução da receita (classificação económica)
- **Quadro 2** — Execução da despesa (classificação económica)

Âncoras típicas para slice_section()::

    # Receita
    slice_section(text, "quadro 1", "1.2 execução da despesa")

    # Despesa
    slice_section(text, "quadro 2", "1.3 estrutura")

Estrutura das colunas nas tabelas SNC-AP (índices 0-based)::

    col 0 — Dotação / Previsão inicial
    col 1 — Valor executado / Cobrado líquido
    col 2 — % de execução
    col 3 — % global (opcional)
"""
from .categories import REVENUE_CATEGORIES, EXPENDITURE_CATEGORIES

__all__ = ["REVENUE_CATEGORIES", "EXPENDITURE_CATEGORIES"]
