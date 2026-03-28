"""
anime_handler.py - Manejador del comando /anime
Fuentes: AniList (principal) + MyAnimeList + AniDB + Anime-Planet + AniSearch + Kitsu
Incluye: doblaje español latino, links a sitios, puntuación, popularidad
"""

import asyncio
import json
import re
import logging
import subprocess
from pathlib import Path
from pyrogram import filters, enums
from pyrogram.types import Message

logger = logging.getLogger(__name__)

ANILIST_API = "https://graphql.anilist.co"
KITSU_API   = "https://kitsu.app/api/edge"
JIKAN_API   = "https://api.jikan.moe/v4"   # API no oficial de MAL (sin auth)

ESTADOS = {
    'FINISHED':         'Finalizado ✅',
    'RELEASING':        'En emisión 📡',
    'NOT_YET_RELEASED': 'Próximamente 🔜',
    'CANCELLED':        'Cancelado ❌',
    'HIATUS':           'En pausa ⏸',
}
TEMPORADAS = {
    'WINTER': '❄️ Invierno',
    'SPRING': '🌸 Primavera',
    'SUMMER': '☀️ Verano',
    'FALL':   '🍂 Otoño',
}
FORMATOS = {
    'TV':       'Serie TV',
    'MOVIE':    'Película',
    'SPECIAL':  'Especial',
    'OVA':      'OVA',
    'ONA':      'ONA',
    'MUSIC':    'Musical',
    'TV_SHORT': 'Serie Corta',
}


# ── Helpers síncronos (llamados con asyncio.to_thread) ────────────────────────

def _curl(args: list, timeout: int = 20) -> str:
    r = subprocess.run(
        ['curl', '-s', '--max-time', str(timeout), *args],
        capture_output=True, text=True, timeout=timeout + 5
    )
    return r.stdout if r.returncode == 0 else ''


def _fetch_anilist(search: str) -> dict | None:
    query = """
    query ($search: String) {
      Media (search: $search, type: ANIME) {
        id
        idMal
        title { romaji english native }
        studios(isMain: true) { nodes { name } }
        seasonYear episodes genres duration format season status
        averageScore popularity
        description
        bannerImage
        coverImage { extraLarge large }
        externalLinks { site url }
        trailer { site id }
      }
    }
    """
    raw = _curl([
        '-X', 'POST', ANILIST_API,
        '-H', 'Content-Type: application/json',
        '-d', json.dumps({'query': query, 'variables': {'search': search}}),
    ], timeout=15)
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return data.get('data', {}).get('Media')
    except Exception:
        return None


def _fetch_mal_extra(mal_id: int) -> dict:
    """Obtiene datos extra de MAL via Jikan v4: score, rank, doblaje."""
    out = {}
    if not mal_id:
        return out
    try:
        raw = _curl([f'{JIKAN_API}/anime/{mal_id}'], timeout=15)
        if not raw:
            return out
        d = json.loads(raw).get('data', {})
        out['mal_score']    = d.get('score', 'N/A')
        out['mal_rank']     = d.get('rank', 'N/A')
        out['mal_url']      = d.get('url', '')
        out['mal_members']  = d.get('members', 0)
        # Voces / doblaje en español latino
        out['has_spa_lat']  = False
    except Exception:
        pass
    # Buscar doblaje en el endpoint de voices
    try:
        raw2 = _curl([f'{JIKAN_API}/anime/{mal_id}/voices'], timeout=15)
        if raw2:
            voices = json.loads(raw2).get('data', [])
            for v in voices:
                lang = (v.get('language') or '').lower()
                if 'spanish' in lang and ('latin' in lang or 'america' in lang or 'la' in lang):
                    out['has_spa_lat'] = True
                    break
    except Exception:
        pass
    return out


def _fetch_kitsu(search: str) -> dict:
    """Obtiene datos de Kitsu: URL, rating, popularidad."""
    out = {}
    try:
        raw = _curl([
            f'{KITSU_API}/anime',
            '-G',
            '--data-urlencode', f'filter[text]={search}',
            '--data-urlencode', 'page[limit]=1',
            '-H', 'Accept: application/vnd.api+json',
        ], timeout=12)
        if not raw:
            return out
        items = json.loads(raw).get('data', [])
        if not items:
            return out
        item  = items[0]
        attrs = item.get('attributes', {})
        slug  = attrs.get('slug', '')
        out['kitsu_url']    = f"https://kitsu.app/anime/{slug}" if slug else ''
        out['kitsu_rating'] = attrs.get('averageRating', '')
    except Exception:
        pass
    return out


def _translate(text: str) -> str:
    """Traduce al español con MyMemory."""
    try:
        raw = _curl([
            '-G', 'https://api.mymemory.translated.net/get',
            '--data-urlencode', f'q={text[:500]}',
            '--data-urlencode', 'langpair=en|es',
        ], timeout=10)
        if raw:
            d = json.loads(raw)
            if d.get('responseStatus') == 200:
                return d['responseData']['translatedText']
    except Exception:
        pass
    return text


