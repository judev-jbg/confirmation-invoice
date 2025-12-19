"""
Servicio para interactuar con Google Drive
Busca y descarga archivos JSON de facturas usando Service Account
"""
import io
import logging
from typing import Optional, Dict
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError

logger = logging.getLogger("ConfirmationInvoiceLogger")

SCOPES = ['https://www.googleapis.com/auth/drive']


class DriveService:
    """Maneja operaciones con Google Drive usando Service Account"""

    def __init__(self, credentials_file: str, folder_id: str = None):
        """
        Inicializa el servicio de Google Drive.

        Args:
            credentials_file: Ruta al archivo de credenciales de Service Account
            folder_id: ID de la carpeta donde buscar archivos (opcional)
        """
        self.service = None
        self.folder_id = folder_id
        self.credentials_file = credentials_file
        self._authenticate()

    def _authenticate(self):
        """Autentica con Google Drive API usando Service Account"""
        try:
            creds = Credentials.from_service_account_file(
                self.credentials_file,
                scopes=SCOPES
            )

            self.service = build('drive', 'v3', credentials=creds)

            # Validar conexión
            self.service.about().get(fields="user").execute()
            logger.info("✅ Google Drive Service authenticated successfully")

        except Exception as e:
            logger.error(f"❌ Error authenticating with Google Drive: {str(e)}")
            self.service = None

    def search_file_by_name(self, file_name: str) -> Optional[Dict]:
        """
        Busca un archivo por nombre en la carpeta especificada.

        Args:
            file_name: Nombre del archivo a buscar (ej: "factura_ABCDEFGH.json")

        Returns:
            Información del archivo si existe, None en caso contrario
        """
        if not self.service:
            logger.error("Google Drive service not available")
            return None

        try:
            # Construir query
            query_parts = [f"name='{file_name}'", "trashed=false"]

            if self.folder_id:
                query_parts.append(f"'{self.folder_id}' in parents")

            query = " and ".join(query_parts)

            logger.debug(f"Searching for file: {file_name}")

            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name, mimeType, modifiedTime, size)',
                pageSize=10
            ).execute()

            files = results.get('files', [])

            if files:
                logger.info(f"✅ File found in Drive: {file_name}")
                return files[0]
            else:
                logger.debug(f"File not found in Drive: {file_name}")
                return None

        except HttpError as e:
            logger.error(f"❌ Error searching file in Drive: {str(e)}")
            return None

    def download_file(self, file_id: str) -> Optional[bytes]:
        """
        Descarga un archivo desde Google Drive.

        Args:
            file_id: ID del archivo en Google Drive

        Returns:
            Contenido del archivo en bytes, None si hay error
        """
        if not self.service:
            logger.error("Google Drive service not available")
            return None

        try:
            logger.debug(f"Downloading file: {file_id}")

            request = self.service.files().get_media(fileId=file_id)
            file_buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(file_buffer, request)

            done = False
            while not done:
                status, done = downloader.next_chunk()

            file_buffer.seek(0)
            content = file_buffer.read()

            logger.info(f"✅ File downloaded successfully ({len(content)} bytes)")
            return content

        except HttpError as e:
            logger.error(f"❌ Error downloading file from Drive: {str(e)}")
            return None

    def download_file_by_name(self, file_name: str) -> Optional[bytes]:
        """
        Busca y descarga un archivo por su nombre.

        Args:
            file_name: Nombre del archivo a descargar

        Returns:
            Contenido del archivo en bytes, None si no existe o hay error
        """
        file_info = self.search_file_by_name(file_name)

        if not file_info:
            logger.warning(f"Cannot download file '{file_name}': not found")
            return None

        return self.download_file(file_info['id'])
