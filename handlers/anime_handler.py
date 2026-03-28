"""
anime_handler.py - Manejador del comando /anime
"""

import json
import re
import logging
import subprocess
from pathlib import Path
from pyrogram import filters, enums
from pyrogram.types import Message

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Helpers de red
# ─────────────────────────────────────────────

def _curl_get(url: str, timeout: int = 15) -> str | None:
    """GET simple con curl, devuelve stdout o None."""
    cmd = [
        'curl', '-s', '-L',
        '-A', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/122.0 Safari/537.36',
        '--max-time', str(timeout),
        '-H', 'Accept-Language: es,en;q=0.9',
        url
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
        return r.stdout if r.returncode == 0 else None
    except Exception as e:
        logger.warning(f"curl GET falló ({url}): {e}")
        return None


def _curl_post_json(url: str, payload: dict, timeout: int = 15) -> str | None:
    """POST JSON con curl, devuelve stdout o None."""
    cmd = [
        'curl', '-s', '-X', 'POST', url,
        '-H', 'Content-Type: application/json',
        '-H', 'Accept: application/json',
        '--max-time', str(timeout),
        '-d', json.dumps(payload)
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
        return r.stdout if r.returncode == 0 else None
    except Exception as e:
        logger.warning(f"curl POST falló ({url}): {e}")
        return None


def _clean_html(text: str) -> str:
    """Elimina etiquetas HTML y decodifica entidades básicas."""
    text = re.sub(r'<[^>]+>', '', text)
    text = (text.replace('&#39;', "'").replace('&amp;', '&')
                .replace('&quot;', '"').replace('&lt;', '<')
                .replace('&gt;', '>').replace('&nbsp;', ' '))
    return text.strip()


# ─────────────────────────────────────────────
# Sinopsis — fuentes en cascada
# ─────────────────────────────────────────────

def _synopsis_from_animeplanet(title: str) -> str | None:
    """
    Busca en Anime-Planet y extrae la sinopsis del cuerpo de la página.
    El <meta description> es genérico del sitio, así que buscamos en el HTML.
    """
    slug_query = title.replace(' ', '+')
    search_url = f"https://www.anime-planet.com/anime/all?name={slug_query}"
    html = _curl_get(search_url, timeout=15)
    if not html:
        return None

    # Primer enlace de resultado de tipo /anime/<slug> (no /manga/)
    match = re.search(r'href="(/anime/[a-z0-9][a-z0-9\-]+)"', html)
    if not match:
        logger.info("Anime-Planet: no se encontró enlace de resultado")
        return None

    anime_url = f"https://www.anime-planet.com{match.group(1)}"
    logger.info(f"Anime-Planet URL: {anime_url}")

    anime_html = _curl_get(anime_url, timeout=15)
    if not anime_html:
        return None

    # ── Selector 1: <div class="entrySynopsis"> ──
    m = re.search(r'class=["\'][^"\']*entrySynopsis[^"\']*["\'][^>]*>(.*?)</div>',
                  anime_html, re.DOTALL | re.IGNORECASE)
    if m:
        text = _clean_html(m.group(1))
        if len(text) > 30:
            return text

    # ── Selector 2: <p itemprop="description"> ──
    m = re.search(r'<p[^>]+itemprop=["\']description["\'][^>]*>(.*?)</p>',
                  anime_html, re.DOTALL | re.IGNORECASE)
    if m:
        text = _clean_html(m.group(1))
        if len(text) > 30:
            return text

    # ── Selector 3: bloque "synopsis" genérico ──
    m = re.search(r'id=["\']synopsis["\'][^>]*>.*?<p[^>]*>(.*?)</p>',
                  anime_html, re.DOTALL | re.IGNORECASE)
    if m:
        text = _clean_html(m.group(1))
        if len(text) > 30:
            return text

    logger.info("Anime-Planet: página encontrada pero no se extrajo sinopsis")
    return None


def _synopsis_from_livechart(title: str) -> str | None:
    """Busca en LiveChart.me y extrae la sinopsis."""
    encoded = title.replace(' ', '+')
    search_url = f"https://www.livechart.me/search?q={encoded}"
    html = _curl_get(search_url, timeout=15)
    if not html:
        return None

    # Primer enlace /anime/<id>
    m = re.search(r'href="(/anime/\d+)"', html)
    if not m:
        return None

    anime_url = f"https://www.livechart.me{m.group(1)}"
    anime_html = _curl_get(anime_url, timeout=15)
    if not anime_html:
        return None

    # Bloque de sinopsis en LiveChart
    m = re.search(r'class=["\'][^"\']*synopsis[^"\']*["\'][^>]*>(.*?)</(?:p|div|section)>',
                  anime_html, re.DOTALL | re.IGNORECASE)
    if m:
        text = _clean_html(m.group(1))
        if len(text) > 30:
            return text
    return None


def _synopsis_from_animeschedule(title: str) -> str | None:
    """Busca en AnimeSchedule.net y extrae la sinopsis."""
    # AnimeSchedule tiene una API JSON pública
    encoded = title.replace(' ', '%20')
    api_url = f"https://animeschedule.net/api/v3/anime?q={encoded}&limit=1"
    raw = _curl_get(api_url, timeout=15)
    if not raw:
        return None
    try:
        data = json.loads(raw)
        items = data.get('anime') or data  # puede ser lista directa
        if isinstance(items, list) and items:
            synopsis = items[0].get('synopsis') or items[0].get('description')
            if synopsis and len(synopsis) > 30:
                return _clean_html(synopsis)
    except Exception:
        pass
    return None


def _get_synopsis(title: str, anilist_description: str | None) -> tuple[str, str]:
    """
    Intenta obtener sinopsis en cascada:
      1. Anime-Planet
      2. LiveChart
      3. AnimeSchedule
      4. AniList (fallback)
    Devuelve (sinopsis_en_ingles, nombre_fuente).
    """
    logger.info("Intentando sinopsis desde Anime-Planet...")
    text = _synopsis_from_animeplanet(title)
    if text:
        return text, "Anime-Planet"

    logger.info("Intentando sinopsis desde LiveChart...")
    text = _synopsis_from_livechart(title)
    if text:
        return text, "LiveChart"

    logger.info("Intentando sinopsis desde AnimeSchedule...")
    text = _synopsis_from_animeschedule(title)
    if text:
        return text, "AnimeSchedule"

    # Fallback: AniList
    if anilist_description and anilist_description != 'No disponible':
        text = _clean_html(anilist_description)
        return text, "AniList"

    return "No disponible", ""


# ─────────────────────────────────────────────
# Traducción
# ─────────────────────────────────────────────

def _translate_to_spanish(text: str) -> str:
    """Traduce al español vía MyMemory. Devuelve el original si falla."""
    snippet = text[:500]
    cmd = [
        'curl', '-s', '-G',
        'https://api.mymemory.translated.net/get',
        '--data-urlencode', f'q={snippet}',
        '--data-urlencode', 'langpair=en|es',
        '--max-time', '10'
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if r.returncode == 0:
            data = json.loads(r.stdout)
            if data.get('responseStatus') == 200:
                return data['responseData']['translatedText']
    except Exception:
        pass
    return text


# ─────────────────────────────────────────────
# Detección de Doblaje Latino
# ─────────────────────────────────────────────

_LAT_DUB_SITES = [
    'animeflv.net', 'jkanime.net', 'latanime.me',
    'mundodoblajes.com', 'animeid.tv', 'tioanime.com',
    'crunchyroll.com', 'funimation.com', 'netflix.com',
]

_LAT_DUB_KEYWORDS = [
    'doblaje latino', 'dub latino', 'latino dub',
    'español latino', 'audio latino', 'doblado al español',
    'latin dub', 'spanish dub', 'doblado',
]


def _check_latin_dub(title: str) -> tuple[str, str]:
    """
    Detecta si el anime tiene doblaje latino.
    Devuelve (estado_emoji_texto, fuente).
    """
    encoded = '+'.join(title.split())

    # ── 1) DuckDuckGo HTML ──
    ddg_url = f"https://html.duckduckgo.com/html/?q={encoded}+doblaje+latino+anime"
    ddg_html = _curl_get(ddg_url, timeout=15)
    if ddg_html:
        combined = ddg_html.lower()
        found_site = next((s for s in _LAT_DUB_SITES if s in combined), '')
        found_keyword = any(kw in combined for kw in _LAT_DUB_KEYWORDS)
        if found_keyword and found_site:
            if any(w in combined for w in ['disponible', 'ya disponible', 'ver ahora', 'puedes ver']):
                return '✅ Disponible', found_site
            elif any(w in combined for w in ['anunciado', 'próximamente', 'soon', 'confirmado', 'confirmed']):
                return '📢 Anunciado', found_site
            else:
                return '✅ Disponible', found_site
        elif found_keyword:
            return '📢 Anunciado', 'varios sitios'

    # ── 2) Crunchyroll ──
    cr_url = f"https://www.crunchyroll.com/search?q={encoded}"
    cr_html = _curl_get(cr_url, timeout=15)
    if cr_html and 'español (latino)' in cr_html.lower():
        return '✅ Disponible', 'Crunchyroll'

    # ── 3) AnimeFlv ──
    flv_url = f"https://www3.animeflv.net/browse?q={encoded}"
    flv_html = _curl_get(flv_url, timeout=15)
    if flv_html:
        lower = flv_html.lower()
        if 'latino' in lower or 'doblado' in lower:
            return '✅ Disponible', 'AnimeFlv'

    return '❌ No confirmado', ''


# ─────────────────────────────────────────────
# Formateo de campos que pueden ser None
# ─────────────────────────────────────────────

def _fmt(value, suffix: str = '', fallback: str = 'N/A') -> str:
    """Formatea un valor que puede ser None."""
    if value is None or value == 'None':
        return fallback
    return f"{value}{suffix}"


# ─────────────────────────────────────────────
# Registro del handler
# ─────────────────────────────────────────────

def register(app, user_states, work_dir):
    """Registra el handler del comando /anime"""

    @app.on_message(filters.command("anime"))
    async def anime_command(client, message: Message):
        """Comando /anime - Busca información de anime"""

        args = message.text.split(maxsplit=1)

        if len(args) < 2:
            await message.reply_text(
                "🈺 <b>Búsqueda de Anime</b>\n\n"
                "Por favor ingresa el nombre del anime:\n"
                "<code>/anime Nombre del anime</code>\n\n"
                "Ejemplo:\n"
                "<code>/anime One Piece</code>",
                parse_mode=enums.ParseMode.HTML
            )
            return

        anime_name = args[1]
        logger.info(f"🈺 Buscando anime: {anime_name}")
        status_msg = await message.reply_text("⏳ Buscando información del anime...")

        try:
            # ── AniList: metadata principal ──
            query = """
            query ($search: String) {
                Media (search: $search, type: ANIME) {
                    id
                    title { romaji english native }
                    studios(isMain: true) { nodes { name } }
                    seasonYear
                    episodes
                    genres
                    duration
                    format
                    season
                    status
                    description
                    bannerImage
                    coverImage { extraLarge large medium }
                }
            }
            """

            raw = _curl_post_json(
                'https://graphql.anilist.co',
                {'query': query, 'variables': {'search': anime_name}},
                timeout=15
            )

            if not raw:
                await status_msg.edit_text("❌ Error al contactar AniList. Intenta de nuevo.")
                return

            data = json.loads(raw)

            if not data.get('data') or not data['data'].get('Media'):
                await status_msg.edit_text(
                    f"❌ No se encontró el anime: <b>{anime_name}</b>",
                    parse_mode=enums.ParseMode.HTML
                )
                return

            anime = data['data']['Media']

            # ── Traducciones de campos ──
            ESTADOS = {
                'FINISHED': 'Finalizado', 'RELEASING': 'En emisión',
                'NOT_YET_RELEASED': 'Próximamente', 'CANCELLED': 'Cancelado', 'HIATUS': 'En pausa'
            }
            TEMPORADAS = {
                'WINTER': 'Invierno', 'SPRING': 'Primavera',
                'SUMMER': 'Verano', 'FALL': 'Otoño'
            }
            FORMATOS = {
                'TV': 'Serie de TV', 'MOVIE': 'Película', 'SPECIAL': 'Especial',
                'OVA': 'OVA', 'ONA': 'ONA', 'MUSIC': 'Musical', 'TV_SHORT': 'Serie Corta'
            }
            GENEROS_TRAD = {
                'Action': 'Acción', 'Adventure': 'Aventura', 'Comedy': 'Comedia',
                'Drama': 'Drama', 'Ecchi': 'Ecchi', 'Fantasy': 'Fantasía',
                'Horror': 'Terror', 'Mahou Shoujo': 'Magical Girls', 'Mecha': 'Mecha',
                'Music': 'Música', 'Mystery': 'Misterio', 'Psychological': 'Psicológico',
                'Romance': 'Romance', 'Sci-Fi': 'Ciencia Ficción',
                'Slice of Life': 'Recuentos de la vida', 'Sports': 'Deportes',
                'Supernatural': 'Sobrenatural', 'Thriller': 'Suspenso'
            }

            # ── Títulos ──
            titulo = (anime['title']['romaji']
                      or anime['title']['english']
                      or anime['title']['native'])
            titulo_ingles = anime['title'].get('english', '')
            titulo_nativo = anime['title'].get('native', '')

            estudios = (', '.join([s['name'] for s in anime['studios']['nodes']])
                        if anime['studios']['nodes'] else 'Desconocido')
            generos = (', '.join([GENEROS_TRAD.get(g, g) for g in anime['genres']])
                       if anime['genres'] else 'N/A')

            # Episodios y duración — evitar "None"
            episodios = _fmt(anime.get('episodes'), fallback='En emisión')
            duracion = _fmt(anime.get('duration'), suffix=' min', fallback='N/A')

            # ── Sinopsis: cascada multi-fuente ──
            await status_msg.edit_text("⏳ Obteniendo sinopsis...")
            anilist_desc = anime.get('description', '')
            sinopsis_raw, sinopsis_fuente = _get_synopsis(titulo, anilist_desc)

            if sinopsis_raw != 'No disponible':
                sinopsis = _translate_to_spanish(sinopsis_raw)
            else:
                sinopsis = 'No disponible'

            # ── Doblaje Latino ──
            await status_msg.edit_text("⏳ Verificando doblaje latino...")
            dub_estado, dub_fuente = _check_latin_dub(titulo)
            dub_linea = dub_estado
            if dub_fuente:
                dub_linea += f" <i>({dub_fuente})</i>"

            # ── Bloque títulos alternativos ──
            titulo_bloque = ""
            if titulo_ingles and titulo_ingles != titulo:
                titulo_bloque += f"\n<b>🔤 Título inglés:</b> <b>{titulo_ingles}</b>"
            if titulo_nativo and titulo_nativo != titulo:
                titulo_bloque += f"\n<b>🈯 Título nativo:</b> <b>{titulo_nativo}</b>"

            # Etiqueta de fuente de sinopsis
            fuente_tag = f" <i>(vía {sinopsis_fuente})</i>" if sinopsis_fuente else ""

            # ── Mensaje final ──
            info = (
                f"<b>✨ INFORMACIÓN DEL ANIME ✨</b>\n\n"
                f"<b>🈺 Título:</b> <b>{titulo}</b>"
                f"{titulo_bloque}\n"
                f"<b>🏦 Estudio:</b> <b>{estudios}</b>\n"
                f"<b>📆 Año:</b> <b>{_fmt(anime.get('seasonYear'))}</b>\n"
                f"<b>🗂 Episodios:</b> <b>{episodios}</b>\n"
                f"<b>🏷 Géneros:</b> <b>{generos}</b>\n"
                f"<b>⏱ Duración:</b> <b>{duracion}</b>\n"
                f"<b>💽 Formato:</b> <b>{FORMATOS.get(anime.get('format'), anime.get('format', 'N/A'))}</b>\n"
                f"<b>🔅 Temporada:</b> <b>{TEMPORADAS.get(anime.get('season'), 'N/A')}</b>\n"
                f"<b>⏳ Estado:</b> <b>{ESTADOS.get(anime.get('status'), anime.get('status', 'N/A'))}</b>\n"
                f"<b>🎙 Doblaje Latino:</b> {dub_linea}\n\n"
                f"<b>📜 Sinopsis{fuente_tag}:</b>\n"
                f"<blockquote><b>{sinopsis}</b></blockquote>"
            )

            # ── Portada ──
            image_url = (anime['coverImage'].get('extraLarge')
                         or anime.get('bannerImage')
                         or anime['coverImage'].get('large'))

            if image_url:
                img_result = subprocess.run(
                    ['curl', '-s', '-L', '--max-time', '30', image_url],
                    capture_output=True, timeout=35
                )
                if img_result.returncode == 0 and len(img_result.stdout) > 0:
                    temp_img = work_dir / f"anime_{message.from_user.id}.jpg"
                    temp_img.write_bytes(img_result.stdout)

                    if len(info) > 1024:
                        await message.reply_photo(photo=str(temp_img))
                        await message.reply_text(info, parse_mode=enums.ParseMode.HTML)
                    else:
                        await message.reply_photo(
                            photo=str(temp_img),
                            caption=info,
                            parse_mode=enums.ParseMode.HTML
                        )

                    await status_msg.delete()
                    temp_img.unlink(missing_ok=True)
                    return

            # Sin imagen
            await status_msg.edit_text(info, parse_mode=enums.ParseMode.HTML)

        except Exception as e:
            logger.error(f"❌ Error en anime_command: {e}")
            await status_msg.edit_text(
                f"❌ <b>Error</b>\n\n{str(e)[:100]}",
                parse_mode=enums.ParseMode.HTML
            )

