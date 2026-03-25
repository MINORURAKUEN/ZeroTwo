"""
enhance_handler.py - Mejora de imagen con IA (upscale 4x)
Comandos: /enhance, /hd, /remini
Acepta: foto enviada directamente o respondiendo a una foto/documento imagen
"""

import io
import logging
import subprocess
from pathlib import Path
from pyrogram import filters, enums
from pyrogram.types import Message

logger = logging.getLogger(__name__)

# API de APICausas — upscale 4x
_APIKEY   = "causa-0e3eacf90ab7be15"
_ENDPOINT = "https://rest.apicausas.xyz/api/v1/utilidades/upscale?apikey={apikey}&url={url}&type=4"

# Tipos MIME de imagen aceptados
_VALID_MIME = {'image/jpeg', 'image/jpg', 'image/png'}


def register(app, work_dir):
    """Registra el handler de mejora de imagen."""

    @app.on_message(filters.command(["enhance", "hd", "remini"]))
    async def enhance_command(client, message: Message):
        """
        Mejora la calidad de una imagen con IA (upscale 4x).
        Uso:
          - Envía /enhance respondiendo a una foto
          - Envía /enhance con una foto adjunta
        """

        # ── Obtener foto: del quoted o del propio mensaje ─────────────────────
        target = message.reply_to_message if message.reply_to_message else message

        photo = target.photo
        doc   = target.document if (
            target.document and
            getattr(target.document, 'mime_type', '') in _VALID_MIME
        ) else None

        if not photo and not doc:
            await message.reply_text(
                "🖼️ <b>Mejorador de Imagen con IA</b>\n\n"
                "Envíame una imagen o responde a una con el comando.\n\n"
                "<b>Uso:</b>\n"
                "<code>/enhance</code> — responde a una foto\n"
                "<code>/hd</code>     — alias\n"
                "<code>/remini</code> — alias\n\n"
                "✨ Mejora la resolución hasta <b>4x</b> con IA.",
                parse_mode=enums.ParseMode.HTML
            )
            return

        user_id  = message.from_user.id
        username = message.from_user.username or message.from_user.first_name
        logger.info(f"🖼️ Enhance solicitado por @{username}")

        status_msg = await message.reply_text(
            "⏳ <b>Procesando imagen…</b>\n"
            "⬇️ Descargando foto…",
            parse_mode=enums.ParseMode.HTML
        )

        local_path = work_dir / f"{user_id}_enhance_input.jpg"
        output_path = work_dir / f"{user_id}_enhance_output.jpg"

        try:
            # ── 1. Descargar la foto ──────────────────────────────────────────
            await target.download(file_name=str(local_path))
            size_kb = local_path.stat().st_size / 1024
            logger.info(f"✅ Foto descargada: {size_kb:.1f} KB")

            await status_msg.edit_text(
                "⏳ <b>Procesando imagen…</b>\n"
                "☁️ Subiendo a servidor para mejorar…",
                parse_mode=enums.ParseMode.HTML
            )

            # ── 2. Subir imagen a un host público para obtener URL ────────────
            image_url = await _upload_image(local_path)
            if not image_url:
                raise RuntimeError("No se pudo obtener URL pública de la imagen.")

            logger.info(f"🔗 URL pública: {image_url[:80]}")

            await status_msg.edit_text(
                "⏳ <b>Procesando imagen…</b>\n"
                "✨ Aplicando mejora con IA (upscale 4x)…\n"
                "<i>Esto puede tardar 10-30 segundos</i>",
                parse_mode=enums.ParseMode.HTML
            )

            # ── 3. Llamar a la API de upscale ─────────────────────────────────
            enhanced_bytes = await _upscale_image(image_url)
            if not enhanced_bytes:
                raise RuntimeError("La API no devolvió una imagen válida.")

            output_path.write_bytes(enhanced_bytes)
            out_size_kb = output_path.stat().st_size / 1024
            logger.info(f"✅ Imagen mejorada: {out_size_kb:.1f} KB")

            await status_msg.edit_text(
                "⏳ <b>Procesando imagen…</b>\n"
                "📤 Enviando imagen mejorada…",
                parse_mode=enums.ParseMode.HTML
            )

            # ── 4. Enviar resultado ────────────────────────────────────────────
            await message.reply_photo(
                photo=str(output_path),
                caption=(
                    "✅ <b>Imagen mejorada con IA</b>\n\n"
                    f"📥 Original: {size_kb:.1f} KB\n"
                    f"📤 Mejorada: {out_size_kb:.1f} KB\n"
                    "✨ Upscale 4x aplicado"
                ),
                parse_mode=enums.ParseMode.HTML
            )

            await status_msg.delete()
            logger.info("✅ Imagen mejorada enviada exitosamente")

        except Exception as e:
            logger.error(f"❌ Error en enhance: {e}", exc_info=True)
            await status_msg.edit_text(
                f"❌ <b>Error al mejorar la imagen</b>\n\n{str(e)[:200]}",
                parse_mode=enums.ParseMode.HTML
            )
        finally:
            local_path.unlink(missing_ok=True)
            output_path.unlink(missing_ok=True)


