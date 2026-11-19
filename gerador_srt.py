import sys
import time
from pathlib import Path

import whisper

# Extensões reconhecidas como vídeo
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".webm",
              ".flv", ".wmv", ".m4v", ".mpg", ".mpeg", ".ts"}

# Modelos conhecidos do Whisper (permite rodar: python gerador_srt.py small)
MODELOS_WHISPER = {
    "tiny", "base", "small", "medium",
    "large", "large-v1", "large-v2", "large-v3", "turbo"
}


def format_timestamp(seconds: float) -> str:
    """Converte segundos (float) para o formato SRT: HH:MM:SS,mmm"""
    if seconds < 0:
        seconds = 0.0
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1_000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def encontrar_videos_pendentes(pasta_script: Path) -> list[Path]:
    """
    Busca automaticamente na pasta 'temp/' (e na pasta raiz) todos os vídeos
    que ainda não possuem arquivo .srt correspondente.
    """
    pastas_busca = []
    pasta_temp = pasta_script / "temp"
    if pasta_temp.exists() and pasta_temp.is_dir():
        pastas_busca.append(pasta_temp)
    if pasta_script not in pastas_busca:
        pastas_busca.append(pasta_script)

    pendentes: list[Path] = []
    todos_videos: list[Path] = []

    for pasta in pastas_busca:
        videos_pasta = sorted(
            (
                p for p in pasta.iterdir()
                if p.is_file()
                and p.suffix.lower() in VIDEO_EXTS
                and not p.name.lower().startswith("corte_")
            ),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for v in videos_pasta:
            todos_videos.append(v)
            if not v.with_suffix(".srt").exists():
                pendentes.append(v)

    if not todos_videos:
        locais = ", ".join(str(p) for p in pastas_busca)
        raise FileNotFoundError(
            f"Nenhum arquivo de vídeo encontrado em: {locais}\n"
            f"Extensões aceitas: {', '.join(sorted(VIDEO_EXTS))}"
        )

    return pendentes


def salvar_srt(segments, destino: Path) -> None:
    """Grava os segmentos do Whisper no formato SRT."""
    with destino.open("w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, start=1):
            inicio = format_timestamp(seg["start"])
            fim = format_timestamp(seg["end"])
            texto = seg["text"].strip()
            f.write(f"{i}\n{inicio} --> {fim}\n{texto}\n\n")


def transcrever_video(modelo, video: Path, modelo_nome: str, indice: int = 1, total: int = 1) -> None:
    """Executa a transcrição de um único vídeo com o modelo já carregado."""
    srt_saida = video.with_suffix(".srt")

    # ---- Banner ---------------------------------------------------------------
    print("=" * 60)
    if total > 1:
        print(f"📦 Progresso: Vídeo {indice} de {total}")
    print(f"🎬 Vídeo   : {video.name}")
    print(f"📂 Pasta   : {video.parent}")
    print(f"📝 Saída   : {srt_saida.name}")
    print(f"🤖 Modelo  : {modelo_nome}")
    print("=" * 60)

    # ---- Transcrever ----------------------------------------------------------
    print("\n🎙️  Transcrevendo... (barra de progresso abaixo; segmentos aparecem na hora)\n")
    t0 = time.time()
    resultado = modelo.transcribe(
        str(video),
        language="pt",
        task="transcribe",
        verbose=True,   # mostra cada segmento transcrito em tempo real
        fp16=False,     # evita warning em CPU
    )
    duracao = time.time() - t0
    print(f"\n✅ Transcrição concluída em {duracao:.1f}s")

    # ---- Salvar SRT -----------------------------------------------------------
    segments = resultado.get("segments", [])
    if not segments:
        print("⚠️  Nenhum segmento transcrito — nenhum SRT foi gerado.\n")
        return

    print(f"\n💾 Salvando {len(segments)} segmentos em: {srt_saida.name}")
    salvar_srt(segments, srt_saida)
    print(f"✅ Pronto! Arquivo gerado: {srt_saida}\n")


def resolver_video_argumento(arg: str, pasta_script: Path) -> Path:
    """Localiza um vídeo informado via argumento (caminho direto, raiz ou pasta temp)."""
    candidatos = [
        Path(arg).resolve(),
        (pasta_script / arg).resolve(),
        (pasta_script / "temp" / arg).resolve(),
    ]
    for c in candidatos:
        if c.exists() and c.is_file():
            return c
    return Path(arg).resolve()


def main() -> None:
    pasta_script = Path(__file__).resolve().parent

    # ---- 1) Localizar vídeo(s) e definir modelo -------------------------------
    videos_para_processar: list[Path] = []
    modelo_nome = "base"

    if len(sys.argv) > 1 and sys.argv[1].lower() not in MODELOS_WHISPER:
        video = resolver_video_argumento(sys.argv[1], pasta_script)
        if not video.exists():
            print(f"❌ Arquivo não encontrado: {video}")
            sys.exit(1)
        videos_para_processar = [video]
        if len(sys.argv) > 2:
            modelo_nome = sys.argv[2]
    else:
        if len(sys.argv) > 1 and sys.argv[1].lower() in MODELOS_WHISPER:
            modelo_nome = sys.argv[1].lower()

        try:
            videos_para_processar = encontrar_videos_pendentes(pasta_script)
        except FileNotFoundError as e:
            print(f"❌ {e}")
            sys.exit(1)

        if not videos_para_processar:
            print("✅ Todos os vídeos encontrados em 'temp/' (e na pasta raiz) já possuem arquivo .srt!")
            sys.exit(0)

        print(f"🔎 Encontrados {len(videos_para_processar)} vídeo(s) sem legenda (.srt):")
        for idx, v in enumerate(videos_para_processar, start=1):
            print(f"   {idx}. [{v.parent.name}] {v.name}")
        print()

    # ---- 2) Carregar modelo (uma única vez) -----------------------------------
    print(f"⏳ Carregando modelo Whisper '{modelo_nome}'...")
    t0 = time.time()
    modelo = whisper.load_model(modelo_nome)
    print(f"✅ Modelo carregado em {time.time() - t0:.1f}s\n")

    # ---- 3) Transcrever vídeo(s) ----------------------------------------------
    total = len(videos_para_processar)
    for indice, video in enumerate(videos_para_processar, start=1):
        transcrever_video(modelo, video, modelo_nome, indice=indice, total=total)

    # ---- 4) Encerrar ----------------------------------------------------------
    print("🏁 Processo encerrado.")


if __name__ == "__main__":
    main()
