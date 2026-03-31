"""
anime_handler.py - Manejador del comando /anime
Fuentes: AniList (principal) → MyAnimeList/Jikan (fallback)
Doblaje: Crunchyroll Latinoamérica (temporada Primavera 2026 + historial)
"""

import json
import re
import logging
import subprocess
import tempfile
import os
from pathlib import Path
from pyrogram import filters, enums
from pyrogram.types import Message

logger = logging.getLogger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Lista de animes con doblaje latino confirmado en Crunchyroll
# Fuente: Crunchyroll Latinoamérica — Primavera 2026 + temporadas previas
# 🟢 = tiene doblaje latino en Crunchyroll  |  🔴 = sin doblaje
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRUNCHYROLL_DUBS = {
    # ── Primavera 2026 (confirmados 24 mar 2026) ──────────────────────────
    "agents of the four seasons: dance of spring": True,
    "the beginning after the end": True,
    "classroom of the elite": True,
    "classroom of the elite season 4": True,
    "i want to end this love game": True,
    "dr. stone: science future": True,
    "dr stone science future": True,
    "that time i got reincarnated as a slime": True,
    "that time i got reincarnated as a slime season 4": True,
    "tensura": True,
    "ascendance of a bookworm": True,
    "daemons of the shadow realm": True,
    "mistress kanan is devilishly easy": True,
    "welcome to demon school! iruma-kun": True,
    "iruma-kun": True,
    "mairimashita! iruma-kun": True,
    "one piece": True,
    "liar game": True,
    "an observation log of my fiancee who calls herself a villainess": True,
    "witch hat atelier": True,
    "atelier of witch hat": True,
    "i made friends with the second prettiest girl in my class": True,
    "marriagetoxin": True,
    "rent a girlfriend": True,
    "rent a girlfriend season 5": True,
    "kanojo okarishimasu": True,
    "re:zero": True,
    "re:zero - starting life in another world": True,
    "re:zero season 4": True,
    "the warrior princess and the barbaric king": True,
    "drops of god": True,
    "wistoria: wand and sword": True,
    "wistoria wand and sword": True,
    "wistoria: wand and sword season 2": True,
    # ── Invierno 2026 ──────────────────────────────────────────────────────
    "jujutsu kaisen": True,
    "jujutsu kaisen season 3": True,
    "frieren: beyond journey's end": True,
    "frieren beyond journey's end": True,
    "sousou no frieren": True,
    "fire force": True,
    "enen no shouboutai": True,
    "you and i are polar opposites": True,
    # ── Títulos populares con doblaje histórico en Crunchyroll ────────────
    "naruto": True,
    "naruto shippuden": True,
    "boruto": True,
    "boruto: naruto next generations": True,
    "dragon ball super": True,
    "dragon ball z": True,
    "bleach": True,
    "bleach: thousand-year blood war": True,
    "attack on titan": True,
    "shingeki no kyojin": True,
    "demon slayer": True,
    "kimetsu no yaiba": True,
    "my hero academia": True,
    "boku no hero academia": True,
    "black clover": True,
    "fairy tail": True,
    "overlord": True,
    "sword art online": True,
    "sword art online: alicization": True,
    "the rising of the shield hero": True,
    "tate no yuusha no nariagari": True,
    "konosuba": True,
    "kono subarashii sekai ni shukufuku wo!": True,
    "tensura diary": True,
    "mushoku tensei": True,
    "mushoku tensei: jobless reincarnation": True,
    "jobless reincarnation": True,
    "reincarnated as a sword": True,
    "tensei shitara ken deshita": True,
    "the eminence in shadow": True,
    "kage no jitsuryokusha ni naritakute": True,
    "solo leveling": True,
    "ore dake level up na ken": True,
    "chainsaw man": True,
    "spy x family": True,
    "tokyo revengers": True,
    "hunter x hunter": True,
    "fullmetal alchemist: brotherhood": True,
    "made in abyss": True,
    "vinland saga": True,
    "dr. stone": True,
    "dr stone": True,
    "tower of god": True,
    "the god of high school": True,
    "noblesse": True,
    "classroom of the elite season 2": True,
    "classroom of the elite season 3": True,
    "rent-a-girlfriend": True,
    "that time i got reincarnated as a slime season 2": True,
    "that time i got reincarnated as a slime season 3": True,
    "dorohedoro": True,
    "dorohedoro season 2": True,
    "one punch man": True,
    "mob psycho 100": True,
    "death note": True,
    "tokyo ghoul": True,
    "no game no life": True,
    "is it wrong to try to pick up girls in a dungeon?": True,
    "danmachi": True,
    "re:zero season 2": True,
    "re:zero season 3": True,
    "that time i got reincarnated as a slime: trinity in tempest": True,
    "welcome to demon school! iruma-kun season 2": True,
    "welcome to demon school! iruma-kun season 3": True,
}


