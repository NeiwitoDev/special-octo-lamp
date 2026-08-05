"""
Constantes globales del bot V1 Sistemas.
"""

# ──────────────────────────────────────────────
# Colores principales
# ──────────────────────────────────────────────
COLOR_PRIMARIO    = 0x5865F2   # Azul Discord
COLOR_EXITO       = 0x57F287   # Verde
COLOR_ERROR       = 0xED4245   # Rojo
COLOR_ADVERTENCIA = 0xFEE75C   # Amarillo
COLOR_INFO        = 0xEB459E   # Rosa
COLOR_LOG         = 0x2B2D31   # Oscuro

# ──────────────────────────────────────────────
# Prefijo por defecto
# ──────────────────────────────────────────────
PREFIJO_DEFAULT = "?"

# ──────────────────────────────────────────────
# Límites
# ──────────────────────────────────────────────
MAX_TICKETS_DEFAULT      = 1
MAX_WARNS_DEFAULT        = 3
TIMEOUT_ELIMINAR_TICKET  = 10   # segundos tras cerrar

# ──────────────────────────────────────────────
# Archivos de datos
# ──────────────────────────────────────────────
ARCHIVO_CONFIG  = "config.json"
ARCHIVO_WELCOME = "welcome.json"
ARCHIVO_TICKETS = "tickets.json"
ARCHIVO_WARNS   = "warns.json"
ARCHIVO_STAFF   = "staff.json"
ARCHIVO_LOGS    = "logs.json"

# ──────────────────────────────────────────────
# Variables de bienvenida
# ──────────────────────────────────────────────
VARIABLES_BIENVENIDA = {
    "{usuario}":  "Nombre de usuario (sin #)",
    "{servidor}": "Nombre del servidor",
    "{miembros}": "Número total de miembros",
    "{mencion}":  "Mención directa al usuario (@usuario)",
}
