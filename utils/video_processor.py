"""
VideoProcessor - Clase mejorada para procesar videos con FFmpeg
Soporte para: MKV, AVI, ISO, Subdrips (pistas forzadas) y selección de canales.
"""

import re
import json
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

class VideoProcessor:
    """Clase para procesar videos usando FFmpeg con soporte multicanal"""
    
    @staticmethod
    def probe_media(input_path):
        """
        Analiza el archivo para detectar pistas de audio, subtítulos y subdrips.
        Ideal para archivos MKV, AVI e ISO.
        """
        logger.info(f"🔍 Analizando flujos de: {input_path}")
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_streams', '-show_format', input_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            
            info = {'audio': [], 'subtitle': []}
            
            for stream in data.get('streams', []):
                s_index = stream.get('index')
                s_type = stream.get('codec_type')
                lang = stream.get('tags', {}).get('language', 'und').upper()
                title = stream.get('tags', {}).get('title', 'Pista')
                
                # Detectar si es Subdrip o pista Forzada (disposition)
                disposition = stream.get('disposition', {})
                is_forced = disposition.get('forced', 0) == 1
                suffix = " (FORZADO/SUBDRIP)" if is_forced else ""

                if s_type == 'audio':
                    info['audio'].append({
                        'index': s_index,
                        'label': f"🔊 {lang} - {title}"
                    })
                elif s_type == 'subtitle':
                    info['subtitle'].append({
                        'index': s_index,
                        'label': f"📝 {lang} - {title}{suffix}"
                    })
            
            logger.info(f"✅ Análisis completo: {len(info['audio'])} audios, {len(info['subtitle'])} subs.")
            return info
        except Exception as e:
            logger.error(f"❌ Error en probe_media: {e}")
            return None

    @staticmethod
    def burn_subtitles(video_path, output_path, audio_idx=None, sub_idx=None, is_external=False, external_sub_path=None):
        """
        Quema subtítulos con alta calidad.
        Soporta pistas internas (MKV/AVI/ISO) o archivos externos (.srt/.ass).
        """
        logger.info(f"📝 Iniciando quemado de subtítulos")
        
        # Escapar rutas para el filtro de FFmpeg
        video_escaped = str(video_path).replace('\\', '/').replace(':', '\\:')
        
        # Configuración del filtro según el origen del subtítulo
        if is_external and external_sub_path:
            sub_path_escaped = str(external_sub_path).replace('\\', '/').replace(':', '\\:')
            sub_filter = f"subtitles='{sub_path_escaped}'"
        else:
            # Para pistas internas (Subdrips/MKV), usamos el índice si_index
            sub_filter = f"subtitles='{video_escaped}':si={sub_idx}"

        # Estilo visual optimizado para legibilidad (Blanco, borde negro, sombra)
        style = (
            "force_style='"
            "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
            "BackColour=&H80000000,BorderStyle=3,Outline=2.5,"
            "Shadow=1.5,MarginV=25,Fontsize=22,Bold=1'"
        )

        # Mapeo de pistas
        # Si no se especifica audio, FFmpeg elige el primero por defecto
        audio_map = ["-map", f"0:{audio_idx}"] if audio_idx is not None else ["-map", "0:a:0"]

        cmd = [
            'ffmpeg', '-i', video_path,
            '-map', '0:v:0',           # Mapear video principal
            *audio_map,                # Mapear audio elegido
            '-vf', f"{sub_filter}:{style}",
            '-c:v', 'libx264', '-crf', '20', '-preset', 'medium',
            '-c:a', 'aac', '-b:a', '128k',
            '-movflags', '+faststart', '-y', output_path
        ]

        try:
            logger.info(f"🚀 Ejecutando quema: Audio Index {audio_idx}, Sub Index {sub_idx}")
            process = subprocess.Popen(cmd, stderr=subprocess.PIPE, universal_newlines=True)
            
            for line in process.stderr:
                if 'time=' in line and 'frame=' in line:
                    # Log simplificado para no saturar
                    time_match = re.search(r'time=(\S+)', line)
                    if time_match:
                        # Se puede emitir este dato a un callback para la barra de progreso
                        pass 

            process.wait()
            return process.returncode == 0
        except Exception as e:
            logger.error(f"❌ Error quemando subtítulos: {e}")
            return False

    @staticmethod
    def compress_video_resolution(input_path, output_path, scale=None, bitrate='2000k', crf='23', preset='medium'):
        """Comprime video manteniendo la compatibilidad (ya implementado en tu código base)"""
        # ... (Tu código original de compresión se mantiene aquí) ...
        cmd = ['ffmpeg', '-i', input_path]
        if scale:
            cmd.extend(['-vf', f'scale={scale}:force_original_aspect_ratio=decrease:flags=lanczos,pad={scale}:(ow-iw)/2:(oh-ih)/2'])
        
        cmd.extend(['-c:v', 'libx264', '-crf', crf, '-preset', preset, '-b:v', bitrate, '-c:a', 'aac', '-b:a', '128k', '-y', output_path])
        
        try:
            subprocess.run(cmd, check=True)
            return True
        except:
            return False

    @staticmethod
    def extract_audio(video_path, output_path):
        """Extrae el audio en MP3 (ya implementado en tu código base)"""
        cmd = ['ffmpeg', '-i', video_path, '-vn', '-acodec', 'libmp3lame', '-b:a', '192k', '-y', output_path]
        try:
            subprocess.run(cmd, check=True)
            return True
        except:
            return False
                                           
