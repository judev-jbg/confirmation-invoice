"""
Procesador principal de facturas
Orquesta el flujo completo: obtener pedidos, procesar facturas y enviar emails
"""
import asyncio
import json
import logging
from typing import Dict, Any, Optional

from services.prestashop_service import PrestaShopService
from services.drive_service import DriveService
from services.sheets_service import SheetsService
from services.email_service import EmailService
from services.pdf_service import PDFService
from services.notifications import NotificationManager

logger = logging.getLogger("ConfirmationInvoiceLogger")


class InvoiceProcessor:
    """Procesa pedidos y envía facturas"""

    def __init__(
        self,
        prestashop_service: PrestaShopService,
        drive_service: DriveService,
        sheets_service: SheetsService,
        email_service: EmailService,
        pdf_service: PDFService,
        notification_manager: NotificationManager
    ):
        """
        Inicializa el procesador de facturas.

        Args:
            prestashop_service: Servicio de PrestaShop
            drive_service: Servicio de Google Drive
            sheets_service: Servicio de Google Sheets
            email_service: Servicio de email
            pdf_service: Servicio de generación de PDF
            notification_manager: Gestor de notificaciones
        """
        self.prestashop = prestashop_service
        self.drive = drive_service
        self.sheets = sheets_service
        self.email = email_service
        self.pdf = pdf_service
        self.notifications = notification_manager

        self.processed_count = 0
        self.success_count = 0
        self.error_count = 0
        self.skipped_count = 0

    async def process_all_orders_async(self):
        """Procesa todos los pedidos pendientes de factura."""
        try:
            logger.info("=" * 60)
            logger.info("STARTING INVOICE CONFIRMATION PROCESS")
            logger.info("=" * 60)

            # Obtener pedidos pendientes
            orders = self.prestashop.get_orders_pending_invoice()

            if not orders:
                logger.info("No orders pending invoice confirmation")
                await self.notifications.notify_info(
                    "Confirmación de Facturas",
                    "No hay pedidos pendientes de confirmación de factura"
                )
                return

            logger.info(f"Found {len(orders)} orders to process")

            # Procesar cada pedido
            for order in orders:
                await self.process_single_order(order)

            # Resumen final
            logger.info("=" * 60)
            logger.info("PROCESS COMPLETED")
            logger.info(f"Total processed: {self.processed_count}")
            logger.info(f"Success: {self.success_count}")
            logger.info(f"Errors: {self.error_count}")
            logger.info(f"Skipped: {self.skipped_count}")
            logger.info("=" * 60)

            # Notificar resumen
            summary = (
                f"Procesados: {self.processed_count} | "
                f"Exitosos: {self.success_count} | "
                f"Errores: {self.error_count} | "
                f"Omitidos: {self.skipped_count}"
            )

            if self.error_count > 0:
                await self.notifications.notify_warning(
                    "Confirmación de Facturas - Completado con errores",
                    summary
                )
            else:
                await self.notifications.notify_success(
                    "Confirmación de Facturas - Completado",
                    summary
                )

        except Exception as e:
            logger.error(f"Critical error in process: {e}", exc_info=True)
            await self.notifications.notify_critical_error(
                "Error crítico en confirmación de facturas",
                f"El proceso falló: {str(e)}",
                {"exception": str(e)}
            )

    async def process_single_order(self, order: Dict[str, Any]):
        """
        Procesa un solo pedido.

        Args:
            order: Datos del pedido de PrestaShop
        """
        order_id = order.get('id')
        order_reference = order.get('reference')

        logger.info(f"\n{'=' * 60}")
        logger.info(f"Processing order {order_reference} (ID: {order_id})")
        logger.info(f"{'=' * 60}")

        self.processed_count += 1

        try:
            # 1. Buscar factura JSON en Google Drive
            invoice_file_name = f"factura_{order_reference}.json"
            logger.info(f"[1/7] Searching for invoice file: {invoice_file_name}")

            invoice_file = self.drive.search_file_by_name(invoice_file_name)

            if not invoice_file:
                logger.warning(f"Invoice file not found for order {order_reference}, skipping")
                self.skipped_count += 1
                return

            logger.info(f"✅ Invoice file found: {invoice_file['name']}")

            # 2. Descargar archivo JSON
            logger.info(f"[2/7] Downloading invoice JSON file")
            invoice_json_content = self.drive.download_file(invoice_file['id'])

            if not invoice_json_content:
                raise Exception("Failed to download invoice JSON file")

            # Parsear JSON
            invoice_data = json.loads(invoice_json_content.decode('utf-8'))
            invoice_details = invoice_data.get('data', {})

            logger.info(f"✅ Invoice JSON loaded: {invoice_details.get('num_factura')}-{invoice_details.get('año_factura')}")

            # 3. Obtener datos del cliente
            logger.info(f"[3/7] Fetching customer data")
            customer_url = order.get('id_customer', {}).get('@xlink:href')

            if not customer_url:
                raise Exception("Customer URL not found in order")

            customer_data = self.prestashop.get_customer_data(customer_url)

            if not customer_data:
                raise Exception("Failed to fetch customer data")

            logger.info(f"✅ Customer data loaded: {customer_data.get('email')}")

            # 4. Preparar datos de dirección
            logger.info(f"[4/7] Preparing address data")
            address_data = {
                'customer': invoice_details.get('cliente'),
                'postcode': invoice_details.get('cod_postal'),
                'city': invoice_details.get('ciudad'),
                'num_invoice': f"{invoice_details.get('num_factura')}-{invoice_details.get('año_factura')}"
            }

            # 5. Generar PDF
            logger.info(f"[5/7] Generating invoice PDF")
            pdf_content = await self.pdf.generate_invoice_pdf(invoice_details)

            if not pdf_content:
                raise Exception("Failed to generate PDF")

            logger.info(f"✅ PDF generated successfully")

            # 6. Enviar email
            logger.info(f"[6/7] Sending invoice email")
            email_sent = await self.email.send_invoice_with_template(
                order_data=order,
                customer_data=customer_data,
                address_data=address_data,
                pdf_content=pdf_content,
                invoice_number=address_data['num_invoice']
            )

            if not email_sent:
                raise Exception("Failed to send invoice email")

            logger.info(f"✅ Invoice email sent successfully")

            # 7. Actualizar estado del pedido en PrestaShop
            logger.info(f"[7/7] Updating order state in PrestaShop")
            state_updated = self.prestashop.update_order_state(order_id, new_state_id=23)

            if not state_updated:
                logger.warning("Failed to update order state (non-critical)")

            # 8. Registrar en Google Sheets
            logger.info(f"[8/8] Logging to Google Sheets")
            self.sheets.append_or_update_invoice(
                reference=order_reference,
                invoice_id=invoice_details.get('id', ''),
                invoice_number=address_data['num_invoice']
            )

            # Éxito
            self.success_count += 1
            logger.info(f"✅ Order {order_reference} processed successfully")

        except Exception as e:
            self.error_count += 1
            logger.error(f"❌ Error processing order {order_reference}: {e}", exc_info=True)

            # Notificar error
            await self.notifications.notify_warning(
                f"Error procesando pedido {order_reference}",
                str(e),
                {
                    "order_id": order_id,
                    "order_reference": order_reference,
                    "error": str(e)
                }
            )
