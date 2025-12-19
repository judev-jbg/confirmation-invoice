"""
Servicio para generación de PDFs de facturas
Usa una API externa para convertir datos a PDF
"""
import aiohttp
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger("ConfirmationInvoiceLogger")


class PDFService:
    """Maneja la generación de PDFs de facturas"""

    def __init__(self, pdf_api_url: str):
        """
        Inicializa el servicio de PDF.

        Args:
            pdf_api_url: URL de la API para generar PDFs
        """
        self.pdf_api_url = pdf_api_url
        logger.info("PDF Service initialized")

    async def generate_invoice_pdf(self, invoice_data: Dict[str, Any]) -> Optional[bytes]:
        """
        Genera un PDF de factura desde los datos proporcionados.

        Args:
            invoice_data: Datos de la factura para generar el PDF

        Returns:
            Contenido del PDF en bytes, None si hay error
        """
        try:
            logger.debug(f"Generating PDF for invoice {invoice_data.get('num_factura', 'N/A')}")

            payload = {
                "data": invoice_data
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.pdf_api_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    if response.status == 200:
                        result = await response.json()

                        # La API retorna el PDF en base64 dentro de body.pdf
                        if 'body' in result and 'pdf' in result['body']:
                            import base64
                            pdf_base64 = result['body']['pdf']
                            pdf_bytes = base64.b64decode(pdf_base64)

                            logger.info(f"✅ PDF generated successfully ({len(pdf_bytes)} bytes)")
                            return pdf_bytes
                        else:
                            logger.error("PDF generation response missing 'body.pdf' field")
                            return None
                    else:
                        error_text = await response.text()
                        logger.error(f"Error generating PDF: {response.status} - {error_text}")
                        return None

        except Exception as e:
            logger.error(f"Failed to generate PDF: {e}")
            return None
