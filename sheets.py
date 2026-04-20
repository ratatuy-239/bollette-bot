import os
import json
import logging
from google.oauth2.service_account import Credentials
import gspread

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "1zLO85tPtJkAyPclcWYlTCSlznz-oFtzOqUvhwFMtUTg")

SHEET_LUCE = "Luce"
SHEET_CONTATORE = "Contatore Picotti"


class SheetsClient:
    def __init__(self):
        creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
        if not creds_json:
            raise ValueError("GOOGLE_CREDENTIALS_JSON environment variable not set")

        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        self.gc = gspread.authorize(creds)
        self.spreadsheet = self.gc.open_by_key(SPREADSHEET_ID)

    def _get_sheet(self, name):
        return self.spreadsheet.worksheet(name)

    def _find_month_row(self, sheet, month: str) -> int | None:
        """Find row index (1-based) for a given month name. Returns the LAST match."""
        col_a = sheet.col_values(1)
        result = None
        for i, cell in enumerate(col_a):
            if cell.strip().lower() == month.strip().lower():
                result = i + 1
        return result

    def _next_empty_row(self, sheet) -> int:
        """Find first empty row in column A (1-based)."""
        col_a = sheet.col_values(1)
        return len(col_a) + 1

    # -------------------------
    # Contattore Picotti sheet
    # -------------------------
    def write_contatore(self, month: str, counter_su: float):
        """Write or update counter reading for a month.
        Columns: A=Mese, B=Sopra (reading), C=Sotto (diff — calculated externally, we skip)
        """
        sheet = self._get_sheet(SHEET_CONTATORE)
        row = self._find_month_row(sheet, month)

        if row:
            # Update existing row
            sheet.update_cell(row, 2, counter_su)
            logger.info(f"Updated Contatore row {row} for {month}")
        else:
            # Append new row
            next_row = self._next_empty_row(sheet)
            sheet.update_cell(next_row, 1, month)
            sheet.update_cell(next_row, 2, counter_su)
            logger.info(f"Inserted Contatore row {next_row} for {month}")

    # -------------------------
    # Luce sheet
    # -------------------------
    def write_luce(self, month: str, costo_energia: float, costo_accessori: float, kwh_total: float):
        """Write or update Luce row for a month.
        Columns: A=Mese, B=Costo energia, C=Costo accessori, D=Kwh total
        kWh su and kWh giu are calculated automatically by the spreadsheet.
        """
        sheet = self._get_sheet(SHEET_LUCE)
        row = self._find_month_row(sheet, month)

        values = [month, costo_energia, costo_accessori, kwh_total]

        if row:
            sheet.update([values], f"A{row}:D{row}")
            logger.info(f"Updated Luce row {row} for {month}")
        else:
            next_row = self._next_empty_row(sheet)
            sheet.update([values], f"A{next_row}:D{next_row}")
            logger.info(f"Inserted Luce row {next_row} for {month}")

    # -------------------------
    # Read results
    # -------------------------
    def get_month_result(self, month: str) -> dict | None:
        """Read columns J and K for a month from Luce sheet (results table in col H).
        H=Mese, J=A testa sopra, K=A testa sotto
        """
        sheet = self._get_sheet(SHEET_LUCE)
        col_h = sheet.col_values(8)  # column H
        row = None
        for i, cell in enumerate(col_h):
            if cell.strip().lower() == month.strip().lower():
                row = i + 1  # keep overwriting → last match wins
        if row is None:
            return None
        row_data = sheet.row_values(row)
        # J=col10(idx9), K=col11(idx10)
        return {
            "a_testa_su": row_data[9] if len(row_data) > 9 else "—",
            "a_testa_giu": row_data[10] if len(row_data) > 10 else "—",
        }

    def debug_info(self, current_month: str, billing_month: str) -> str:
        lines = []

        sheet_c = self._get_sheet(SHEET_CONTATORE)
        row_c = self._find_month_row(sheet_c, current_month)
        lines.append(
            f"*Contatore Picotti*\n"
            f"Cerco: '{current_month}' → riga {row_c or 'NON TROVATA'}"
        )

        sheet_l = self._get_sheet(SHEET_LUCE)
        row_l = self._find_month_row(sheet_l, billing_month)
        lines.append(
            f"*Luce*\n"
            f"Cerco: '{billing_month}' → riga {row_l or 'NON TROVATA'}"
        )

        return "\n\n".join(lines)

    def get_luce_row(self, month: str) -> dict | None:
        """Read a Luce row for a given month."""
        sheet = self._get_sheet(SHEET_LUCE)
        row = self._find_month_row(sheet, month)
        if not row:
            return None
        row_data = sheet.row_values(row)
        return {
            "month": row_data[0] if len(row_data) > 0 else "",
            "costo_energia": row_data[1] if len(row_data) > 1 else "—",
            "costo_accessori": row_data[2] if len(row_data) > 2 else "—",
            "kwh_total": row_data[3] if len(row_data) > 3 else "—",
        }
