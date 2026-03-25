"""
enhance_handler.py - Mejora de imagen con IA (upscale 4x)
Comandos: /enhance, /hd, /remini
Modos:
  1. Envía la foto con /hd como caption
  2. Responde a una foto con /hd
  3. Escribe /hd solo → activa modo espera → envía foto
"""

import asyncio
import json
import logging
import subprocess
from pathlib import Path
from pyrogram import filters, enums
from pyrogram.types import Message

logger = logging.getLogger(__name__)

_APIKEY   = "causa-0e3eacf90ab7be15"
_ENDPOINT = "https://rest.apicausas.xyz/api/v1/utilidades/upscale?apikey={apikey}&url={url}&type=4"
_VALID_MIME = {'image/jpeg', 'image/jpg', 'image/png'}


def register(app, user_states, work_dir):
    """Registra el handler de mejora de imagen."""

    # ── MODO 1 y 2: comando con foto adjunta o respondiendo a foto ────────────
    @app.on_message(filters.command(["enhance", "hd", "remini"]))
    async def enhance_command(client, message: Message):

        # Caso A: foto enviada con el comando como caption
        photo = message.photo
        doc   = message.document if (
            message.document and
            getattr(message.document, 'mime_type', '') in _VALID_MIME
        ) else None

        # Caso B: respondiendo a un mensaje con foto
        if not photo and not doc and message.reply_to_message:
            rep   = message.reply_to_message
            photo = rep.photo
            doc   = rep.document if (
                rep.document and
                getattr(rep.document, 'mime_type', '') in _VALID_MIME
            ) else None

        # Caso C: solo el comando, sin foto → activar modo espera
        if not photo and not doc:
            user_id = message.from_user.id
            user_states[user_id] = {'action': 'enhance', 'step': 'waiting_photo'}
            await message.reply_text(
                "🖼️ <b>Mejorador de Imagen con IA</b>\n\n"
                "Ahora envíame la imagen que quieres mejorar.\n"
                "✨ Aplicaré upscale 4x con IA.",
                parse_mode=enums.ParseMode.HTML
            )
            return

        await _process_enhance(message, photo or doc, work_dir)

    # ── MODO 3: foto enviada tras activar modo espera ─────────────────────────
    @app.on_message(filters.photo | filters.document)
    async def enhance_waiting(client, message: Message):
        user_id = message.from_user.id

        if user_id not in user_states:
            return
        state = user_states.get(user_id, {})
        if state.get('action') != 'enhance' or state.get('step') != 'waiting_photo':
            return

        media = message.photo or (
            message.document if getattr(message.document, 'mime_type', '') in _VALID_MIME
            else None
        )
        if not media:
            return

        del user_states[user_id]
        await _process_enhance(message, media, work_dir)


# ── Lógica principal ──────────────────────────────────────────────────────────

async def _process_enhance(message: Message, media, work_dir: Path):
    """Descarga, sube, llama a la API y responde con la imagen mejorada."""
    user_id  = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    logger.info(f"🖼️ Enhance solicitado por @{username}")

    status_msg = await message.reply_text(
        "⏳ <b>Procesando imagen…</b>\n⬇️ Descargando…",
        parse_mode=enums.ParseMode.HTML
    )

    local_path  = work_dir / f"{user_id}_enhance_in.jpg"
    output_path = work_dir / f"{user_id}_enhance_out.jpg"

    try:
        # 1. Descargar
        await message.download(file_name=str(local_path))
        size_kb = local_path.stat().st_size / 1024
        logger.info(f"✅ Descargada: {size_kb:.1f} KB")

        await status_msg.edit_text(
            "⏳ <b>Procesando imagen…</b>\n☁️ Subiendo para obtener URL…",
            parse_mode=enums.ParseMode.HTML
        )

        # 2. Subir a host público (en thread para no bloquear)
        image_url = await asyncio.to_thread(_upload_image_sync, local_path)
        if not image_url:
            raise RuntimeError("No se pudo obtener URL pública. Revisa conexión a internet.")

        logger.info(f"🔗 URL: {image_url}")

        await status_msg.edit_text(
            "⏳ <b>Procesando imagen…</b>\n✨ Aplicando upscale 4x con IA…\n"
            "<i>Puede tardar 15-30 segundos</i>",
            parse_mode=enums.ParseMode.HTML
        )

        # 3. Llamar API upscale (en thread)
        enhanced_bytes = await asyncio.to_thread(_upscale_sync, image_url)
        if not enhanced_bytes:
            raise RuntimeError("La API no devolvió imagen válida. Intenta con otra foto.")

        output_path.write_bytes(enhanced_bytes)
        out_size_kb = output_path.stat().st_size / 1024
        logger.info(f"✅ Imagen mejorada: {out_size_kb:.1f} KB")

        await status_msg.edit_text(
            "⏳ <b>Procesando imagen…</b>\n📤 Enviando resultado…",
            parse_mode=enums.ParseMode.HTML
        )

        # 4. Enviar
        await message.reply_photo(
            photo=str(output_path),
            caption=(
                "✅ <b>Imagen mejorada con IA</b>\n\n"
                f"📥 Original:  {size_kb:.1f} KB\n"
                f"📤 Mejorada: {out_size_kb:.1f} KB\n"
                "✨ Upscale 4x aplicado"
            ),
            parse_mode=enums.ParseMode.HTML
        )
        await status_msg.delete()
        logger.info("✅ Enviada exitosamente")

    except Exception as e:
        logger.error(f"❌ enhance error: {e}", exc_info=True)
        await status_msg.edit_text(
            f"❌ <b>Error al mejorar la imagen</b>\n\n{str(e)[:300]}",
            parse_mode=enums.ParseMode.HTML
        )
    finally:
        local_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)


