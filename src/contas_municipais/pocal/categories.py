"""
Mapas de categorias POCAL para receita e despesa.

O POCAL usa classificação económica idêntica ao SNC-AP nas grandes
rubricas, mas a terminologia e o nível de detalhe variam entre
municípios e anos. Estes mapas derivam dos parsers de Lousada (2012–2017)
e devem ser validados contra os PDFs do seu município.

Diferenças importantes face ao SNC-AP:

- A rubrica "SALDO DA GERÊNCIA ANTERIOR" aparece com um único número
  (previsão), sem valor executado separado.
- Algumas rubricas têm codificação numérica (ex: "01 RECEITAS CORRENTES")
  que precisa de ser removida antes da comparação de prefixos.
- A percentagem de execução usa separador decimal de ponto ("90.77")
  em vez de vírgula — não é apanhada por find_numbers() e requer
  regex próprio (ver parsers de referência).
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
    "VENDA DE BENS E SERV":            ("venda_bens_servicos",         True),
    "OUTRAS RECEITAS CORRENTES":       ("outras_receitas_correntes",   True),
    # Receitas de capital
    "RECEITAS DE CAPITAL":             ("receitas_capital",            False),
    "VENDA DE BENS DE INVESTIMENTO":   ("vendas_bens_investimento",    True),
    "TRANSFERÊNCIAS DE CAPITAL":       ("transferencias_capital",      True),
    "PASSIVOS FINANCEIROS":            ("passivos_financeiros_rec",    True),
    "OUTRAS RECEITAS DE CAPITAL":      ("outras_receitas_capital",     True),
    # Outros
    "SALDO DA GERÊNCIA ANTERIOR":      ("saldo_gerencia_anterior",     False),
    "TOTAL DAS RECEITAS":              ("total_receitas",              False),
    "TOTAL DA RECEITA":                ("total_receitas",              False),
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
    "PASSIVOS FINANCEIROS":            ("passivos_financeiros_desp",    True),
    # Total
    "TOTAL DAS DESPESAS":              ("total_despesas",               False),
    "TOTAL DA DESPESA":                ("total_despesas",               False),
}
