"""
Sistema de Confirmación de Facturas para Toolstock
Migrado desde n8n a Python

Este script:
1. Consulta la API de PrestaShop para obtener pedidos en estado 4 (preparación en curso)
2. Para cada pedido, busca su factura JSON en Google Drive
3. Descarga y procesa la información de la factura
4. Obtiene datos del cliente desde PrestaShop
5. Genera el PDF de la factura usando una API externa
6. Genera y envía un email de confirmación con la factura adjunta
7. Actualiza el estado del pedido en PrestaShop a 23 (factura enviada)
8. Registra la factura enviada en Google Sheets
9. Envía notificaciones internas de éxito o error
"""

import os
import sys
import logging
import asyncio
from dotenv import load_dotenv

# Importar servicios
from services.prestashop_service import PrestaShopService
from services.drive_service import DriveService
from services.sheets_service import SheetsService
from services.email_service import EmailService
from services.pdf_service import PDFService
from services.notifications import NotificationManager
from services.invoice_processor import InvoiceProcessor

# Cargar variables de entorno
load_dotenv()

# Configurar logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "logs/confirmation_invoice.log")

# Crear directorio de logs si no existe
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

# Configurar logger
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("ConfirmationInvoiceLogger")


def validate_environment():
    """Valida que todas las variables de entorno necesarias estén configuradas."""
    required_vars = [
        "PRESTASHOP_API_URL",
        "PRESTASHOP_API_USERNAME",
        "ORDERS_SENDER_EMAIL",
        "ORDERS_SENDER_PASSWORD",
        "EMAIL_TEMPLATE_API_URL",
        "PDF_GENERATION_API_URL",
        "GOOGLE_SERVICE_ACCOUNT_FILE",
        "GOOGLE_SHEET_ID"
    ]

    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please check your .env file")
        return False

    return True


def main():
    """Función principal."""
    try:
        # Validar configuración
        if not validate_environment():
            logger.error("Environment validation failed. Exiting.")
            sys.exit(1)

        # Obtener el entorno
        environment = os.getenv("ENVIRONMENT", "production")
        logger.info(f"Iniciando en modo: {environment.upper()}")

        # Inicializar servicios
        logger.info("Initializing services...")

        # PrestaShop
        prestashop_service = PrestaShopService(
            api_url=os.getenv("PRESTASHOP_API_URL"),
            username=os.getenv("PRESTASHOP_API_USERNAME"),
            password=os.getenv("PRESTASHOP_API_PASSWORD", "")
        )

        # Google Drive
        drive_service = DriveService(
            credentials_file=os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE"),
            folder_id=os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
        )

        # Google Sheets
        sheets_service = SheetsService(
            credentials_file=os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE"),
            spreadsheet_id=os.getenv("GOOGLE_SHEET_ID"),
            sheet_name=os.getenv("GOOGLE_SHEET_NAME", "Facturas")
        )

        # Email service (para enviar facturas a clientes)
        email_service = EmailService(
            smtp_server=os.getenv("ORDERS_SMTP_SERVER", "smtp.office365.com"),
            smtp_port=int(os.getenv("ORDERS_SMTP_PORT", "587")),
            sender_email=os.getenv("ORDERS_SENDER_EMAIL"),
            sender_password=os.getenv("ORDERS_SENDER_PASSWORD"),
            template_api_url=os.getenv("EMAIL_TEMPLATE_API_URL"),
            bcc_email=os.getenv("BCC_EMAIL", ""),
            environment=environment,
            dev_test_email=os.getenv("DEV_TEST_EMAIL", "")
        )

        # PDF service
        pdf_service = PDFService(
            pdf_api_url=os.getenv("PDF_GENERATION_API_URL")
        )

        # Notification manager (para notificaciones internas)
        notification_manager = NotificationManager()

        # Invoice processor
        processor = InvoiceProcessor(
            prestashop_service=prestashop_service,
            drive_service=drive_service,
            sheets_service=sheets_service,
            email_service=email_service,
            pdf_service=pdf_service,
            notification_manager=notification_manager
        )

        logger.info("All services initialized successfully")

        # Ejecutar proceso
        asyncio.run(processor.process_all_orders_async())

        logger.info("Process finished successfully")

    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
