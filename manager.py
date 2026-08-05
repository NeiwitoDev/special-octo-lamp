"""
Gestor de base de datos JSON para V1 Sistemas.
Escritura atómica para evitar corrupción de datos.
"""

import asyncio
import json
import os
import tempfile
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# Carpeta "data" junto al script principal
RUTA_DATOS = Path(__file__).parent / "data"


class JSONDatabase:
    """
    Singleton que gestiona archivos JSON como base de datos.
    Implementa escritura atómica: temp → rename.
    """

    _instancia = None
    _locks: dict[str, asyncio.Lock] = {}

    def __new__(cls):
        if cls._instancia is None:
            cls._instancia = super().__new__(cls)
            RUTA_DATOS.mkdir(parents=True, exist_ok=True)
        return cls._instancia

    def _ruta(self, archivo: str) -> Path:
        return RUTA_DATOS / archivo

    def _lock(self, archivo: str) -> asyncio.Lock:
        if archivo not in self._locks:
            self._locks[archivo] = asyncio.Lock()
        return self._locks[archivo]

    async def leer(self, archivo: str, default: Any = None) -> Any:
        async with self._lock(archivo):
            ruta = self._ruta(archivo)
            if not ruta.exists():
                return default if default is not None else {}
            try:
                loop = asyncio.get_event_loop()
                contenido = await loop.run_in_executor(None, ruta.read_text, "utf-8")
                return json.loads(contenido)
            except (json.JSONDecodeError, OSError) as e:
                log.error(f"[DB] Error al leer '{archivo}': {e}")
                return default if default is not None else {}

    async def guardar(self, archivo: str, datos: Any) -> bool:
        async with self._lock(archivo):
            ruta = self._ruta(archivo)
            try:
                loop = asyncio.get_event_loop()
                serializado = json.dumps(datos, ensure_ascii=False, indent=2)

                def _escribir():
                    with tempfile.NamedTemporaryFile(
                        mode="w", encoding="utf-8",
                        dir=ruta.parent, delete=False, suffix=".tmp",
                    ) as tmp:
                        tmp.write(serializado)
                        tmp_path = tmp.name
                    os.replace(tmp_path, ruta)

                await loop.run_in_executor(None, _escribir)
                return True
            except OSError as e:
                log.error(f"[DB] Error al guardar '{archivo}': {e}")
                return False

    async def obtener(self, archivo: str, clave: str, default: Any = None) -> Any:
        datos = await self.leer(archivo)
        return datos.get(str(clave), default)

    async def establecer(self, archivo: str, clave: str, valor: Any) -> bool:
        async with self._lock(archivo):
            ruta = self._ruta(archivo)
            try:
                contenido = json.loads(ruta.read_text("utf-8")) if ruta.exists() else {}
                contenido[str(clave)] = valor
                serializado = json.dumps(contenido, ensure_ascii=False, indent=2)

                def _escribir():
                    with tempfile.NamedTemporaryFile(
                        mode="w", encoding="utf-8",
                        dir=ruta.parent, delete=False, suffix=".tmp",
                    ) as tmp:
                        tmp.write(serializado)
                        tmp_path = tmp.name
                    os.replace(tmp_path, ruta)

                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, _escribir)
                return True
            except (json.JSONDecodeError, OSError) as e:
                log.error(f"[DB] Error en establecer '{archivo}[{clave}]': {e}")
                return False

    async def eliminar_clave(self, archivo: str, clave: str) -> bool:
        datos = await self.leer(archivo)
        if str(clave) in datos:
            del datos[str(clave)]
            return await self.guardar(archivo, datos)
        return False


# Instancia global
db = JSONDatabase()