def _tiene_doblaje(titulo_romaji: str, titulo_english: str, titulo_native: str) -> bool:
    """Verifica si el anime tiene doblaje latino en Crunchyroll."""
    for titulo in [titulo_romaji, titulo_english, titulo_native]:
        if titulo and titulo.lower().strip() in CRUNCHYROLL_DUBS:
            return True
        # Búsqueda parcial para variantes de título
        if titulo:
            titulo_lower = titulo.lower().strip()
            for key in CRUNCHYROLL_DUBS:
                if key in titulo_lower or titulo_lower in key:
                    return True
    return False


def _curl_post_json(url: str, payload: dict, timeout: int = 15) -> dict | None:
    """Hace POST JSON con curl usando archivo temporal (evita problemas de escapado)."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as tmp:
        json.dump(payload, tmp, ensure_ascii=False)
        tmp_path = tmp.name

    try:
        cmd = [
            'curl', '-s', '-X', 'POST', url,
            '-H', 'Content-Type: application/json',
            '-H', 'Accept: application/json',
            '-d', f'@{tmp_path}'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            return None
        return json.loads(result.stdout)
    except Exception as e:
        logger.error(f"curl POST error: {e}")
        return None
    finally:
        os.unlink(tmp_path)


def _curl_get(url: str, timeout: int = 15) -> dict | None:
    """Hace GET con curl y devuelve JSON parseado."""
    try:
        cmd = ['curl', '-s', '-L', url,
               '-H', 'Accept: application/json',
               '-H', 'User-Agent: Mozilla/5.0']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            return None
        return json.loads(result.stdout)
    except Exception as e:
        logger.error(f"curl GET error: {e}")
        return None


def _buscar_anilist(anime_name: str) -> dict | None:
    """Busca en AniList GraphQL. Devuelve el objeto Media o None."""
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
    data = _curl_post_json(
        'https://graphql.anilist.co',
        {'query': query, 'variables': {'search': anime_name}}
    )
    if not data:
        return None
    if data.get('errors'):
        logger.info(f"AniList: no encontrado → {anime_name}")
        return None
    return data.get('data', {}).get('Media')


def _buscar_mal(anime_name: str) -> dict | None:
    """
    Fallback: busca en MyAnimeList via Jikan API v4.
    Devuelve un dict normalizado con los mismos campos que AniList.
    """
    import urllib.parse
    query_enc = urllib.parse.quote(anime_name)
    data = _curl_get(f'https://api.jikan.moe/v4/anime?q={query_enc}&limit=1')

    if not data or not data.get('data'):
        return None

    mal = data['data'][0]

    # Normalizar al formato que usa el resto del código
    return {
        '_source': 'mal',
        'title': {
            'romaji': mal.get('title'),
            'english': mal.get('title_english') or mal.get('title'),
            'native': mal.get('title_japanese') or '',
        },
        'studios': {
            'nodes': [{'name': s['name']} for s in mal.get('studios', [])]
        },
        'seasonYear': mal.get('aired', {}).get('prop', {}).get('from', {}).get('year'),
        'episodes': mal.get('episodes'),
        'genres': [g['name'] for g in mal.get('genres', [])],
        'duration': None,          # MAL da string, lo ignoramos
        'format': _mal_type(mal.get('type')),
        'season': None,
        'status': _mal_status(mal.get('status')),
        'description': mal.get('synopsis') or 'No disponible',
        'bannerImage': None,
        'coverImage': {
            'extraLarge': mal.get('images', {}).get('jpg', {}).get('large_image_url'),
            'large': mal.get('images', {}).get('jpg', {}).get('image_url'),
        },
        'mal_url': mal.get('url'),
        'score': mal.get('score'),
    }


def _mal_type(t: str | None) -> str:
    mapping = {'TV': 'TV', 'Movie': 'MOVIE', 'Special': 'SPECIAL',
               'OVA': 'OVA', 'ONA': 'ONA', 'Music': 'MUSIC'}
    return mapping.get(t or '', t or 'TV')


def _mal_status(s: str | None) -> str:
    mapping = {
        'Finished Airing': 'FINISHED',
        'Currently Airing': 'RELEASING',
        'Not yet aired': 'NOT_YET_RELEASED',
    }
    return mapping.get(s or '', s or '')


def _traducir(texto: str) -> str:
    """Traduce al español usando MyMemory (max 500 chars)."""
    try:
        cmd = [
            'curl', '-s', '-G',
            'https://api.mymemory.translated.net/get',
            '--data-urlencode', f'q={texto[:500]}',
            '--data-urlencode', 'langpair=en|es'
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            d = json.loads(r.stdout)
            if d.get('responseStatus') == 200:
                return d['responseData']['translatedText']
    except Exception:
        pass
    return texto


def register(app, user_states, work_dir):
    """Registra el handler del comando /anime."""

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
        'Supernatural': 'Sobrenatural', 'Thriller': 'Suspenso',
        # Géneros extra de MAL
        'Shounen': 'Shōnen', 'Shoujo': 'Shōjo', 'Seinen': 'Seinen',
        'Josei': 'Josei', 'Isekai': 'Isekai', 'Harem': 'Harem',
        'School': 'Escolar', 'Magic': 'Magia', 'Super Power': 'Superpoderes',
        'Martial Arts': 'Artes Marciales', 'Historical': 'Histórico',
        'Military': 'Militar', 'Space': 'Espacial', 'Game': 'Juegos',
        'Vampire': 'Vampiros', 'Demons': 'Demonios', 'Police': 'Policía',
        'Cars': 'Autos', 'Kids': 'Infantil', 'Parody': 'Parodia',
        'Samurai': 'Samurái', 'Award Winning': 'Premiado',
        'Suspense': 'Suspenso', 'Gourmet': 'Gastronomía',
        'Boys Love': 'Boys Love', 'Girls Love': 'Girls Love',
    }

    @app.on_message(filters.command("anime"))
    async def anime_command(client, message: Message):
        """Comando /anime — busca info de anime (AniList + MAL fallback)."""

        args = message.text.split(maxsplit=1)

        if len(args) < 2:
            await message.reply_text(
                "🈺 <b>Búsqueda de Anime</b>\n\n"
                "Por favor ingresa el nombre del anime:\n"
                "<code>/anime Nombre del anime</code>\n\n"
                "Ejemplos:\n"
                "<code>/anime One Piece</code>\n"
                "<code>/anime Solo Leveling</code>",
                parse_mode=enums.ParseMode.HTML
            )
            return

        anime_name = args[1].strip()
        logger.info(f"🈺 Buscando anime: {anime_name}")

        status_msg = await message.reply_text("⏳ Buscando información del anime...")

        try:
            # ── 1. Buscar en AniList ──────────────────────────────────────
            anime = _buscar_anilist(anime_name)
            fuente = "AniList"

            # ── 2. Fallback a MyAnimeList/Jikan ──────────────────────────
            if not anime:
                logger.info(f"AniList sin resultados, probando MAL para: {anime_name}")
                await status_msg.edit_text("⏳ Buscando en MyAnimeList...")
                anime = _buscar_mal(anime_name)
                fuente = "MyAnimeList"

            if not anime:
                await status_msg.edit_text(
                    f"❌ No se encontró el anime: <b>{anime_name}</b>\n\n"
                    "Intenta con el título en japonés o inglés.",
                    parse_mode=enums.ParseMode.HTML
                )
                return

            # ── 3. Procesar campos ────────────────────────────────────────
            titulo = (
                anime['title'].get('romaji')
                or anime['title'].get('english')
                or anime['title'].get('native')
                or 'Desconocido'
            )
            titulo_ingles = anime['title'].get('english') or ''
            titulo_nativo = anime['title'].get('native') or ''

            estudios_nodes = anime.get('studios', {}).get('nodes', [])
            estudios = ', '.join([s['name'] for s in estudios_nodes]) if estudios_nodes else 'Desconocido'

            generos_raw = anime.get('genres') or []
            generos = ', '.join([GENEROS_TRAD.get(g, g) for g in generos_raw]) if generos_raw else 'N/A'

            sinopsis = anime.get('description') or 'No disponible'
            if sinopsis not in ('No disponible', '', None):
                sinopsis = re.sub(r'<[^>]+>', '', sinopsis).strip()
                sinopsis = _traducir(sinopsis)

            episodios = anime.get('episodes') or 'En emisión'
            duracion  = anime.get('duration')
            duracion_txt = f"{duracion} min" if duracion else 'N/A'
            anio      = anime.get('seasonYear') or 'N/A'
            formato   = FORMATOS.get(anime.get('format'), anime.get('format') or 'N/A')
            temporada = TEMPORADAS.get(anime.get('season'), 'N/A')
            estado    = ESTADOS.get(anime.get('status'), anime.get('status') or 'N/A')

            # ── 4. Doblaje Crunchyroll ────────────────────────────────────
            tiene_dub = _tiene_doblaje(titulo, titulo_ingles, titulo_nativo)
            doblaje_txt = "🟢 Disponible en Crunchyroll" if tiene_dub else "🔴 No disponible"

            # ── 5. Bloques opcionales de título ───────────────────────────
            titulo_bloque = ""
            if titulo_ingles and titulo_ingles.strip() != titulo.strip():
                titulo_bloque += f"\n<b>🔤 Título inglés:</b> <b>{titulo_ingles}</b>"
            if titulo_nativo and titulo_nativo.strip() != titulo.strip():
                titulo_bloque += f"\n<b>🈯 Título nativo:</b> <b>{titulo_nativo}</b>"

            info = (
                f"<b>✨ INFORMACIÓN DEL ANIME ✨</b>\n\n"
                f"<b>🈺 Título:</b> <b>{titulo}</b>"
                f"{titulo_bloque}\n"
                f"<b>🏦 Estudio:</b> <b>{estudios}</b>\n"
                f"<b>📆 Año:</b> <b>{anio}</b>\n"
                f"<b>🗂 Episodios:</b> <b>{episodios}</b>\n"
                f"<b>🎙 Doblaje latino:</b> <b>{doblaje_txt}</b>\n\n"
                f"<b>🏷 Géneros:</b> <b>{generos}</b>\n"
                f"<b>⏱ Duración:</b> <b>{duracion_txt}</b>\n"
                f"<b>💽 Formato:</b> <b>{formato}</b>\n"
                f"<b>🔅 Temporada:</b> <b>{temporada}</b>\n"
                f"<b>⏳ Estado:</b> <b>{estado}</b>\n"
                f"<b>📜 Sinopsis:</b>\n"
                f"<blockquote><b>{sinopsis}</b></blockquote>"
            )

            # ── 6. Imagen de portada ──────────────────────────────────────
            cover = anime.get('coverImage') or {}
            image_url = (
                cover.get('extraLarge')
                or anime.get('bannerImage')
                or cover.get('large')
            )

            if image_url:
                img_result = subprocess.run(
                    ['curl', '-s', '-L', image_url],
                    capture_output=True, timeout=30
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

            # Sin imagen → solo texto
            await status_msg.edit_text(info, parse_mode=enums.ParseMode.HTML)

        except Exception as e:
            logger.error(f"❌ Error en /anime: {e}", exc_info=True)
            await status_msg.edit_text(
                f"❌ <b>Error interno</b>\n\n<code>{str(e)[:200]}</code>",
                parse_mode=enums.ParseMode.HTML
        )
    