# ── Funciones auxiliares ───────────────────────────────────────────────────────

async def _upload_image(image_path: Path) -> str | None:
    """
    Sube la imagen a un host público y devuelve la URL directa.
    Intenta: tmpfiles.org → 0x0.st → file.io
    """
    import urllib.request

    uploaders = [
        _upload_tmpfiles,
        _upload_0x0,
        _upload_fileio,
    ]

    for uploader in uploaders:
        try:
            url = await uploader(image_path)
            if url and url.startswith('http'):
                return url
        except Exception as e:
            logger.warning(f"⚠️ Uploader {uploader.__name__} falló: {e}")
            continue

    return None


async def _upload_tmpfiles(path: Path) -> str | None:
    """Sube a tmpfiles.org — devuelve URL directa."""
    import json
    result = subprocess.run(
        ['curl', '-s', '-F', f'file=@{path}', 'https://tmpfiles.org/api/v1/upload'],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        return None
    data = json.loads(result.stdout)
    url  = data.get('data', {}).get('url', '')
    # Convertir URL de vista a URL directa
    return url.replace('tmpfiles.org/', 'tmpfiles.org/dl/') if url else None


async def _upload_0x0(path: Path) -> str | None:
    """Sube a 0x0.st — devuelve URL directa."""
    result = subprocess.run(
        ['curl', '-s', '-F', f'file=@{path}', 'https://0x0.st'],
        capture_output=True, text=True, timeout=30
    )
    url = result.stdout.strip()
    return url if url.startswith('http') else None


async def _upload_fileio(path: Path) -> str | None:
    """Sube a file.io — devuelve URL directa."""
    import json
    result = subprocess.run(
        ['curl', '-s', '-F', f'file=@{path}', 'https://file.io'],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        return None
    data = json.loads(result.stdout)
    return data.get('link') if data.get('success') else None


async def _upscale_image(image_url: str) -> bytes | None:
    """Llama a la API de APICausas para upscale 4x y devuelve los bytes."""
    import json

    endpoint = _ENDPOINT.format(apikey=_APIKEY, url=image_url)
    logger.info(f"🔌 Llamando API upscale: {endpoint[:80]}…")

    result = subprocess.run(
        ['curl', '-s', '-L', '--max-time', '60', '-o', '-', endpoint],
        capture_output=True, timeout=70
    )

    if result.returncode != 0 or not result.stdout:
        logger.error(f"❌ API upscale sin respuesta (código {result.returncode})")
        return None

    # Verificar que la respuesta sea imagen y no JSON de error
    raw = result.stdout
    if raw[:4] in (b'\xff\xd8\xff\xe0', b'\xff\xd8\xff\xe1',  # JPEG
                   b'\x89PNG', b'GIF8'):                        # PNG / GIF
        return raw

    # Puede ser JSON de error
    try:
        err = json.loads(raw.decode('utf-8', errors='ignore'))
        logger.error(f"❌ API upscale error: {err}")
    except Exception:
        logger.error(f"❌ Respuesta inesperada de API ({len(raw)} bytes)")

    return None
