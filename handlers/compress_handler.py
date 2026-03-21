"""
compress_handler.py - Manejador del comando /compress
"""

from pyrogram import filters, enums
from pyrogram.types import Message


def register(app, user_states):
    """Registra el handler del comando /compress"""
    
    @app.on_message(filters.command("compress"))
    async def compress_command(client, message: Message):
        """Comando /compress - Activar modo compresión"""
        user_id = message.from_user.id
        user_states[user_id] = {'action': 'compress', 'step': 'waiting_video'}
        
        await message.reply_text(
            "📹 <b>Modo Compresión Activado</b>\n\n"
            "Envíame el video que quieres comprimir.\n"
            "✨ Sin límite de tamaño!",
            parse_mode=enums.ParseMode.HTML
        )
