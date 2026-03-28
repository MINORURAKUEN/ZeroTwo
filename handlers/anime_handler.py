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

def _curl_get(url: str, timeout: int = 15, extra_args: list = None) -> str | None:
    """GET simple con curl, devuelve stdout o None."""
    cmd = ['curl', '-s', '-L',
           '-A', 'Mozilla/5.0 (compatible; ZeroTwoBot/1.0)',
           '--max-time', str(timeout),
           url]
    if extra_args:
        cmd += extra_args
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


# ─────────────────────────────────────────────
# Sinopsis desde Anime-Planet
# ─────────────────────────────────────────────

def _get_animeplanet_synopsis(title: str) -> str | None:
    """
    Busca el anime en Anime-Planet y extrae la sinopsis.
    Devuelve el texto en inglés (sin HTML) o None.
    """
    # 1) Búsqueda en Anime-Planet
    slug_query = title.replace(' ', '+')
    search_url = f"https://www.anime-planet.com/anime/all?name={slug_query}"
    html = _curl_get(search_url, timeout=15)
    if not html:
        return None

    # Extraer primer enlace de resultado: /anime/<slug>
    match = re.search(r'href="(/anime/[a-z0-9\-]+)"', html)
    if not match:
        return None

    anime_path = match.group(1)
    anime_url = f"https://www.anime-planet.com{anime_path}"

    # 2) Página del anime
    anime_html = _curl_get(anime_url, timeout=15)
    if not anime_html:
        return None

    # Extraer sinopsis: <meta itemprop="description" content="...">
    meta_match = re.search(
        r'<meta\s+itemprop=["\']description["\']\s+content=["\'](.*?)["\']',
        anime_html, re.DOTALL
    )
    if meta_match:
        synopsis = meta_match.group(1).strip()
        synopsis = re.sub(r'<[^>]+>', '', synopsis)
        synopsis = synopsis.replace('&#39;', "'").replace('&amp;', '&').replace('&quot;', '"').replace('&lt;', '<').replace('&gt;', '>')
        return synopsis if len(synopsis) > 20 else None

    # Fallback: <div itemprop="description">
    div_match = re.search(
        r'<div[^>]+itemprop=["\']description["\'][^>]*>(.*?)</div>',
        anime_html, re.DOTALL
    )
    if div_match:
        synopsis = re.sub(r'<[^>]+>', '', div_match.group(1)).strip()
        return synopsis if len(synopsis) > 20 else None

    return None


# ─────────────────────────────────────────────
# Traducción de sinopsis
# ─────────────────────────────────────────────

def _translate_to_spanish(text: str) -> str:
    """Traduce texto al español vía MyMemory. Devuelve original si falla."""
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
    'latin dub', 'spanish dub',
]


