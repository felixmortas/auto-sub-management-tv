"""
Unit tests for ExcelManager.

All calls to gspread are mocked, so tests never touch the network or the
real Google Sheets API.

Run with:
    pytest test_excel_manager.py -v
"""

from unittest.mock import MagicMock

import gspread
import pytest

from services.excel_manager import ExcelManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def service(monkeypatch):
    """
    Build an ExcelManager instance with gspread fully mocked out.

    ExcelManager.__init__ authenticates and opens the spreadsheet right
    away, so gspread must be patched *before* instantiation (unlike
    OutlookService, which authenticates lazily).
    """
    fake_gc = MagicMock(name="fake_gspread_client")
    fake_sh = MagicMock(name="fake_spreadsheet")
    fake_gc.open_by_key.return_value = fake_sh

    monkeypatch.setattr(
        "services.excel_manager.gspread.service_account_from_dict",
        MagicMock(return_value=fake_gc),
    )

    manager = ExcelManager(
        spreadsheet_id="fake-spreadsheet-id",
        credentials_dict={"type": "service_account", "project_id": "fake"},
    )
    # Keep a handle on the fake spreadsheet so individual tests can
    # configure worksheet() / get_all_records() / find() return values.
    manager._fake_sh = fake_sh
    return manager


def make_cell(row):
    """Build a fake gspread.Cell-like object with just a .row attribute."""
    cell = MagicMock()
    cell.row = row
    return cell


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------

class TestInit:

    def test_authenticates_and_opens_spreadsheet(self, monkeypatch):
        fake_gc = MagicMock()
        fake_sh = MagicMock()
        fake_gc.open_by_key.return_value = fake_sh
        mock_service_account = MagicMock(return_value=fake_gc)

        monkeypatch.setattr(
            "services.excel_manager.gspread.service_account_from_dict",
            mock_service_account,
        )
        credentials = {"type": "service_account"}

        manager = ExcelManager(spreadsheet_id="sheet-123", credentials_dict=credentials)

        mock_service_account.assert_called_once_with(credentials)
        fake_gc.open_by_key.assert_called_once_with("sheet-123")
        assert manager.sh is fake_sh


# ---------------------------------------------------------------------------
# find_member_in_sheet
# ---------------------------------------------------------------------------

class TestFindMemberInSheet:

    def test_finds_member_by_email_in_column_k(self, service):
        ws = service._fake_sh.worksheet.return_value
        ws.find.return_value = make_cell(row=5)
        ws.row_values.return_value = ["Dupont", "Jean", "..."]

        result = service.find_member_in_sheet("2024", email="jean@example.com")

        assert result == ["Dupont", "Jean", "..."]
        ws.find.assert_called_once_with("jean@example.com", in_column=11)
        ws.row_values.assert_called_once_with(5)

    def test_finds_member_by_last_name_in_column_a(self, service):
        ws = service._fake_sh.worksheet.return_value
        ws.find.return_value = make_cell(row=3)
        ws.row_values.return_value = ["Martin", "Alice", "..."]

        result = service.find_member_in_sheet("2024", last_name="Martin")

        assert result == ["Martin", "Alice", "..."]
        ws.find.assert_called_once_with("Martin", in_column=1)

    def test_email_takes_priority_over_last_name(self, service):
        ws = service._fake_sh.worksheet.return_value
        ws.find.return_value = make_cell(row=1)
        ws.row_values.return_value = ["Row"]

        service.find_member_in_sheet("2024", email="a@b.com", last_name="Martin")

        ws.find.assert_called_once_with("a@b.com", in_column=11)

    def test_returns_none_when_no_criteria_given(self, service):
        ws = service._fake_sh.worksheet.return_value

        result = service.find_member_in_sheet("2024")

        assert result is None
        ws.find.assert_not_called()

    def test_returns_none_when_cell_not_found(self, service):
        ws = service._fake_sh.worksheet.return_value
        ws.find.return_value = None

        result = service.find_member_in_sheet("2024", email="unknown@example.com")

        assert result is None

    def test_returns_none_when_worksheet_missing(self, service):
        service._fake_sh.worksheet.side_effect = gspread.WorksheetNotFound("2024")

        result = service.find_member_in_sheet("2024", email="a@b.com")

        assert result is None

    def test_returns_none_on_unexpected_error(self, service):
        ws = service._fake_sh.worksheet.return_value
        ws.find.side_effect = Exception("API quota exceeded")

        result = service.find_member_in_sheet("2024", email="a@b.com")

        assert result is None