# ── Funciones síncronas (se llaman desde asyncio.to_thread) ──────────────────

def _upload_image_sync(path: Path) -> str | None:
    """Intenta subir la imagen a hosts públicos en cascada."""
    for fn in [_try_tmpfiles, _try_0x0, _try_fileio]:
        try:
            url = fn(path)
            if url and url.startswith('http'):
                logger.info(f"✅ Subida exitosa con {fn.__name__}: {url}")
                return url
        except Exception as e:
            logger.warning(f"⚠️ {fn.__name__} falló: {e}")
    return None


def _try_tmpfiles(path: Path) -> str | None:
    r = subprocess.run(
        ['curl', '-s', '-F', f'file=@{path}', 'https://tmpfiles.org/api/v1/upload'],
        capture_output=True, text=True, timeout=30
    )
    if r.returncode != 0 or not r.stdout.strip():
        return None
    data = json.loads(r.stdout)
    url  = data.get('data', {}).get('url', '')
    return url.replace('tmpfiles.org/', 'tmpfiles.org/dl/') if url else None


def _try_0x0(path: Path) -> str | None:
    r = subprocess.run(
        ['curl', '-s', '-F', f'file=@{path}', 'https://0x0.st'],
        capture_output=True, text=True, timeout=30
    )
    url = r.stdout.strip()
    return url if url.startswith('http') else None


def _try_fileio(path: Path) -> str | None:
    r = subprocess.run(
        ['curl', '-s', '-F', f'file=@{path}', 'https://file.io'],
        capture_output=True, text=True, timeout=30
    )
    if r.returncode != 0 or not r.stdout.strip():
        return None
    data = json.loads(r.stdout)
    return data.get('link') if data.get('success') else None


def _upscale_sync(image_url: str) -> bytes | None:
    """Llama a la API de APICausas y devuelve bytes de imagen."""
    endpoint = _ENDPOINT.format(apikey=_APIKEY, url=image_url)
    logger.info(f"🔌 API upscale: {endpoint[:100]}")

    r = subprocess.run(
        ['curl', '-s', '-L', '--max-time', '90', '-o', '-', endpoint],
        capture_output=True, timeout=100
    )

    if r.returncode != 0 or not r.stdout:
        logger.error(f"❌ curl falló (código {r.returncode})")
        return None

    raw = r.stdout
    # Verificar magic bytes de imagen
    if (raw[:2] == b'\xff\xd8' or          # JPEG
        raw[:8] == b'\x89PNG\r\n\x1a\n'):  # PNG
        return raw

    # Loguear respuesta de error
    try:
        logger.error(f"❌ API error: {json.loads(raw.decode('utf-8', errors='ignore'))}")
    except Exception:
        logger.error(f"❌ Respuesta no es imagen ({len(raw)} bytes): {raw[:80]}")
    return None
