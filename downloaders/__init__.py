"""
Downloaders - Módulos para descargar de diferentes servicios
"""

from .mega_downloader import MEGADownloader
from .mediafire_downloader import MediaFireDownloader

# Solo exportamos los módulos que no dependen de las APIs de Google
__all__ = ['MEGADownloader', 'MediaFireDownloader']
