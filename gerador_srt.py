import sys
import time
from pathlib import Path

import whisper

# Extensões reconhecidas como vídeo
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".webm",
              ".flv", ".wmv", ".m4v", ".mpg", ".mpeg", ".ts"}


def format_timestamp(seconds: float) -> str:
    """Converte segundos (float) para o formato SRT: HH:MM:SS,mmm"""
    if seconds < 0:
        seconds = 0.0
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1_000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def encontrar_video(pasta: Path) -> Path:
    """Retorna o primeiro vídeo encontrado na pasta."""
    videos = sorted(
        p for p in pasta.iterdir()
        if p.is_file() and p.suffix.lower() in VIDEO_EXTS
    )
    if not videos:
        raise FileNotFoundError(
            f"Nenhum arquivo de vídeo encontrado em: {pasta}\n"
            f"Extensões aceitas: {', '.join(sorted(VIDEO_EXTS))}"
        )
    if len(videos) > 1:
        print(f"⚠️  Encontrei {len(videos)} vídeos. Vou usar o primeiro:")
        for v in videos:
            print(f"   - {v.name}")
        print()
    return videos[0]


def salvar_srt(segments, destino: Path) -> None:
    """Grava os segmentos do Whisper no formato SRT."""
    with destino.open("w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, start=1):
            inicio = format_timestamp(seg["start"])
            fim = format_timestamp(seg["end"])
            texto = seg["text"].strip()
            f.write(f"{i}\n{inicio} --> {fim}\n{texto}\n\n")


def main() -> None:
    pasta_script = Path(__file__).resolve().parent

    # ---- 1) Localizar o vídeo -------------------------------------------------
    if len(sys.argv) > 1:
        video = Path(sys.argv[1]).resolve()
        if not video.exists() and (pasta_script / sys.argv[1]).exists():
            video = (pasta_script / sys.argv[1]).resolve()
    else:
        try:
            video = encontrar_video(pasta_script)
        except FileNotFoundError as e:
            print(f"❌ {e}")
            sys.exit(1)

    if not video.exists():
        print(f"❌ Arquivo não encontrado: {video}")
        sys.exit(1)

    srt_saida = video.with_suffix(".srt")
    modelo_nome = sys.argv[2] if len(sys.argv) > 2 else "base"

    # ---- 2) Banner ------------------------------------------------------------
    print("=" * 60)
    print(f"🎬 Vídeo   : {video.name}")
    print(f"📝 Saída   : {srt_saida.name}")
    print(f"🤖 Modelo  : {modelo_nome}")
    print("=" * 60)

    # ---- 3) Carregar modelo ---------------------------------------------------
    print(f"\n⏳ Carregando modelo Whisper '{modelo_nome}'...")
    t0 = time.time()
    modelo = whisper.load_model(modelo_nome)
    print(f"✅ Modelo carregado em {time.time() - t0:.1f}s")

    # ---- 4) Transcrever -------------------------------------------------------
    print("\n🎙️  Transcrevendo... (barra de progresso abaixo; segmentos aparecem na hora)\n")
    t0 = time.time()
    resultado = modelo.transcribe(
        str(video),
        verbose=True,   # mostra cada segmento transcrito em tempo real
        fp16=False,     # evita warning em CPU
    )
    duracao = time.time() - t0
    print(f"\n✅ Transcrição concluída em {duracao:.1f}s")

    # ---- 5) Salvar SRT --------------------------------------------------------
    segments = resultado.get("segments", [])
    if not segments:
        print("⚠️  Nenhum segmento transcrito — nenhum SRT foi gerado.")
        sys.exit(0)

    print(f"\n💾 Salvando {len(segments)} segmentos em: {srt_saida.name}")
    salvar_srt(segments, srt_saida)
    print(f"✅ Pronto! Arquivo gerado: {srt_saida}")

    # ---- 6) Encerrar ----------------------------------------------------------
    print("\n🏁 Processo encerrado.")


if __name__ == "__main__":
    main()