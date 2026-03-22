"""
VideoProcessor - Clase profesional para procesar videos con FFmpeg
Soporte para: MKV, AVI, ISO, Subdrips (pistas forzadas) y selección visual con banderas.
"""

import re
import json
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

class VideoProcessor:
    """Clase para procesar videos usando FFmpeg con soporte multicanal y visual"""
    
    @staticmethod
    def probe_media(input_path):
        """
        Analiza el archivo, detecta idiomas y asigna banderas para los botones.
        """
        logger.info(f"🔍 Analizando flujos de: {input_path}")
        
        # Diccionario de banderas por código de idioma (ISO 639-2)
        flags = {
            'SPA': '🇪🇸', 'ESP': '🇪🇸',
            'JPN': '🇯🇵', 'JAP': '🇯🇵',
            'ENG': '🇺🇸', 'ENU': '🇺🇸',
            'FRA': '🇫🇷', 'FRE': '🇫🇷',
            'GER': '🇩🇪', 'DEU': '🇩🇪',
            'POR': '🇧🇷', 'ITA': '🇮🇹',
            'KOR': '🇰🇷', 'CHI': '🇨🇳', 
            'ZHO': '🇨🇳', 'RUS': '🇷🇺',
            'UND': '🏳️'
        }

        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_streams', '-show_format', input_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            
            info = {'audio': [], 'subtitle': []}
            sub_count = 0 
            
            for stream in data.get('streams', []):
                s_index = stream.get('index')
                s_type = stream.get('codec_type')
                
                # Obtener idioma y asignar bandera
                lang_code = stream.get('tags', {}).get('language', 'UND').upper()
                flag = flags.get(lang_code, '🏳️')
                
                title = stream.get('tags', {}).get('title', 'Pista')
                
                disposition = stream.get('disposition', {})
                is_forced = disposition.get('forced', 0) == 1
                suffix = " (FORZADO)" if is_forced else ""

                if s_type == 'audio':
                    info['audio'].append({
                        'index': s_index,
                        'label': f"{flag} {lang_code} - {title}"
                    })
                elif s_type == 'subtitle':
                    # Usamos sub_count para el filtro 'si' en burn_subtitles
                    info['subtitle'].append({
                        'index': sub_count,
                        'label': f"{flag} [{sub_count}] {lang_code}{suffix}"
                    })
                    sub_count += 1
            
            logger.info(f"✅ Análisis completo: {len(info['audio'])} audios, {len(info['subtitle'])} subs.")
            return info
        except Exception as e:
            logger.error(f"❌ Error en probe_media: {e}")
            return None

    @staticmethod
    def burn_subtitles(video_path, output_path, audio_idx=None, sub_idx=None, is_external=False, external_sub_path=None):
        """
        Quema subtítulos con estilo: Texto blanco, contorno azul claro, sin fondo.
        """
        logger.info(f"📝 Iniciando quemado de subtítulos")
        
        video_escaped = str(video_path).replace('\\', '/').replace(':', '\\:')
        
        if is_external and external_sub_path:
            sub_path_escaped = str(external_sub_path).replace('\\', '/').replace(':', '\\:')
            sub_filter = f"subtitles='{sub_path_escaped}'"
        else:
            # si={sub_idx} es el índice relativo de la pista de subtítulos
            sub_filter = f"subtitles='{video_escaped}':si={sub_idx}"

        # Estilo visual solicitado:
        # BorderStyle=1 (Sin caja negra), OutlineColour=&HAABB00 (Azul claro)
        style = (
            "force_style='"
            "Fontname=Arial,FontSize=22,Bold=1,"
            "PrimaryColour=&HFFFFFF,"      
            "OutlineColour=&HAABB00,"      
            "BorderStyle=1,"                
            "Outline=2.0,"                  
            "Shadow=1.0,"                   
            "MarginV=25'"
        )

        audio_map = ["-map", f"0:{audio_idx}"] if audio_idx is not None else ["-map", "0:a:0"]

        cmd = [
            'ffmpeg', '-y', '-i', video_path,
            '-map', '0:v:0',
            *audio_map,
            '-vf', f"{sub_filter}:{style}",
            '-c:v', 'libx264', '-crf', '20', '-preset', 'veryfast',
            '-c:a', 'aac', '-b:a', '128k',
            '-movflags', '+faststart',
            output_path
        ]

        try:
            process = subprocess.run(cmd, capture_output=True, text=True)
            return process.returncode == 0
        except Exception as e:
            logger.error(f"❌ Error quemando subtítulos: {e}")
            return False

    @staticmethod
    def compress_video_resolution(input_path, output_path, scale=None, bitrate='2000k', crf='23', preset='medium'):
        """Comprime video manteniendo la compatibilidad"""
        cmd = ['ffmpeg', '-y', '-i', input_path]
        if scale:
            cmd.extend(['-vf', f'scale={scale}:force_original_aspect_ratio=decrease:flags=lanczos,pad={scale}:(ow-iw)/2:(oh-ih)/2'])
        
        cmd.extend([
            '-c:v', 'libx264', '-crf', crf, '-preset', preset, 
            '-b:v', bitrate, '-c:a', 'aac', '-b:a', '128k', output_path
        ])
        
        try:
            subprocess.run(cmd, check=True)
            return True
        except:
            return False

    @staticmethod
    def extract_audio(video_path, output_path):
        """Extrae el audio en MP3"""
        cmd = ['ffmpeg', '-y', '-i', video_path, '-vn', '-acodec', 'libmp3lame', '-b:a', '192k', output_path]
        try:
            subprocess.run(cmd, check=True)
            return True
        except:
            return False
                                         
