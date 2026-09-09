"""
Integration tests for ExcelManager.

Unlike the unit tests, these hit the REAL Google Sheets API through gspread.
They require a real service account and a real spreadsheet, and some tests
write data to that spreadsheet (then clean up after themselves), so they
are opt-in only.

Setup:
    1. Create (or reuse) a Google Cloud service account with the Sheets API
       enabled, and share the test spreadsheet with its client_email as an
       Editor.
    2. Export the following environment variables before running:
        GOOGLE_CREDS   # path to the service account JSON key
        EXCEL_TEST_SPREADSHEET_ID         # id of the test spreadsheet
        EXCEL_TEST_MEMBER_SHEET           # optional, defaults to "IntegrationTest"

    The test spreadsheet must contain:
        - A sheet named after EXCEL_TEST_MEMBER_SHEET with, at minimum, the
          columns "Nom" (A), "Prénom", and "Mail 1" (K), with at least one
          known data row.
        - A sheet named "Configuration_Parcelles" with columns
          "Numéro Parcelle" and "Occupant Actuel", with at least one row
          whose "Occupant Actuel" is empty (needed for the plot workflow
          test).

Run with:
    pytest -m integration test_excel_manager_integration.py -v

These tests are skipped automatically when the credentials are missing, so
they never break a regular CI run (`pytest -m "not integration"`).
"""

import json
import os

import pytest

from services.excel_manager import ExcelManager


# ---------------------------------------------------------------------------
# Skip condition: only run if a real service account + spreadsheet are given.
# ---------------------------------------------------------------------------

REQUIRED_ENV_VARS = [
    "GOOGLE_CREDS",
    "EXCEL_TEST_SPREADSHEET_ID",
]

missing_vars = [var for var in REQUIRED_ENV_VARS if not os.environ.get(var)]

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        bool(missing_vars),
        reason=(
            "Missing environment variables for integration tests: "
            f"{', '.join(missing_vars)}"
        ),
    ),
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def credentials_dict():
    """Load the real service account key directly from the environment variable."""
    return json.loads(os.environ["GOOGLE_CREDS"])


@pytest.fixture(scope="module")
def real_manager(credentials_dict):
    """Build a real ExcelManager pointed at the actual test spreadsheet."""
    return ExcelManager(
        spreadsheet_id=os.environ["EXCEL_TEST_SPREADSHEET_ID"],
        credentials_dict=credentials_dict,
    )


@pytest.fixture(scope="module")
def member_sheet_name():
    return os.environ.get("EXCEL_TEST_MEMBER_SHEET", "IntegrationTest")


# ---------------------------------------------------------------------------
# Authentication / connection
# ---------------------------------------------------------------------------

class TestRealConnection:

    def test_can_authenticate_and_open_spreadsheet(self, real_manager):
        """
        Validates that the service account is accepted by Google and that
        the spreadsheet id actually resolves to a real document.
        """
        assert real_manager.sh is not None
        assert real_manager.sh.title  # forces a real round trip to the API


# ---------------------------------------------------------------------------
# Member lookups
# ---------------------------------------------------------------------------

class TestRealMemberLookups:

    def test_list_members_in_existing_sheet_returns_names(
        self, real_manager, member_sheet_name
    ):
        names = real_manager.list_members_in_sheet(member_sheet_name)

        assert isinstance(names, list)
        assert len(names) > 0

    def test_list_members_in_missing_sheet_returns_empty_string(self, real_manager):
        result = real_manager.list_members_in_sheet("SheetThatDoesNotExist_XYZ")

        assert result == ""

    def test_find_member_by_last_name(self, real_manager, member_sheet_name):
        # Pull an existing name from row 2, then look it up through the
        # service to make sure the real "find" call behaves as expected.
        worksheet = real_manager.sh.worksheet(member_sheet_name)
        first_data_row = worksheet.row_values(2)
        last_name = first_data_row[0]

        result = real_manager.find_member_in_sheet(member_sheet_name, last_name=last_name)

        assert result is not None
        assert result[0] == last_name

    def test_find_member_returns_none_when_not_found(self, real_manager, member_sheet_name):
        result = real_manager.find_member_in_sheet(
            member_sheet_name, last_name="NomInexistant_XYZ_999"
        )

        assert result is None


# ---------------------------------------------------------------------------
# Plot assignment workflow (get_free_plot / assign_plot / remove_plot)
# ---------------------------------------------------------------------------

class TestRealPlotWorkflow:
    """
    Exercises the three plot-related methods together, since they operate
    on shared state in "Configuration_Parcelles". The plot is released
    again at the end so the spreadsheet is left as we found it.
    """

    def test_assign_and_release_a_free_plot(self, real_manager):
        plot_number, row_index = real_manager.get_free_plot()
        assert plot_number is not None, "Test spreadsheet needs at least one free plot"

        test_email = "integration-test@example.com"
        real_manager.assign_plot(plot_number, row_index, test_email)

        ws = real_manager.sh.worksheet("Configuration_Parcelles")
        assert ws.cell(row_index, 2).value == test_email

        # Clean up so the spreadsheet stays reusable for future test runs.
        real_manager.remove_plot(plot_number)
        assert ws.cell(row_index, 2).value in (None, "")


# ---------------------------------------------------------------------------
# add_new_row
# ---------------------------------------------------------------------------

class TestRealAddNewRow:

    def test_add_new_row_to_existing_sheet(self, real_manager, member_sheet_name):
        worksheet = real_manager.sh.worksheet(member_sheet_name)
        rows_before = len(worksheet.get_all_values())

        real_manager.add_new_row(member_sheet_name, ["[TEST]", "IntegrationRow"])

        rows_after = len(worksheet.get_all_values())
        assert rows_after == rows_before + 1

        # Clean up the row we just added.
        worksheet.delete_rows(rows_after)

    def test_add_new_row_to_missing_sheet_does_not_raise(self, real_manager):
        # Should be silently swallowed (logged at debug level), not raised.
        real_manager.add_new_row("SheetThatDoesNotExist_XYZ", ["a", "b"])
