"""
Cog de sistema de tickets para V1 Sistemas.
Gestiona /tickets-setup y el panel de configuración.
"""

import logging
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Modal, TextInput, View, Button

from ticket_views import BotonAbrirTicket, BotonesTicket
from embeds import embed_exito, embed_error, embed_info, embed_advertencia
from checks import solo_administrador
from manager import db
from constants import ARCHIVO_TICKETS, COLOR_PRIMARIO, MAX_TICKETS_DEFAULT

log = logging.getLogger(__name__)


# ── Modal de configuración general ────────────

class ModalConfigTickets(Modal, title="🎫 Configurar Tickets"):
    mensaje_inicial = TextInput(
        label="Mensaje inicial del ticket",
        style=discord.TextStyle.paragraph,
        placeholder="¡Bienvenido a tu ticket! El staff te atenderá en breve.",
        max_length=1024,
        required=True,
    )
    titulo_panel = TextInput(label="Título del panel de apertura", placeholder="Sistema de Tickets", max_length=256, required=True)
    descripcion_panel = TextInput(
        label="Descripción del panel",
        style=discord.TextStyle.paragraph,
        placeholder="Haz clic en el botón para abrir un ticket.",
        max_length=2048,
        required=True,
    )
    max_tickets = TextInput(label="Máximo de tickets por usuario", placeholder="1", max_length=2, required=True)

    def __init__(self, config_actual: dict):
        super().__init__()
        self.mensaje_inicial.default = config_actual.get("mensaje_inicial", "")
        self.titulo_panel.default = config_actual.get("titulo_panel", "Sistema de Tickets")
        self.descripcion_panel.default = config_actual.get("descripcion_panel", "")
        self.max_tickets.default = str(config_actual.get("max_por_usuario", MAX_TICKETS_DEFAULT))

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            maximo = int(self.max_tickets.value)
        except ValueError:
            maximo = MAX_TICKETS_DEFAULT
        self._datos = {
            "mensaje_inicial": self.mensaje_inicial.value,
            "titulo_panel": self.titulo_panel.value,
            "descripcion_panel": self.descripcion_panel.value,
            "max_por_usuario": maximo,
        }
        await interaction.followup.send("✅ Configuración guardada.", ephemeral=True)


# ── Panel de configuración de tickets ─────────

