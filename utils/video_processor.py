import json
import logging
import subprocess
from pathlib import Path

# Configuración de logging para Termux
logger = logging.getLogger(__name__)

class VideoProcessor:
    """
    Clase profesional para procesar videos.
    Actualizada para usar HandBrakeCLI manteniendo compatibilidad con nombres antiguos.
    """
    
    @staticmethod
    def _escape_path(path):
        """Escapa rutas para evitar errores con espacios o caracteres especiales."""
        p = str(path).replace('\\', '/').replace(':', '\\:').replace("'", r"\'")
        return f"'{p}'"

    @staticmethod
    def probe_media(input_path):
        """Analiza el archivo usando FFprobe para detectar pistas e idiomas."""
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
    def compress_video_resolution(input_path, output_path, scale='640:360', bitrate='800k', crf='25', preset='veryfast'):
        """
        Mantiene el nombre original solicitado por el handler.
        Ahora utiliza HandBrakeCLI para una compresión superior a 360p.
        """
        logger.info(f"⚙️ Comprimiendo a 360p con HandBrakeCLI: {input_path}")
        
        # HandBrakeCLI usa -w para ancho y -l para alto. 
        # Si scale es '640:360', extraemos los valores:
        try:
            width, height = scale.split(':')
        except:
            width, height = '640', '360'

        cmd = [
            'HandBrakeCLI',
            '-i', str(input_path),
            '-o', str(output_path),
            '-e', 'x264',             # Encoder H.264
            '-q', str(crf),           # Calidad (CRF)
            '--preset', preset,
            '-w', width,
            '-l', height.replace('-1', '360'), # Asegura 360 si viene como -1
            '--keep-display-aspect',
            '--modulus', '2',
            '-a', '1',                # Primer pista de audio
            '-E', 'av_aac',           # Encoder AAC
            '-B', '128',              # Bitrate Audio
            '--mixdown', 'stereo',
            '--optimize'              # Optimización para Telegram (Fast Start)
        ]

        try:
            # Ejecutamos HandBrake
            process = subprocess.run(cmd, capture_output=True, text=True)
            if process.returncode != 0:
                logger.error(f"❌ HandBrake falló: {process.stderr}")
                return False
            return True
        except Exception as e:
            logger.error(f"❌ Error en compresión: {e}")
            return False

    @staticmethod
    def burn_subtitles(video_path, output_path, audio_idx=None, sub_idx=None, is_external=False, external_sub_path=None):
        """
        Quema subtítulos y agrega la marca de agua 'CID' temporal.
        Se usa FFmpeg aquí por su flexibilidad con filtros de texto.
        """
        logger.info(f"📝 Iniciando quemado con marca de agua (CID)")
        
        if is_external and external_sub_path:
            sub_p = VideoProcessor._escape_path(external_sub_path)
            sub_filter = f"subtitles={sub_p}"
        else:
            vid_p = VideoProcessor._escape_path(video_path)
            sub_filter = f"subtitles={vid_p}:si={sub_idx}"

        sub_style = (
            "force_style='Fontname=sans,FontSize=20,Bold=1,"
            "PrimaryColour=&HFFFFFF,OutlineColour=&HAABB00,"      
            "BorderStyle=1,Outline=2.0,Shadow=1.0,MarginV=25'"
        )

        # Marca de agua que desaparece a los 6 segundos
        watermark = (
            "drawtext=text='CID':x=20:y=20:font='sans':fontsize=22:"
            "fontcolor=white:bordercolor=black:borderw=1.5:enable='lt(t,6)'" 
        )

        full_vf = f"{watermark},{sub_filter}:{sub_style}"
        audio_map = ["-map", f"0:{audio_idx}"] if audio_idx is not None else ["-map", "0:a:0"]

        cmd = [
            'ffmpeg', '-y', '-i', str(video_path),
            '-map', '0:v:0', *audio_map,
            '-vf', full_vf,
            '-c:v', 'libx264', '-crf', '26', '-preset', 'veryfast',
            '-c:a', 'aac', '-b:a', '128k',
            '-movflags', '+faststart'
        ]
        
        # Si el input ya fue comprimido a 360p, este proceso será muy rápido
        cmd.append(str(output_path))

        try:
            process = subprocess.run(cmd, capture_output=True, text=True)
            if process.returncode != 0:
                logger.error(f"❌ FFmpeg falló: {process.stderr}")
                return False
            return True
        except Exception as e:
            logger.error(f"❌ Error en quemado de subtítulos: {e}")
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
        
