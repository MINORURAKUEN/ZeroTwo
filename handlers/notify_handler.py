"""
notify_handler.py - Notificaciones de episodios de anime en streaming
Fuente principal : LiveChart.me  (RSS /feeds/episodes)
Fuente de respaldo: AniList GraphQL (airingSchedules)

Comandos:
  /notify on          — Activar notificaciones en este chat
  /notify off         — Desactivar notificaciones
  /notify status      — Ver estado actual
  /notify add <anime> — Suscribirse a un anime específico
  /notify list        — Ver suscripciones
  /notify remove <n>  — Eliminar suscripción por número
  /notify now         — Forzar revisión manual ahora
"""

import asyncio
import json
import logging
import re
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from pyrogram import filters, enums
from pyrogram.types import Message

logger = logging.getLogger(__name__)

# ── Configuración ──────────────────────────────────────────────────────────────
CHECK_INTERVAL   = 600          # segundos entre revisiones (10 min)
LIVECHART_RSS    = "https://www.livechart.me/feeds/episodes"
ANILIST_API      = "https://graphql.anilist.co"
DATA_FILE        = Path(__file__).parent.parent / "notify_data.json"

# Servicios de streaming con emoji
SERVICES = {
    'crunchyroll': '🟠 Crunchyroll',
    'funimation':  '🟣 Funimation',
    'hidive':      '🔵 HIDIVE',
    'netflix':     '🔴 Netflix',
    'amazon':      '🟡 Prime Video',
    'disney':      '🔵 Disney+',
    'youtube':     '🔴 YouTube',
    'bilibili':    '🩵 Bilibili',
}


# ── Persistencia ───────────────────────────────────────────────────────────────

def _load_data() -> dict:
    """Carga la configuración de notificaciones desde disco."""
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text())
        except Exception:
            pass
    return {}   # { chat_id: { "active": bool, "subs": ["anime1", ...], "seen": ["ep_id1", ...] } }


def _save_data(data: dict):
    """Guarda la configuración en disco."""
    try:
        DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    except Exception as e:
        logger.error(f"❌ Error guardando notify_data: {e}")


def _get_chat(data: dict, chat_id: int) -> dict:
    """Devuelve o crea el registro de un chat."""
    key = str(chat_id)
    if key not in data:
        data[key] = {"active": False, "subs": [], "seen": []}
    return data[key]


# ── Scraping LiveChart.me ──────────────────────────────────────────────────────

def _fetch_livechart() -> list[dict]:
    """
    Descarga y parsea el RSS de LiveChart.me.
    Devuelve lista de episodios: {id, title, anime, episode, service, link, image, aired_at}
    """
    try:
        r = subprocess.run(
            ['curl', '-sL', '--max-time', '20',
             '-A', 'Mozilla/5.0 (compatible; RikkaBot/1.0)',
             LIVECHART_RSS],
            capture_output=True, timeout=25
        )
        if r.returncode != 0 or not r.stdout:
            return []

        xml_text = r.stdout.decode('utf-8', errors='replace')
        root = ET.fromstring(xml_text)

        # Namespaces usados por LiveChart
        ns = {
            'lc':    'https://www.livechart.me',
            'media': 'http://search.yahoo.com/mrss/',
        }

        episodes = []
        channel  = root.find('channel')
        if channel is None:
            return []

        for item in channel.findall('item'):
            def _t(tag, default=''):
                el = item.find(tag)
                return el.text.strip() if el is not None and el.text else default

            def _ns(prefix, tag, default=''):
                el = item.find(f'{prefix}:{tag}', ns)
                return el.text.strip() if el is not None and el.text else default

            title    = _t('title')
            link     = _t('link')
            pub_date = _t('pubDate')
            ep_num   = _ns('lc', 'episode', '?')
            service  = _ns('lc', 'service', '').lower()
            anime_title = _ns('lc', 'anime', title.split(' - ')[0] if ' - ' in title else title)

            # Imagen: media:thumbnail o enclosure
            image = ''
            mt = item.find('media:thumbnail', ns)
            if mt is not None:
                image = mt.get('url', '')
            if not image:
                enc = item.find('enclosure')
                if enc is not None:
                    image = enc.get('url', '')

            # ID único del episodio
            guid = _t('guid') or f"{anime_title}-{ep_num}-{pub_date}"

            # Parsear fecha
            aired_at = ''
            try:
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(pub_date)
                aired_at = dt.strftime('%d/%m/%Y %H:%M UTC')
            except Exception:
                aired_at = pub_date

            episodes.append({
                'id':       guid,
                'title':    title,
                'anime':    anime_title,
                'episode':  ep_num,
                'service':  service,
                'link':     link,
                'image':    image,
                'aired_at': aired_at,
            })

        logger.info(f"📡 LiveChart: {len(episodes)} episodios obtenidos")
        return episodes

    except Exception as e:
        logger.warning(f"⚠️ LiveChart scraping falló: {e}")
        return []


