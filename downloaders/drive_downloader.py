"""
drive_downloader.py - Descarga y subida a Google Drive con progreso y screenshots
Requiere: google-auth-oauthlib google-api-python-client
"""

import io
import json
import logging
import os
import subprocess
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Importación opcional de las librerías de Google ───────────────────────────
try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    logger.warning("⚠️ google-api-python-client no instalado. "
                   "Ejecuta: pip install google-auth-oauthlib google-api-python-client")

SCOPES = ['https://www.googleapis.com/auth/drive']

# Ruta del token y credenciales (junto al módulo)
_BASE = Path(__file__).parent
TOKEN_PATH  = _BASE / 'drive_token.json'
CREDS_PATH  = _BASE / 'drive_credentials.json'


def _get_service():
    """Devuelve un cliente autenticado de Google Drive API v3."""
    if not GOOGLE_AVAILABLE:
        raise RuntimeError("Instala: pip install google-auth-oauthlib google-api-python-client")
    if not CREDS_PATH.exists():
        raise FileNotFoundError(
            f"No se encontró {CREDS_PATH}.\n"
            "Descarga tu credentials.json desde Google Cloud Console y renómbralo."
        )

    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())

    return build('drive', 'v3', credentials=creds)


def _extract_file_id(url_or_id: str) -> str:
    """Extrae el ID de archivo de una URL de Drive o lo devuelve tal cual."""
    import re
    patterns = [
        r'/file/d/([a-zA-Z0-9_-]+)',
        r'id=([a-zA-Z0-9_-]+)',
        r'^([a-zA-Z0-9_-]{25,})$',
    ]
    for pat in patterns:
        m = re.search(pat, url_or_id)
        if m:
            return m.group(1)
    return url_or_id


