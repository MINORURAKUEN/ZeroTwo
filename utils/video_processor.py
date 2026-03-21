"""
VideoProcessor - Clase para procesar videos con FFmpeg
"""

import re
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class VideoProcessor:
    """Clase para procesar videos usando FFmpeg"""
    
    @staticmethod
    def compress_video_resolution(input_path, output_path, scale=None, bitrate='2000k', crf='23', preset='medium', max_size_mb=None):
        """
        Comprime un video con resolución específica
        scale: '640:360' para 360p, '1280:720' para 720p, None para mantener original
        """
        logger.info(f"🎬 Iniciando compresión de video con resolución")
        logger.info(f"📁 Entrada: {input_path}")
        logger.info(f"📁 Salida: {output_path}")
        logger.info(f"📺 Resolución: {scale if scale else 'Original'}")
        logger.info(f"📊 Bitrate: {bitrate}, CRF: {crf}, Preset: {preset}")
        
        # Construir comando base
        cmd = ['ffmpeg', '-i', input_path]
        
        # Si hay escala, agregar filtro de video con mejor calidad
        if scale:
            # Para 360p usar algoritmo de escala Lanczos (mejor calidad) + optimizaciones
            if '360' in scale:
                cmd.extend([
                    '-vf', f'scale={scale}:force_original_aspect_ratio=decrease:flags=lanczos,pad={scale}:(ow-iw)/2:(oh-ih)/2',
                    '-c:v', 'libx264',
                    '-crf', crf,  # CRF 26 = buena calidad con bajo peso
                    '-preset', preset,
                    '-b:v', bitrate,
                    '-maxrate', bitrate,
                    '-bufsize', '900k',
                    '-profile:v', 'main',  # Perfil main para mejor calidad que baseline
                    '-level', '3.1',
                    '-pix_fmt', 'yuv420p'  # Compatibilidad universal
                ])
            else:
                cmd.extend([
                    '-vf', f'scale={scale}:force_original_aspect_ratio=decrease:flags=lanczos,pad={scale}:(ow-iw)/2:(oh-ih)/2',
                    '-c:v', 'libx264',
                    '-crf', crf,
                    '-preset', preset,
                    '-b:v', bitrate
                ])
        else:
            # Sin escala, solo recodificar
            cmd.extend([
                '-c:v', 'libx264',
                '-crf', crf,
                '-preset', preset,
                '-b:v', bitrate
            ])
        
        # Audio optimizado
        if '360' in str(scale):
            cmd.extend(['-c:a', 'aac', '-b:a', '96k', '-ar', '44100'])  # Audio comprimido pero con calidad
        else:
            cmd.extend(['-c:a', 'aac', '-b:a', '128k'])
        
        # Opciones generales
        cmd.extend(['-movflags', '+faststart', '-y', output_path])
        
        logger.info(f"🔧 Comando FFmpeg: {' '.join(cmd[:15])}...")
        
        try:
            logger.info("⏳ Procesando video...")
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            line_count = 0
            for line in process.stderr:
                # Mostrar progreso de FFmpeg de forma más limpia
                if 'time=' in line:
                    line_count += 1
                    # Mostrar solo cada 30 líneas (aprox. cada 5-10%)
                    if line_count % 30 == 0:
                        time_match = re.search(r'time=(\S+)', line)
                        if time_match:
                            logger.info(f"⚙️ Procesando: {time_match.group(1)}")
                elif 'error' in line.lower():
                    logger.error(f"❌ {line.strip()}")
            
            process.wait()
            
            if process.returncode != 0:
                logger.error(f"❌ Error en compresión: código {process.returncode}")
                return False
            
            # Mostrar tamaño final
            output_size_mb = Path(output_path).stat().st_size / (1024 * 1024)
            logger.info(f"📦 Tamaño final: {output_size_mb:.2f} MB")
            logger.info("✅ Video comprimido exitosamente")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error comprimiendo video: {e}")
            return False
    
    @staticmethod
    def add_thumbnail_fast(video_path, thumbnail_path, output_path):
        """Añade una portada al video SIN recodificar (ultra rápido)"""
        logger.info(f"🖼️ Iniciando añadido de portada (método rápido)")
        logger.info(f"📁 Video: {video_path}")
        logger.info(f"📁 Imagen: {thumbnail_path}")
        logger.info(f"📁 Salida: {output_path}")
        
        # Método optimizado: Solo copia streams y añade portada
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-i', thumbnail_path,
            '-map', '0',           # Mapear todo del video original
            '-map', '1',           # Mapear la imagen
            '-c', 'copy',          # Copiar sin recodificar
            '-disposition:v:0', 'default',  # Video principal
            '-disposition:v:1', 'attached_pic',  # Thumbnail
            '-metadata:s:v:1', 'comment=Cover (front)',
            '-y',
            output_path
        ]
        
        logger.info(f"🔧 Comando FFmpeg (ultra rápido - sin recodificar)")
        
        try:
            logger.info("⚡ Añadiendo portada (esto solo toma segundos)...")
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                stderr=subprocess.PIPE, 
                timeout=60  # Solo 60 segundos, es muy rápido
            )
            
            if result.returncode == 0:
                logger.info("✅ Portada añadida exitosamente en pocos segundos!")
                return True
            else:
                logger.error(f"❌ Error añadiendo portada: código {result.returncode}")
                stderr = result.stderr.decode()[:500]
                logger.error(f"FFmpeg stderr: {stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("❌ Timeout añadiendo portada")
            return False
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            return False
    
    @staticmethod
    def burn_subtitles(video_path, subtitle_path, output_path):
        """Quema subtítulos en el video con alta calidad y estilo personalizado"""
        logger.info(f"📝 Iniciando quemado de subtítulos")
        logger.info(f"📁 Video: {video_path}")
        logger.info(f"📁 Subtítulos: {subtitle_path}")
        logger.info(f"📁 Salida: {output_path}")
        
        subtitle_path_escaped = subtitle_path.replace('\\', '\\\\').replace(':', '\\:')
        
        # Comando con subtítulos estilizados de alta calidad
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-vf', (
                f"subtitles='{subtitle_path_escaped}':"
                "force_style='"
                "PrimaryColour=&H00FFFFFF,"  # Blanco
                "OutlineColour=&H00000000,"  # Negro para borde
                "BackColour=&H80000000,"     # Fondo semi-transparente
                "BorderStyle=3,"             # Borde + sombra
                "Outline=2.5,"               # Borde grueso
                "Shadow=1.5,"                # Sombra pronunciada
                "MarginV=25,"                # Margen vertical
                "Fontsize=24,"               # Tamaño de fuente
                "Bold=1"                     # Negrita
                "'"
            ),
            '-c:v', 'libx264',
            '-preset', 'medium',        # Balance calidad/velocidad
            '-crf', '20',               # Alta calidad visual
            '-profile:v', 'high',       # Perfil alto
            '-level', '4.1',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-ac', '2',
            '-movflags', '+faststart',
            '-threads', '0',            # Usar todos los cores
            '-y',
            output_path
        ]
        
        logger.info(f"🔧 Comando FFmpeg optimizado para subtítulos")
        logger.info(f"💡 Usando preset 'medium' para mejor calidad")
        
        try:
            logger.info("⏳ Quemando subtítulos con alta calidad...")
            
            # Obtener total de frames para progreso
            probe_cmd = [
                'ffprobe', '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=nb_frames',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                video_path
            ]
            
            probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
            total_frames = int(probe_result.stdout.strip()) if probe_result.returncode == 0 and probe_result.stdout.strip() else 0
            
            if total_frames > 0:
                logger.info(f"🎬 Total de frames: {total_frames}")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            # Monitorear progreso con detalles
            line_count = 0
            for line in process.stderr:
                if 'frame=' in line:
                    line_count += 1
                    
                    # Extraer información del progreso
                    frame_match = re.search(r'frame=\s*(\d+)', line)
                    fps_match = re.search(r'fps=\s*([\d.]+)', line)
                    time_match = re.search(r'time=\s*([\d:.]+)', line)
                    speed_match = re.search(r'speed=\s*([\d.]+)x', line)
                    
                    if frame_match and line_count % 30 == 0:  # Cada 30 líneas
                        frame = int(frame_match.group(1))
                        fps = fps_match.group(1) if fps_match else '0'
                        time = time_match.group(1) if time_match else '00:00:00'
                        speed = speed_match.group(1) if speed_match else '0'
                        
                        if total_frames > 0:
                            percent = int((frame / total_frames) * 100)
                            logger.info(
                                f"⚙️ Progreso: {percent}% | "
                                f"Frame: {frame}/{total_frames} | "
                                f"FPS: {fps} | "
                                f"Time: {time} | "
                                f"Speed: {speed}x"
                            )
                        else:
                            logger.info(f"⚙️ Frame: {frame} | FPS: {fps} | Time: {time}")
                
                elif 'error' in line.lower() and 'error' not in line.lower().split()[0]:
                    logger.warning(f"⚠️ FFmpeg: {line.strip()}")
            
            process.wait()
            
            if process.returncode == 0:
                output_size_mb = Path(output_path).stat().st_size / (1024 * 1024)
                logger.info(f"✅ Subtítulos quemados exitosamente")
                logger.info(f"📦 Tamaño final: {output_size_mb:.2f} MB")
                return True
            else:
                logger.error(f"❌ Error quemando subtítulos: código {process.returncode}")
                return False
            
        except Exception as e:
            logger.error(f"❌ Error: {e}", exc_info=True)
            return False
    
    @staticmethod
    def extract_audio(video_path, output_path):
        """Extrae el audio de un video"""
        logger.info(f"🎵 Iniciando extracción de audio")
        logger.info(f"📁 Video: {video_path}")
        logger.info(f"📁 Audio salida: {output_path}")
        
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-vn',
            '-acodec', 'libmp3lame',
            '-b:a', '192k',
            '-y',
            output_path
        ]
        
        logger.info(f"🔧 Comando FFmpeg: {' '.join(cmd)}")
        
        try:
            logger.info("⏳ Extrayendo audio...")
            result = subprocess.run(cmd, capture_output=True)
            
            if result.returncode == 0:
                audio_size = Path(output_path).stat().st_size / (1024 * 1024)
                logger.info(f"✅ Audio extraído exitosamente ({audio_size:.2f} MB)")
            else:
                logger.error(f"❌ Error extrayendo audio: código {result.returncode}")
                logger.error(f"FFmpeg stderr: {result.stderr.decode()[:500]}")
            
            return result.returncode == 0
        except Exception as e:
            logger.error(f"❌ Error extrayendo audio: {e}")
            return False
