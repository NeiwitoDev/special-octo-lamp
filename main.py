"""
Punto de entrada principal del bot V1 Sistemas.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Añadir el directorio actual al path de Python
sys.path.insert(0, str(Path(__file__).parent))

import discord
from discord.ext import commands
from dotenv import load_dotenv

from keep_alive import iniciar_servidor
from logger import configurar_logging
from manager import db
from constants import PREFIJO_DEFAULT, ARCHIVO_CONFIG

# ──────────────────────────────────────────────
# Variables de entorno
# ──────────────────────────────────────────────
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    print("[ERROR CRÍTICO] La variable de entorno DISCORD_TOKEN no está definida.")
    print("  → Crea un archivo .env con: DISCORD_TOKEN=tu_token_aquí")
    sys.exit(1)

# ──────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────
configurar_logging()
log = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Intents
# ──────────────────────────────────────────────
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True

# ──────────────────────────────────────────────
# Prefijo dinámico por servidor
# ──────────────────────────────────────────────
async def obtener_prefijo(bot: commands.Bot, message: discord.Message) -> str:
    if not message.guild:
        return PREFIJO_DEFAULT
    config = await db.obtener(ARCHIVO_CONFIG, str(message.guild.id), {})
    return config.get("prefijo", PREFIJO_DEFAULT) if isinstance(config, dict) else PREFIJO_DEFAULT


# ──────────────────────────────────────────────
# Cogs a cargar (archivos .py en la misma carpeta)
# ──────────────────────────────────────────────
COGS = ["welcome", "moderation", "tickets", "setup", "automod"]


# ──────────────────────────────────────────────
# Bot
# ──────────────────────────────────────────────
class V1Bot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=obtener_prefijo,
            intents=intents,
            help_command=None,
            case_insensitive=True,
        )

    async def setup_hook(self) -> None:
        """Carga todos los cogs al iniciar."""
        for nombre_cog in COGS:
            try:
                await self.load_extension(nombre_cog)
                log.info(f"[COG] Cargado: {nombre_cog}")
            except Exception as e:
                log.error(f"[COG] Error al cargar {nombre_cog}: {e}", exc_info=True)

        # Sincronizar slash commands globalmente
        try:
            synced = await self.tree.sync()
            log.info(f"[SLASH] {len(synced)} comandos sincronizados globalmente.")
        except Exception as e:
            log.error(f"[SLASH] Error al sincronizar comandos: {e}", exc_info=True)

    async def on_ready(self) -> None:
        log.info(f"[BOT] Conectado como {self.user} (ID: {self.user.id})")
        log.info(f"[BOT] Servidores: {len(self.guilds)}")
        await self._aplicar_actividad_global()

    async def _aplicar_actividad_global(self) -> None:
        actividad = discord.Activity(
            type=discord.ActivityType.watching,
            name="V1 Sistemas | /bot-setup",
        )
        await self.change_presence(status=discord.Status.online, activity=actividad)

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        """Manejador global de errores para comandos de prefijo."""
        from embeds import embed_error, embed_advertencia

        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(embed=embed_advertencia(
                "Sin permisos",
                "No tienes los permisos necesarios para usar este comando.",
            ), delete_after=10)
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send(embed=embed_error(
                "Permisos insuficientes",
                f"Al bot le faltan permisos: `{', '.join(error.missing_permissions)}`",
            ), delete_after=10)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(embed=embed_advertencia(
                "Argumento faltante",
                f"Falta el argumento `{error.param.name}`.\nUso: `{ctx.prefix}{ctx.command.qualified_name} {ctx.command.signature}`",
            ), delete_after=15)
        elif isinstance(error, commands.BadArgument):
            await ctx.send(embed=embed_error("Argumento inválido", str(error)), delete_after=10)
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(embed=embed_advertencia(
                "Espera un momento",
                f"Podrás usar este comando en `{error.retry_after:.1f}` segundos.",
            ), delete_after=8)
        elif isinstance(error, commands.NoPrivateMessage):
            await ctx.send(embed=embed_error("Solo en servidores", "Este comando no está disponible en mensajes privados."))
        else:
            log.error(f"[ERROR] Comando '{ctx.command}' por {ctx.author}: {error}", exc_info=error)
            await ctx.send(embed=embed_error(
                "Error inesperado",
                "Ocurrió un error interno. Por favor, intenta de nuevo.",
            ), delete_after=10)


# ──────────────────────────────────────────────
# Punto de entrada
# ──────────────────────────────────────────────
async def main():
    iniciar_servidor()
    async with V1Bot() as bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
