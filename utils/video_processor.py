import json
import logging
import subprocess
from pathlib import Path

# Configuración básica de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VideoProcessor:
    """
    Clase profesional para procesar videos.
    Combina la potencia de FFmpeg y la eficiencia de HandBrakeCLI.
    """
    
    @staticmethod
    def _escape_path(path):
        """Escapa rutas para que FFmpeg/HandBrake no fallen con caracteres especiales."""
        p = str(path).replace('\\', '/').replace(':', '\\:').replace("'", r"\'")
        return f"'{p}'"

    @staticmethod
    def probe_media(input_path):
        """Analiza el archivo usando FFprobe."""
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
            
            return info
        except Exception as e:
            logger.error(f"❌ Error en probe_media: {e}")
            return None

    @staticmethod
    def compress_to_360p(input_path, output_path, encoder='x264', quality=25):
        """
        USA HANDBRAKE para comprimir a 360p.
        Ideal para reducir tamaño manteniendo máxima compatibilidad.
        """
        logger.info(f"⚙️ Comprimiendo a 360p con HandBrake: {input_path}")
        
        cmd = [
            'HandBrakeCLI',
            '-i', str(input_path),
            '-o', str(output_path),
            '-e', encoder,            # 'x264' o 'x265'
            '-q', str(quality),       # Calidad (20-25 es ideal)
            '--preset', 'veryfast',
            '-w', '640',              # Ancho 360p
            '-l', '360',              # Alto 360p
            '--keep-display-aspect',
            '--modulus', '2',
            '-a', '1',                # Primer track de audio
            '-E', 'av_aac',           # Audio en AAC
            '-B', '128',              # Bitrate audio
            '--mixdown', 'stereo',
            '--optimize'              # Web Optimized (Fast Start)
        ]

        try:
            # HandBrake envía el progreso a stderr
            process = subprocess.run(cmd, capture_output=True, text=True)
            if process.returncode != 0:
                logger.error(f"❌ HandBrake falló: {process.stderr}")
                return False
            logger.info(f"✅ Compresión completada: {output_path}")
            return True
        except Exception as e:
            logger.error(f"❌ Error en proceso HandBrake: {e}")
            return False

    @staticmethod
    def burn_subtitles_with_watermark(video_path, output_path, sub_idx=0):
        """
        USA FFMPEG para quemar subtítulos y marca de agua (HandBrake es limitado aquí).
        Mantiene los 360p si el input ya lo es.
        """
        logger.info(f"📝 Quemando subtítulos y marca de agua con FFmpeg")
        
        vid_p = VideoProcessor._escape_path(video_path)
        
        sub_filter = f"subtitles={vid_p}:si={sub_idx}"
        sub_style = (
            "force_style='Fontname=sans,FontSize=18,Bold=1,"
            "PrimaryColour=&HFFFFFF,OutlineColour=&HAABB00,"      
            "BorderStyle=1,Outline=2.0,Shadow=1.0,MarginV=20'"
        )

        watermark = (
            "drawtext=text='CID':x=20:y=20:font='sans':fontsize=20:"
            "fontcolor=white:bordercolor=black:borderw=1.5:enable='lt(t,6)'" 
        )

        full_vf = f"{watermark},{sub_filter}:{sub_style}"

        cmd = [
            'ffmpeg', '-y', '-i', str(video_path),
            '-vf', full_vf,
            '-c:v', 'libx264', '-crf', '26', '-preset', 'veryfast',
            '-c:a', 'copy', # Copiamos el audio para no re-procesar
            str(output_path)
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except Exception as e:
            logger.error(f"❌ Error quemando subtítulos: {e}")
            return False

    @staticmethod
    def extract_audio(video_path, output_path):
        """Extrae el audio en MP3 usando FFmpeg."""
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

# --- EJEMPLO DE USO ---
if __name__ == "__main__":
    vp = VideoProcessor()
    input_file = "mi_video_4k.mp4"
    temp_360p = "video_360p_base.mp4"
    final_file = "resultado_final_360p.mp4"

    # 1. Comprimir a 360p con HandBrake (Rápido y eficiente)
    if vp.compress_to_360p(input_file, temp_360p):
        # 2. Quemar subtítulos y marca de agua sobre el archivo ya pequeño
        vp.burn_subtitles_with_watermark(temp_360p, final_file, sub_idx=0)
        print("🚀 Proceso terminado con éxito")
                
