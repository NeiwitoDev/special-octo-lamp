"""
Funciones reutilizables para construir Discord Embeds estilizados.
"""

from datetime import datetime
import discord
from constants import (
    COLOR_PRIMARIO, COLOR_EXITO, COLOR_ERROR,
    COLOR_ADVERTENCIA, COLOR_INFO, COLOR_LOG,
)


def _timestamp() -> datetime:
    return datetime.utcnow()


def embed_exito(titulo: str, descripcion: str = "", color: int = COLOR_EXITO) -> discord.Embed:
    """Embed verde para operaciones exitosas."""
    return discord.Embed(title=f"✅  {titulo}", description=descripcion, color=color, timestamp=_timestamp())


def embed_error(titulo: str, descripcion: str = "") -> discord.Embed:
    """Embed rojo para errores."""
    return discord.Embed(title=f"❌  {titulo}", description=descripcion, color=COLOR_ERROR, timestamp=_timestamp())


def embed_advertencia(titulo: str, descripcion: str = "") -> discord.Embed:
    """Embed amarillo para advertencias."""
    return discord.Embed(title=f"⚠️  {titulo}", description=descripcion, color=COLOR_ADVERTENCIA, timestamp=_timestamp())


def embed_info(titulo: str, descripcion: str = "", color: int = COLOR_PRIMARIO) -> discord.Embed:
    """Embed azul para información general."""
    return discord.Embed(title=f"ℹ️  {titulo}", description=descripcion, color=color, timestamp=_timestamp())


def embed_log(
    accion: str,
    moderador: discord.Member | None,
    objetivo: discord.Member | discord.User | None,
    razon: str = "Sin razón especificada",
    color: int = COLOR_LOG,
    campos_extra: list[tuple[str, str, bool]] | None = None,
) -> discord.Embed:
    """Embed estandarizado para registros de moderación."""
    e = discord.Embed(title=f"📋  {accion}", color=color, timestamp=_timestamp())
    if objetivo:
        e.set_author(name=str(objetivo), icon_url=objetivo.display_avatar.url)
        e.add_field(name="🎯 Objetivo", value=f"{objetivo.mention} (`{objetivo.id}`)", inline=True)
    if moderador:
        e.add_field(name="🛡️ Moderador", value=f"{moderador.mention} (`{moderador.id}`)", inline=True)
    e.add_field(name="📝 Razón", value=razon, inline=False)
    if campos_extra:
        for nombre, valor, inline in campos_extra:
            e.add_field(name=nombre, value=valor, inline=inline)
    return e


def embed_bienvenida(
    miembro: discord.Member,
    titulo: str,
    descripcion: str,
    color: int,
    imagen: str | None,
    thumbnail: str | None,
    footer: str | None,
    autor: str | None,
) -> discord.Embed:
    """Construye el embed de bienvenida con las variables sustituidas."""
    variables = {
        "{usuario}":  miembro.name,
        "{servidor}": miembro.guild.name,
        "{miembros}": str(miembro.guild.member_count),
        "{mencion}":  miembro.mention,
    }

    def reemplazar(texto: str) -> str:
        for var, val in variables.items():
            texto = texto.replace(var, val)
        return texto

    e = discord.Embed(
        title=reemplazar(titulo),
        description=reemplazar(descripcion),
        color=color,
        timestamp=_timestamp(),
    )
    if imagen:
        e.set_image(url=imagen)
    if thumbnail:
        e.set_thumbnail(url=thumbnail)
    if footer:
        e.set_footer(text=reemplazar(footer))
    if autor:
        e.set_author(name=reemplazar(autor), icon_url=miembro.display_avatar.url)
    return e
