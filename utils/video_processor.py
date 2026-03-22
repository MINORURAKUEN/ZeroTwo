"""
VideoProcessor - Clase mejorada para procesar videos con FFmpeg
Soporte para: MKV, AVI, ISO, Subdrips (pistas forzadas) y selección de canales.
Actualización: Estilo visual optimizado y corrección de índices de subtítulos.
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
        Usa un contador independiente para los subtítulos (necesario para el filtro si).
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
            sub_count = 0  # Contador relativo para pistas de subtítulos
            
            for stream in data.get('streams', []):
                s_index = stream.get('index')
                s_type = stream.get('codec_type')
                lang = stream.get('tags', {}).get('language', 'und').upper()
                title = stream.get('tags', {}).get('title', 'Pista')
                
                # Detectar si es Subdrip o pista Forzada
                disposition = stream.get('disposition', {})
                is_forced = disposition.get('forced', 0) == 1
                suffix = " (FORZADO/SUBDRIP)" if is_forced else ""

                if s_type == 'audio':
                    info['audio'].append({
                        'index': s_index,
                        'label': f"🔊 {lang} - {title}"
                    })
                elif s_type == 'subtitle':
                    # IMPORTANTE: Para el filtro 'subtitles', usamos sub_count (0, 1, 2...)
                    info['subtitle'].append({
                        'index': sub_count,
                        'label': f"📝 [{sub_count}] {lang} {suffix}"
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
        Quema subtítulos con estilo personalizado:
        - Texto: Blanco
        - Borde: Azul Claro
        - Fondo: Transparente (Sin recuadro negro)
        """
        logger.info(f"📝 Iniciando quemado de subtítulos")
        
        video_escaped = str(video_path).replace('\\', '/').replace(':', '\\:')
        
        if is_external and external_sub_path:
            sub_path_escaped = str(external_sub_path).replace('\\', '/').replace(':', '\\:')
            sub_filter = f"subtitles='{sub_path_escaped}'"
        else:
            # Selecciona la pista interna exacta usando el índice relativo
            sub_filter = f"subtitles='{video_escaped}':si={sub_idx}"

        # --- ESTILO ACTUALIZADO ---
        # PrimaryColour: Blanco (&HFFFFFF)
        # OutlineColour: Azul Claro (&HAABB00 en formato BGR)
        # BorderStyle=1: Contorno simple (sin fondo negro)
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
            '-map', '0:v:0',           # Video original
            *audio_map,                # Audio elegido
            '-vf', f"{sub_filter}:{style}",
            '-c:v', 'libx264', '-crf', '20', '-preset', 'veryfast',
            '-c:a', 'aac', '-b:a', '128k',
            '-movflags', '+faststart',
            output_path
        ]

        try:
            logger.info(f"🚀 Ejecutando quema: Audio {audio_idx}, Sub {sub_idx}")
            process = subprocess.run(cmd, capture_output=True, text=True)
            
            if process.returncode != 0:
                logger.error(f"❌ FFmpeg Error: {process.stderr}")
                return False
                
            return True
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
            
