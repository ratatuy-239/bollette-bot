import re
import logging
import pdfplumber

logger = logging.getLogger(__name__)

MONTH_MAP = {
    "gennaio": "Gennaio", "febbraio": "Febbraio", "marzo": "Marzo",
    "aprile": "Aprile", "maggio": "Maggio", "giugno": "Giugno",
    "luglio": "Luglio", "agosto": "Agosto", "settembre": "Settembre",
    "ottobre": "Ottobre", "novembre": "Novembre", "dicembre": "Dicembre",
}


def parse_bolletta(pdf_path: str) -> dict | None:
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as e:
        logger.error(f"Failed to open PDF: {e}")
        return None

    # Billing period: "01 marzo 2026 - 31 marzo 2026"
    month_match = re.search(
        r'\d{1,2}\s+(\w+)\s+\d{4}\s*[-–]\s*\d{1,2}\s+\w+\s+\d{4}', text, re.IGNORECASE
    )
    month = None
    if month_match:
        month = MONTH_MAP.get(month_match.group(1).lower())

    # kWh total: "Consumo totale fatturato 350,77 kWh"
    kwh_match = re.search(r'Consumo totale fatturato\s+([\d]+[,\.][\d]+)\s*kWh', text, re.IGNORECASE)
    kwh_total = float(kwh_match.group(1).replace(",", ".")) if kwh_match else None

    # Costo energia: "A Quota Consumi: 87,99 €"
    energia_match = re.search(r'A\s+Quota Consumi:\s*([\d]+[,\.][\d]+)', text, re.IGNORECASE)
    costo_energia = float(energia_match.group(1).replace(",", ".")) if energia_match else None

    # Total: "Importo totale da\npagare\n140,00 €"
    total_match = re.search(r'Importo totale da\s+pagare\s+([\d]+[,\.][\d]+)\s*€', text, re.IGNORECASE)
    total = float(total_match.group(1).replace(",", ".")) if total_match else None

    if not all([month, kwh_total, costo_energia, total]):
        logger.warning(f"Incomplete parse: month={month}, kwh={kwh_total}, energia={costo_energia}, total={total}")
        return None

    return {
        "month": month,
        "kwh_total": kwh_total,
        "costo_energia": costo_energia,
        "costo_accessori": round(total - costo_energia, 2),
    }
