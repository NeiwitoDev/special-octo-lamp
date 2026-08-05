"""
Cog de moderación para V1 Sistemas.
Incluye todos los comandos de moderación más utilizados.
"""

import asyncio
import datetime
import logging
from datetime import timedelta

import discord
from discord.ext import commands

from embeds import embed_exito, embed_error, embed_advertencia, embed_log
from checks import es_moderador, tiene_permiso, es_administrador
from logger import log_accion
from manager import db
from constants import ARCHIVO_WARNS, ARCHIVO_CONFIG, COLOR_ADVERTENCIA, COLOR_ERROR

log = logging.getLogger(__name__)


class Moderation(commands.Cog, name="Moderación"):
    """Comandos de moderación con logs, permisos y errores controlados."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _registrar(self, ctx: commands.Context, embed: discord.Embed) -> None:
        await log_accion(self.bot, ctx.guild, embed)

    # ── ?lock / ?unlock ────────────────────────

    @commands.command(name="lock", help="Bloquea el canal actual.")
    @tiene_permiso("manage_channels")
    @commands.guild_only()
    async def lock(self, ctx: commands.Context, *, razon: str = "Sin razón especificada") -> None:
        await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
        await ctx.send(embed=embed_exito("Canal bloqueado", f"{ctx.channel.mention} ha sido bloqueado.\n**Razón:** {razon}"))
        await self._registrar(ctx, embed_log("Canal Bloqueado", ctx.author, None, razon,
                                             campos_extra=[("📢 Canal", ctx.channel.mention, True)]))

    @commands.command(name="unlock", help="Desbloquea el canal actual.")
    @tiene_permiso("manage_channels")
    @commands.guild_only()
    async def unlock(self, ctx: commands.Context, *, razon: str = "Sin razón especificada") -> None:
        await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=None)
        await ctx.send(embed=embed_exito("Canal desbloqueado", f"{ctx.channel.mention} ha sido desbloqueado."))
        await self._registrar(ctx, embed_log("Canal Desbloqueado", ctx.author, None, razon,
                                             campos_extra=[("📢 Canal", ctx.channel.mention, True)]))

    # ── ?clear ─────────────────────────────────

    @commands.command(name="clear", aliases=["purge"], help="Elimina mensajes del canal. Uso: ?clear <cantidad>")
    @tiene_permiso("manage_messages")
    @commands.guild_only()
    async def clear(self, ctx: commands.Context, cantidad: int) -> None:
        if not 1 <= cantidad <= 1000:
            await ctx.send(embed=embed_advertencia("Rango inválido", "La cantidad debe estar entre 1 y 1000."), delete_after=8)
            return
        try:
            eliminados = await ctx.channel.purge(limit=cantidad + 1)
            confirmacion = await ctx.send(embed=embed_exito("Mensajes eliminados", f"Se eliminaron **{len(eliminados) - 1}** mensajes."))
            await asyncio.sleep(5)
            await confirmacion.delete()
        except discord.Forbidden:
            await ctx.send(embed=embed_error("Sin permisos", "No tengo permisos para eliminar mensajes."))
        await self._registrar(ctx, embed_log("Mensajes Eliminados", ctx.author, None, f"{cantidad} mensajes en {ctx.channel.mention}"))

    # ── ?warn / ?warns / ?delwarn ───────────────

    @commands.command(name="warn", help="Advierte a un usuario. Uso: ?warn @usuario [razón]")
    @es_moderador()
    @commands.guild_only()
    async def warn(self, ctx: commands.Context, miembro: discord.Member, *, razon: str = "Sin razón especificada") -> None:
        if miembro.bot:
            await ctx.send(embed=embed_error("Acción inválida", "No puedes advertir a un bot."), delete_after=8)
            return
        if miembro.guild_permissions.administrator:
            await ctx.send(embed=embed_error("Acción inválida", "No puedes advertir a un administrador."), delete_after=8)
            return

        guild_warns = await db.leer(ARCHIVO_WARNS)
        servidor = guild_warns.setdefault(str(ctx.guild.id), {})
        usuario_warns = servidor.setdefault(str(miembro.id), [])
        nueva_advertencia = {
            "razon": razon,
            "moderador_id": ctx.author.id,
            "moderador_nombre": str(ctx.author),
            "fecha": datetime.datetime.utcnow().isoformat(),
        }
        usuario_warns.append(nueva_advertencia)
        await db.guardar(ARCHIVO_WARNS, guild_warns)

        total = len(usuario_warns)
        await ctx.send(embed=embed_exito("Advertencia registrada",
                                         f"{miembro.mention} ha recibido una advertencia.\n"
                                         f"**Razón:** {razon}\n**Total de advertencias:** {total}"))
        try:
            await miembro.send(embed=embed_advertencia(
                "Has recibido una advertencia",
                f"**Servidor:** {ctx.guild.name}\n**Razón:** {razon}\n**Total:** {total} advertencia(s).",
            ))
        except discord.Forbidden:
            pass

        await self._registrar(ctx, embed_log("Advertencia", ctx.author, miembro, razon,
                                             campos_extra=[("📊 Total warns", str(total), True)]))

    @commands.command(name="warns", help="Muestra las advertencias de un usuario.")
    @es_moderador()
    @commands.guild_only()
    async def warns(self, ctx: commands.Context, miembro: discord.Member) -> None:
        guild_warns = await db.leer(ARCHIVO_WARNS)
        lista = guild_warns.get(str(ctx.guild.id), {}).get(str(miembro.id), [])

        if not lista:
            await ctx.send(embed=embed_exito("Sin advertencias", f"{miembro.mention} no tiene advertencias."))
            return

        e = discord.Embed(title=f"⚠️ Advertencias de {miembro}", color=COLOR_ADVERTENCIA)
        for i, w in enumerate(lista, start=1):
            e.add_field(
                name=f"#{i} — {w['fecha'][:10]}",
                value=f"**Razón:** {w['razon']}\n**Mod:** {w['moderador_nombre']}",
                inline=False,
            )
        e.set_footer(text=f"Total: {len(lista)} advertencia(s)")
        await ctx.send(embed=e)

    @commands.command(name="delwarn", help="Elimina la advertencia #N de un usuario. Uso: ?delwarn @usuario <número>")
    @es_moderador()
    @commands.guild_only()
    async def delwarn(self, ctx: commands.Context, miembro: discord.Member, numero: int) -> None:
        guild_warns = await db.leer(ARCHIVO_WARNS)
        lista = guild_warns.get(str(ctx.guild.id), {}).get(str(miembro.id), [])

        if not lista:
            await ctx.send(embed=embed_error("Sin advertencias", f"{miembro.mention} no tiene advertencias."), delete_after=8)
            return
        if not 1 <= numero <= len(lista):
            await ctx.send(embed=embed_error("Número inválido", f"Elige un número entre 1 y {len(lista)}."), delete_after=8)
            return

        eliminada = lista.pop(numero - 1)
        guild_warns[str(ctx.guild.id)][str(miembro.id)] = lista
        await db.guardar(ARCHIVO_WARNS, guild_warns)
        await ctx.send(embed=embed_exito("Advertencia eliminada",
                                         f"Advertencia #{numero} de {miembro.mention} eliminada.\n**Razón original:** {eliminada['razon']}"))

    # ── ?kick ──────────────────────────────────

    @commands.command(name="kick", help="Expulsa a un usuario del servidor.")
    @tiene_permiso("kick_members")
    @commands.guild_only()
    async def kick(self, ctx: commands.Context, miembro: discord.Member, *, razon: str = "Sin razón especificada") -> None:
        if miembro == ctx.author:
            await ctx.send(embed=embed_error("Acción inválida", "No puedes expulsarte a ti mismo."), delete_after=8)
            return
        if miembro.top_role >= ctx.author.top_role and not ctx.author.guild_permissions.administrator:
            await ctx.send(embed=embed_error("Sin permisos", "No puedes expulsar a alguien con igual o mayor rango."), delete_after=8)
            return
        try:
            await miembro.send(embed=embed_advertencia("Has sido expulsado", f"**Servidor:** {ctx.guild.name}\n**Razón:** {razon}"))
        except discord.Forbidden:
            pass
        await miembro.kick(reason=f"{ctx.author}: {razon}")
        await ctx.send(embed=embed_exito("Usuario expulsado", f"{miembro} fue expulsado.\n**Razón:** {razon}"))
        await self._registrar(ctx, embed_log("Expulsión (Kick)", ctx.author, miembro, razon))

    # ── ?ban / ?unban ──────────────────────────

    @commands.command(name="ban", help="Banea a un usuario del servidor.")
    @tiene_permiso("ban_members")
    @commands.guild_only()
    async def ban(self, ctx: commands.Context, miembro: discord.Member, *, razon: str = "Sin razón especificada") -> None:
        if miembro == ctx.author:
            await ctx.send(embed=embed_error("Acción inválida", "No puedes banearte a ti mismo."), delete_after=8)
            return
        if miembro.top_role >= ctx.author.top_role and not ctx.author.guild_permissions.administrator:
            await ctx.send(embed=embed_error("Sin permisos", "No puedes banear a alguien con igual o mayor rango."), delete_after=8)
            return
        try:
            await miembro.send(embed=embed_error("Has sido baneado", f"**Servidor:** {ctx.guild.name}\n**Razón:** {razon}"))
        except discord.Forbidden:
            pass
        await miembro.ban(reason=f"{ctx.author}: {razon}", delete_message_days=0)
        await ctx.send(embed=embed_exito("Usuario baneado", f"{miembro} fue baneado.\n**Razón:** {razon}"))
        await self._registrar(ctx, embed_log("Baneo (Ban)", ctx.author, miembro, razon))

    @commands.command(name="unban", help="Desbanea a un usuario. Uso: ?unban <ID o usuario#discriminador>")
    @tiene_permiso("ban_members")
    @commands.guild_only()
    async def unban(self, ctx: commands.Context, *, identificador: str) -> None:
        bans = [entry async for entry in ctx.guild.bans()]
        usuario_encontrado = None
        if identificador.isdigit():
            usuario_encontrado = next((e.user for e in bans if e.user.id == int(identificador)), None)
        else:
            usuario_encontrado = next((e.user for e in bans if str(e.user) == identificador), None)

        if not usuario_encontrado:
            await ctx.send(embed=embed_error("Usuario no encontrado", f"No se encontró a `{identificador}` en los bans."), delete_after=10)
            return

        await ctx.guild.unban(usuario_encontrado, reason=f"Desban por {ctx.author}")
        await ctx.send(embed=embed_exito("Usuario desbaneado", f"{usuario_encontrado} ha sido desbaneado."))
        await self._registrar(ctx, embed_log("Desbaneo (Unban)", ctx.author, usuario_encontrado))

    # ── ?mute / ?unmute ────────────────────────

    @commands.command(name="mute", help="Silencia a un usuario. Uso: ?mute @usuario [minutos] [razón]")
    @tiene_permiso("moderate_members")
    @commands.guild_only()
    async def mute(self, ctx: commands.Context, miembro: discord.Member, minutos: int = 10, *, razon: str = "Sin razón especificada") -> None:
        if not 1 <= minutos <= 40320:
            await ctx.send(embed=embed_advertencia("Duración inválida", "La duración debe estar entre 1 y 40320 minutos (28 días)."), delete_after=8)
            return
        try:
            await miembro.timeout(timedelta(minutes=minutos), reason=f"{ctx.author}: {razon}")
            await ctx.send(embed=embed_exito("Usuario silenciado", f"{miembro.mention} silenciado por {minutos} minutos.\n**Razón:** {razon}"))
            await self._registrar(ctx, embed_log("Silencio (Mute)", ctx.author, miembro, razon,
                                                 campos_extra=[("⏱️ Duración", f"{minutos} min", True)]))
        except discord.Forbidden:
            await ctx.send(embed=embed_error("Sin permisos", "No puedo silenciar a este usuario."))

    @commands.command(name="unmute", help="Quita el silencio a un usuario.")
    @tiene_permiso("moderate_members")
    @commands.guild_only()
    async def unmute(self, ctx: commands.Context, miembro: discord.Member, *, razon: str = "Sin razón especificada") -> None:
        try:
            await miembro.timeout(None, reason=f"{ctx.author}: {razon}")
            await ctx.send(embed=embed_exito("Silencio removido", f"{miembro.mention} ya puede hablar nuevamente."))
            await self._registrar(ctx, embed_log("Silencio Removido (Unmute)", ctx.author, miembro, razon))
        except discord.Forbidden:
            await ctx.send(embed=embed_error("Sin permisos", "No puedo quitar el silencio a este usuario."))

    # ── ?slowmode ──────────────────────────────

    @commands.command(name="slowmode", help="Establece el modo lento del canal. Uso: ?slowmode <segundos>")
    @tiene_permiso("manage_channels")
    @commands.guild_only()
    async def slowmode(self, ctx: commands.Context, segundos: int) -> None:
        if not 0 <= segundos <= 21600:
            await ctx.send(embed=embed_error("Valor inválido", "El modo lento debe estar entre 0 y 21600 segundos."), delete_after=8)
            return
        await ctx.channel.edit(slowmode_delay=segundos)
        if segundos == 0:
            await ctx.send(embed=embed_exito("Modo lento desactivado", f"El canal {ctx.channel.mention} ya no tiene modo lento."))
        else:
            await ctx.send(embed=embed_exito("Modo lento activado", f"Canal {ctx.channel.mention}: {segundos}s entre mensajes."))

    # ── ?nick ──────────────────────────────────

    @commands.command(name="nick", help="Cambia el apodo de un usuario. Uso: ?nick @usuario <nuevo apodo>")
    @tiene_permiso("manage_nicknames")
    @commands.guild_only()
    async def nick(self, ctx: commands.Context, miembro: discord.Member, *, apodo: str) -> None:
        apodo_anterior = miembro.display_name
        try:
            await miembro.edit(nick=apodo[:32] if apodo.lower() != "reset" else None)
            await ctx.send(embed=embed_exito("Apodo cambiado", f"**{apodo_anterior}** → **{apodo}**"))
        except discord.Forbidden:
            await ctx.send(embed=embed_error("Sin permisos", "No puedo cambiar el apodo de ese usuario."))

    # ── ?say / ?embed ──────────────────────────

    @commands.command(name="say", help="Hace que el bot diga algo. Uso: ?say <mensaje>")
    @es_moderador()
    @commands.guild_only()
    async def say(self, ctx: commands.Context, *, mensaje: str) -> None:
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass
        await ctx.send(mensaje)

    @commands.command(name="embed", help="Envía un embed. Uso: ?embed <título> | <descripción>")
    @es_moderador()
    @commands.guild_only()
    async def send_embed(self, ctx: commands.Context, *, contenido: str) -> None:
        if "|" not in contenido:
            await ctx.send(embed=embed_advertencia("Formato incorrecto", "Usa: `?embed Título | Descripción`"), delete_after=8)
            return
        partes = contenido.split("|", 1)
        titulo = partes[0].strip()
        descripcion = partes[1].strip()
        config = await db.obtener(ARCHIVO_CONFIG, str(ctx.guild.id), {})
        color = config.get("color_principal", 0x5865F2) if isinstance(config, dict) else 0x5865F2
        e = discord.Embed(title=titulo, description=descripcion, color=color)
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass
        await ctx.send(embed=e)

    # ── ?role / ?removerole ────────────────────

    @commands.command(name="role", help="Añade un rol a un usuario. Uso: ?role @usuario @rol")
    @tiene_permiso("manage_roles")
    @commands.guild_only()
    async def role(self, ctx: commands.Context, miembro: discord.Member, rol: discord.Role) -> None:
        if rol >= ctx.guild.me.top_role:
            await ctx.send(embed=embed_error("Sin permisos", "No puedo asignar un rol más alto que el mío."), delete_after=8)
            return
        await miembro.add_roles(rol, reason=f"Por {ctx.author}")
        await ctx.send(embed=embed_exito("Rol añadido", f"Se añadió {rol.mention} a {miembro.mention}."))

    @commands.command(name="removerole", help="Remueve un rol de un usuario. Uso: ?removerole @usuario @rol")
    @tiene_permiso("manage_roles")
    @commands.guild_only()
    async def removerole(self, ctx: commands.Context, miembro: discord.Member, rol: discord.Role) -> None:
        if rol >= ctx.guild.me.top_role:
            await ctx.send(embed=embed_error("Sin permisos", "No puedo remover un rol más alto que el mío."), delete_after=8)
            return
        await miembro.remove_roles(rol, reason=f"Por {ctx.author}")
        await ctx.send(embed=embed_exito("Rol removido", f"Se removió {rol.mention} de {miembro.mention}."))

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        pass  # Delegamos al handler global en main.py


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))