# ── Fallback: AniList ──────────────────────────────────────────────────────────

def _fetch_anilist_airing() -> list[dict]:
    """
    Fallback: obtiene episodios recién emitidos (última hora) desde AniList.
    """
    try:
        import time
        now       = int(time.time())
        one_hour  = now - 3600

        query = """
        query($from: Int, $to: Int) {
          Page(page: 1, perPage: 30) {
            airingSchedules(airingAt_greater: $from, airingAt_lesser: $to) {
              id
              airingAt
              episode
              media {
                title { romaji english }
                coverImage { medium }
                siteUrl
                externalLinks { site url }
              }
            }
          }
        }
        """
        payload = json.dumps({
            'query': query,
            'variables': {'from': one_hour, 'to': now}
        })

        r = subprocess.run(
            ['curl', '-s', '--max-time', '15',
             '-X', 'POST', ANILIST_API,
             '-H', 'Content-Type: application/json',
             '-d', payload],
            capture_output=True, text=True, timeout=20
        )
        if r.returncode != 0 or not r.stdout:
            return []

        data      = json.loads(r.stdout)
        schedules = data.get('data', {}).get('Page', {}).get('airingSchedules', [])
        episodes  = []

        for s in schedules:
            media   = s.get('media', {})
            title   = (media.get('title') or {})
            anime   = title.get('romaji') or title.get('english') or 'Desconocido'
            ep_num  = str(s.get('episode', '?'))
            link    = media.get('siteUrl', '')
            image   = (media.get('coverImage') or {}).get('medium', '')
            aired_ts = s.get('airingAt', 0)

            # Detectar servicio desde externalLinks
            service = ''
            for ext in media.get('externalLinks') or []:
                site = (ext.get('site') or '').lower()
                if site in SERVICES:
                    service = site
                    break

            aired_at = datetime.fromtimestamp(aired_ts, tz=timezone.utc).strftime('%d/%m/%Y %H:%M UTC') if aired_ts else ''

            episodes.append({
                'id':       f"al-{s['id']}",
                'title':    f"{anime} - Episodio {ep_num}",
                'anime':    anime,
                'episode':  ep_num,
                'service':  service,
                'link':     link,
                'image':    image,
                'aired_at': aired_at,
            })

        logger.info(f"📡 AniList fallback: {len(episodes)} episodios")
        return episodes

    except Exception as e:
        logger.warning(f"⚠️ AniList fallback falló: {e}")
        return []


# ── Formateo de notificación ───────────────────────────────────────────────────

def _format_episode(ep: dict) -> str:
    """Formatea un episodio como mensaje HTML."""
    service_raw  = ep.get('service', '').lower()
    service_name = SERVICES.get(service_raw, f'📺 {service_raw.title()}' if service_raw else '📺 Streaming')
    link         = ep.get('link', '')
    link_text    = f'\n<b>🔗 Ver:</b> <a href="{link}">{service_name}</a>' if link else f'\n<b>📺 Servicio:</b> {service_name}'

    return (
        f"🎌 <b>Nuevo episodio disponible</b>\n\n"
        f"<b>📺 Anime:</b> {ep.get('anime', '?')}\n"
        f"<b>🎬 Episodio:</b> {ep.get('episode', '?')}\n"
        f"<b>🕐 Emitido:</b> {ep.get('aired_at', '?')}"
        f"{link_text}"
    )


# ── Tarea de revisión en background ───────────────────────────────────────────