class PanelTicketsSetup(View):
    def __init__(self, guild_id: int, autor_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.autor_id = autor_id
        self.config: dict = {}

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.autor_id:
            await interaction.response.send_message("Solo el administrador que abrió el panel puede usarlo.", ephemeral=True)
            return False
        return True

    async def _cargar(self) -> None:
        self.config = await db.obtener(ARCHIVO_TICKETS, str(self.guild_id), {})
        if not isinstance(self.config, dict):
            self.config = {}

    async def _guardar(self) -> None:
        await db.establecer(ARCHIVO_TICKETS, str(self.guild_id), self.config)

    @discord.ui.button(label="⚙️ Configurar mensajes", style=discord.ButtonStyle.secondary, row=0)
    async def btn_mensajes(self, interaction: discord.Interaction, button: Button):
        await self._cargar()
        modal = ModalConfigTickets(self.config)
        await interaction.response.send_modal(modal)
        await modal.wait()
        if hasattr(modal, "_datos"):
            self.config.update(modal._datos)
            await self._guardar()

    @discord.ui.button(label="📁 Categoría", style=discord.ButtonStyle.secondary, row=0)
    async def btn_categoria(self, interaction: discord.Interaction, button: Button):
        vista = _SeleccionarCategoria(self.guild_id, self.autor_id, self)
        await interaction.response.send_message("Selecciona la categoría para los tickets:", view=vista, ephemeral=True)

    @discord.ui.button(label="🛡️ Rol Staff", style=discord.ButtonStyle.secondary, row=0)
    async def btn_rol_staff(self, interaction: discord.Interaction, button: Button):
        vista = _SeleccionarRolTickets(self.guild_id, self.autor_id, self, "rol_staff_id", "rol de staff")
        await interaction.response.send_message("Selecciona el rol de staff:", view=vista, ephemeral=True)

    @discord.ui.button(label="🎨 Color", style=discord.ButtonStyle.secondary, row=1)
    async def btn_color(self, interaction: discord.Interaction, button: Button):
        modal = _ModalColorTickets()
        await interaction.response.send_modal(modal)
        await modal.wait()
        if hasattr(modal, "_color"):
            await self._cargar()
            self.config["color"] = modal._color
            await self._guardar()

    @discord.ui.button(label="📤 Publicar panel", style=discord.ButtonStyle.primary, row=1)
    async def btn_publicar(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        await self._cargar()
        vista = _SeleccionarCanalPublicar(self.guild_id, self.autor_id, self.config)
        await interaction.followup.send("¿En qué canal publicar el panel de tickets?", view=vista, ephemeral=True)

    @discord.ui.button(label="✅ Guardar", style=discord.ButtonStyle.success, row=2)
    async def btn_guardar(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        await self._guardar()
        self.stop()
        await interaction.followup.send(embed=embed_exito("Sistema de tickets guardado", "La configuración fue guardada correctamente."), ephemeral=True)

    @discord.ui.button(label="❌ Cerrar", style=discord.ButtonStyle.danger, row=2)
    async def btn_cerrar(self, interaction: discord.Interaction, button: Button):
        self.stop()
        await interaction.response.send_message("Panel cerrado.", ephemeral=True)


class _ModalColorTickets(Modal, title="🎨 Color del Panel"):
    color = TextInput(label="Color hexadecimal", placeholder="#5865F2", max_length=7, min_length=6, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        valor = self.color.value.lstrip("#")
        try:
            self._color = int(valor, 16)
            await interaction.followup.send(f"✅ Color `#{valor.upper()}` guardado.", ephemeral=True)
        except ValueError:
            self._color = COLOR_PRIMARIO
            await interaction.followup.send("⚠️ Color inválido. Se usará el color por defecto.", ephemeral=True)


class _SeleccionarCategoria(View):
    def __init__(self, guild_id: int, autor_id: int, panel: PanelTicketsSetup):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.autor_id = autor_id
        self.panel = panel

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.autor_id

    @discord.ui.select(cls=discord.ui.ChannelSelect, placeholder="Elige la categoría...", channel_types=[discord.ChannelType.category])
    async def seleccionar(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        cat = select.values[0]
        self.panel.config["categoria_id"] = cat.id
        await self.panel._guardar()
        await interaction.response.send_message(f"✅ Categoría `{cat.name}` guardada.", ephemeral=True)
        self.stop()


class _SeleccionarRolTickets(View):
    def __init__(self, guild_id: int, autor_id: int, panel: PanelTicketsSetup, clave: str, nombre: str):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.autor_id = autor_id
        self.panel = panel
        self.clave = clave
        self.nombre = nombre

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.autor_id

    @discord.ui.select(cls=discord.ui.RoleSelect, placeholder="Elige un rol...")
    async def seleccionar(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        rol = select.values[0]
        self.panel.config[self.clave] = rol.id
        await self.panel._guardar()
        await interaction.response.send_message(f"✅ {self.nombre.capitalize()} guardado: `{rol.name}`.", ephemeral=True)
        self.stop()


class _SeleccionarCanalPublicar(View):
    def __init__(self, guild_id: int, autor_id: int, config: dict):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.autor_id = autor_id
        self.config = config

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.autor_id

    @discord.ui.select(cls=discord.ui.ChannelSelect, placeholder="Elige el canal...", channel_types=[discord.ChannelType.text])
    async def seleccionar(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        await interaction.response.defer(ephemeral=True)
        canal = select.values[0]
        canal_obj = interaction.guild.get_channel(canal.id)
        if not canal_obj:
            await interaction.followup.send("Canal no encontrado.", ephemeral=True)
            return

        color = self.config.get("color", COLOR_PRIMARIO)
        titulo = self.config.get("titulo_panel", "🎫 Sistema de Tickets")
        descripcion = self.config.get("descripcion_panel", "Haz clic en el botón para abrir un ticket.")

        e = discord.Embed(title=titulo, description=descripcion, color=color)
        try:
            await canal_obj.send(embed=e, view=BotonAbrirTicket())
            await interaction.followup.send(f"✅ Panel publicado en {canal_obj.mention}.", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send(embed=embed_error("Sin permisos", f"No puedo enviar mensajes en {canal_obj.mention}."), ephemeral=True)
        self.stop()


# ── Cog ────────────────────────────────────────

class Tickets(commands.Cog, name="Tickets"):
    """Sistema profesional de tickets con botones y transcripts."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.add_view(BotonAbrirTicket())
        bot.add_view(BotonesTicket())

    @app_commands.command(name="tickets-setup", description="Configura el sistema de tickets del servidor.")
    @solo_administrador()
    async def tickets_setup(self, interaction: discord.Interaction) -> None:
        config = await db.obtener(ARCHIVO_TICKETS, str(interaction.guild_id), {})
        if not isinstance(config, dict):
            config = {}

        abiertos = len(config.get("abiertos", {}))
        e = embed_info(
            "🎫 Configuración del Sistema de Tickets",
            (
                f"**Estado:** {'✅ Activo' if config.get('titulo_panel') else '❌ Sin configurar'}\n"
                f"**Tickets abiertos:** {abiertos}\n"
                f"**Máx. por usuario:** {config.get('max_por_usuario', MAX_TICKETS_DEFAULT)}\n\n"
                "Usa los botones para configurar el sistema."
            ),
        )
        panel = PanelTicketsSetup(guild_id=interaction.guild_id, autor_id=interaction.user.id)
        await interaction.response.send_message(embed=e, view=panel, ephemeral=True)

    @tickets_setup.error
    async def tickets_setup_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                embed=embed_error("Sin permisos", "Solo los administradores pueden usar este comando."),
                ephemeral=True,
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Tickets(bot))
