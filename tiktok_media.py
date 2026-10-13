"""Download de vídeos públicos do TikTok com yt-dlp.

Processa apenas URLs de vídeos previamente incluídas nos CSVs. Nunca recebe
URLs arbitrárias enviadas pelo visitante da LP. Falhas de extração não afetam
a API principal nem alteram os arquivos já armazenados.
"""
from __future__ import annotations

import logging
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from yt_dlp import YoutubeDL

LOG = logging.getLogger("dahuer.tiktok")
VIDEO_PATH = re.compile(r"^/@[A-Za-z0-9._-]+/video/[0-9]{15,25}/?$")


def is_tiktok_video(url: str) -> bool:
    try:
        u = urlsplit(url)
        return (
            u.scheme == "https"
            and u.hostname == "www.tiktok.com"
            and u.port in (None, 443)
            and not u.username
            and not u.password
            and VIDEO_PATH.fullmatch(u.path) is not None
        )
    except (TypeError, ValueError):
        return False


def fetch_tiktok_video(url: str, destination: Path, max_bytes: int) -> None:
    """Extrai um vídeo TikTok e grava atomicamente no volume persistente."""
    if not is_tiktok_video(url):
        raise ValueError("URL TikTok não permitida")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    # Diretório de trabalho isolado para que .part, logs e fragmentos também
    # desapareçam em caso de bloqueio, vídeo apagado ou interrupção.
    with tempfile.TemporaryDirectory(prefix=".tiktok-", dir=destination.parent) as work:
        folder = Path(work)
        output = folder / "video.%(ext)s"

        def progress(data: dict) -> None:
            if data.get("status") != "downloading":
                return
            downloaded = data.get("downloaded_bytes") or 0
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            if max(downloaded, total) > max_bytes:
                raise ValueError("Vídeo TikTok excede o limite de tamanho")

        opts = {
            "format": "best[ext=mp4]/best",
            "outtmpl": str(output),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "no_color": True,
            "socket_timeout": 15,
            "retries": 1,
            "fragment_retries": 1,
            "extractor_retries": 1,
            "max_filesize": max_bytes,
            "cachedir": False,
            "progress_hooks": [progress],
            "nopart": False,
            "restrictfilenames": True,
            "skip_download": False,
        }
        try:
            with YoutubeDL(opts) as yt:
                result = yt.download([url])
            if result not in (None, 0):
                raise ValueError("yt-dlp não conseguiu baixar o vídeo")
        except Exception as exc:
            # A exceção ficará registrada no status de mídia; a API continua no ar.
            raise ValueError("Falha do extrator TikTok: " + str(exc)[:180]) from exc

        files = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in (".mp4", ".webm")]
        if len(files) != 1:
            raise ValueError("Vídeo TikTok não gerou exatamente um arquivo de vídeo")
        output_file = files[0]
        size = output_file.stat().st_size
        if size <= 16 or size > max_bytes:
            raise ValueError("Arquivo de vídeo vazio ou acima do limite")
        with output_file.open("rb") as fh:
            header = fh.read(16)
        valid_mp4 = header[4:8] == b"ftyp" and header[8:12] not in (b"avif", b"avis", b"mif1")
        valid_webm = header[:4] == b"\x1a\x45\xdf\xa3"
        if not (valid_mp4 or valid_webm):
            raise ValueError("Resposta TikTok não parece MP4/WebM")
        os.replace(output_file, destination)
        LOG.info("Vídeo TikTok armazenado: %s (%s bytes)", destination.name, size)
