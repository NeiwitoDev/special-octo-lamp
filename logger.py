"""
Sistema de logging para V1 Sistemas.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import discord

# Carpeta "logs" junto al script principal
RUTA_LOGS = Path(__file__).parent / "logs"
RUTA_LOGS.mkdir(parents=True, exist_ok=True)

FORMATO      = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"


def configurar_logging(nivel: int = logging.INFO) -> None:
    """Inicializa los handlers de logging al arrancar el bot."""
    logger_raiz = logging.getLogger()
    logger_raiz.setLevel(nivel)

    if logger_raiz.handlers:
        return

    formatter = logging.Formatter(FORMATO, datefmt=FORMATO_FECHA)

    # Consola
    consola = logging.StreamHandler(sys.stdout)
    consola.setFormatter(formatter)
    logger_raiz.addHandler(consola)

    # Archivo rotativo (5 MB × 5 archivos)
    archivo = RotatingFileHandler(
        RUTA_LOGS / "bot.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    archivo.setFormatter(formatter)
    logger_raiz.addHandler(archivo)

    # Silenciar loggers ruidosos
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


async def enviar_log_discord(
    bot: discord.Client,
    guild_id: int,
    canal_id: int | None,
    embed: discord.Embed,
) -> None:
    """Envía un embed de log al canal configurado. Falla silenciosamente."""
    if not canal_id:
        return
    try:
        canal = bot.get_channel(canal_id) or await bot.fetch_channel(canal_id)
        if isinstance(canal, discord.TextChannel):
            await canal.send(embed=embed)
    except (discord.Forbidden, discord.NotFound, discord.HTTPException) as e:
        logging.getLogger(__name__).warning(
            f"[LOG-DISCORD] No se pudo enviar log al canal {canal_id}: {e}"
        )


async def log_accion(
    bot: discord.Client,
    guild: discord.Guild,
    embed: discord.Embed,
) -> None:
    """Obtiene el canal de logs del servidor y envía el embed."""
    from manager import db
    from constants import ARCHIVO_CONFIG

    config = await db.obtener(ARCHIVO_CONFIG, str(guild.id), {})
    canal_id = config.get("canal_logs") if isinstance(config, dict) else None
    await enviar_log_discord(bot, guild.id, canal_id, embed)