async def _check_and_notify(app, data: dict):
    """Revisa nuevos episodios y notifica a los chats suscritos."""
    episodes = await asyncio.to_thread(_fetch_livechart)
    if not episodes:
        logger.info("⚠️ LiveChart vacío, usando AniList...")
        episodes = await asyncio.to_thread(_fetch_anilist_airing)

    if not episodes:
        logger.info("ℹ️ Sin episodios nuevos en esta revisión")
        return

    notified = 0

    for chat_id_str, cfg in list(data.items()):
        if not cfg.get('active'):
            continue

        chat_id  = int(chat_id_str)
        subs     = [s.lower() for s in cfg.get('subs', [])]
        seen     = cfg.get('seen', [])

        for ep in episodes:
            ep_id     = ep['id']
            anime_low = ep.get('anime', '').lower()

            # Filtrar por suscripciones si hay alguna
            if subs and not any(s in anime_low for s in subs):
                continue

            # Evitar duplicados
            if ep_id in seen:
                continue

            # Marcar como visto
            seen.append(ep_id)
            if len(seen) > 500:          # limpiar cache antiguo
                seen = seen[-300:]
            cfg['seen'] = seen

            # Enviar notificación
            try:
                text  = _format_episode(ep)
                image = ep.get('image', '')

                if image:
                    await app.send_photo(
                        chat_id=chat_id,
                        photo=image,
                        caption=text,
                        parse_mode=enums.ParseMode.HTML
                    )
                else:
                    await app.send_message(
                        chat_id=chat_id,
                        text=text,
                        parse_mode=enums.ParseMode.HTML,
                        disable_web_page_preview=False
                    )
                notified += 1
                await asyncio.sleep(0.5)   # flood control

            except Exception as e:
                logger.error(f"❌ Error notificando a {chat_id}: {e}")

    _save_data(data)
    if notified:
        logger.info(f"🔔 {notified} notificaciones enviadas")


async def _background_loop(app, data: dict):
    """Bucle infinito que revisa cada CHECK_INTERVAL segundos."""
    logger.info(f"🔔 Sistema de notificaciones iniciado (cada {CHECK_INTERVAL//60} min)")
    while True:
        try:
            await _check_and_notify(app, data)
        except Exception as e:
            logger.error(f"❌ Error en bucle de notificaciones: {e}", exc_info=True)
        await asyncio.sleep(CHECK_INTERVAL)


# ── Registro del handler ───────────────────────────────────────────────────────

