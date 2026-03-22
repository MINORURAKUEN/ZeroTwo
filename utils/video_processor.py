import json
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

class VideoProcessor:
    """
    Clase profesional para procesar videos con FFmpeg.
    Optimizado para FFmpeg 8.1+ (Termux/Android).
    """
    
    @staticmethod
    def _escape_path(path):
        """Escapa rutas para que FFmpeg no falle con caracteres especiales o ':'."""
        p = str(path).replace('\\', '/').replace(':', '\\:').replace("'", r"\'")
        return f"'{p}'"

    @staticmethod
    def probe_media(input_path):
        """Analiza el archivo, detecta idiomas y asigna banderas."""
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
                '-show_streams', '-show_format', str(input_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            
            info = {'audio': [], 'subtitle': []}
            sub_count = 0 
            
            for stream in data.get('streams', []):
                s_index = stream.get('index')
                s_type = stream.get('codec_type')
                
                tags = stream.get('tags', {})
                lang_code = tags.get('language', 'UND').upper()
                flag = flags.get(lang_code, '🏳️')
                title = tags.get('title', 'Pista')
                
                is_forced = stream.get('disposition', {}).get('forced', 0) == 1
                suffix = " (FORZADO)" if is_forced else ""

                if s_type == 'audio':
                    info['audio'].append({
                        'index': s_index,
                        'label': f"{flag} {lang_code} - {title}"
                    })
                elif s_type == 'subtitle':
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
        Quema subtítulos y agrega marca de agua 'CID' (Sin cursiva).
        Estilo: Texto blanco, contorno azul claro.
        """
        logger.info(f"📝 Iniciando quemado con marca de agua 'CID'")
        
        # Escapado robusto de rutas
        if is_external and external_sub_path:
            sub_p = VideoProcessor._escape_path(external_sub_path)
            sub_filter = f"subtitles={sub_p}"
        else:
            vid_p = VideoProcessor._escape_path(video_path)
            sub_filter = f"subtitles={vid_p}:si={sub_idx}"

        # Estilo de Subtítulos: Borde Azul Claro. Usamos 'sans' por compatibilidad.
        sub_style = (
            "force_style='"
            "Fontname=sans,FontSize=22,Bold=1,"
            "PrimaryColour=&HFFFFFF,OutlineColour=&HAABB00,"      
            "BorderStyle=1,Outline=2.0,Shadow=1.0,MarginV=25'"
        )

        # Marca de Agua: SIN CURSIVA (italic eliminado para FFmpeg 8.1)
        watermark = (
            "drawtext="
            "text='CID':x=20:y=20:"
            "font='sans':fontsize=24:"
            "fontcolor=white:bordercolor=black:borderw=1.5"
        )

        full_vf = f"{watermark},{sub_filter}:{sub_style}"
        audio_map = ["-map", f"0:{audio_idx}"] if audio_idx is not None else ["-map", "0:a:0"]

        cmd = [
            'ffmpeg', '-y', '-i', str(video_path),
            '-map', '0:v:0', *audio_map,
            '-vf', full_vf,
            '-c:v', 'libx264', '-crf', '22', '-preset', 'ultrafast',
            '-c:a', 'aac', '-b:a', '128k',
            '-threads', '0',
            '-movflags', '+faststart',
            str(output_path)
        ]

        try:
            process = subprocess.run(cmd, capture_output=True, text=True)
            if process.returncode != 0:
                logger.error(f"❌ FFmpeg falló: {process.stderr}")
                return False
            return True
        except Exception as e:
            logger.error(f"❌ Error en proceso FFmpeg: {e}")
            return False

    @staticmethod
    def compress_video_resolution(input_path, output_path, scale='1280:-1', bitrate='1500k', crf='24', preset='ultrafast'):
        """Comprime video manteniendo la compatibilidad."""
        cmd = [
            'ffmpeg', '-y', '-i', str(input_path),
            '-vf', f'scale={scale}:force_original_aspect_ratio=decrease,pad={scale}:(ow-iw)/2:(oh-ih)/2',
            '-c:v', 'libx264', '-crf', crf, '-preset', preset, 
            '-b:v', bitrate, '-c:a', 'aac', '-b:a', '128k', 
            str(output_path)
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except Exception as e:
            logger.error(f"❌ Error comprimiendo: {e}")
            return False

    @staticmethod
    def extract_audio(video_path, output_path):
        """Extrae el audio en MP3."""
        cmd = [
            'ffmpeg', '-y', '-i', str(video_path),
            '-vn', '-acodec', 'libmp3lame', '-b:a', '192k', 
            str(output_path)
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except Exception as e:
            logger.error(f"❌ Error extrayendo audio: {e}")
            return False
            
