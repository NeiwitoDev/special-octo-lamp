"""
Vistas e interacciones para el sistema de tickets.
"""

import asyncio
import io
import logging
from datetime import datetime

import discord
from discord.ui import Modal, TextInput, View, Button

from embeds import embed_exito, embed_error, embed_advertencia, embed_log, embed_info
from manager import db
from constants import (
    ARCHIVO_TICKETS, ARCHIVO_CONFIG, COLOR_PRIMARIO,
    COLOR_ERROR, MAX_TICKETS_DEFAULT, TIMEOUT_ELIMINAR_TICKET,
)

log = logging.getLogger(__name__)


# ── Transcript HTML ────────────────────────────

async def generar_transcript(canal: discord.TextChannel) -> io.BytesIO:
    mensajes = [m async for m in canal.history(limit=None, oldest_first=True)]
    html_lines = [
        "<!DOCTYPE html><html lang='es'><head>",
        "<meta charset='UTF-8'>",
        f"<title>Transcript — {canal.name}</title>",
        "<style>body{font-family:sans-serif;background:#36393f;color:#dcddde;padding:20px}",
        ".msg{margin:8px 0;padding:8px;background:#2f3136;border-radius:6px}",
        ".autor{font-weight:bold;color:#7289da}.hora{font-size:0.8em;color:#72767d}</style>",
        "</head><body>",
        f"<h2>Transcript: {canal.name}</h2>",
        f"<p>Generado el {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</p>",
    ]
    for m in mensajes:
        contenido = discord.utils.escape_markdown(m.content) if m.content else "<em>[sin texto]</em>"
        html_lines.append(
            f"<div class='msg'>"
            f"<span class='autor'>{discord.utils.escape_html(str(m.author))}</span> "
            f"<span class='hora'>{m.created_at.strftime('%H:%M %d/%m/%Y')}</span>"
            f"<p>{contenido}</p></div>"
        )
    html_lines.append("</body></html>")
    return io.BytesIO("\n".join(html_lines).encode("utf-8"))


# ── Modal de razón de cierre ───────────────────

