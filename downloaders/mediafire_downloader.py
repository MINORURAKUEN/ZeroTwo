"""
MediaFireDownloader - Descarga archivos de MediaFire
"""

import re
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class MediaFireDownloader:
    """Clase para descargar archivos de MediaFire"""
    
    @staticmethod
    def is_mediafire_url(url):
        """Verifica si es una URL de MediaFire"""
        return bool(re.search(r'mediafire\.com', url, re.IGNORECASE))
    
    @staticmethod
    async def get_direct_link(url):
        """Obtiene el enlace directo de descarga de MediaFire (método mejorado)"""
        try:
            logger.info("🌐 Parseando página de MediaFire...")
            
            # Obtener página con User-Agent
            cmd = ['curl', '-s', '-L', '-A', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', url]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                logger.error("❌ Error obteniendo página de MediaFire")
                return None, None
            
            html = result.stdout
            
            # Patrón 1: Buscar botón de descarga (#downloadButton)
            download_button_match = re.search(r'<a[^>]*id="downloadButton"[^>]*href="([^"]+)"', html)
            if download_button_match:
                direct_url = download_button_match.group(1)
                logger.info(f"✅ Enlace encontrado (downloadButton): {direct_url[:80]}...")
            else:
                # Patrón 2: Buscar enlace de descarga directa
                direct_match = re.search(r'href="(https://download\d+\.mediafire\.com[^"]+)"', html)
                if direct_match:
                    direct_url = direct_match.group(1)
                    logger.info(f"✅ Enlace encontrado (regex): {direct_url[:80]}...")
                else:
                    logger.error("❌ No se encontró enlace de descarga")
                    return None, None
            
            # Obtener nombre del archivo
            filename = None
            
            # Patrón 1: promoDownloadName
            name_match1 = re.search(r'<div[^>]*class="[^"]*promoDownloadName[^"]*"[^>]*title="([^"]+)"', html)
            if name_match1:
                filename = name_match1.group(1)
            else:
                # Patrón 2: filename class
                name_match2 = re.search(r'<div[^>]*class="[^"]*filename[^"]*"[^>]*>([^<]+)', html)
                if name_match2:
                    filename = name_match2.group(1).strip()
                else:
                    # Extraer del URL
                    url_name_match = re.search(r'/file/[^/]+/([^/]+)/', url)
                    if url_name_match:
                        filename = url_name_match.group(1)
                    else:
                        filename = 'mediafire_file'
            
            # Limpiar nombre
            filename = re.sub(r'\s+', ' ', filename).strip()
            filename = re.sub(r'[^\w\s\-\.]', '_', filename)
            
            logger.info(f"📁 Nombre del archivo: {filename}")
            
            return direct_url, filename
            
        except Exception as e:
            logger.error(f"❌ Error parseando MediaFire: {e}")
            return None, None
    
    @staticmethod
    async def download(url, output_dir, progress_callback=None):
        """Descarga archivo de MediaFire con monitoreo mejorado"""
        try:
            if progress_callback:
                await progress_callback("🔍 Obteniendo enlace de descarga...")
            
            logger.info("🌐 Obteniendo enlace de MediaFire...")
            direct_url, filename = await MediaFireDownloader.get_direct_link(url)
            
            if not direct_url or not filename:
                return False, None, "❌ No se pudo obtener el enlace de descarga"
            
            output_path = output_dir / filename
            logger.info(f"📁 Descargando: {filename}")
            logger.info(f"📥 Desde: {direct_url[:80]}...")
            
            if progress_callback:
                await progress_callback(f"⬇️ Descargando: {filename}")
            
            # Usar wget con parámetros optimizados para velocidad
            wget_cmd = [
                'wget',
                '-O', str(output_path),
                '--progress=dot:giga',  # Menos verboso, más rápido
                '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                '--no-check-certificate',
                '--timeout=30',  # Timeout de 30 segundos
                '--tries=3',  # 3 intentos
                '--continue',  # Continuar descarga si se interrumpe
                direct_url
            ]
            
            curl_cmd = [
                'curl',
                '-L',
                '-C', '-',  # Continuar descarga
                '-A', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                '-o', str(output_path),
                '--speed-limit', '1000',  # Velocidad mínima 1KB/s
                '--speed-time', '30',  # Timeout si está por debajo de velocidad mínima
                direct_url
            ]
            
            aria2c_cmd = [
                'aria2c',
                '-x', '16',  # 16 conexiones simultáneas
                '-s', '16',  # 16 servidores
                '-k', '1M',  # Fragmentos de 1MB
                '--file-allocation=none',
                '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                '--allow-overwrite=true',
                '--auto-file-renaming=false',
                '-d', str(output_dir),
                '-o', filename,
                direct_url
            ]
            
            # Intentar con aria2c primero (más rápido), luego wget, luego curl
            cmd = None
            downloader = None
            
            try:
                subprocess.run(['aria2c', '--version'], check=True, capture_output=True)
                cmd = aria2c_cmd
                downloader = "aria2c"
                logger.info("🚀 Usando aria2c para descarga rápida (16 conexiones)")
            except:
                try:
                    subprocess.run(['wget', '--version'], check=True, capture_output=True)
                    cmd = wget_cmd
                    downloader = "wget"
                    logger.info("📥 Usando wget para descargar")
                except:
                    cmd = curl_cmd
                    downloader = "curl"
                    logger.info("📥 Usando curl para descargar")
            
            logger.info("⏳ Iniciando descarga de MediaFire...")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            # Monitorear progreso en tiempo real (filtrado mejorado)
            last_percent = [0]
            for line in process.stdout:
                line = line.strip()
                if line:
                    # Para aria2c - mostrar solo cada 5%
                    if downloader == "aria2c" and "SPD:" in line:
                        percent_match = re.search(r'\((\d+)%\)', line)
                        if percent_match:
                            percent = int(percent_match.group(1))
                            if percent - last_percent[0] >= 5:
                                logger.info(f"📥 Descargando: {percent}%")
                                last_percent[0] = percent
                    # Para wget/curl - mostrar solo cada 10%
                    elif any(kw in line.lower() for kw in ['%', 'mb', 'kb']):
                        percent_match = re.search(r'(\d+)%', line)
                        if percent_match:
                            percent = int(percent_match.group(1))
                            if percent - last_percent[0] >= 10:
                                logger.info(f"📥 Descargando: {percent}%")
                                last_percent[0] = percent
                        elif 'saving' in line.lower() or 'mb' in line.lower():
                            logger.info(f"[MEDIAFIRE] {line}")
            
            process.wait()
            
            if process.returncode == 0 and output_path.exists():
                file_size = output_path.stat().st_size / (1024 * 1024)
                logger.info(f"✅ Descarga MediaFire completada")
                logger.info(f"📦 Tamaño: {file_size:.2f} MB")
                return True, output_path, None
            else:
                logger.error(f"❌ Error en descarga, código: {process.returncode}")
                return False, None, "❌ Error descargando de MediaFire"
            
        except Exception as e:
            logger.error(f"❌ Error descargando de MediaFire: {e}", exc_info=True)
            return False, None, f"❌ Error: {str(e)}"
