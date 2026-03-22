import json
import logging
import subprocess
import os
from pathlib import Path

logger = logging.getLogger(__name__)

class VideoProcessor:
    @staticmethod
    def _escape_path(path):
        p = str(path).replace('\\', '/').replace(':', '\\:').replace("'", r"\'")
        return f"'{p}'"

    @staticmethod
    def probe_media(input_path):
        flags = {
            'SPA': '🇪🇸', 'ESP': '🇪🇸', 'JPN': '🇯🇵', 'JAP': '🇯🇵',
            'ENG': '🇺🇸', 'ENU': '🇺🇸', 'FRA': '🇫🇷', 'FRE': '🇫🇷',
            'GER': '🇩🇪', 'DEU': '🇩🇪', 'POR': '🇧🇷', 'ITA': '🇮🇹',
            'KOR': '🇰🇷', 'CHI': '🇨🇳', 'ZHO': '🇨🇳', 'RUS': '🇷🇺', 'UND': '🏳️'
        }
        try:
            cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', '-show_format', str(input_path)]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            info = {'audio': [], 'subtitle': []}
            sub_count = 0 
            for stream in data.get('streams', []):
                s_index, s_type = stream.get('index'), stream.get('codec_type')
                tags = stream.get('tags', {})
                lang_code = tags.get('language', 'UND').upper()
                flag = flags.get(lang_code, '🏳️')
                title = tags.get('title', 'Pista')
                is_forced = stream.get('disposition', {}).get('forced', 0) == 1
                suffix = " (FORZADO)" if is_forced else ""
                if s_type == 'audio':
                    info['audio'].append({'index': s_index, 'label': f"{flag} {lang_code} - {title}"})
                elif s_type == 'subtitle':
                    info['subtitle'].append({'index': sub_count, 'label': f"{flag} [{sub_count}] {lang_code}{suffix}"})
                    sub_count += 1
            return info
        except Exception as e:
            logger.error(f"❌ Error en probe_media: {e}")
            return None

    @staticmethod
    def compress_video_resolution(input_path, output_path, scale='640:360', bitrate='800k', crf='25', preset='veryfast'):
        """
        Versión final corregida para Termux. Usa '-x' para las opciones del codificador.
        """
        logger.info(f"⚙️ Intentando compresión 360p (HandBrake): {input_path}")
        
        try:
            width, height = scale.split(':')
            height = '360' if height == '-1' else height
        except:
            width, height = '640', '360'

        # Cambiamos --x264-opts por -x (que es el alias universal)
        # y eliminamos el prefijo 'preset=' si causa problemas, 
        # aunque aquí lo dejamos como cadena de opciones.
        cmd = [
            'HandBrakeCLI',
            '-i', str(input_path),
            '-o', str(output_path),
            '--format', 'av_mp4',
            '-e', 'x264',
            '-q', str(crf),
            '-x', 'preset=veryfast:threads=auto', # -x es más compatible que --x264-opts
            '-w', width,
            '-l', height,
            '--keep-display-aspect',
            '-a', '1',
            '-E', 'av_aac',
            '-B', '128',
            '--mixdown', 'stereo',
            '--optimize'
        ]

        try:
            process = subprocess.run(cmd, capture_output=True, text=True)
            
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                logger.info(f"✅ Compresión exitosa: {output_path}")
                return True
            else:
                logger.error(f"❌ Error en HandBrake. Stderr: {process.stderr}")
                # Si -x también falla, intentamos una versión ultra-simple sin opciones extra
                return VideoProcessor._compress_fallback(input_path, output_path, width, height, crf)
        except Exception as e:
            logger.error(f"❌ Error fatal: {e}")
            return False

    @staticmethod
    def _compress_fallback(input_path, output_path, width, height, crf):
        """Intento de emergencia con el comando más básico posible."""
        logger.warning("⚠️ Usando modo fallback de HandBrake...")
        cmd = [
            'HandBrakeCLI', '-i', str(input_path), '-o', str(output_path),
            '-w', width, '-l', height, '-e', 'x264', '-q', str(crf), '--optimize'
        ]
        try:
            subprocess.run(cmd, capture_output=True)
            return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        except: return False

    @staticmethod
    def burn_subtitles(video_path, output_path, audio_idx=None, sub_idx=None, is_external=False, external_sub_path=None):
        if is_external and external_sub_path:
            sub_p = VideoProcessor._escape_path(external_sub_path)
            sub_filter = f"subtitles={sub_p}"
        else:
            vid_p = VideoProcessor._escape_path(video_path)
            sub_filter = f"subtitles={vid_p}:si={sub_idx}"

        sub_style = "force_style='Fontname=sans,FontSize=20,Bold=1,PrimaryColour=&HFFFFFF,OutlineColour=&HAABB00,BorderStyle=1,Outline=2.0,Shadow=1.0,MarginV=25'"
        watermark = "drawtext=text='CID':x=20:y=20:font='sans':fontsize=22:fontcolor=white:bordercolor=black:borderw=1.5:enable='lt(t,6)'" 
        full_vf = f"{watermark},{sub_filter}:{sub_style}"
        audio_map = ["-map", f"0:{audio_idx}"] if audio_idx is not None else ["-map", "0:a:0"]

        cmd = ['ffmpeg', '-y', '-i', str(video_path), '-map', '0:v:0', *audio_map, '-vf', full_vf, '-c:v', 'libx264', '-crf', '26', '-preset', 'veryfast', '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', str(output_path)]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return os.path.exists(output_path)
        except: return False

    @staticmethod
    def extract_audio(video_path, output_path):
        cmd = ['ffmpeg', '-y', '-i', str(video_path), '-vn', '-acodec', 'libmp3lame', '-b:a', '192k', str(output_path)]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return os.path.exists(output_path)
        except: return False
        