def _take_screenshot(video_path: Path, timestamp: str, output_path: Path) -> bool:
    """Captura un fotograma del video en el timestamp indicado."""
    try:
        cmd = [
            'ffmpeg', '-y',
            '-ss', timestamp,
            '-i', str(video_path),
            '-vframes', '1',
            '-q:v', '2',
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        return result.returncode == 0 and output_path.exists()
    except Exception as e:
        logger.warning(f"⚠️ Screenshot en {timestamp} falló: {e}")
        return False


def _get_video_duration(video_path: Path) -> float:
    """Devuelve la duración en segundos del video, o 0.0 si falla."""
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            str(video_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def _seconds_to_ts(seconds: float) -> str:
    """Convierte segundos a HH:MM:SS.mmm para ffmpeg."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


async def take_video_screenshots(video_path: Path, work_dir: Path, prefix: str = "shot") -> list[Path]:
    """
    Captura 5 screenshots del video en:
      inicio(5%), cuarto(25%), mitad(50%), tres cuartos(75%), casi final(95%)
    Devuelve lista de paths generados.
    """
    duration = _get_video_duration(video_path)
    if duration < 5:
        logger.warning("⚠️ Video demasiado corto para screenshots")
        return []

    positions = {
        "inicio":      0.05,
        "cuarto":      0.25,
        "mitad":       0.50,
        "tres_cuartos":0.75,
        "final":       0.95,
    }

    shots = []
    for name, ratio in positions.items():
        ts = _seconds_to_ts(duration * ratio)
        out = work_dir / f"{prefix}_{name}.jpg"
        if _take_screenshot(video_path, ts, out):
            shots.append(out)
            logger.info(f"📸 Screenshot '{name}' en {ts}: OK")
        else:
            logger.warning(f"⚠️ Screenshot '{name}' en {ts}: falló")

    return shots


class DriveDownloader:
    """Descarga archivos desde Google Drive con barra de progreso."""

    @staticmethod
    def is_drive_url(url: str) -> bool:
        import re
        return bool(re.search(r'drive\.google\.com|docs\.google\.com', url, re.IGNORECASE))

    @staticmethod
    async def get_file_info(url_or_id: str) -> dict | None:
        """Retorna metadatos del archivo: id, name, mimeType, size."""
        try:
            service = _get_service()
            file_id = _extract_file_id(url_or_id)
            meta = service.files().get(
                fileId=file_id,
                fields='id,name,mimeType,size,webViewLink'
            ).execute()
            return meta
        except Exception as e:
            logger.error(f"❌ Error obteniendo info de Drive: {e}")
            return None

    @staticmethod
    async def download(url_or_id: str, output_dir: Path, progress_callback=None) -> tuple[bool, Path | None, str | None]:
        """
        Descarga un archivo de Google Drive.

        progress_callback(text) → actualiza el mensaje de Telegram.
        Retorna (success, file_path, error_msg).
        """
        try:
            service = _get_service()
            file_id = _extract_file_id(url_or_id)

            # Obtener metadatos
            meta = service.files().get(
                fileId=file_id,
                fields='id,name,size'
            ).execute()
            filename  = meta.get('name', 'drive_file')
            total_bytes = int(meta.get('size', 0))
            total_mb    = total_bytes / (1024 * 1024) if total_bytes else 0

            logger.info(f"📥 Drive: descargando '{filename}' ({total_mb:.1f} MB)")
            if progress_callback:
                await progress_callback(
                    f"📥 <b>Descargando de Drive</b>\n"
                    f"📄 {filename}\n"
                    f"📦 {total_mb:.1f} MB\n"
                    f"⏳ Iniciando..."
                )

            output_path = output_dir / filename
            request = service.files().get_media(fileId=file_id)
            fh = io.FileIO(str(output_path), 'wb')
            downloader = MediaIoBaseDownload(fh, request, chunksize=8 * 1024 * 1024)

            last_reported = -10
            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    pct = int(status.progress() * 100)
                    downloaded_mb = (status.resumable_progress or 0) / (1024 * 1024)

                    logger.info(f"📥 Drive {pct}% — {downloaded_mb:.1f}/{total_mb:.1f} MB")

                    if pct - last_reported >= 10 and progress_callback:
                        bar = _progress_bar(pct)
                        await progress_callback(
                            f"📥 <b>Descargando de Drive</b>\n"
                            f"📄 {filename}\n"
                            f"{bar} {pct}%\n"
                            f"💾 {downloaded_mb:.1f} / {total_mb:.1f} MB"
                        )
                        last_reported = pct

            fh.close()
            file_size = output_path.stat().st_size / (1024 * 1024)
            logger.info(f"✅ Drive descargado: {filename} ({file_size:.1f} MB)")
            return True, output_path, None

        except Exception as e:
            logger.error(f"❌ Error descargando de Drive: {e}", exc_info=True)
            return False, None, str(e)


class DriveUploader:
    """Sube archivos a Google Drive con barra de progreso."""

    @staticmethod
    async def upload(
        file_path: Path,
        folder_id: str | None = None,
        mime_type: str = 'application/octet-stream',
        progress_callback=None,
    ) -> tuple[bool, dict | None, str | None]:
        """
        Sube un archivo a Google Drive.

        progress_callback(text) → actualiza el mensaje de Telegram.
        Retorna (success, file_info_dict, error_msg).
        """
        try:
            service   = _get_service()
            filename  = file_path.name
            total_mb  = file_path.stat().st_size / (1024 * 1024)

            logger.info(f"📤 Drive: subiendo '{filename}' ({total_mb:.1f} MB)")
            if progress_callback:
                await progress_callback(
                    f"📤 <b>Subiendo a Drive</b>\n"
                    f"📄 {filename}\n"
                    f"📦 {total_mb:.1f} MB\n"
                    f"⏳ Iniciando..."
                )

            metadata = {'name': filename}
            if folder_id:
                metadata['parents'] = [folder_id]

            media = MediaFileUpload(
                str(file_path),
                mimetype=mime_type,
                resumable=True,
                chunksize=8 * 1024 * 1024,
            )

            request = service.files().create(
                body=metadata,
                media_body=media,
                fields='id,name,webViewLink',
            )

            last_reported = -10
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    pct = int(status.progress() * 100)
                    uploaded_mb = (status.resumable_progress or 0) / (1024 * 1024)

                    logger.info(f"📤 Drive {pct}% — {uploaded_mb:.1f}/{total_mb:.1f} MB")

                    if pct - last_reported >= 10 and progress_callback:
                        bar = _progress_bar(pct)
                        await progress_callback(
                            f"📤 <b>Subiendo a Drive</b>\n"
                            f"📄 {filename}\n"
                            f"{bar} {pct}%\n"
                            f"💾 {uploaded_mb:.1f} / {total_mb:.1f} MB"
                        )
                        last_reported = pct

            logger.info(f"✅ Drive subida completa: {response.get('webViewLink', '')}")
            return True, response, None

        except Exception as e:
            logger.error(f"❌ Error subiendo a Drive: {e}", exc_info=True)
            return False, None, str(e)


# ── Utilidad compartida ────────────────────────────────────────────────────────

def _progress_bar(pct: int, width: int = 10) -> str:
    """Genera una barra de progreso visual con emojis."""
    filled = int(width * pct / 100)
    empty  = width - filled
    return '▓' * filled + '░' * empty
