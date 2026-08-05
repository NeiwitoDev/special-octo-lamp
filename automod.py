"""
Cog de AutoModeración para V1 Sistemas.

Detecta y sanciona automáticamente:
  • Flood  — múltiples mensajes rápidos del mismo usuario.
  • Links  — cualquier enlace enviado por usuarios sin permiso de administrador.
             (política de cero tolerancia: se borra SIEMPRE)

Flujo por infracción:
  1. Elimina el/los mensajes infractores.
  2. Avisa al usuario en el canal (auto-eliminado a los 15 seg).
  3. Registra en el canal de logs configurado en /bot-setup.
  4. Acumula advertencias internas (por tipo); al llegar a 3 aplica un warn
     oficial (warns.json) + timeout breve.
"""

import asyncio
import logging
import re
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import DefaultDict

import discord
from discord.ext import commands
from discord import app_commands

from manager import db
from embeds import embed_advertencia, embed_error, embed_exito, embed_log
from checks import solo_administrador
from logger import log_accion
from constants import (
    ARCHIVO_CONFIG, ARCHIVO_WARNS, COLOR_ADVERTENCIA, COLOR_ERROR,
)

log = logging.getLogger(__name__)

# ── Configuración ──────────────────────────────
FLOOD_MENSAJES         = 5
FLOOD_VENTANA_SEG      = 5
ADVERTENCIAS_PARA_WARN = 3
TIMEOUT_TRAS_WARN      = 5   # minutos

URL_REGEX = re.compile(
    r"https?://[^\s]+"
    r"|discord(?:\.gg|app\.com/invite)/[^\s]+"
    r"|www\.[a-zA-Z0-9\-]+\.[a-zA-Z]{2,}[^\s]*",
    re.IGNORECASE,
)


# ── Tracker de flood ───────────────────────────

class _FloodTracker:
    def __init__(self, ventana: int, limite: int):
        self.ventana = ventana
        self.limite  = limite
        self._datos: DefaultDict[int, DefaultDict[int, deque]] = (
            defaultdict(lambda: defaultdict(deque))
        )

    def registrar(self, guild_id: int, user_id: int) -> bool:
        ahora = datetime.now(timezone.utc)
        corte = ahora - timedelta(seconds=self.ventana)
        cola  = self._datos[guild_id][user_id]
        while cola and cola[0] < corte:
            cola.popleft()
        cola.append(ahora)
        return len(cola) >= self.limite

    def resetear(self, guild_id: int, user_id: int) -> None:
        self._datos[guild_id][user_id].clear()


# Advertencias acumuladas: (guild_id, user_id, tipo) → int
_advertencias: DefaultDict[tuple, int] = defaultdict(int)


# ── Cog ────────────────────────────────────────