def _check_spa_lat_dub(anime_title: str, mal_extra: dict) -> str:
    """Determina si hay doblaje español latino."""
    # Si MAL ya lo confirmó
    if mal_extra.get('has_spa_lat'):
        return '✅ Sí'
    # Heurística: buscar en AniSearch (scraping ligero)
    try:
        slug = anime_title.lower().replace(' ', '+')
        raw  = _curl([
            '-A', 'Mozilla/5.0',
            f'https://www.anisearch.com/anime/index/page-1?char=all&q={slug}&language=es-419',
        ], timeout=10)
        if raw and anime_title.lower()[:8] in raw.lower():
            return '✅ Sí (AniSearch)'
    except Exception:
        pass
    return '❓ Sin confirmar'


# ── Handler principal ──────────────────────────────────────────────────────────

def register(app, user_states, work_dir):
    """Registra el handler del comando /anime"""

    @app.on_message(filters.command("anime"))
    async def anime_command(client, message: Message):

        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.reply_text(
                "🈺 <b>Búsqueda de Anime</b>\n\n"
                "Ingresa el nombre del anime:\n"
                "<code>/anime Nombre del anime</code>\n\n"
                "Ejemplo:\n<code>/anime Berserk</code>",
                parse_mode=enums.ParseMode.HTML
            )
            return

        anime_name = args[1].strip()
        logger.info(f"🈺 Buscando: {anime_name}")

        status_msg = await message.reply_text("⏳ Buscando información del anime…")

        try:
            # ── 1. AniList (fuente principal) ─────────────────────────────────
            await status_msg.edit_text("⏳ Consultando AniList…")
            anime = await asyncio.to_thread(_fetch_anilist, anime_name)

            if not anime:
                await status_msg.edit_text(f"❌ No se encontró el anime: <b>{anime_name}</b>",
                                           parse_mode=enums.ParseMode.HTML)
                return

            mal_id = anime.get('idMal')

            # ── 2. MAL via Jikan (score, rank, doblaje) ───────────────────────
            await status_msg.edit_text("⏳ Consultando MyAnimeList…")
            mal_extra = await asyncio.to_thread(_fetch_mal_extra, mal_id)

            # ── 3. Kitsu (rating alternativo) ─────────────────────────────────
            await status_msg.edit_text("⏳ Consultando Kitsu…")
            kitsu = await asyncio.to_thread(_fetch_kitsu, anime_name)

            # ── 4. Traducir sinopsis ──────────────────────────────────────────
            await status_msg.edit_text("⏳ Traduciendo sinopsis…")
            sinopsis_raw = anime.get('description', 'No disponible')
            sinopsis_raw = re.sub(r'<[^>]+>', '', sinopsis_raw).strip()
            if len(sinopsis_raw) > 600:
                sinopsis_raw = sinopsis_raw[:600] + '…'
            sinopsis = await asyncio.to_thread(_translate, sinopsis_raw)

            # ── 5. Doblaje español latino ─────────────────────────────────────
            titulo    = (anime['title']['romaji'] or
                         anime['title']['english'] or
                         anime['title']['native'])
            doblaje   = await asyncio.to_thread(_check_spa_lat_dub, titulo, mal_extra)

            # ── Construir datos ───────────────────────────────────────────────
            titulo_en = anime['title'].get('english', '')
            titulo_jp = anime['title'].get('native', '')
            estudios  = ', '.join(s['name'] for s in anime['studios']['nodes']) or 'Desconocido'
            generos   = ', '.join(anime.get('genres') or []) or 'N/A'

            score_al  = f"{anime.get('averageScore', 'N/A')}/100" if anime.get('averageScore') else 'N/A'
            score_mal = f"{mal_extra.get('mal_score', 'N/A')}/10"
            rank_mal  = f"#{mal_extra.get('mal_rank', 'N/A')}"
            kit_score = f"{kitsu.get('kitsu_rating', 'N/A')}/100" if kitsu.get('kitsu_rating') else 'N/A'
            popularidad = f"{anime.get('popularity', 0):,} usuarios"

            # ── Links externos ────────────────────────────────────────────────
            # AniList siempre disponible
            links_lines = [f'<a href="https://anilist.co/anime/{anime["id"]}">AniList</a>']

            # MAL
            if mal_id:
                links_lines.append(f'<a href="{mal_extra.get("mal_url") or f"https://myanimelist.net/anime/{mal_id}"}">MyAnimeList</a>')

            # AniDB — buscar en externalLinks de AniList
            ext_links = {l['site'].lower(): l['url'] for l in anime.get('externalLinks') or []}
            if 'anidb' in ext_links:
                links_lines.append(f'<a href="{ext_links["anidb"]}">AniDB</a>')
            else:
                slug_anidb = re.sub(r'[^a-z0-9]', '-', titulo.lower()).strip('-')
                links_lines.append(f'<a href="https://anidb.net/anime/?adb.search={slug_anidb}">AniDB</a>')

            # Anime-Planet
            slug_ap = re.sub(r'[^a-z0-9]+', '-', titulo.lower()).strip('-')
            links_lines.append(f'<a href="https://www.anime-planet.com/anime/{slug_ap}">Anime-Planet</a>')

            # AniSearch
            slug_as = re.sub(r'[^a-z0-9]+', '-', titulo.lower()).strip('-')
            links_lines.append(f'<a href="https://www.anisearch.com/anime/index?q={slug_as}">AniSearch</a>')

            # Kitsu
            if kitsu.get('kitsu_url'):
                links_lines.append(f'<a href="{kitsu["kitsu_url"]}">Kitsu</a>')

            links_str = ' • '.join(links_lines)

            # ── Trailer ───────────────────────────────────────────────────────
            trailer = anime.get('trailer') or {}
            trailer_line = ''
            if trailer.get('site') == 'youtube' and trailer.get('id'):
                trailer_line = f"\n<b>🎬 Trailer:</b> <a href=\"https://youtu.be/{trailer['id']}\">Ver en YouTube</a>"

            # ── Bloque de títulos opcionales ──────────────────────────────────
            titulo_bloque = ''
            if titulo_en and titulo_en != titulo:
                titulo_bloque += f'\n<b>🔤 Inglés:</b> {titulo_en}'
            if titulo_jp and titulo_jp != titulo:
                titulo_bloque += f'\n<b>🈯 Japonés:</b> {titulo_jp}'

            # ── Mensaje final ─────────────────────────────────────────────────
            info = (
                f"<b>✨ INFORMACIÓN DEL ANIME ✨</b>\n\n"

                f"<b>🈺 Título:</b> {titulo}"
                f"{titulo_bloque}\n\n"

                f"<b>🏦 Estudio:</b> {estudios}\n"
                f"<b>📆 Año:</b> {anime.get('seasonYear', 'N/A')}\n"
                f"<b>🗂 Episodios:</b> {anime.get('episodes') or 'En emisión'}\n"
                f"<b>⏱ Duración:</b> {anime.get('duration', 'N/A')} min\n"
                f"<b>💽 Formato:</b> {FORMATOS.get(anime.get('format'), anime.get('format', 'N/A'))}\n"
                f"<b>🔅 Temporada:</b> {TEMPORADAS.get(anime.get('season'), 'N/A')}\n"
                f"<b>⏳ Estado:</b> {ESTADOS.get(anime.get('status'), anime.get('status', 'N/A'))}\n"
                f"<b>🏷 Géneros:</b> {generos}\n\n"

                f"<b>⭐ Score AniList:</b> {score_al}\n"
                f"<b>⭐ Score MAL:</b> {score_mal}  <b>Rank:</b> {rank_mal}\n"
                f"<b>⭐ Score Kitsu:</b> {kit_score}\n"
                f"<b>👥 Popularidad:</b> {popularidad}\n\n"

                f"<b>🎙 Doblaje Español Latino:</b> {doblaje}\n\n"

                f"<b>🔗 Ver en:</b>\n{links_str}"
                f"{trailer_line}\n\n"

                f"<b>📜 Sinopsis:</b>\n"
                f"<blockquote>{sinopsis}</blockquote>"
            )

            # ── Enviar con imagen ─────────────────────────────────────────────
            await status_msg.edit_text("⏳ Preparando respuesta…")

            image_url = (anime['coverImage'].get('extraLarge') or
                         anime.get('bannerImage') or
                         anime['coverImage'].get('large'))

            if image_url:
                img_raw = await asyncio.to_thread(
                    lambda: subprocess.run(
                        ['curl', '-s', '-L', '--max-time', '20', image_url],
                        capture_output=True, timeout=25
                    ).stdout
                )
                if img_raw:
                    temp_img = work_dir / f"anime_{message.from_user.id}.jpg"
                    temp_img.write_bytes(img_raw)
                    await message.reply_photo(
                        photo=str(temp_img),
                        caption=info,
                        parse_mode=enums.ParseMode.HTML
                    )
                    await status_msg.delete()
                    temp_img.unlink(missing_ok=True)
                    logger.info(f"✅ Anime enviado con imagen: {titulo}")
                    return

            await status_msg.edit_text(info, parse_mode=enums.ParseMode.HTML)
            logger.info(f"✅ Anime enviado (sin imagen): {titulo}")

        except Exception as e:
            logger.error(f"❌ Error buscando anime: {e}", exc_info=True)
            await status_msg.edit_text(
                f"❌ <b>Error al buscar el anime</b>\n\nDetalles: {str(e)[:200]}",
                parse_mode=enums.ParseMode.HTML
)
