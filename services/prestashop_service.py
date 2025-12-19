"""
Servicio para interactuar con la API de PrestaShop
Obtiene pedidos pendientes de confirmación de factura
"""
import requests
import xmltodict
import logging
from typing import List, Dict, Optional, Any
from requests.auth import HTTPBasicAuth

logger = logging.getLogger("ConfirmationInvoiceLogger")


class PrestaShopService:
    """Maneja operaciones con la API de PrestaShop"""

    def __init__(self, api_url: str, username: str, password: str = ""):
        """
        Inicializa el servicio de PrestaShop.

        Args:
            api_url: URL base de la API de PrestaShop
            username: Usuario para autenticación (API Key)
            password: Contraseña (vacío para PrestaShop)
        """
        self.api_url = api_url.rstrip('/')
        self.auth = HTTPBasicAuth(username, password)
        self.session = requests.Session()
        self.session.auth = self.auth

        logger.info("PrestaShop Service initialized")

    def get_orders_pending_invoice(self) -> List[Dict[str, Any]]:
        """
        Obtiene pedidos en estado 4 (pendientes de factura) con pagos confirmados.

        Filtros:
        - payment: PayPal, Redsys, PayPal with fee, Pagos por transferencia bancaria
        - current_state: 4 (Preparación en curso)

        Returns:
            Lista de pedidos en formato dict
        """
        try:
            # Construir la URL con filtros
            filters = {
                "filter[payment]": "[PayPal|Redsys|PayPal with fee|Pagos por transferencia bancaria]",
                "filter[current_state]": "[4]",
                "display": "full"
            }

            url = f"{self.api_url}/orders"

            logger.info(f"Fetching orders from PrestaShop API: {url}")

            response = self.session.get(url, params=filters, timeout=30)
            response.raise_for_status()

            # Parsear XML a dict
            data = xmltodict.parse(response.content)

            # Normalizar la estructura de orders
            orders = self._normalize_orders(data)

            logger.info(f"Found {len(orders)} pending orders")
            return orders

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching orders from PrestaShop: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error parsing orders: {e}")
            raise

    def _normalize_orders(self, data: Dict) -> List[Dict]:
        """
        Normaliza la estructura de órdenes que puede venir en diferentes formatos.

        Args:
            data: Datos parseados del XML

        Returns:
            Lista normalizada de pedidos
        """
        prestashop = data.get('prestashop', {})
        orders = []

        if prestashop.get('orders', {}).get('order'):
            order_data = prestashop['orders']['order']

            # Si es un solo pedido, convertir a lista
            if isinstance(order_data, dict):
                orders = [order_data]
            elif isinstance(order_data, list):
                orders = order_data
        elif prestashop.get('order'):
            # Orden directa
            orders = [prestashop['order']]

        # Asegurar que el campo shipping_number existe
        for order in orders:
            if 'shipping_number' not in order or order['shipping_number'] is None:
                order['shipping_number'] = {'_': ''}
            elif isinstance(order['shipping_number'], dict) and '_' not in order['shipping_number']:
                order['shipping_number']['_'] = ''

        return orders

    def get_customer_data(self, customer_url: str) -> Optional[Dict]:
        """
        Obtiene información del cliente desde su URL.

        Args:
            customer_url: URL del recurso del cliente (xlink:href)

        Returns:
            Información del cliente
        """
        try:
            logger.debug(f"Fetching customer data from: {customer_url}")

            response = self.session.get(customer_url, timeout=30)
            response.raise_for_status()

            data = xmltodict.parse(response.content)

            customer = data.get('prestashop', {}).get('customer', {})

            return {
                'id': customer.get('id'),
                'firstname': customer.get('firstname'),
                'lastname': customer.get('lastname'),
                'email': customer.get('email')
            }

        except Exception as e:
            logger.error(f"Error fetching customer data: {e}")
            return None

    def update_order_state(self, order_id: str, new_state_id: int = 23, employee_id: int = 5) -> bool:
        """
        Actualiza el estado del pedido.

        Args:
            order_id: ID del pedido
            new_state_id: ID del nuevo estado (23 = Factura enviada)
            employee_id: ID del empleado que hace el cambio

        Returns:
            True si se actualizó correctamente
        """
        try:
            url = f"{self.api_url}/order_histories"

            # Crear XML para actualizar el estado
            xml_data = f"""<?xml version="1.0" encoding="UTF-8"?>
<prestashop xmlns:xlink="http://www.w3.org/1999/xlink">
    <order_history>
        <id_order>{order_id}</id_order>
        <id_employee>{employee_id}</id_employee>
        <id_order_state>{new_state_id}</id_order_state>
    </order_history>
</prestashop>"""

            headers = {
                'Content-Type': 'application/xml'
            }

            logger.info(f"Updating order {order_id} to state {new_state_id}")

            response = self.session.post(
                url,
                data=xml_data.encode('utf-8'),
                headers=headers,
                timeout=30
            )
            response.raise_for_status()

            logger.info(f"Order {order_id} state updated successfully")
            return True

        except Exception as e:
            logger.error(f"Error updating order state: {e}")
            return False

    def close(self):
        """Cierra la sesión HTTP."""
        self.session.close()