# ---------------------------------------------------------------------------
# list_members_in_sheet
# ---------------------------------------------------------------------------

class TestListMembersInSheet:

    def test_returns_full_names(self, service):
        ws = service._fake_sh.worksheet.return_value
        ws.get_all_records.return_value = [
            {"Prénom": "Jean", "Nom": "Dupont"},
            {"Prénom": "Alice", "Nom": "Martin"},
        ]

        result = service.list_members_in_sheet("2024")

        assert result == ["Jean Dupont", "Alice Martin"]

    def test_returns_empty_list_when_sheet_has_no_rows(self, service):
        ws = service._fake_sh.worksheet.return_value
        ws.get_all_records.return_value = []

        result = service.list_members_in_sheet("2024")

        assert result == []

    def test_returns_empty_string_when_worksheet_missing(self, service):
        service._fake_sh.worksheet.side_effect = gspread.WorksheetNotFound("2024")

        result = service.list_members_in_sheet("2024")

        assert result == ""

    def test_returns_empty_string_on_unexpected_error(self, service):
        ws = service._fake_sh.worksheet.return_value
        ws.get_all_records.side_effect = Exception("boom")

        result = service.list_members_in_sheet("2024")

        assert result == ""


# ---------------------------------------------------------------------------
# get_free_plot
# ---------------------------------------------------------------------------

class TestGetFreePlot:

    def test_returns_first_row_with_no_occupant(self, service):
        ws = service._fake_sh.worksheet.return_value
        ws.get_all_records.return_value = [
            {"Numéro Parcelle": "P1", "Occupant Actuel": "a@b.com"},
            {"Numéro Parcelle": "P2", "Occupant Actuel": ""},
            {"Numéro Parcelle": "P3", "Occupant Actuel": ""},
        ]

        plot_number, row_index = service.get_free_plot()

        # Row 2 in the spreadsheet corresponds to data index 0 (start=2 offset).
        assert plot_number == "P2"
        assert row_index == 3

    def test_returns_none_when_no_free_plot(self, service):
        ws = service._fake_sh.worksheet.return_value
        ws.get_all_records.return_value = [
            {"Numéro Parcelle": "P1", "Occupant Actuel": "a@b.com"},
        ]

        plot_number, row_index = service.get_free_plot()

        assert plot_number is None
        assert row_index is None


# ---------------------------------------------------------------------------
# assign_plot
# ---------------------------------------------------------------------------

class TestAssignPlot:

    def test_writes_email_in_occupant_column(self, service):
        ws = service._fake_sh.worksheet.return_value

        service.assign_plot("P2", row_index=3, email="jean@example.com")

        ws.update_cell.assert_called_once_with(3, 2, "jean@example.com")


# ---------------------------------------------------------------------------
# remove_plot
# ---------------------------------------------------------------------------

class TestRemovePlot:

    def test_clears_occupant_when_plot_found(self, service):
        ws = service._fake_sh.worksheet.return_value
        ws.get_all_records.return_value = [
            {"Numéro Parcelle": "P1", "Occupant Actuel": "a@b.com"},
            {"Numéro Parcelle": "P2", "Occupant Actuel": "b@c.com"},
        ]

        service.remove_plot("P2")

        ws.update_cell.assert_called_once_with(3, 2, "")

    def test_does_nothing_when_plot_not_found(self, service):
        ws = service._fake_sh.worksheet.return_value
        ws.get_all_records.return_value = [
            {"Numéro Parcelle": "P1", "Occupant Actuel": "a@b.com"},
        ]

        service.remove_plot("PX")

        ws.update_cell.assert_not_called()


# ---------------------------------------------------------------------------
# add_new_row
# ---------------------------------------------------------------------------

class TestAddNewRow:

    def test_appends_row_to_existing_sheet(self, service):
        ws = service._fake_sh.worksheet.return_value

        service.add_new_row("2024", ["Dupont", "Jean", "jean@example.com"])

        ws.append_row.assert_called_once_with(["Dupont", "Jean", "jean@example.com"])

    def test_silently_ignores_missing_worksheet(self, service):
        service._fake_sh.worksheet.side_effect = gspread.exceptions.WorksheetNotFound("2024")

        # Should not raise.
        service.add_new_row("2024", ["a", "b"])

    def test_silently_ignores_unexpected_error(self, service):
        ws = service._fake_sh.worksheet.return_value
        ws.append_row.side_effect = Exception("boom")

        # Should not raise.
        service.add_new_row("2024", ["a", "b"])
