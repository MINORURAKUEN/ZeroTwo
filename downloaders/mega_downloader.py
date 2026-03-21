"""
MEGADownloader - Descarga archivos de MEGA usando megatools
"""

import re
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class MEGADownloader:
    """Clase para descargar archivos de MEGA con progreso en tiempo real"""
    
    @staticmethod
    def is_mega_url(url):
        """Verifica si es una URL de MEGA"""
        mega_patterns = [r'mega\.nz', r'mega\.co\.nz']
        return any(re.search(pattern, url, re.IGNORECASE) for pattern in mega_patterns)
    
    @staticmethod
    async def download(url, output_dir, progress_callback=None):
        """Descarga archivo de MEGA usando megatools con monitoreo mejorado"""
        try:
            logger.info("🔷 Iniciando descarga desde MEGA")
            
            # Verificar que megatools esté instalado
            check_cmd = ['megadl', '--version']
            result = subprocess.run(check_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error("❌ megatools no está instalado")
                return False, None, "❌ megatools no está instalado.\nInstala con: pkg install megatools"
            
            if progress_callback:
                await progress_callback("📥 Descargando de MEGA...")
            
            logger.info(f"📥 URL: {url}")
            
            # Comando de descarga con opciones mejoradas
            cmd = [
                'megadl',
                '--path', str(output_dir),
                '--print-names',
                '--no-progress',  # Desactivar barra de progreso de megadl
                url
            ]
            
            logger.info(f"🔧 Ejecutando: megadl --path {output_dir} [URL]")
            logger.info("⏳ Descargando desde MEGA...")
            
            # Ejecutar comando
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            # Monitorear salida en tiempo real
            filename = None
            for line in process.stdout:
                line = line.strip()
                if line:
                    logger.info(f"[MEGA] {line}")
                    
                    # Capturar nombre del archivo
                    if not filename and line and not line.startswith('ERROR'):
                        filename = line
            
            process.wait()
            
            if process.returncode == 0:
                # Buscar el archivo descargado
                files = list(output_dir.glob('*'))
                if files:
                    latest_file = max(files, key=lambda p: p.stat().st_mtime)
                    file_size = latest_file.stat().st_size / (1024 * 1024)
                    
                    logger.info(f"✅ Descarga MEGA completada")
                    logger.info(f"📁 Archivo: {latest_file.name}")
                    logger.info(f"📦 Tamaño: {file_size:.2f} MB")
                    
                    return True, latest_file, None
                else:
                    logger.error("❌ Archivo no encontrado después de la descarga")
                    return False, None, "❌ Archivo no encontrado"
            else:
                logger.error(f"❌ Error en megadl: código {process.returncode}")
                return False, None, "❌ Error descargando de MEGA"
            
        except Exception as e:
            logger.error(f"❌ Error en descarga MEGA: {e}", exc_info=True)
            return False, None, f"❌ Error: {str(e)}"
