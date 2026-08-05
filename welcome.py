"""
Cog de bienvenidas para V1 Sistemas.
Gestiona el comando /welcome-setup y el evento on_member_join.
"""

import logging
import discord
from discord.ext import commands
from discord import app_commands

from welcome_views import PanelBienvenida
from embeds import embed_bienvenida, embed_info, embed_error
from checks import solo_administrador
from logger import log_accion
from manager import db
from constants import ARCHIVO_WELCOME, COLOR_PRIMARIO

log = logging.getLogger(__name__)


class Welcome(commands.Cog, name="Bienvenidas"):
    """Sistema completo de bienvenidas con panel interactivo."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="welcome-setup", description="Configura el sistema de bienvenidas del servidor.")
    @solo_administrador()
    async def welcome_setup(self, interaction: discord.Interaction) -> None:
        panel = PanelBienvenida(guild_id=interaction.guild_id, autor_id=interaction.user.id)

        config = await db.obtener(ARCHIVO_WELCOME, str(interaction.guild_id), {})
        canal_id = config.get("canal_id") if isinstance(config, dict) else None

        e = embed_info(
            "⚙️ Configuración de Bienvenidas",
            (
                "Usa los botones para personalizar el sistema de bienvenidas.\n\n"
                f"**Estado actual:** {'✅ Activo' if config.get('activo') else '❌ Inactivo'}\n"
                f"**Canal:** {f'<#{canal_id}>' if canal_id else 'No configurado'}\n\n"
                "**Variables disponibles:**\n"
                "`{usuario}` · `{servidor}` · `{miembros}` · `{mencion}`"
            ),
        )
        await interaction.response.send_message(embed=e, view=panel, ephemeral=True)

    @welcome_setup.error
    async def welcome_setup_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                embed=embed_error("Sin permisos", "Solo los administradores pueden usar este comando."),
                ephemeral=True,
            )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        config = await db.obtener(ARCHIVO_WELCOME, str(member.guild.id), {})
        if not isinstance(config, dict) or not config.get("activo"):
            return

        canal_id = config.get("canal_id")
        if not canal_id:
            return

        canal = member.guild.get_channel(canal_id)
        if not canal or not isinstance(canal, discord.TextChannel):
            return

        try:
            e = embed_bienvenida(
                miembro=member,
                titulo=config.get("titulo", "¡Bienvenido a {servidor}!"),
                descripcion=config.get("descripcion", "Hola {mencion}, ¡bienvenido!"),
                color=config.get("color", COLOR_PRIMARIO),
                imagen=config.get("imagen"),
                thumbnail=config.get("thumbnail"),
                footer=config.get("footer"),
                autor=config.get("autor"),
            )
            await canal.send(embed=e)
        except discord.Forbidden:
            log.warning(f"[WELCOME] Sin permiso para enviar en canal {canal_id} en {member.guild.name}")
        except Exception as e:
            log.error(f"[WELCOME] Error en on_member_join: {e}", exc_info=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Welcome(bot))