class ModalCierreTicket(Modal, title="🔒 Cerrar Ticket"):
    razon = TextInput(
        label="Razón del cierre",
        style=discord.TextStyle.paragraph,
        placeholder="Describe el motivo del cierre...",
        max_length=1000,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        self._razon = self.razon.value
        await interaction.followup.send("✅ Razón registrada. Procesando cierre...", ephemeral=True)


# ── Confirmación de cierre ─────────────────────

class ConfirmacionCierre(View):
    def __init__(self, solicitante_id: int):
        super().__init__(timeout=60)
        self.solicitante_id = solicitante_id
        self.confirmado = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.solicitante_id

    @discord.ui.button(label="Confirmar cierre", style=discord.ButtonStyle.danger, emoji="🔒")
    async def confirmar(self, interaction: discord.Interaction, button: Button):
        self.confirmado = True
        self.stop()
        modal = ModalCierreTicket()
        await interaction.response.send_modal(modal)
        await modal.wait()
        self._razon = getattr(modal, "_razon", "Sin razón especificada")

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancelar(self, interaction: discord.Interaction, button: Button):
        self.stop()
        await interaction.response.send_message("Cierre cancelado.", ephemeral=True)


# ── Botones dentro del ticket ──────────────────

class BotonesTicket(View):
    """Fila de botones de acción dentro del ticket. Persistente."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Reclamar", style=discord.ButtonStyle.primary, emoji="🙋", custom_id="ticket:reclamar", row=0)
    async def reclamar(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        canal = interaction.channel
        tickets = await db.leer(ARCHIVO_TICKETS)
        guild_tickets = tickets.get(str(interaction.guild_id), {}).get("abiertos", {})
        if str(canal.id) in guild_tickets:
            guild_tickets[str(canal.id)]["reclamado_por"] = interaction.user.id
            tickets.setdefault(str(interaction.guild_id), {}).setdefault("abiertos", {})[str(canal.id)] = guild_tickets[str(canal.id)]
            await db.guardar(ARCHIVO_TICKETS, tickets)
        await interaction.followup.send(f"✅ {interaction.user.mention} ha reclamado el ticket.", ephemeral=False)

    @discord.ui.button(label="Liberar", style=discord.ButtonStyle.secondary, emoji="🔓", custom_id="ticket:liberar", row=0)
    async def liberar(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        tickets = await db.leer(ARCHIVO_TICKETS)
        datos = tickets.get(str(interaction.guild_id), {}).get("abiertos", {}).get(str(interaction.channel_id), {})
        if datos.get("reclamado_por") != interaction.user.id and not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("Solo quien reclamó el ticket puede liberarlo.", ephemeral=True)
            return
        datos.pop("reclamado_por", None)
        tickets.setdefault(str(interaction.guild_id), {}).setdefault("abiertos", {})[str(interaction.channel_id)] = datos
        await db.guardar(ARCHIVO_TICKETS, tickets)
        await interaction.followup.send("🔓 Ticket liberado.", ephemeral=False)

    @discord.ui.button(label="Cerrar", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="ticket:cerrar", row=0)
    async def cerrar(self, interaction: discord.Interaction, button: Button):
        conf = ConfirmacionCierre(interaction.user.id)
        await interaction.response.send_message("¿Confirmar cierre del ticket?", view=conf, ephemeral=True)
        await conf.wait()
        if not conf.confirmado:
            return

        razon = getattr(conf, "_razon", "Sin razón especificada")
        canal = interaction.channel

        # Generar transcript
        try:
            transcript_bytes = await generar_transcript(canal)
            archivo_transcript = discord.File(transcript_bytes, filename=f"transcript-{canal.name}.html")
        except Exception as e:
            log.error(f"Error generando transcript: {e}")
            archivo_transcript = None

        # Enviar transcript al canal de logs
        config = await db.obtener(ARCHIVO_CONFIG, str(interaction.guild_id), {})
        canal_logs_id = config.get("canal_logs") if isinstance(config, dict) else None
        if canal_logs_id and archivo_transcript:
            try:
                canal_logs = interaction.guild.get_channel(canal_logs_id)
                if canal_logs:
                    e = embed_log("Ticket Cerrado", interaction.user, None, razon,
                                  campos_extra=[("📁 Canal", canal.name, True)])
                    transcript_bytes.seek(0)
                    await canal_logs.send(embed=e, file=discord.File(transcript_bytes, filename=f"transcript-{canal.name}.html"))
            except Exception as e:
                log.warning(f"No se pudo enviar transcript a logs: {e}")

        # Enviar transcript por DM al creador
        tickets_data = await db.leer(ARCHIVO_TICKETS)
        creador_id = tickets_data.get(str(interaction.guild_id), {}).get("abiertos", {}).get(str(canal.id), {}).get("creador_id")
        if creador_id and archivo_transcript:
            try:
                creador = await interaction.client.fetch_user(creador_id)
                transcript_bytes.seek(0)
                await creador.send(
                    embed=embed_info("Transcript de tu ticket", f"Ticket `{canal.name}` cerrado.\n**Razón:** {razon}"),
                    file=discord.File(transcript_bytes, filename=f"transcript-{canal.name}.html"),
                )
            except discord.Forbidden:
                pass
            except Exception as e:
                log.warning(f"No se pudo enviar DM al creador: {e}")

        # Eliminar datos del ticket de la DB
        g_tickets = tickets_data.get(str(interaction.guild_id), {}).get("abiertos", {})
        g_tickets.pop(str(canal.id), None)
        tickets_data.setdefault(str(interaction.guild_id), {})["abiertos"] = g_tickets
        await db.guardar(ARCHIVO_TICKETS, tickets_data)

        await canal.send(embed=embed_advertencia("Ticket cerrado", f"Cerrando en {TIMEOUT_ELIMINAR_TICKET} segundos..."))
        await asyncio.sleep(TIMEOUT_ELIMINAR_TICKET)
        try:
            await canal.delete(reason=f"Ticket cerrado por {interaction.user}: {razon}")
        except discord.HTTPException as e:
            log.error(f"Error al eliminar canal ticket: {e}")

    @discord.ui.button(label="Transcript", style=discord.ButtonStyle.secondary, emoji="📄", custom_id="ticket:transcript", row=1)
    async def transcript(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        try:
            t = await generar_transcript(interaction.channel)
            await interaction.followup.send(
                "📄 Transcript generado:",
                file=discord.File(t, filename=f"transcript-{interaction.channel.name}.html"),
                ephemeral=True,
            )
        except Exception as e:
            await interaction.followup.send(embed=embed_error("Error", f"No se pudo generar el transcript: {e}"), ephemeral=True)

    @discord.ui.button(label="Añadir usuario", style=discord.ButtonStyle.secondary, emoji="➕", custom_id="ticket:agregar", row=1)
    async def agregar_usuario(self, interaction: discord.Interaction, button: Button):
        vista = _SeleccionarUsuario(interaction.user.id, "agregar", interaction.channel)
        await interaction.response.send_message("Selecciona el usuario a añadir:", view=vista, ephemeral=True)

    @discord.ui.button(label="Quitar usuario", style=discord.ButtonStyle.secondary, emoji="➖", custom_id="ticket:quitar", row=1)
    async def quitar_usuario(self, interaction: discord.Interaction, button: Button):
        vista = _SeleccionarUsuario(interaction.user.id, "quitar", interaction.channel)
        await interaction.response.send_message("Selecciona el usuario a quitar:", view=vista, ephemeral=True)


class _SeleccionarUsuario(View):
    def __init__(self, autor_id: int, accion: str, canal: discord.TextChannel):
        super().__init__(timeout=60)
        self.autor_id = autor_id
        self.accion = accion
        self.canal = canal

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.autor_id

    @discord.ui.user_select(placeholder="Elige un usuario...")
    async def seleccionar(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        await interaction.response.defer(ephemeral=True)
        usuario = select.values[0]
        try:
            if self.accion == "agregar":
                await self.canal.set_permissions(usuario, view_channel=True, send_messages=True)
                await interaction.followup.send(f"✅ {usuario.mention} añadido al ticket.", ephemeral=True)
            else:
                await self.canal.set_permissions(usuario, overwrite=None)
                await interaction.followup.send(f"✅ {usuario.mention} removido del ticket.", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send(embed=embed_error("Sin permisos", "No puedo modificar los permisos del canal."), ephemeral=True)
        self.stop()


# ── Botón para abrir ticket ────────────────────

class BotonAbrirTicket(View):
    """Vista persistente con el botón de abrir ticket en el canal."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Abrir Ticket", style=discord.ButtonStyle.success, emoji="🎫", custom_id="ticket:abrir")
    async def abrir(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        config_tickets = await db.obtener(ARCHIVO_TICKETS, str(guild.id), {})

        if not isinstance(config_tickets, dict):
            await interaction.followup.send(embed=embed_error("Sin configuración", "El sistema de tickets no está configurado."), ephemeral=True)
            return

        max_tickets = config_tickets.get("max_por_usuario", MAX_TICKETS_DEFAULT)
        abiertos = config_tickets.get("abiertos", {})
        tickets_usuario = sum(1 for t in abiertos.values() if t.get("creador_id") == interaction.user.id)
        if tickets_usuario >= max_tickets:
            await interaction.followup.send(
                embed=embed_advertencia("Límite alcanzado", f"Ya tienes `{tickets_usuario}/{max_tickets}` tickets abiertos."),
                ephemeral=True,
            )
            return

        categoria_id = config_tickets.get("categoria_id")
        categoria = guild.get_channel(categoria_id) if categoria_id else None

        nombre_canal = f"ticket-{interaction.user.name.lower().replace(' ', '-')}"
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }

        rol_staff_id = config_tickets.get("rol_staff_id")
        if rol_staff_id:
            rol_staff = guild.get_role(rol_staff_id)
            if rol_staff:
                overwrites[rol_staff] = discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_messages=True)

        try:
            nuevo_canal = await guild.create_text_channel(
                name=nombre_canal,
                category=categoria,
                overwrites=overwrites,
                reason=f"Ticket creado por {interaction.user}",
            )
        except discord.Forbidden:
            await interaction.followup.send(embed=embed_error("Sin permisos", "No puedo crear canales en este servidor."), ephemeral=True)
            return

        abiertos[str(nuevo_canal.id)] = {
            "creador_id": interaction.user.id,
            "creado_en": datetime.utcnow().isoformat(),
        }
        config_tickets["abiertos"] = abiertos
        await db.establecer(ARCHIVO_TICKETS, str(guild.id), config_tickets)

        mensaje_inicial = config_tickets.get("mensaje_inicial", "¡Bienvenido a tu ticket! El staff te atenderá pronto.")
        ping_rol = f"<@&{rol_staff_id}>" if rol_staff_id else ""

        e = discord.Embed(
            title="🎫 Ticket Abierto",
            description=mensaje_inicial,
            color=config_tickets.get("color", COLOR_PRIMARIO),
            timestamp=datetime.utcnow(),
        )
        e.set_footer(text=f"Creado por {interaction.user}")

        await nuevo_canal.send(
            content=f"{interaction.user.mention} {ping_rol}".strip(),
            embed=e,
            view=BotonesTicket(),
        )
        await interaction.followup.send(f"✅ Tu ticket ha sido creado: {nuevo_canal.mention}", ephemeral=True)
