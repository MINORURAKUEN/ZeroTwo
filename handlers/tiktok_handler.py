import re
import httpx  # Rikka-Bot prefiere httpx o aiohttp para asincronía
import logging
from pyrogram import filters, enums
from pyrogram.types import Message

logger = logging.getLogger(__name__)

def register(app):
    """Registra el handler de TikTok"""
    
    @app.on_message(filters.command(["tiktok", "tt", "ttdl"]))
    async def tiktok_command(client, message: Message):
        """Comando para descargar videos de TikTok"""
        
        # Obtener URL del mensaje
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.reply_text(
                "🎵 <b>TikTok Downloader</b>\n\n"
                "⚠️ Ingresa un enlace de TikTok.\n\n"
                "<b>Ejemplo:</b>\n"
                "<code>/tiktok https://vt.tiktok.com/ZS12345/</code>",
                parse_mode=enums.ParseMode.HTML
            )
            return

        tiktok_url = args[1].strip()
        
        # Validar URL
        if not re.search(r'tiktok\.com', tiktok_url):
            await message.reply_text("❌ El enlace no parece ser de TikTok.")
            return

        status_msg = await message.reply_text("⏳ <b>Buscando video en TikTok...</b>", parse_mode=enums.ParseMode.HTML)
        logger.info(f"🎵 TikTok - URL: {tiktok_url[:60]}...")

        try:
            video_url = None
            # Intentar con la API de TikWM (HD forzado)
            encoded = tiktok_url.replace(':', '%3A').replace('/', '%2F')
            api_url = f"https://www.tikwm.com/api/?url={encoded}&hd=1"
            
            async with httpx.AsyncClient() as client_http:
                response = await client_http.get(api_url, timeout=15)
                if response.status_code == 200:
                    json_data = response.json()
                    # Priorizar HD
                    video_url = json_data.get("data", {}).get("hdplay") or json_data.get("data", {}).get("play")

            if not video_url:
                # Fallback API 2
                api_fallback = f"https://api.vreden.my.id/api/tiktok?url={encoded}"
                async with httpx.AsyncClient() as client_http:
                    res = await client_http.get(api_fallback, timeout=15)
                    video_url = res.json().get("result", {}).get("url")

            if not video_url:
                raise Exception("No se pudo obtener el enlace de descarga.")

            await status_msg.edit_text("📥 <b>Descargando y enviando...</b>", parse_mode=enums.ParseMode.HTML)

            # Enviar directamente por URL (Pyrogram lo maneja eficientemente)
            await message.reply_video(
                video=video_url,
                caption="✅ <b>TikTok descargado en alta calidad</b>",
                parse_mode=enums.ParseMode.HTML
            )
            
            await status_msg.delete()
            logger.info("✅ TikTok enviado exitosamente")

        except Exception as e:
            logger.error(f"❌ Error en TikTok: {e}")
            await status_msg.edit_text(f"❌ <b>Error al descargar el video</b>\n\nDetalles: {str(e)[:100]}", parse_mode=enums.ParseMode.HTML)
                  