def register(app):
    """Registra comandos y lanza el bucle de notificaciones."""

    data = _load_data()

    # Lanzar bucle en background cuando el bot esté listo
    @app.on_message(filters.command("start") & filters.private, group=-1)
    async def _launch_loop_once(client, message: Message):
        pass   # el loop se lanza en el startup hook (ver abajo)

    # ── /notify ───────────────────────────────────────────────────────────────
    @app.on_message(filters.command("notify"))
    async def notify_command(client, message: Message):
        chat_id = message.chat.id
        args    = message.text.split(maxsplit=2)
        sub_cmd = args[1].lower() if len(args) > 1 else ''
        param   = args[2].strip() if len(args) > 2 else ''

        cfg = _get_chat(data, chat_id)

        # ── /notify on ────────────────────────────────────────────────────────
        if sub_cmd == 'on':
            cfg['active'] = True
            _save_data(data)
            subs_info = (
                f"\n<b>📋 Suscripciones:</b> {', '.join(cfg['subs'])}" if cfg['subs']
                else "\n<i>Sin filtros — recibirás todos los estrenos</i>"
            )
            await message.reply_text(
                f"🔔 <b>Notificaciones activadas</b>\n"
                f"<b>📡 Fuente:</b> LiveChart.me\n"
                f"<b>⏱ Revisión:</b> cada {CHECK_INTERVAL//60} minutos"
                f"{subs_info}",
                parse_mode=enums.ParseMode.HTML
            )

        # ── /notify off ───────────────────────────────────────────────────────
        elif sub_cmd == 'off':
            cfg['active'] = False
            _save_data(data)
            await message.reply_text("🔕 <b>Notificaciones desactivadas</b>", parse_mode=enums.ParseMode.HTML)

        # ── /notify status ────────────────────────────────────────────────────
        elif sub_cmd == 'status':
            estado  = "🟢 Activas" if cfg['active'] else "🔴 Desactivadas"
            subs    = cfg.get('subs', [])
            filtros = ', '.join(subs) if subs else 'Todos los animes'
            visto   = len(cfg.get('seen', []))
            await message.reply_text(
                f"📊 <b>Estado de Notificaciones</b>\n\n"
                f"<b>Estado:</b> {estado}\n"
                f"<b>📋 Filtros:</b> {filtros}\n"
                f"<b>📌 Episodios vistos:</b> {visto}\n"
                f"<b>⏱ Intervalo:</b> {CHECK_INTERVAL//60} min\n"
                f"<b>📡 Fuente:</b> LiveChart.me",
                parse_mode=enums.ParseMode.HTML
            )

        # ── /notify add <anime> ───────────────────────────────────────────────
        elif sub_cmd == 'add':
            if not param:
                await message.reply_text(
                    "❌ Indica el nombre del anime.\n"
                    "Ejemplo: <code>/notify add Berserk</code>",
                    parse_mode=enums.ParseMode.HTML
                )
                return
            subs = cfg.setdefault('subs', [])
            if param.lower() not in [s.lower() for s in subs]:
                subs.append(param)
                _save_data(data)
                await message.reply_text(
                    f"✅ <b>Suscrito a:</b> {param}\n\n"
                    f"<b>📋 Lista actual:</b>\n" +
                    '\n'.join(f"  {i+1}. {s}" for i, s in enumerate(subs)),
                    parse_mode=enums.ParseMode.HTML
                )
            else:
                await message.reply_text(f"ℹ️ Ya estás suscrito a <b>{param}</b>", parse_mode=enums.ParseMode.HTML)

        # ── /notify list ──────────────────────────────────────────────────────
        elif sub_cmd == 'list':
            subs = cfg.get('subs', [])
            if subs:
                lista = '\n'.join(f"  <b>{i+1}.</b> {s}" for i, s in enumerate(subs))
                await message.reply_text(
                    f"📋 <b>Tus suscripciones ({len(subs)}):</b>\n\n{lista}\n\n"
                    f"<i>Usa /notify remove &lt;número&gt; para eliminar</i>",
                    parse_mode=enums.ParseMode.HTML
                )
            else:
                await message.reply_text(
                    "📋 <b>Sin suscripciones específicas</b>\n"
                    "<i>Recibirás notificaciones de todos los animes en streaming.</i>\n\n"
                    "Usa <code>/notify add Nombre</code> para filtrar.",
                    parse_mode=enums.ParseMode.HTML
                )

        # ── /notify remove <n> ────────────────────────────────────────────────
        elif sub_cmd == 'remove':
            subs = cfg.get('subs', [])
            try:
                idx = int(param) - 1
                removed = subs.pop(idx)
                _save_data(data)
                await message.reply_text(
                    f"🗑️ <b>Eliminado:</b> {removed}",
                    parse_mode=enums.ParseMode.HTML
                )
            except (ValueError, IndexError):
                await message.reply_text(
                    "❌ Número inválido.\nUsa <code>/notify list</code> para ver los números.",
                    parse_mode=enums.ParseMode.HTML
                )

        # ── /notify now ───────────────────────────────────────────────────────
        elif sub_cmd == 'now':
            await message.reply_text("🔄 <b>Revisando ahora…</b>", parse_mode=enums.ParseMode.HTML)
            await _check_and_notify(app, data)
            await message.reply_text("✅ <b>Revisión completada</b>", parse_mode=enums.ParseMode.HTML)

        # ── Sin argumentos → ayuda ────────────────────────────────────────────
        else:
            await message.reply_text(
                "🔔 <b>Notificaciones de Anime Streaming</b>\n\n"
                "<b>Comandos:</b>\n"
                "<code>/notify on</code>         — Activar notificaciones\n"
                "<code>/notify off</code>        — Desactivar\n"
                "<code>/notify status</code>     — Ver estado\n"
                "<code>/notify add &lt;anime&gt;</code>  — Suscribirse a un anime\n"
                "<code>/notify list</code>       — Ver suscripciones\n"
                "<code>/notify remove &lt;n&gt;</code>   — Eliminar suscripción\n"
                "<code>/notify now</code>        — Revisar ahora mismo\n\n"
                "<b>📡 Fuente:</b> LiveChart.me\n"
                "<b>⏱ Intervalo:</b> cada 10 minutos\n\n"
                "<i>Sin filtros: recibes todos los estrenos.\n"
                "Con /notify add: solo los que elijas.</i>",
                parse_mode=enums.ParseMode.HTML
            )

    # ── Iniciar loop al arrancar el bot ───────────────────────────────────────
    @app.on_message(filters.all, group=-999)
    async def _ensure_loop(client, message: Message):
        """Arranca el loop de notificaciones la primera vez que llega cualquier mensaje."""
        if not hasattr(app, '_notify_loop_started'):
            app._notify_loop_started = True
            asyncio.create_task(_background_loop(app, data))
            logger.info("🔔 Loop de notificaciones iniciado")
