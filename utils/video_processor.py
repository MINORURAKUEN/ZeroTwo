import re
import json
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

class VideoProcessor:
    """Clase para procesar videos usando FFmpeg con soporte multicanal y visual"""
    
    @staticmethod
    def _escape_filter_path(path):
        """Escapa rutas para filtros de FFmpeg (maneja ':', '\' y caracteres especiales)"""
        p = str(path).replace('\\', '/').replace(':', '\\:').replace("'", r"\'")
        return f"'{p}'"

    @staticmethod
    def probe_media(input_path):
        """Analiza el archivo y detecta idiomas."""
        logger.info(f"🔍 Analizando flujos de: {input_path}")
        
        flags = {
            'SPA': '🇪🇸', 'ESP': '🇪🇸', 'JPN': '🇯🇵', 'JAP': '🇯🇵',
            'ENG': '🇺🇸', 'ENU': '🇺🇸', 'FRA': '🇫🇷', 'FRE': '🇫🇷',
            'GER': '🇩🇪', 'DEU': '🇩🇪', 'POR': '🇧🇷', 'ITA': '🇮🇹',
            'KOR': '🇰🇷', 'CHI': '🇨🇳', 'ZHO': '🇨🇳', 'RUS': '🇷🇺', 'UND': '🏳️'
        }

        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_streams', '-show_format', input_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            
            info = {'audio': [], 'subtitle': []}
            # FFmpeg usa índices globales, pero para filtros de subtítulos internos se usa el índice relativo
            sub_relative_idx = 0 
            
            for stream in data.get('streams', []):
                s_index = stream.get('index')
                s_type = stream.get('codec_type')
                
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
                    # Importante: para filtros 'subtitles', si_index es el orden del sub en el archivo
                    info['subtitle'].append({
                        'index': sub_relative_idx, 
                        'label': f"{flag} [{sub_relative_idx}] {lang_code}{suffix}"
                    })
                    sub_relative_idx += 1
            
            return info
        except Exception as e:
            logger.error(f"❌ Error en probe_media: {e}")
            return None

    @staticmethod
    def burn_subtitles(video_path, output_path, audio_idx=None, sub_idx=None, is_external=False, external_sub_path=None):
        """Quema subtítulos y agrega marca de agua 'CID'"""
        logger.info(f"📝 Iniciando quemado con marca de agua 'CID'")
        
        # 1. Escapado Robusto de Rutas
        if is_external and external_sub_path:
            sub_path = VideoProcessor._escape_filter_path(external_sub_path)
            sub_filter = f"subtitles={sub_path}"
        else:
            video_p = VideoProcessor._escape_filter_path(video_path)
            sub_filter = f"subtitles={video_p}:si={sub_idx}"

        # 2. Estilos mejorados (se usa 'sans-serif' por compatibilidad en Termux/Linux)
        sub_style = (
            "force_style='"
            "Fontname=sans-serif,FontSize=22,Bold=1,"
            "PrimaryColour=&HFFFFFF,"      
            "OutlineColour=&HAABB00,"      
            "BorderStyle=1,Outline=2.0,Shadow=1.0,MarginV=25'"
        )

        watermark = (
            "drawtext="
            "text='CID':x=20:y=20:"
            "font='sans-serif':italic=1:fontsize=24:"
            "fontcolor=white:bordercolor=black:borderw=1.5"
        )

        # 3. Construcción del filtro de video
        full_vf = f"{watermark},{sub_filter}:{sub_style}"
        
        # Selección de audio
        audio_map = ["-map", f"0:{audio_idx}"] if audio_idx is not None else ["-map", "0:a:0"]

        cmd = [
            'ffmpeg', '-y', '-i', str(video_path),
            '-map', '0:v:0',
            *audio_map,
            '-vf', full_vf,
            '-c:v', 'libx264', '-crf', '20', '-preset', 'veryfast',
            '-c:a', 'aac', '-b:a', '128k',
            '-threads', '4', # Recomendado para Termux para no saturar el kernel
            '-movflags', '+faststart',
            str(output_path)
        ]

        try:
            # Capturamos stderr para ver qué falla exactamente si falla
            process = subprocess.run(cmd, capture_output=True, text=True)
            if process.returncode != 0:
                logger.error(f"❌ FFmpeg falló. Error: {process.stderr}")
                return False
            return True
        except Exception as e:
            logger.error(f"❌ Excepción en FFmpeg: {e}")
            return False
    
