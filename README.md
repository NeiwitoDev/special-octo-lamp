# V1 Sistemas — Bot de Discord

Bot profesional de Discord con moderación, tickets, bienvenidas y automoderación.

## Estructura de archivos (todo plano, sin carpetas)

```
main.py           → Punto de entrada
keep_alive.py     → Servidor HTTP para UptimeRobot
constants.py      → Colores, prefijos, nombres de archivos
manager.py        → Base de datos JSON (escritura atómica)
embeds.py         → Constructores de embeds reutilizables
logger.py         → Sistema de logging (consola + archivo)
checks.py         → Decoradores de permisos
welcome.py        → Cog: /welcome-setup + on_member_join
moderation.py     → Cog: ?ban ?kick ?warn ?mute etc.
tickets.py        → Cog: /tickets-setup + panel
setup.py          → Cog: /bot-setup
automod.py        → Cog: /automod-setup + flood/links
welcome_views.py  → Vistas del sistema de bienvenidas
setup_views.py    → Vistas del panel de configuración
ticket_views.py   → Vistas del sistema de tickets
requirements.txt  → Dependencias
.env.example      → Plantilla de variables de entorno
```

## Instalación local

```bash
pip install -r requirements.txt
cp .env.example .env
# Edita .env y añade tu DISCORD_TOKEN
python main.py
```

## Deploy en Render

1. Sube todos los archivos a la raíz de tu repositorio de GitHub.
2. Crea un nuevo **Web Service** en [render.com](https://render.com).
3. Conecta tu repositorio.
4. Configura:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python main.py`
   - **Environment Variable:** `DISCORD_TOKEN` = tu token
5. Haz deploy.

## UptimeRobot

Añade un monitor HTTP apuntando a la URL de tu servicio en Render para mantener el bot activo.

## Comandos

### Slash commands (administradores)
| Comando | Descripción |
|---|---|
| `/bot-setup` | Configura prefijo, color, canales y rol staff |
| `/welcome-setup` | Configura el sistema de bienvenidas |
| `/tickets-setup` | Configura el sistema de tickets |
| `/automod-setup` | Activa/desactiva la automoderación |

### Comandos de prefijo (por defecto `?`)
| Comando | Permisos necesarios |
|---|---|
| `?ban @usuario [razón]` | Banear miembros |
| `?unban <ID>` | Banear miembros |
| `?kick @usuario [razón]` | Expulsar miembros |
| `?mute @usuario [min] [razón]` | Moderar miembros |
| `?unmute @usuario` | Moderar miembros |
| `?warn @usuario [razón]` | Gestionar mensajes |
| `?warns @usuario` | Gestionar mensajes |
| `?delwarn @usuario <#>` | Gestionar mensajes |
| `?clear <cantidad>` | Gestionar mensajes |
| `?lock [razón]` | Gestionar canales |
| `?unlock [razón]` | Gestionar canales |
| `?slowmode <seg>` | Gestionar canales |
| `?nick @usuario <apodo>` | Gestionar apodos |
| `?role @usuario @rol` | Gestionar roles |
| `?removerole @usuario @rol` | Gestionar roles |
| `?say <mensaje>` | Moderador |
| `?embed <título> \| <desc>` | Moderador |
