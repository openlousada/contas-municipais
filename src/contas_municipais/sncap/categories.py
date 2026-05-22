"""
Mapas de categorias SNC-AP para receita e despesa.

Cada entrada é ``{PREFIXO_MAIÚSCULAS: (slug, is_subcategory)}``.

O prefixo é comparado ao início de cada linha do PDF (insensível a
maiúsculas/minúsculas é feito em parse_budget_table). O slug é o
identificador normalizado usado nos registos devolvidos.

Estes mapas reflectem a classificação económica definida pelo SNC-AP
(Decreto-Lei n.º 192/2015) e são comuns a todos os municípios
portugueses. Se o relatório do seu município usar uma formulação
ligeiramente diferente, adicione a variante como chave extra apontando
para o mesmo slug.

Exemplo de variante::

    "IMPOSTOS DIRETOS": ("impostos_diretos", True),   # sem acento
    "IMPOSTOS DIRECTOS": ("impostos_diretos", True),   # com acento (mais comum nos PDFs)
"""

REVENUE_CATEGORIES: dict[str, tuple[str, bool]] = {
    # Receitas correntes
    "RECEITAS CORRENTES":              ("receitas_correntes",          False),
    "IMPOSTOS DIRECTOS":               ("impostos_diretos",            True),
    "IMPOSTOS DIRETOS":                ("impostos_diretos",            True),
    "IMPOSTOS INDIRECTOS":             ("impostos_indiretos",          True),
    "IMPOSTOS INDIRETOS":              ("impostos_indiretos",          True),
    "TAXAS, MULTAS":                   ("taxas_multas",                True),
    "RENDIMENTOS DE PROPRIEDADE":      ("rendimentos_propriedade",     True),
    "TRANSFERÊNCIAS CORRENTES":        ("transferencias_correntes",    True),
    "VENDA DE BENS E SERVIÇOS":        ("venda_bens_servicos",         True),
    "OUTRAS RECEITAS CORRENTES":       ("outras_receitas_correntes",   True),
    # Receitas de capital
    "RECEITAS DE CAPITAL":             ("receitas_capital",            False),
    "VENDAS BENS DE INVESTIMENTO":     ("vendas_bens_investimento",    True),
    "TRANSFERÊNCIAS DE CAPITAL":       ("transferencias_capital",      True),
    "PASSIVOS FINANCEIROS":            ("passivos_financeiros_rec",    True),
    "OUTRAS RECEITAS DE CAPITAL":      ("outras_receitas_capital",     True),
    # Outros
    "SALDO DA GERÊNCIA ANTERIOR":      ("saldo_gerencia_anterior",     False),
    "TOTAL DAS RECEITAS":              ("total_receitas",              False),
}

EXPENDITURE_CATEGORIES: dict[str, tuple[str, bool]] = {
    # Despesas correntes
    "DESPESAS CORRENTES":              ("despesas_correntes",           False),
    "DESPESAS COM O PESSOAL":          ("despesas_pessoal",             True),
    "AQUISIÇÃO DE BENS E SERVIÇOS":    ("aquisicao_bens_servicos",      True),
    "JUROS E OUTROS ENCARGOS":         ("juros_encargos",               True),
    "TRANSFERÊNCIAS CORRENTES":        ("transferencias_correntes_desp", True),
    "SUBSÍDIOS":                       ("subsidios",                    True),
    "OUTRAS DESPESAS CORRENTES":       ("outras_despesas_correntes",    True),
    # Despesas de capital
    "DESPESAS DE CAPITAL":             ("despesas_capital",             False),
    "AQUISIÇÃO DE BENS DE CAPITAL":    ("aquisicao_bens_capital",       True),
    "TRANSFERÊNCIAS DE CAPITAL":       ("transferencias_capital_desp",  True),
    "ACTIVOS FINANCEIROS":             ("activos_financeiros",          True),
    "ATIVOS FINANCEIROS":              ("activos_financeiros",          True),
    "PASSIVOS FINANCEIROS":            ("passivos_financeiros_desp",    True),
    # Total
    "TOTAL DAS DESPESAS":              ("total_despesas",               False),
}
