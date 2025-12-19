# Sistema de Confirmación de Facturas - Toolstock

Sistema automatizado para enviar facturas a clientes cuando sus pedidos han sido enviados

## Descripción

Este sistema automatiza el proceso de envío de facturas:

1. **Consulta pedidos** en PrestaShop (estado 4 - Enviado)
2. **Busca facturas** en Google Drive (archivos JSON)
3. **Descarga y procesa** la información de la factura
4. **Obtiene datos del cliente** desde PrestaShop
5. **Genera PDF** de la factura mediante API externa
6. **Envía email** con la factura adjunta al cliente
7. **Actualiza estado** del pedido en PrestaShop (estado 23 - Factura enviada)
8. **Registra** la factura enviada en Google Sheets
9. **Notifica** éxitos y errores por email y Slack

## Requisitos

- Python 3.8+
- PowerShell (para ejecución en Windows)
- Acceso a:
  - PrestaShop API
  - Google Drive API (Service Account)
  - Google Sheets API (Service Account)
  - SMTP Office365
  - APIs de plantillas y generación de PDF

## Instalación

### 1. Clonar o descargar el proyecto

cd c:\ruta\al\directorio

### 2. Configurar credenciales de Google

Coloca el archivo `credentials-service.json` en la raíz del proyecto. Este archivo contiene las credenciales de la Service Account de Google.

**Importante:** La carpeta de Google Drive debe estar compartida con la cuenta de servicio:

```
name@project-name.iam.gserviceaccount.com
```

### 3. Configurar variables de entorno

Copia el archivo `.env.example` a `.env` y configura todas las variables:

```bash
cp .env.example .env
```

Edita `.env` y completa los valores faltantes.

### 4. Ejecutar el script de instalación

El script `run.ps1` se encarga de:

- Crear el entorno virtual
- Instalar dependencias
- Ejecutar el proceso

```powershell
.\run.ps1
```

## Estructura del Proyecto

```
confirmation-invoice/
├── main.py                      # Punto de entrada principal
├── requirements.txt             # Dependencias de Python
├── .env                         # Variables de entorno
├── .env.example                 # Plantilla de variables de entorno
├── credentials-service.json     # Credenciales de Google (no versionado)
├── run.ps1                      # Script de ejecución para Windows
├── README.md                    # Esta documentación
├── services/                    # Módulos de servicios
│   ├── __init__.py
│   ├── prestashop_service.py   # Interacción con PrestaShop API
│   ├── drive_service.py        # Búsqueda y descarga desde Google Drive
│   ├── sheets_service.py       # Registro en Google Sheets
│   ├── email_service.py        # Envío de emails SMTP
│   ├── pdf_service.py          # Generación de PDFs
│   ├── notifications.py        # Notificaciones internas (Email/Slack)
│   └── invoice_processor.py    # Orquestación del flujo completo
└── logs/                        # Logs de ejecución
    ├── confirmation_invoice.log
    ├── scheduler.log
    ├── scheduler_output.log
    └── scheduler_error.log
```

## Configuración

### Variables de Entorno

Las variables más importantes son:

#### Entorno

- `ENVIRONMENT`: `development` o `production`

#### PrestaShop

- `PRESTASHOP_API_URL`: URL de la API de PrestaShop
- `PRESTASHOP_API_USERNAME`: API Key de PrestaShop

#### Email (Clientes)

- `ORDERS_SMTP_SERVER`: servidor SMTP (smtp.office365.com)
- `ORDERS_SENDER_EMAIL`: sender email
- `ORDERS_SENDER_PASSWORD`: contraseña del email

#### Email (Notificaciones Internas)

- `SENDER_EMAIL`: sender email
- `SENDER_PASSWORD`: contraseña del email
- `NOTIFICATION_EMAILS`: Lista de emails separados por coma

#### Slack (Notificaciones)

- `SLACK_WEBHOOK_URL`: URL del webhook de Slack
- `SLACK_CHANNEL`: Canal de Slack

#### Google Drive & Sheets

