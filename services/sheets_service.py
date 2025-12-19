"""
Servicio para interactuar con Google Sheets
Registra las facturas enviadas en una hoja de cálculo
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger("ConfirmationInvoiceLogger")

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']


class SheetsService:
    """Maneja operaciones con Google Sheets usando Service Account"""

    def __init__(self, credentials_file: str, spreadsheet_id: str, sheet_name: str = "Facturas"):
        """
        Inicializa el servicio de Google Sheets.

        Args:
            credentials_file: Ruta al archivo de credenciales de Service Account
            spreadsheet_id: ID de la hoja de cálculo
            sheet_name: Nombre de la hoja dentro del spreadsheet
        """
        self.service = None
        self.spreadsheet_id = spreadsheet_id
        self.sheet_name = sheet_name
        self.credentials_file = credentials_file
        self._authenticate()

    def _authenticate(self):
        """Autentica con Google Sheets API usando Service Account"""
        try:
            creds = Credentials.from_service_account_file(
                self.credentials_file,
                scopes=SCOPES
            )

            self.service = build('sheets', 'v4', credentials=creds)
            logger.info("✅ Google Sheets Service authenticated successfully")

        except Exception as e:
            logger.error(f"❌ Error authenticating with Google Sheets: {str(e)}")
            self.service = None

    def append_or_update_invoice(self, reference: str, invoice_id: str, invoice_number: str) -> bool:
        """
        Añade o actualiza un registro de factura enviada en la hoja.

        Args:
            reference: Referencia del pedido (ej: ABCDEFGH)
            invoice_id: ID interno de la factura
            invoice_number: Número de factura (ej: 2024-0001)

        Returns:
            True si la operación fue exitosa
        """
        if not self.service:
            logger.error("Google Sheets service not available")
            return False

        try:
            # Preparar datos
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
            file_name = f"factura_{reference}.json"

            # Buscar si ya existe la referencia
            existing_row = self._find_row_by_reference(reference)

            if existing_row is not None:
                # Actualizar fila existente
                return self._update_row(existing_row, file_name, invoice_id, invoice_number, timestamp)
            else:
                # Añadir nueva fila
                return self._append_row(file_name, invoice_id, invoice_number, timestamp)

        except Exception as e:
            logger.error(f"Error appending/updating invoice in Sheets: {e}")
            return False

    def _find_row_by_reference(self, reference: str) -> Optional[int]:
        """
        Busca la fila que contiene una referencia específica.

        Args:
            reference: Referencia a buscar

        Returns:
            Número de fila (índice base 1) o None si no existe
        """
        try:
            file_name = f"factura_{reference}.json"
            range_name = f"{self.sheet_name}!A:A"

            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()

            values = result.get('values', [])

            for idx, row in enumerate(values, start=1):
                if row and row[0] == file_name:
                    logger.debug(f"Reference found in row {idx}")
                    return idx

            return None

        except HttpError as e:
            logger.error(f"Error finding row by reference: {e}")
            return None

    def _update_row(self, row_number: int, file_name: str, invoice_id: str, invoice_number: str, timestamp: str) -> bool:
        """Actualiza una fila existente."""
        try:
            range_name = f"{self.sheet_name}!A{row_number}:D{row_number}"
            values = [[file_name, invoice_id, invoice_number, timestamp]]

            body = {'values': values}

            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption='RAW',
                body=body
            ).execute()

            logger.info(f"✅ Updated invoice record in Sheets (row {row_number}): {invoice_number}")
            return True

        except HttpError as e:
            logger.error(f"Error updating row in Sheets: {e}")
            return False

    def _append_row(self, file_name: str, invoice_id: str, invoice_number: str, timestamp: str) -> bool:
        """Añade una nueva fila."""
        try:
            range_name = f"{self.sheet_name}!A:D"
            values = [[file_name, invoice_id, invoice_number, timestamp]]

            body = {'values': values}

            self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()

            logger.info(f"✅ Appended invoice record to Sheets: {invoice_number}")
            return True

        except HttpError as e:
            logger.error(f"Error appending row to Sheets: {e}")
            return False

    def get_all_invoices(self) -> List[Dict[str, str]]:
        """
        Obtiene todos los registros de facturas.

        Returns:
            Lista de diccionarios con los datos de las facturas
        """
        if not self.service:
            logger.error("Google Sheets service not available")
            return []

        try:
            range_name = f"{self.sheet_name}!A:D"

            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()

            values = result.get('values', [])

            # Convertir a lista de diccionarios (asumiendo primera fila como headers)
            if not values:
                return []

            headers = values[0] if values else []
            invoices = []

            for row in values[1:]:
                if len(row) >= 4:
                    invoices.append({
                        'reference': row[0],
                        'invoice_id': row[1],
                        'invoice_number': row[2],
                        'sent_date': row[3]
                    })

            logger.info(f"Retrieved {len(invoices)} invoice records from Sheets")
            return invoices

        except HttpError as e:
            logger.error(f"Error getting invoices from Sheets: {e}")
            return []
