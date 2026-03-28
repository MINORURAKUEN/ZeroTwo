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
            
            cmd = [
                'curl', '-s', '-X', 'POST',
                'https://graphql.anilist.co',
                '-H', 'Content-Type: application/json',
                '-H', 'Accept: application/json',
                '-d', json.dumps({
                    'query': query,
                    'variables': {'search': anime_name}
                })
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            
            if result.returncode != 0:
                await status_msg.edit_text("❌ Error al buscar el anime. Intenta de nuevo.")
                return
            
            data = json.loads(result.stdout)
            
            if not data.get('data') or not data['data'].get('Media'):
                await status_msg.edit_text(f"❌ No se encontró el anime: {anime_name}")
                return
            
            anime = data['data']['Media']
            
            # --- TRADUCCIONES ---
            ESTADOS = {'FINISHED': 'Finalizado', 'RELEASING': 'En emisión', 'NOT_YET_RELEASED': 'Próximamente', 'CANCELLED': 'Cancelado', 'HIATUS': 'En pausa'}
            TEMPORADAS = {'WINTER': 'Invierno', 'SPRING': 'Primavera', 'SUMMER': 'Verano', 'FALL': 'Otoño'}
            FORMATOS = {'TV': 'Serie de TV', 'MOVIE': 'Película', 'SPECIAL': 'Especial', 'OVA': 'OVA', 'ONA': 'ONA', 'MUSIC': 'Musical', 'TV_SHORT': 'Serie Corta'}
            GENEROS_TRAD = {'Action': 'Acción', 'Adventure': 'Aventura', 'Comedy': 'Comedia', 'Drama': 'Drama', 'Ecchi': 'Ecchi', 'Fantasy': 'Fantasía', 'Horror': 'Terror', 'Mahou Shoujo': 'Magical Girls', 'Mecha': 'Mecha', 'Music': 'Música', 'Mystery': 'Misterio', 'Psychological': 'Psicológico', 'Romance': 'Romance', 'Sci-Fi': 'Ciencia Ficción', 'Slice of Life': 'Recuentos de la vida', 'Sports': 'Deportes', 'Supernatural': 'Sobrenatural', 'Thriller': 'Suspenso'}
            
            # --- PROCESAMIENTO ---
            titulo = anime['title']['romaji'] or anime['title']['english'] or anime['title']['native']
            titulo_ingles = anime['title'].get('english', '')
            titulo_nativo = anime['title'].get('native', '')
            
            estudios = ', '.join([s['name'] for s in anime['studios']['nodes']]) if anime['studios']['nodes'] else 'Desconocido'
            generos = ', '.join([GENEROS_TRAD.get(g, g) for g in anime['genres']]) if anime['genres'] else 'N/A'
            
            sinopsis = anime.get('description', 'No disponible')
            if sinopsis != 'No disponible':
                sinopsis = re.sub(r'<[^>]+>', '', sinopsis).strip()
                # Sin límite de caracteres aquí, solo traducción
                try:
                    translate_cmd = ['curl', '-s', '-G', 'https://api.mymemory.translated.net/get', '--data-urlencode', f'q={sinopsis[:500]}', '--data-urlencode', 'langpair=en|es']
                    translate_result = subprocess.run(translate_cmd, capture_output=True, text=True, timeout=10)
                    if translate_result.returncode == 0:
                        translate_data = json.loads(translate_result.stdout)
                        if translate_data.get('responseStatus') == 200:
                            sinopsis = translate_data['responseData']['translatedText']
                except: pass

            titulo_bloque = ""
            if titulo_ingles and titulo_ingles != titulo:
                titulo_bloque += f"\n<b>🔤 Título inglés:</b> <b>{titulo_ingles}</b>"
            if titulo_nativo and titulo_nativo != titulo:
                titulo_bloque += f"\n<b>🈯 Título nativo:</b> <b>{titulo_nativo}</b>"

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
                f"<b>⏳ Estado:</b> <b>{ESTADOS.get(anime.get('status'), anime.get('status', 'N/A'))}</b>\n\n"
                f"<b>📜 Sinopsis:</b>\n"
                f"<blockquote><b>{sinopsis}</b></blockquote>"
            )
            
            image_url = anime['coverImage'].get('extraLarge') or anime.get('bannerImage') or anime['coverImage'].get('large')
            
            if image_url:
                img_cmd = ['curl', '-s', '-L', image_url]
                img_result = subprocess.run(img_cmd, capture_output=True, timeout=30)
                
                if img_result.returncode == 0 and len(img_result.stdout) > 0:
                    temp_img = work_dir / f"anime_{message.from_user.id}.jpg"
                    temp_img.write_bytes(img_result.stdout)
                    
                    # Lógica de división si el mensaje es muy largo para una foto
                    if len(info) > 1024:
                        await message.reply_photo(photo=str(temp_img))
                        await message.reply_text(info, parse_mode=enums.ParseMode.HTML)
                    else:
                        await message.reply_photo(photo=str(temp_img), caption=info, parse_mode=enums.ParseMode.HTML)
                    
                    await status_msg.delete()
                    temp_img.unlink()
                else:
                    await status_msg.edit_text(info, parse_mode=enums.ParseMode.HTML)
            else:
                await status_msg.edit_text(info, parse_mode=enums.ParseMode.HTML)
            
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            await status_msg.edit_text(f"❌ <b>Error</b>\n\n{str(e)[:100]}", parse_mode=enums.ParseMode.HTML)
                    
