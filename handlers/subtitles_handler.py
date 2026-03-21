"""
subtitles_handler.py - Manejador del comando /subtitles
"""

from pyrogram import filters, enums
from pyrogram.types import Message


def register(app, user_states):
    """Registra el handler del comando /subtitles"""
    
    @app.on_message(filters.command("subtitles"))
    async def subtitles_command(client, message: Message):
        """Comando /subtitles - Activar modo quemar subtítulos"""
        user_id = message.from_user.id
        user_states[user_id] = {'action': 'subtitles', 'step': 'waiting_video'}
        
        await message.reply_text(
            "📝 <b>Modo Quemar Subtítulos Activado</b>\n\n"
            "Envíame el video al que quieres añadir subtítulos.",
            parse_mode=enums.ParseMode.HTML
        )
