"""
Servicio para envío de emails con facturas
Usa SMTP Office365 y plantillas HTML desde API
"""
import aiosmtplib
import aiohttp
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional, Dict, Any

logger = logging.getLogger("ConfirmationInvoiceLogger")


class EmailService:
    """Maneja el envío de emails con facturas a clientes"""

    def __init__(
        self,
        smtp_server: str,
        smtp_port: int,
        sender_email: str,
        sender_password: str,
        template_api_url: str,
        bcc_email: str = "",
        environment: str = "production",
        dev_test_email: str = ""
    ):
        """
        Inicializa el servicio de email.

        Args:
            smtp_server: Servidor SMTP (ej: smtp.office365.com)
            smtp_port: Puerto SMTP (ej: 587)
            sender_email: Email del remitente
            sender_password: Contraseña del remitente
            template_api_url: URL de la API para generar plantillas HTML
            bcc_email: Email para copia oculta
            environment: Entorno (development/production)
            dev_test_email: Email de prueba para desarrollo
        """
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.template_api_url = template_api_url
        self.bcc_email = bcc_email
        self.environment = environment
        self.dev_test_email = dev_test_email

        logger.info(f"Email Service initialized (environment: {environment})")

    async def generate_email_template(
        self,
        order_data: Dict[str, Any],
        customer_data: Dict[str, Any],
        address_data: Dict[str, Any]
    ) -> Optional[Dict[str, str]]:
        """
        Genera la plantilla HTML del email usando la API.

        Args:
            order_data: Datos del pedido
            customer_data: Datos del cliente
            address_data: Datos de la dirección

        Returns:
            Dict con 'html' y otros datos del template, None si hay error
        """
        try:
            logger.debug(f"Generating email template for order {order_data.get('reference', 'N/A')}")

            payload = {
                "order": order_data,
                "customer": customer_data,
                "address": address_data
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.template_api_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info("✅ Email template generated successfully")
                        return result.get('body', {})
                    else:
                        error_text = await response.text()
                        logger.error(f"Error generating email template: {response.status} - {error_text}")
                        return None

        except Exception as e:
            logger.error(f"Failed to generate email template: {e}")
            return None

    async def send_invoice_email(
        self,
        recipient_email: str,
        subject: str,
        html_body: str,
        pdf_content: bytes,
        pdf_filename: str
    ) -> bool:
        """
        Envía un email con la factura adjunta.

        Args:
            recipient_email: Email del destinatario
            subject: Asunto del email
            html_body: Contenido HTML del email
            pdf_content: Contenido del PDF en bytes
            pdf_filename: Nombre del archivo PDF

        Returns:
            True si el email se envió correctamente
        """
        try:
            # En modo desarrollo, redirigir al email de prueba
            original_recipient = recipient_email
            if self.environment == "development" and self.dev_test_email:
                logger.info(f"🔧 DEV MODE: Redirecting email from {recipient_email} to {self.dev_test_email}")
                recipient_email = self.dev_test_email

            # Crear mensaje
            message = MIMEMultipart("alternative")
            message["From"] = self.sender_email
            message["To"] = recipient_email
            message["Subject"] = subject

            # Añadir BCC si está configurado
            if self.bcc_email and self.environment == "production":
                message["Bcc"] = self.bcc_email

            # Adjuntar contenido HTML
            html_part = MIMEText(html_body, "html", "utf-8")
            message.attach(html_part)

            # Adjuntar PDF
            pdf_part = MIMEBase("application", "pdf")
            pdf_part.set_payload(pdf_content)
            encoders.encode_base64(pdf_part)
            pdf_part.add_header(
                "Content-Disposition",
                f"attachment; filename={pdf_filename}"
            )
            message.attach(pdf_part)

            # Enviar email
            logger.info(f"Sending invoice email to {recipient_email}")

            await aiosmtplib.send(
                message,
                hostname=self.smtp_server,
                port=self.smtp_port,
                start_tls=True,
                username=self.sender_email,
                password=self.sender_password,
                timeout=60
            )

            logger.info(f"✅ Invoice email sent successfully to {original_recipient}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to send invoice email: {e}")
            return False

    async def send_invoice_with_template(
        self,
        order_data: Dict[str, Any],
        customer_data: Dict[str, Any],
        address_data: Dict[str, Any],
        pdf_content: bytes,
        invoice_number: str
    ) -> bool:
        """
        Genera y envía un email con factura (flujo completo).

        Args:
            order_data: Datos del pedido
            customer_data: Datos del cliente
            address_data: Datos de la dirección
            pdf_content: Contenido del PDF de la factura
            invoice_number: Número de factura

        Returns:
            True si el email se envió correctamente
        """
        try:
            # Generar plantilla
            template = await self.generate_email_template(order_data, customer_data, address_data)

            if not template or 'html' not in template:
                logger.error("Cannot send email: template generation failed")
                return False

            # Preparar datos del email
            recipient_email = customer_data.get('email')
            if not recipient_email:
                logger.error("Cannot send email: no recipient email")
                return False

            order_reference = order_data.get('reference', 'N/A')
            subject = f"Factura de tu pedido {order_reference}"

            customer_name = customer_data.get('firstname', 'Cliente')
            pdf_filename = f"Factura {invoice_number} - {customer_name}.pdf"

            # Enviar email
            return await self.send_invoice_email(
                recipient_email=recipient_email,
                subject=subject,
                html_body=template['html'],
                pdf_content=pdf_content,
                pdf_filename=pdf_filename
            )

        except Exception as e:
            logger.error(f"Failed to send invoice with template: {e}")
            return False
