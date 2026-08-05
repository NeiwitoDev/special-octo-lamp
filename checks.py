"""
Decoradores y funciones de verificación de permisos para V1 Sistemas.
"""

import discord
from discord.ext import commands
from discord import app_commands


# ── Checks para comandos de prefijo ───────────

def es_administrador():
    async def predicate(ctx: commands.Context) -> bool:
        if ctx.author.guild_permissions.administrator:
            return True
        raise commands.MissingPermissions(["administrator"])
    return commands.check(predicate)


def es_moderador():
    async def predicate(ctx: commands.Context) -> bool:
        perms = ctx.author.guild_permissions
        if perms.administrator or perms.ban_members or perms.manage_messages:
            return True
        raise commands.MissingPermissions(["manage_messages"])
    return commands.check(predicate)


def tiene_permiso(*permisos: str):
    async def predicate(ctx: commands.Context) -> bool:
        for p in permisos:
            if not getattr(ctx.author.guild_permissions, p, False):
                raise commands.MissingPermissions([p])
        return True
    return commands.check(predicate)


# ── Checks para slash commands ─────────────────

def solo_administrador():
    def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.administrator:
            return True
        raise app_commands.MissingPermissions(["administrator"])
    return app_commands.check(predicate)


# ── Utilidades de verificación ─────────────────

def miembro_tiene_permiso(miembro: discord.Member, *permisos: str) -> bool:
    if miembro.guild_permissions.administrator:
        return True
    return all(getattr(miembro.guild_permissions, p, False) for p in permisos)


def bot_tiene_permiso(guild: discord.Guild, bot_member: discord.Member, *permisos: str) -> tuple[bool, list[str]]:
    faltantes = [p for p in permisos if not getattr(bot_member.guild_permissions, p, False)]
    return (len(faltantes) == 0, faltantes)