def _check_latin_dub(title: str) -> tuple[str, str]:
    """
    Busca indicios de doblaje latino para el anime.
    Devuelve (estado, fuente):
        estado: '✅ Disponible' | '📢 Anunciado' | '❌ No confirmado'
        fuente: nombre del sitio o cadena vacía
    """
    encoded = '+'.join(title.split())

    # ── Estrategia 1: DuckDuckGo HTML (no requiere API key) ──
    ddg_url = f"https://html.duckduckgo.com/html/?q={encoded}+doblaje+latino+anime"
    ddg_html = _curl_get(ddg_url, timeout=15)

    if ddg_html:
        combined = ddg_html.lower()
        # ¿Hay resultado de algún sitio de doblaje conocido?
        found_site = next((s for s in _LAT_DUB_SITES if s in combined), '')
        found_keyword = any(kw in combined for kw in _LAT_DUB_KEYWORDS)

        if found_keyword and found_site:
            # Distinguir "disponible" de "anunciado"
            if any(w in combined for w in ['disponible', 'ya disponible', 'puedes ver', 'ver ahora']):
                return '✅ Disponible', found_site
            elif any(w in combined for w in ['anunciado', 'próximamente', 'soon', 'confirmed', 'confirmado']):
                return '📢 Anunciado', found_site
            else:
                return '✅ Disponible', found_site
        elif found_keyword:
            return '📢 Anunciado', 'varios sitios'

    # ── Estrategia 2: Buscar directamente en Crunchyroll ──
    cr_url = f"https://www.crunchyroll.com/search?q={encoded}"
    cr_html = _curl_get(cr_url, timeout=15)
    if cr_html and 'español (latino)' in cr_html.lower():
        return '✅ Disponible', 'Crunchyroll'

    # ── Estrategia 3: AnimeFlv (popular en LATAM) ──
    flv_url = f"https://www3.animeflv.net/browse?q={encoded}"
    flv_html = _curl_get(flv_url, timeout=15)
    if flv_html:
        lower = flv_html.lower()
        if 'latino' in lower or 'doblado' in lower:
            return '✅ Disponible', 'AnimeFlv'

    return '❌ No confirmado', ''


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
                await status_msg.edit_text(f"❌ No se encontró el anime: <b>{anime_name}</b>",
                                           parse_mode=enums.ParseMode.HTML)
                return

            anime = data['data']['Media']

            # ── Traducciones de campos ──
            ESTADOS = {
                'FINISHED': 'Finalizado', 'RELEASING': 'En emisión',
                'NOT_YET_RELEASED': 'Próximamente', 'CANCELLED': 'Cancelado', 'HIATUS': 'En pausa'
            }
            TEMPORADAS = {'WINTER': 'Invierno', 'SPRING': 'Primavera', 'SUMMER': 'Verano', 'FALL': 'Otoño'}
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

            # ── Sinopsis: preferir Anime-Planet ──
            await status_msg.edit_text("⏳ Obteniendo sinopsis de Anime-Planet...")
            sinopsis = _get_animeplanet_synopsis(titulo)

            if sinopsis:
                logger.info("✅ Sinopsis obtenida de Anime-Planet")
                sinopsis = _translate_to_spanish(sinopsis)
            else:
                logger.info("⚠️ Usando sinopsis de AniList como fallback")
                sinopsis = anime.get('description', 'No disponible')
                if sinopsis != 'No disponible':
                    sinopsis = re.sub(r'<[^>]+>', '', sinopsis).strip()
                    sinopsis = _translate_to_spanish(sinopsis)

            # ── Doblaje Latino ──
            await status_msg.edit_text("⏳ Verificando doblaje latino...")
            dub_estado, dub_fuente = _check_latin_dub(titulo)
            dub_linea = dub_estado
            if dub_fuente:
                dub_linea += f" <i>({dub_fuente})</i>"

            # ── Bloque de títulos alternativos ──
            titulo_bloque = ""
            if titulo_ingles and titulo_ingles != titulo:
                titulo_bloque += f"\n<b>🔤 Título inglés:</b> <b>{titulo_ingles}</b>"
            if titulo_nativo and titulo_nativo != titulo:
                titulo_bloque += f"\n<b>🈯 Título nativo:</b> <b>{titulo_nativo}</b>"

            # ── Mensaje final ──
            info = (
                f"<b>✨ INFORMACIÓN DEL ANIME ✨</b>\n\n"
                f"<b>🈺 Título:</b> <b>{titulo}</b>"
                f"{titulo_bloque}\n"
                f"<b>🏦 Estudio:</b> <b>{estudios}</b>\n"
                f"<b>📆 Año:</b> <b>{anime.get('seasonYear', 'N/A')}</b>\n"
                f"<b>🗂 Episodios:</b> <b>{anime.get('episodes', 'En emisión')}</b>\n"
                f"<b>🏷 Géneros:</b> <b>{generos}</b>\n"
                f"<b>⏱ Duración:</b> <b>{anime.get('duration', 'N/A')} min</b>\n"
                f"<b>💽 Formato:</b> <b>{FORMATOS.get(anime.get('format'), anime.get('format', 'N/A'))}</b>\n"
                f"<b>🔅 Temporada:</b> <b>{TEMPORADAS.get(anime.get('season'), 'N/A')}</b>\n"
                f"<b>⏳ Estado:</b> <b>{ESTADOS.get(anime.get('status'), anime.get('status', 'N/A'))}</b>\n"
                f"<b>🎙 Doblaje Latino:</b> {dub_linea}\n\n"
                f"<b>📜 Sinopsis</b> <i>(vía Anime-Planet)</i><b>:</b>\n"
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

            # Fallback sin imagen
            await status_msg.edit_text(info, parse_mode=enums.ParseMode.HTML)

        except Exception as e:
            logger.error(f"❌ Error en anime_command: {e}")
            await status_msg.edit_text(
                f"❌ <b>Error</b>\n\n{str(e)[:100]}",
                parse_mode=enums.ParseMode.HTML
            )