- `GOOGLE_SERVICE_ACCOUNT_FILE`: ./credentials-service.json
- `GOOGLE_SHEET_ID`: ID de la hoja de Google Sheets

#### APIs Externas

- `EMAIL_TEMPLATE_API_URL`: URL para generar plantillas HTML
- `PDF_GENERATION_API_URL`: URL para generar PDFs

### Modo Development

En modo `development`:

- Los emails se redirigen a `DEV_TEST_EMAIL`
- Se activan logs más detallados (DEBUG)
- Se añaden prefijos en notificaciones

## Uso

### Ejecución Manual

```powershell
.\run.ps1
```

### Ejecución Directa con Python

```bash
# Activar entorno virtual
.\venv\Scripts\Activate.ps1

# Ejecutar
python main.py
```

### Programar Ejecución (Task Scheduler)

1. Abre el Programador de Tareas de Windows
2. Crea una nueva tarea
3. Acción: Ejecutar `powershell.exe`
4. Argumentos: `-ExecutionPolicy Bypass -File "ruta\del\proyecto\run.ps1"`
5. Configura el horario deseado (ej: Lunes a Sábado a las 10:30)

## Logs

Los logs se guardan en `logs/`:

- `confirmation_invoice.log`: Log principal de la aplicación
- `scheduler.log`: Log del script PowerShell
- `scheduler_output.log`: Salida estándar
- `scheduler_error.log`: Errores

## Notificaciones

El sistema envía notificaciones internas en los siguientes casos:

### Slack

- **Info**: Proceso iniciado, no hay pedidos
- **Success**: Proceso completado exitosamente
- **Warning**: Proceso completado con errores
- **Error**: Error crítico

### Email

- Se envía cuando Slack falla o en errores críticos
- Incluye detalles técnicos del error

## Flujo de Procesamiento

Para cada pedido:

1. ✅ Buscar archivo JSON de factura en Google Drive (`factura_REFERENCE.json`)
2. ✅ Descargar y parsear el JSON
3. ✅ Obtener datos del cliente desde PrestaShop
4. ✅ Generar PDF de la factura
5. ✅ Generar plantilla HTML del email
6. ✅ Enviar email con factura adjunta
7. ✅ Actualizar estado del pedido a 23 (Factura enviada)
8. ✅ Registrar en Google Sheets

Si algún paso falla, se notifica el error y se continúa con el siguiente pedido.

## Mantenimiento

### Actualizar Dependencias

```bash
.\venv\Scripts\Activate.ps1
pip install --upgrade -r requirements.txt
```

### Ver Logs en Tiempo Real

```powershell
Get-Content -Path "logs\confirmation_invoice.log" -Wait -Tail 50
```

## Solución de Problemas

### Error: "Google Drive service not available"

- Verifica que `credentials-service.json` existe
- Verifica que la carpeta de Drive está compartida con la Service Account

### Error: "Failed to send email"

- Verifica credenciales SMTP en `.env`
- Verifica que el servidor SMTP es `smtp.office365.com`
- Verifica que el puerto es `587`

### Error: "No orders pending invoice confirmation"

- Es normal si no hay pedidos en estado 4
- Verifica en PrestaShop que hay pedidos con:
  - Estado: 4 (Enviado)
  - Pago: PayPal, Redsys, PayPal with fee, o Transferencia bancaria

### Pedidos se saltan

- Verifica que existe el archivo JSON en Google Drive
- El nombre debe ser exactamente: `factura_REFERENCIA.json`
- Ejemplo: `factura_ABCDEFGH.json`

## Seguridad

- **NUNCA** commitear el archivo `.env`
- **NUNCA** commitear `credentials-service.json`
- Mantener las contraseñas seguras
- Revisar permisos de la Service Account

## Soporte

Para errores o problemas, revisar:

1. Logs en `logs/confirmation_invoice.log`
2. Notificaciones en Slack (#confirmation-invoice-tool)
3. Emails de notificación

## Licencia

Uso interno de Toolstock.
