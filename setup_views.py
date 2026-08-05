"""
Vistas e interacciones para el panel de configuración del bot (/bot-setup).
"""

import discord
from discord.ui import Modal, TextInput, View, Button

from embeds import embed_exito, embed_error, embed_info
from manager import db
from constants import ARCHIVO_CONFIG, COLOR_PRIMARIO


# ── Modals ─────────────────────────────────────

class ModalPrefijo(Modal, title="⚙️ Configurar Prefijo"):
    prefijo = TextInput(label="Prefijo del bot", placeholder="? ! > $ etc.", max_length=5, min_length=1, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        self._valor = self.prefijo.value
        await interaction.followup.send(f"✅ Prefijo cambiado a `{self._valor}`.", ephemeral=True)


class ModalActividad(Modal, title="🎮 Actividad del Bot"):
    tipo = TextInput(label="Tipo (watching / playing / listening)", placeholder="watching", max_length=20, required=True)
    texto = TextInput(label="Texto de la actividad", placeholder="V1 Sistemas | /bot-setup", max_length=128, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        self._tipo = self.tipo.value.lower().strip()
        self._texto = self.texto.value
        await interaction.followup.send(f"✅ Actividad guardada: `{self._tipo} {self._texto}`.", ephemeral=True)


class ModalColorPrincipal(Modal, title="🎨 Color Principal"):
    color = TextInput(label="Color hexadecimal", placeholder="#5865F2", max_length=7, min_length=6, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        valor = self.color.value.lstrip("#")
        try:
            self._color = int(valor, 16)
            await interaction.followup.send(f"✅ Color `#{valor.upper()}` guardado.", ephemeral=True)
        except ValueError:
            self._color = COLOR_PRIMARIO
            await interaction.followup.send("⚠️ Color inválido. Se mantendrá el color actual.", ephemeral=True)


# ── Panel principal ────────────────────────────

class PanelBotSetup(View):
    """Panel de configuración general del bot."""

    def __init__(self, guild_id: int, autor_id: int, bot: discord.Client):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.autor_id = autor_id
        self.bot = bot
        self.config: dict = {}

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.autor_id:
            await interaction.response.send_message("Solo el administrador que abrió el panel puede usarlo.", ephemeral=True)
            return False
        return True

    async def _cargar(self) -> None:
        self.config = await db.obtener(ARCHIVO_CONFIG, str(self.guild_id), {})
        if not isinstance(self.config, dict):
            self.config = {}

    async def _guardar(self) -> None:
        await db.establecer(ARCHIVO_CONFIG, str(self.guild_id), self.config)

    @discord.ui.button(label="⚙️ Prefijo", style=discord.ButtonStyle.secondary, row=0)
    async def btn_prefijo(self, interaction: discord.Interaction, button: Button):
        await self._cargar()
        modal = ModalPrefijo()
        await interaction.response.send_modal(modal)
        await modal.wait()
        if hasattr(modal, "_valor"):
            self.config["prefijo"] = modal._valor
            await self._guardar()

    @discord.ui.button(label="🎮 Actividad", style=discord.ButtonStyle.secondary, row=0)
    async def btn_actividad(self, interaction: discord.Interaction, button: Button):
        await self._cargar()
        modal = ModalActividad()
        await interaction.response.send_modal(modal)
        await modal.wait()
        if hasattr(modal, "_tipo") and hasattr(modal, "_texto"):
            self.config["actividad_tipo"] = modal._tipo
            self.config["actividad_texto"] = modal._texto
            await self._guardar()
            await self._aplicar_actividad(modal._tipo, modal._texto)

    @discord.ui.button(label="🔵 Estado", style=discord.ButtonStyle.secondary, row=0)
    async def btn_estado(self, interaction: discord.Interaction, button: Button):
        vista = _SeleccionEstado(self.guild_id, self.autor_id, self)
        await interaction.response.send_message("Selecciona el estado del bot:", view=vista, ephemeral=True)

    @discord.ui.button(label="🎨 Color", style=discord.ButtonStyle.secondary, row=1)
    async def btn_color(self, interaction: discord.Interaction, button: Button):
        await self._cargar()
        modal = ModalColorPrincipal()
        await interaction.response.send_modal(modal)
        await modal.wait()
        if hasattr(modal, "_color"):
            self.config["color_principal"] = modal._color
            await self._guardar()

    @discord.ui.button(label="📋 Canal de Logs", style=discord.ButtonStyle.secondary, row=1)
    async def btn_logs(self, interaction: discord.Interaction, button: Button):
        vista = _SeleccionarCanalConfig(self.guild_id, self.autor_id, self, "canal_logs", "canal de logs")
        await interaction.response.send_message("Selecciona el canal de logs:", view=vista, ephemeral=True)

    @discord.ui.button(label="💬 Canal de Comandos", style=discord.ButtonStyle.secondary, row=1)
    async def btn_canal_cmd(self, interaction: discord.Interaction, button: Button):
        vista = _SeleccionarCanalConfig(self.guild_id, self.autor_id, self, "canal_comandos", "canal de comandos")
        await interaction.response.send_message("Selecciona el canal de comandos:", view=vista, ephemeral=True)

    @discord.ui.button(label="🛡️ Rol Staff", style=discord.ButtonStyle.secondary, row=2)
    async def btn_staff(self, interaction: discord.Interaction, button: Button):
        vista = _SeleccionarRolConfig(self.guild_id, self.autor_id, self, "rol_staff", "rol de staff")
        await interaction.response.send_message("Selecciona el rol de staff:", view=vista, ephemeral=True)

    @discord.ui.button(label="✅ Guardar", style=discord.ButtonStyle.success, row=3)
    async def btn_guardar(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        await self._guardar()
        self.stop()
        await interaction.followup.send(embed=embed_exito("Configuración guardada", "La configuración del bot ha sido actualizada correctamente."), ephemeral=True)

    @discord.ui.button(label="❌ Cerrar", style=discord.ButtonStyle.danger, row=3)
    async def btn_cerrar(self, interaction: discord.Interaction, button: Button):
        self.stop()
        await interaction.response.send_message("Panel cerrado.", ephemeral=True)

    async def _aplicar_actividad(self, tipo: str, texto: str) -> None:
        tipo_map = {
            "watching": discord.ActivityType.watching,
            "playing": discord.ActivityType.playing,
            "listening": discord.ActivityType.listening,
        }
        actividad = discord.Activity(type=tipo_map.get(tipo, discord.ActivityType.watching), name=texto)
        await self.bot.change_presence(activity=actividad)


# ── Selectores auxiliares ──────────────────────

class _SeleccionEstado(View):
    _estados = {
        "en línea": discord.Status.online,
        "ausente": discord.Status.idle,
        "no molestar": discord.Status.dnd,
        "invisible": discord.Status.invisible,
    }

    def __init__(self, guild_id: int, autor_id: int, panel: PanelBotSetup):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.autor_id = autor_id
        self.panel = panel
        options = [discord.SelectOption(label=k.capitalize()) for k in self._estados]
        self.add_item(_EstadoSelect(options, self))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.autor_id


class _EstadoSelect(discord.ui.Select):
    def __init__(self, options, vista: _SeleccionEstado):
        super().__init__(placeholder="Elige el estado...", options=options)
        self.vista = vista

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        eleccion = self.values[0].lower()
        estado = _SeleccionEstado._estados.get(eleccion, discord.Status.online)
        self.vista.panel.config["estado"] = eleccion
        await self.vista.panel._guardar()
        await self.vista.panel.bot.change_presence(status=estado)
        await interaction.followup.send(f"✅ Estado cambiado a **{eleccion}**.", ephemeral=True)
        self.vista.stop()


class _SeleccionarCanalConfig(View):
    def __init__(self, guild_id: int, autor_id: int, panel: PanelBotSetup, clave: str, nombre: str):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.autor_id = autor_id
        self.panel = panel
        self.clave = clave
        self.nombre = nombre

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.autor_id

    @discord.ui.select(cls=discord.ui.ChannelSelect, placeholder="Elige un canal...", channel_types=[discord.ChannelType.text])
    async def seleccionar(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        canal = select.values[0]
        self.panel.config[self.clave] = canal.id
        await self.panel._guardar()
        await interaction.response.send_message(f"✅ {self.nombre.capitalize()} establecido en `{canal.name}`.", ephemeral=True)
        self.stop()


class _SeleccionarRolConfig(View):
    def __init__(self, guild_id: int, autor_id: int, panel: PanelBotSetup, clave: str, nombre: str):
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
        await interaction.response.send_message(f"✅ {self.nombre.capitalize()} establecido en `{rol.name}`.", ephemeral=True)
        self.stop()
