"""
Cog de configuración general del bot (/bot-setup).
"""

import logging
import discord
from discord.ext import commands
from discord import app_commands

from setup_views import PanelBotSetup
from embeds import embed_info, embed_error
from checks import solo_administrador
from manager import db
from constants import ARCHIVO_CONFIG

log = logging.getLogger(__name__)


class Setup(commands.Cog, name="Configuración"):
    """Panel de configuración general del bot para administradores."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="bot-setup", description="Abre el panel de configuración general del bot.")
    @solo_administrador()
    async def bot_setup(self, interaction: discord.Interaction) -> None:
        config = await db.obtener(ARCHIVO_CONFIG, str(interaction.guild_id), {})
        if not isinstance(config, dict):
            config = {}

        canal_logs_txt = f"<#{config['canal_logs']}>" if config.get('canal_logs') else "❌ No configurado"
        canal_cmds_txt = f"<#{config['canal_comandos']}>" if config.get('canal_comandos') else "❌ No configurado"
        rol_staff_txt  = f"<@&{config['rol_staff']}>" if config.get('rol_staff') else "❌ No configurado"
        color_hex      = hex(config.get('color_principal', 0x5865F2))[2:].upper()

        e = embed_info(
            "⚙️ Configuración del Bot — V1 Sistemas",
            (
                f"**Prefijo actual:** `{config.get('prefijo', '?')}`\n"
                f"**Color principal:** `#{color_hex}`\n"
                f"**Canal de logs:** {canal_logs_txt}\n"
                f"**Canal de comandos:** {canal_cmds_txt}\n"
                f"**Rol Staff:** {rol_staff_txt}\n\n"
                "Usa los botones para personalizar la configuración del bot."
            ),
        )
        panel = PanelBotSetup(
            guild_id=interaction.guild_id,
            autor_id=interaction.user.id,
            bot=self.bot,
        )
        panel.config = config
        await interaction.response.send_message(embed=e, view=panel, ephemeral=True)

    @bot_setup.error
    async def bot_setup_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                embed=embed_error("Sin permisos", "Solo los administradores pueden usar este comando."),
                ephemeral=True,
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Setup(bot))