class AutoMod(commands.Cog, name="AutoMod"):
    """Moderación automática: flood y bloqueo total de enlaces."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._flood_tracker = _FloodTracker(ventana=FLOOD_VENTANA_SEG, limite=FLOOD_MENSAJES)

    @app_commands.command(name="automod-setup", description="Activa o desactiva el sistema de automoderación.")
    @solo_administrador()
    async def automod_setup(self, interaction: discord.Interaction) -> None:
        config = await db.obtener(ARCHIVO_CONFIG, str(interaction.guild_id), {}) or {}
        activo = config.get("automod_activo", True)

        vista = _PanelAutomod(interaction.guild_id, interaction.user.id, activo)
        e = discord.Embed(
            title="🤖  AutoModeración — V1 Sistemas",
            color=COLOR_ADVERTENCIA,
            timestamp=datetime.utcnow(),
        )
        e.add_field(name="Estado", value="✅ Activo" if activo else "❌ Inactivo", inline=False)
        e.add_field(
            name="🌊 Flood",
            value=f"`{FLOOD_MENSAJES}` mensajes en `{FLOOD_VENTANA_SEG}s` → advertencia\n`{ADVERTENCIAS_PARA_WARN}` advertencias → warn oficial",
            inline=False,
        )
        e.add_field(
            name="🔗 Links",
            value=(
                "Cualquier enlace enviado por usuarios sin permiso de administrador "
                "es **eliminado automáticamente**.\n"
                f"`{ADVERTENCIAS_PARA_WARN}` advertencias de links → warn oficial"
            ),
            inline=False,
        )
        e.add_field(name="⏱️ Timeout tras warn oficial", value=f"`{TIMEOUT_TRAS_WARN}` minutos", inline=True)
        e.set_footer(text="Canal de logs heredado de /bot-setup")
        await interaction.response.send_message(embed=e, view=vista, ephemeral=True)

    @automod_setup.error
    async def automod_setup_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                embed=embed_error("Sin permisos", "Solo los administradores pueden usar este comando."),
                ephemeral=True,
            )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return
        miembro = message.author
        if not isinstance(miembro, discord.Member):
            return
        if miembro.guild_permissions.administrator:
            return

        config = await db.obtener(ARCHIVO_CONFIG, str(message.guild.id), {}) or {}
        if not config.get("automod_activo", True):
            return

        # Regla 1: Links (cero tolerancia)
        if URL_REGEX.search(message.content):
            await self._sancionar(
                message=message, tipo="link",
                titulo_aviso="🔗  AutoMod — Enlace no permitido",
                texto_aviso=(
                    f"Hey {miembro.mention}! Los enlaces **no están permitidos** en este servidor.\n"
                    "Tu mensaje fue eliminado y recibiste una advertencia automática."
                ),
                purgar_historial=False,
            )
            return

        # Regla 2: Flood
        if self._flood_tracker.registrar(message.guild.id, miembro.id):
            self._flood_tracker.resetear(message.guild.id, miembro.id)
            await self._sancionar(
                message=message, tipo="flood",
                titulo_aviso="🌊  AutoMod — Flood detectado",
                texto_aviso=(
                    f"Hey {miembro.mention}! Nuestro sistema detectó **flood** de tu parte.\n"
                    "Fuiste advertido automáticamente. Por favor, evita enviar mensajes repetidos en poco tiempo."
                ),
                purgar_historial=True,
            )

    async def _sancionar(self, message, tipo, titulo_aviso, texto_aviso, purgar_historial) -> None:
        guild   = message.guild
        canal   = message.channel
        miembro = message.author

        # 1. Eliminar mensaje(s)
        try:
            if purgar_historial:
                await canal.purge(limit=20, check=lambda m: m.author.id == miembro.id, reason=f"AutoMod — {tipo}")
            else:
                await message.delete()
        except discord.Forbidden:
            log.warning(f"[AUTOMOD] Sin permiso para borrar en #{canal.name}")
        except discord.NotFound:
            pass
        except discord.HTTPException as exc:
            log.error(f"[AUTOMOD] Error al borrar mensaje: {exc}")

        # 2. Aviso en el canal
        clave = (guild.id, miembro.id, tipo)
        _advertencias[clave] += 1
        total_adv = _advertencias[clave]

        try:
            e_aviso = embed_advertencia(titulo_aviso, texto_aviso)
            e_aviso.set_footer(text=f"Advertencia {total_adv}/{ADVERTENCIAS_PARA_WARN} • V1 Sistemas")
            aviso = await canal.send(embed=e_aviso)
            await asyncio.sleep(15)
            try:
                await aviso.delete()
            except discord.HTTPException:
                pass
        except discord.Forbidden:
            log.warning(f"[AUTOMOD] Sin permiso para enviar en #{canal.name}")

        # 3. Log en canal de Discord
        tipo_label = {"flood": "Flood", "link": "Enlace no permitido"}.get(tipo, tipo)
        e_log = embed_log(
            accion=f"AutoMod — {tipo_label}",
            moderador=None,
            objetivo=miembro,
            razon=f"Detección automática: {tipo}.",
            color=COLOR_ADVERTENCIA,
            campos_extra=[
                ("📢 Canal",         canal.mention,                         True),
                ("⚠️ Advertencias", f"{total_adv}/{ADVERTENCIAS_PARA_WARN}", True),
            ],
        )
        await log_accion(self.bot, guild, e_log)

        # 4. Warn oficial al llegar al límite
        if total_adv >= ADVERTENCIAS_PARA_WARN:
            _advertencias[clave] = 0
            await self._aplicar_warn_oficial(guild, canal, miembro, tipo)

    async def _aplicar_warn_oficial(self, guild, canal, miembro, tipo) -> None:
        import datetime as dt
        tipo_label = {"flood": "flood", "link": "envío de enlaces"}.get(tipo, tipo)
        razon = f"[AutoMod] {ADVERTENCIAS_PARA_WARN} advertencias de {tipo_label}."

        guild_warns = await db.leer(ARCHIVO_WARNS)
        servidor    = guild_warns.setdefault(str(guild.id), {})
        lista_warns = servidor.setdefault(str(miembro.id), [])
        lista_warns.append({
            "razon":            razon,
            "moderador_id":     self.bot.user.id,
            "moderador_nombre": str(self.bot.user),
            "fecha":            dt.datetime.utcnow().isoformat(),
        })
        await db.guardar(ARCHIVO_WARNS, guild_warns)
        total_warns = len(lista_warns)

        try:
            await miembro.timeout(timedelta(minutes=TIMEOUT_TRAS_WARN), reason=razon)
        except discord.Forbidden:
            log.warning(f"[AUTOMOD] Sin permiso de timeout sobre {miembro}")
        except Exception as exc:
            log.error(f"[AUTOMOD] Error aplicando timeout: {exc}")

        try:
            e_warn = embed_error(
                "🚨  AutoMod — Warn oficial aplicado",
                (
                    f"{miembro.mention} acumuló **{ADVERTENCIAS_PARA_WARN}** advertencias "
                    f"por `{tipo_label}` y recibió un **warn oficial** "
                    f"+ timeout de `{TIMEOUT_TRAS_WARN}` minutos.\n"
                    f"Total warns: `{total_warns}`"
                ),
            )
            e_warn.set_footer(text="V1 Sistemas AutoMod")
            aviso = await canal.send(embed=e_warn)
            await asyncio.sleep(20)
            try:
                await aviso.delete()
            except discord.HTTPException:
                pass
        except discord.Forbidden:
            pass

        try:
            await miembro.send(embed=embed_advertencia(
                "Has recibido un warn oficial",
                (
                    f"**Servidor:** {guild.name}\n"
                    f"**Razón:** {razon}\n"
                    f"**Total warns:** {total_warns}\n"
                    f"**Timeout:** {TIMEOUT_TRAS_WARN} minutos.\n\n"
                    "Por favor respeta las normas del servidor."
                ),
            ))
        except discord.Forbidden:
            pass

        await log_accion(
            self.bot, guild,
            embed_log(
                accion="AutoMod — Warn oficial",
                moderador=self.bot.user,
                objetivo=miembro,
                razon=razon,
                color=COLOR_ERROR,
                campos_extra=[
                    ("📊 Total warns", str(total_warns),          True),
                    ("⏱️ Timeout",     f"{TIMEOUT_TRAS_WARN} min", True),
                ],
            ),
        )
        log.info(f"[AUTOMOD] Warn oficial → {miembro} en {guild.name} ({tipo_label})")


# ── Panel /automod-setup ───────────────────────

class _PanelAutomod(discord.ui.View):
    def __init__(self, guild_id: int, autor_id: int, activo: bool):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.autor_id = autor_id
        self.activo   = activo

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.autor_id:
            await interaction.response.send_message("Solo el administrador que abrió el panel puede usarlo.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="✅ Activar AutoMod", style=discord.ButtonStyle.success, row=0)
    async def activar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, True)

    @discord.ui.button(label="❌ Desactivar AutoMod", style=discord.ButtonStyle.danger, row=0)
    async def desactivar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, False)

    async def _toggle(self, interaction: discord.Interaction, estado: bool) -> None:
        config = await db.obtener(ARCHIVO_CONFIG, str(self.guild_id), {}) or {}
        config["automod_activo"] = estado
        await db.establecer(ARCHIVO_CONFIG, str(self.guild_id), config)
        self.activo = estado
        label = "activado ✅" if estado else "desactivado ❌"
        self.stop()
        await interaction.response.send_message(
            embed=embed_exito("AutoMod actualizado", f"El sistema de automoderación ha sido **{label}**."),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AutoMod(bot))
