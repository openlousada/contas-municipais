"""Tests for contas_municipais.base pure functions."""
import pytest
from contas_municipais.base import (
    find_numbers,
    parse_budget_table,
    parse_snc_table,
    slice_section,
)


class TestFindNumbers:
    def test_dot_thousands(self):
        assert find_numbers("Total 1.234.567,89 €") == [1234567.89]

    def test_space_thousands(self):
        assert find_numbers("Receita 27 279 272,55 €") == [27279272.55]

    def test_multiple_numbers(self):
        assert find_numbers("100,00 200,50 300,75") == [100.0, 200.5, 300.75]

    def test_no_numbers(self):
        assert find_numbers("nenhum número aqui") == []

    def test_simple_value(self):
        assert find_numbers("45,00") == [45.0]


class TestSliceSection:
    TEXT = "HEADER\nQUADRO 1\nreceita line\nQUADRO 2\ndespesa line\nEND"

    def test_extracts_section(self):
        result = slice_section(self.TEXT, "QUADRO 1", "QUADRO 2")
        assert "receita line" in result
        assert "despesa line" not in result

    def test_case_insensitive(self):
        result = slice_section(self.TEXT, "quadro 1", "quadro 2")
        assert "receita line" in result

    def test_missing_start_returns_empty(self):
        assert slice_section(self.TEXT, "NONEXISTENT", "QUADRO 2") == ""

    def test_includes_start_line(self):
        result = slice_section(self.TEXT, "QUADRO 1", "QUADRO 2")
        assert "QUADRO 1" in result


class TestParseBudgetTable:
    CATEGORY_MAP = {
        "RECEITAS CORRENTES": ("receitas_correntes", False),
        "IMPOSTOS DIRECTOS":  ("impostos_diretos",  True),
    }

    def test_extracts_matching_rows(self):
        section = (
            "RECEITAS CORRENTES   1.000,00   900,00   90,00   45,00\n"
            "IMPOSTOS DIRECTOS      500,00   450,00   90,00   22,50\n"
            "IGNORADA               100,00    80,00   80,00    8,00\n"
        )
        rows = parse_budget_table(section, self.CATEGORY_MAP, year=2023)
        assert len(rows) == 2
        assert rows[0]["category"] == "receitas_correntes"
        assert rows[0]["budget_amount"] == 1000.0
        assert rows[0]["executed_amount"] == 900.0
        assert rows[0]["year"] == 2023
        assert rows[1]["is_subcategory"] is True

    def test_ignores_duplicates(self):
        section = (
            "RECEITAS CORRENTES   1.000,00   900,00   90,00   45,00\n"
            "RECEITAS CORRENTES   2.000,00   800,00   40,00   20,00\n"
        )
        rows = parse_budget_table(section, self.CATEGORY_MAP, year=2023)
        assert len(rows) == 1
        assert rows[0]["budget_amount"] == 1000.0

    def test_missing_numbers_returns_none(self):
        section = "RECEITAS CORRENTES\n"
        rows = parse_budget_table(section, self.CATEGORY_MAP, year=2023)
        assert rows[0]["budget_amount"] is None
        assert rows[0]["executed_amount"] is None

    def test_parse_snc_table_is_alias(self):
        assert parse_snc_table is parse_budget_table


class TestImports:
    """Verify all year parsers can be imported without error."""

    def test_lousada_package_importable(self):
        import contas_municipais.municipalities.lousada as lousada
        assert callable(lousada.parse)
        assert callable(lousada.supported_years)

    def test_supported_years(self):
        from contas_municipais.municipalities.lousada import supported_years
        years = supported_years()
        assert years == list(range(2012, 2025))

    def test_all_year_modules_importable(self):
        from contas_municipais.municipalities.lousada import (
            y2012, y2013, y2014, y2015, y2016, y2017,
            y2018, y2019, y2020, y2021, y2022, y2023, y2024,
        )
        for mod in (y2012, y2013, y2014, y2015, y2016, y2017,
                    y2018, y2019, y2020, y2021, y2022, y2023, y2024):
            assert callable(mod.parse)
