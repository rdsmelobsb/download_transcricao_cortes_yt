"""
Radar de Outliers Virais no Nicho Político Brasileiro (Integração yt-viral / swipe.py).

Coleta listagens públicas recentes (sem login e sem cookies) de canais brasileiros
de política, economia e notícias usando yt-dlp (--flat-playlist), calcula a mediana
de visualizações de CADA canal separadamente e executa o motor oficial
'.agent/skills/yt-viral/swipe.py' para identificar vídeos que furaram a bolha
(2x a 10x+ acima da mediana do próprio canal).

Gera o swipe file executivo em: cortes_prontos/outliers_politica_br.md
"""

import argparse
import json
import statistics
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

import yt_dlp

BASE_DIR = Path(__file__).resolve().parent
CANAIS_JSON = BASE_DIR / "canais.json"
SWIPE_PY = BASE_DIR / ".agent" / "skills" / "yt-viral" / "swipe.py"
OUTPUT_DIR = BASE_DIR / "cortes_prontos"
COLETADOS_JSON = BASE_DIR / "temp" / "virais_politica_coletados.json"
RELATORIO_VIRAIS_MD = OUTPUT_DIR / "outliers_politica_br.md"

# Canais extras de referência no nicho político/notícias BR (listagens públicas)
CANAIS_REFERENCIA_BR = [
    {"nome": "ICL Notícias", "url": "https://www.youtube.com/@ICLNoticias/videos"},
    {"nome": "UOL", "url": "https://www.youtube.com/@uol/videos"},
    {"nome": "CNN Brasil", "url": "https://www.youtube.com/@CNNbrasil/videos"},
    {"nome": "Metrópoles", "url": "https://www.youtube.com/@metropoles/videos"},
    {"nome": "Poder360", "url": "https://www.youtube.com/@Poder360/videos"},
    {"nome": "TV 247", "url": "https://www.youtube.com/@tv247/videos"},
]


def carregar_canais(incluir_referencias: bool = True) -> list[dict[str, str]]:
    canais: list[dict[str, str]] = []
    urls_vistas: set[str] = set()

    if CANAIS_JSON.exists():
        try:
            for c in json.loads(CANAIS_JSON.read_text(encoding="utf-8")):
                if c.get("ativo", True) and c.get("url"):
                    canais.append({"nome": c["nome"], "url": c["url"]})
                    urls_vistas.add(c["url"])
        except Exception:
            pass

    if incluir_referencias:
        for c in CANAIS_REFERENCIA_BR:
            if c["url"] not in urls_vistas:
                canais.append(c)
                urls_vistas.add(c["url"])

    return canais


def coletar_canal(canal: dict[str, str], max_videos: int = 20) -> list[dict[str, Any]]:
    """Coleta metadados públicos recentes via flat-playlist (rápido e sem login)."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",
        "playlistend": max_videos,
        "skip_download": True,
        "extractor_args": {"youtubetab": {"skip": ["authcheck"]}},
    }
    videos: list[dict[str, Any]] = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(canal["url"], download=False)
            entries = info.get("entries") or []
            for e in entries:
                if not e:
                    continue
                views = e.get("view_count")
                if views is None:
                    continue
                vid_id = e.get("id") or ""
                url = e.get("url") or (f"https://www.youtube.com/watch?v={vid_id}" if vid_id else "")
                if url and not url.startswith("http"):
                    url = f"https://www.youtube.com/watch?v={url}"
                videos.append({
                    "channel": canal["nome"],
                    "title": e.get("title") or "",
                    "views": int(views),
                    "url": url,
                    "duration": int(e.get("duration") or 0),
                })
    except Exception as exc:
        print(f"  ⚠️ [{canal['nome']}] falha ao coletar listagem pública: {str(exc)[:90]}")
    return videos


def salvar_swipe_file_md(outliers_data: dict[str, Any], total_videos: int, total_canais: int, minimo: float) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    outliers = outliers_data.get("outliers", [])
    linhas = [
        "# 🔥 Radar de Outliers Virais — Nicho Político BR (`yt-viral`)",
        "",
        f"> **Gerado em:** {datetime.now().strftime('%d/%m/%Y %H:%M')} | "
        f"**Amostra:** {total_videos} vídeos em {total_canais} canais | "
        f"**Filtro:** ≥ `{minimo}x` acima da mediana do próprio canal",
        "",
        "> *Nota metodológica (`yt-viral`):* O múltiplo mede o quanto o vídeo superou a mediana do **próprio canal** (sinal de tema/ideia fora da curva, independente do tamanho do canal).",
        "",
        "---",
        "",
        "## 🏆 Top Outliers da Semana",
        "",
        "| Múltiplo | Views | Mediana Canal | Canal | Fórmula (Título) | Título |",
        "|---:|---:|---:|---|---|---|",
    ]

    for r in outliers[:25]:
        url = r.get("url", "")
        titulo = r.get("title", "").replace("|", "-")
        link = f"[{titulo}]({url})" if url else titulo
        linhas.append(
            f"| **{r['multiple']:.2f}x** | {r['views']:,} | {r['median']:,} | {r['channel']} | `{r['formula']}` | {link} |"
        )

    RELATORIO_VIRAIS_MD.write_text("\n".join(linhas), encoding="utf-8")
    print(f"📄 Swipe file salvo em: {RELATORIO_VIRAIS_MD}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Coleta listagens públicas de canais políticos BR e identifica outliers com yt-viral/swipe.py."
    )
    parser.add_argument("--max-videos", type=int, default=20, help="Vídeos recentes por canal (padrão: 20).")
    parser.add_argument("--min", dest="min_mult", type=float, default=2.0, help="Múltiplo mínimo sobre a mediana (padrão: 2.0).")
    parser.add_argument("--so-meus-canais", action="store_true", help="Analisa apenas os canais do canais.json.")
    args = parser.parse_args()

    canais = carregar_canais(incluir_referencias=not args.so_meus_canais)
    print(f"📡 Coletando últimos {args.max_videos} vídeos públicos de {len(canais)} canais políticos BR...")

    todos_videos: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futuros = {ex.submit(coletar_canal, c, args.max_videos): c["nome"] for c in canais}
        for f in as_completed(futuros):
            nome = futuros[f]
            vids = f.result()
            med = int(statistics.median([v["views"] for v in vids])) if vids else 0
            print(f"  ✅ {nome:<22} -> {len(vids):2d} vídeos | mediana: {med:>8,} views")
            todos_videos.extend(vids)

    COLETADOS_JSON.parent.mkdir(parents=True, exist_ok=True)
    COLETADOS_JSON.write_text(json.dumps(todos_videos, ensure_ascii=False, indent=2), encoding="utf-8")

    # Executa o swipe.py oficial do yt-viral (saída legível + saída JSON para o relatório)
    print("\n🔎 Executando análise de outliers (yt-viral/swipe.py)...")
    subprocess.run([sys.executable, str(SWIPE_PY), str(COLETADOS_JSON), "--min", str(args.min_mult)], check=False)

    res_json = subprocess.run(
        [sys.executable, str(SWIPE_PY), str(COLETADOS_JSON), "--min", str(args.min_mult), "--json"],
        capture_output=True,
        text=True,
        check=True,
    )
    outliers_data = json.loads(res_json.stdout)
    salvar_swipe_file_md(outliers_data, len(todos_videos), len(canais), args.min_mult)


if __name__ == "__main__":
    main()
