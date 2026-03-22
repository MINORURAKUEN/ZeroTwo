"""
facebook_handler.py - Manejador de descargas de Facebook
Usa múltiples APIs con sistema de fallback
"""

import json
import logging
import subprocess
import re
from pathlib import Path
from pyrogram import filters, enums
from pyrogram.types import Message

logger = logging.getLogger(__name__)


def register(app, download_dir):
    """Registra el handler de Facebook"""
    
    @app.on_message(filters.command(["fb", "facebook", "fbdl"]))
    async def facebook_command(client, message: Message):
        """Comando para descargar videos de Facebook"""
        
        # Obtener URL
        args = message.text.split(maxsplit=1)
        
        if len(args) < 2:
            await message.reply_text(
                "📘 <b>Facebook Downloader</b>\n\n"
                "⚠️ Ingresa un enlace de Facebook.\n\n"
                "<b>Ejemplo:</b>\n"
                "<code>/fb https://www.facebook.com/watch/?v=12345</code>",
                parse_mode=enums.ParseMode.HTML
            )
            return
        
        fb_link = args[1].strip()
        
        # Validar que sea un enlace de Facebook
        if not re.search(r'facebook\.com|fb\.watch', fb_link):
            await message.reply_text("❌ El enlace no parece ser de Facebook.")
            return
        
        logger.info(f"📘 Facebook - URL: {fb_link[:60]}...")
        
        status_msg = await message.reply_text("⏳ Descargando video de Facebook...")
        
        try:
            apikey = "causa-0e3eacf90ab7be15"
            encoded_url = fb_link.replace('&', '%26').replace('=', '%3D').replace('?', '%3F')
            
            # Lista de APIs con fallback (prioridad de arriba hacia abajo)
            apis = [
                f"https://rest.apicausas.xyz/api/v1/descargas/facebook?apikey={apikey}&url={encoded_url}",
                f"https://eliasar-yt-api.vercel.app/api/facebookdl?link={encoded_url}",
                f"https://api.botcahx.eu.org/api/dowloader/fbdown?url={encoded_url}&apikey=BrunoSobrino",
                f"https://api.vreden.my.id/api/facebook?url={encoded_url}"
            ]
            
            video_url = None
            video_title = None
            
            # Intentar con cada API hasta que una funcione
            for i, api in enumerate(apis, 1):
                try:
                    logger.info(f"🔄 Intentando API #{i}...")
                    
                    # Llamar a la API
                    api_cmd = f'curl -s -m 30 "{api}"'
                    result = subprocess.run(api_cmd, shell=True, capture_output=True, text=True, timeout=35)
                    
                    if result.returncode != 0:
                        logger.warning(f"❌ API #{i} falló (curl error)")
                        continue
                    
                    # Parsear JSON
                    api_data = json.loads(result.stdout)
                    
                    # Mapeo inteligente para diferentes estructuras de respuesta
                    # APICausas: json.resultado.url
                    # Eliasar: json.data.url
                    # BotCahx: json.result.url
                    # Vreden: json.url o json.data[0].url
                    
                    if 'resultado' in api_data and isinstance(api_data['resultado'], dict):
                        video_url = api_data['resultado'].get('url')
                        video_title = api_data['resultado'].get('title')
                    elif 'data' in api_data:
                        if isinstance(api_data['data'], dict):
                            video_url = api_data['data'].get('url')
                            video_title = api_data['data'].get('title')
                        elif isinstance(api_data['data'], list) and len(api_data['data']) > 0:
                            video_url = api_data['data'][0].get('url')
                            video_title = api_data['data'][0].get('title')
                    elif 'result' in api_data:
                        if isinstance(api_data['result'], dict):
                            video_url = api_data['result'].get('url')
                            video_title = api_data['result'].get('title')
                    elif 'url' in api_data:
                        video_url = api_data['url']
                    
                    # Verificar que la URL sea válida
                    if video_url and video_url.startswith('http'):
                        logger.info(f"✅ API #{i} exitosa!")
                        break
                    else:
                        logger.warning(f"❌ API #{i} no devolvió URL válida")
                        video_url = None
                        
                except json.JSONDecodeError:
                    logger.warning(f"❌ API #{i} devolvió JSON inválido")
                    continue
                except Exception as e:
                    logger.warning(f"❌ API #{i} error: {e}")
                    continue
            
            if not video_url:
                raise Exception("No se pudo extraer el video. Las APIs podrían estar caídas.")
            
            logger.info(f"✅ URL de descarga obtenida: {video_url[:60]}...")
            
            # Descargar video primero (Telegram no puede acceder directo a algunas URLs)
            await status_msg.edit_text("📥 Descargando video...")
            
            output_file = download_dir / f"fb_{message.from_user.id}.mp4"
            
            logger.info("📥 Descargando video de Facebook...")
            dl_cmd = f'curl -s -L -o "{output_file}" "{video_url}"'
            dl_result = subprocess.run(dl_cmd, shell=True, timeout=180)
            
            if dl_result.returncode != 0 or not output_file.exists():
                raise Exception("Error descargando el video")
            
            file_size = output_file.stat().st_size / (1024 * 1024)
            logger.info(f"✅ Video descargado: {file_size:.2f} MB")
            
            # Enviar video desde archivo local
            await status_msg.edit_text("📤 Enviando video...")
            
            caption = f"✅ <b>Video de Facebook</b>"
            if video_title:
                caption = f"✅ <b>{video_title}</b>"
            
            # Función de progreso
            last_percent = [0]
            async def upload_progress(current, total):
                percent = int((current / total) * 100)
                if percent - last_percent[0] >= 10:
                    mb_current = current / (1024**2)
                    mb_total = total / (1024**2)
                    logger.info(f"📤 Subida: {percent}% ({mb_current:.1f}/{mb_total:.1f} MB)")
                    last_percent[0] = percent
            
            await message.reply_video(
                video=str(output_file),
                caption=caption,
                parse_mode=enums.ParseMode.HTML,
                supports_streaming=True,
                progress=upload_progress
            )
            
            # Limpiar archivo temporal
            output_file.unlink()
            logger.info("🗑️ Archivo temporal eliminado")
            
            await status_msg.delete()
            logger.info("✅ Video de Facebook enviado exitosamente")
            
        except subprocess.TimeoutExpired:
            logger.error("⏱️ Timeout en descarga de Facebook")
            await status_msg.edit_text("⏱️ La descarga tardó demasiado. Intenta de nuevo.")
            
        except Exception as e:
            logger.error(f"❌ Error: {e}", exc_info=True)
            await status_msg.edit_text(f"❌ <b>Error:</b> {str(e)}", parse_mode=enums.ParseMode.HTML)
