"""
Vistas e interacciones para el sistema de bienvenidas (/welcome-setup).
"""

import discord
from discord.ui import Modal, TextInput, View, Button

from embeds import embed_exito, embed_error, embed_bienvenida
from manager import db
from constants import ARCHIVO_WELCOME, COLOR_PRIMARIO, VARIABLES_BIENVENIDA


# ── Modals ─────────────────────────────────────

class ModalMensajeBienvenida(Modal, title="✏️ Configurar Mensaje"):
    titulo = TextInput(label="Título del embed", placeholder="¡Bienvenido a {servidor}!", max_length=256, required=True)
    descripcion = TextInput(label="Descripción", style=discord.TextStyle.paragraph, placeholder="Hola {mencion}, ¡nos alegra tenerte aquí!\nSomos {miembros} miembros.", max_length=2048, required=True)
    footer = TextInput(label="Footer (opcional)", placeholder="V1 Sistemas • Miembro #{miembros}", max_length=2048, required=False)
    autor = TextInput(label="Autor (opcional)", placeholder="Nombre del autor del embed", max_length=256, required=False)

    def __init__(self, config_actual: dict):
        super().__init__()
        self.titulo.default = config_actual.get("titulo", "¡Bienvenido a {servidor}!")
        self.descripcion.default = config_actual.get("descripcion", "Hola {mencion}, ¡bienvenido!")
        self.footer.default = config_actual.get("footer", "")
        self.autor.default = config_actual.get("autor", "")

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        self._resultado = {
            "titulo": self.titulo.value,
            "descripcion": self.descripcion.value,
            "footer": self.footer.value,
            "autor": self.autor.value,
        }
        await interaction.followup.send("✅ Texto guardado.", ephemeral=True)


class ModalImagenesBienvenida(Modal, title="🖼️ Imágenes del Embed"):
    imagen = TextInput(label="URL de imagen principal (opcional)", placeholder="https://...", max_length=500, required=False)
    thumbnail = TextInput(label="URL de thumbnail (opcional)", placeholder="https://...", max_length=500, required=False)

    def __init__(self, config_actual: dict):
        super().__init__()
        self.imagen.default = config_actual.get("imagen", "")
        self.thumbnail.default = config_actual.get("thumbnail", "")

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        self._imagen = self.imagen.value or None
        self._thumbnail = self.thumbnail.value or None
        await interaction.followup.send("✅ Imágenes guardadas.", ephemeral=True)


class ModalColorBienvenida(Modal, title="🎨 Color del Embed"):
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


# ── Panel principal ────────────────────────────

class PanelBienvenida(View):
    """Panel interactivo para configurar el sistema de bienvenidas."""

    def __init__(self, guild_id: int, autor_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.autor_id = autor_id
        self.config: dict = {}

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.autor_id:
            await interaction.response.send_message("Solo el administrador que inició el panel puede usarlo.", ephemeral=True)
            return False
        return True

    async def _cargar_config(self) -> None:
        self.config = await db.obtener(ARCHIVO_WELCOME, str(self.guild_id), {})
        if not isinstance(self.config, dict):
            self.config = {}

    async def _guardar_config(self) -> None:
        await db.establecer(ARCHIVO_WELCOME, str(self.guild_id), self.config)

    @discord.ui.button(label="📢 Canal", style=discord.ButtonStyle.secondary, row=0)
    async def btn_canal(self, interaction: discord.Interaction, button: Button):
        vista = _SeleccionarCanal(self.guild_id, self.autor_id, self)
        await interaction.response.send_message("Selecciona el canal de bienvenida:", view=vista, ephemeral=True)

    @discord.ui.button(label="✏️ Mensaje", style=discord.ButtonStyle.secondary, row=0)
    async def btn_mensaje(self, interaction: discord.Interaction, button: Button):
        await self._cargar_config()
        modal = ModalMensajeBienvenida(self.config)
        await interaction.response.send_modal(modal)
        await modal.wait()
        if hasattr(modal, "_resultado"):
            self.config.update(modal._resultado)
            await self._guardar_config()

    @discord.ui.button(label="🎨 Color", style=discord.ButtonStyle.secondary, row=0)
    async def btn_color(self, interaction: discord.Interaction, button: Button):
        await self._cargar_config()
        modal = ModalColorBienvenida()
        await interaction.response.send_modal(modal)
        await modal.wait()
        if hasattr(modal, "_color"):
            self.config["color"] = modal._color
            await self._guardar_config()

    @discord.ui.button(label="🖼️ Imágenes", style=discord.ButtonStyle.secondary, row=1)
    async def btn_imagenes(self, interaction: discord.Interaction, button: Button):
        await self._cargar_config()
        modal = ModalImagenesBienvenida(self.config)
        await interaction.response.send_modal(modal)
        await modal.wait()
        if hasattr(modal, "_imagen"):
            self.config["imagen"] = modal._imagen
            self.config["thumbnail"] = modal._thumbnail
            await self._guardar_config()

    @discord.ui.button(label="👁️ Vista previa", style=discord.ButtonStyle.primary, row=1)
    async def btn_preview(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        await self._cargar_config()
        if not self.config.get("canal_id"):
            await interaction.followup.send(embed=embed_error("Sin canal", "Configura primero el canal de bienvenida."), ephemeral=True)
            return
        e = embed_bienvenida(
            miembro=interaction.user,
            titulo=self.config.get("titulo", "¡Bienvenido a {servidor}!"),
            descripcion=self.config.get("descripcion", "Hola {mencion}!"),
            color=self.config.get("color", COLOR_PRIMARIO),
            imagen=self.config.get("imagen"),
            thumbnail=self.config.get("thumbnail"),
            footer=self.config.get("footer"),
            autor=self.config.get("autor"),
        )
        e.set_footer(text="Vista previa — así se verá la bienvenida")
        await interaction.followup.send(embed=e, ephemeral=True)

    @discord.ui.button(label="✅ Guardar y activar", style=discord.ButtonStyle.success, row=2)
    async def btn_guardar(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        await self._cargar_config()
        if not self.config.get("canal_id"):
            await interaction.followup.send(embed=embed_error("Sin canal", "Selecciona un canal antes de guardar."), ephemeral=True)
            return
        self.config["activo"] = True
        await self._guardar_config()
        self.stop()
        await interaction.followup.send(embed=embed_exito("Sistema de bienvenidas activado", f"Canal: <#{self.config['canal_id']}>"), ephemeral=True)

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.danger, row=2)
    async def btn_cancelar(self, interaction: discord.Interaction, button: Button):
        self.stop()
        await interaction.response.send_message("Configuración cancelada.", ephemeral=True)


class _SeleccionarCanal(View):
    def __init__(self, guild_id: int, autor_id: int, panel: PanelBienvenida):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.autor_id = autor_id
        self.panel = panel

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.autor_id

    @discord.ui.channel_select(placeholder="Elige el canal de bienvenidas...", channel_types=[discord.ChannelType.text])
    async def seleccionar_canal(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        await interaction.response.defer(ephemeral=True)
        canal = select.values[0]
        self.panel.config["canal_id"] = canal.id
        await db.establecer(ARCHIVO_WELCOME, str(self.guild_id), self.panel.config)
        await interaction.followup.send(f"✅ Canal `{canal.name}` guardado.", ephemeral=True)
        self.stop()
