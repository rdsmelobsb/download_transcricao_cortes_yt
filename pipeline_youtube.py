"""
Pipeline Automatizado do YouTube Shorts — Política Direta.

Orquestra de ponta a ponta todas as etapas de produção e publicação no YouTube:
  1. Auditoria de métricas reais (avaliar_metricas.py) -> retroalimenta a IA
  2. Coleta de novos vídeos dos canais monitorados (download.py --monitor)
  3. Transcrição em lote para SRT (gerador_srt.py)
  4. Curadoria IA + Validação de Packaging CTR (analisar_srt.py --novos)
  5. Renderização vertical 9:16 via FFmpeg (cortes.py --modo 5)
  6. Publicação e agendamento sem colisões (publicar_youtube.py --todos)

Projetado para rodar diariamente às 08:00 e 17:00 via Agendador de Tarefas do Windows,
com lockfile anti-sobreposição e logs persistentes em logs/pipeline_youtube_YYYYMMDD.log.
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"
LOCK_FILE = BASE_DIR / "temp" / ".pipeline_youtube.lock"


def _adquirir_lock() -> bool:
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    if LOCK_FILE.exists():
        # Se o lock tem mais de 3 horas, considera órfão (crash anterior)
        idade_seg = datetime.now().timestamp() - LOCK_FILE.stat().st_mtime
        if idade_seg < 3 * 3600:
            return False
    LOCK_FILE.write_text(f"{os.getpid()} | {datetime.now().isoformat()}", encoding="utf-8")
    return True


def _liberar_lock() -> None:
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
    except OSError:
        pass


def _executar_etapa(nome: str, cmd: list[str], log_file: Path, obrigatoria: bool = False) -> bool:
    cabecalho = f"\n[{datetime.now().strftime('%H:%M:%S')}] ▶ ETAPA: {nome}\n"
    cabecalho += f"   Comando: {' '.join(cmd)}\n"
    print(cabecalho, end="", flush=True)
    with log_file.open("a", encoding="utf-8") as lf:
        lf.write(cabecalho)

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    proc = subprocess.Popen(
        cmd,
        cwd=str(BASE_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )

    assert proc.stdout is not None
    with log_file.open("a", encoding="utf-8") as lf:
        for linha in proc.stdout:
            print(linha, end="", flush=True)
            lf.write(linha)

    ret = proc.wait()
    status_txt = f"[{datetime.now().strftime('%H:%M:%S')}] {'✅ OK' if ret == 0 else f'⚠️ FALHOU (exit={ret})'}: {nome}\n"
    print(status_txt, end="", flush=True)
    with log_file.open("a", encoding="utf-8") as lf:
        lf.write(status_txt)

    if ret != 0 and obrigatoria:
        raise RuntimeError(f"Etapa obrigatória '{nome}' falhou com código {ret}.")
    return ret == 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline diário automatizado do YouTube Shorts.")
    parser.add_argument("--modo", default="5", help="Modo de corte FFmpeg (padrão: 5 = vertical_tela_cheia).")
    parser.add_argument("--modelo-whisper", default="base", help="Modelo Whisper para transcrição (padrão: base).")
    parser.add_argument("--por-dia", type=int, default=3, help="Slots por dia na grade YouTube (padrão: 3).")
    parser.add_argument("--limite", type=int, default=3, help="Máximo de uploads por execução (padrão: 3 -> 2x/dia = 6 cota diária).")
    parser.add_argument("--sem-metricas", action="store_true", help="Pula a auditoria inicial de métricas.")
    parser.add_argument("--simular", action="store_true", help="Executa o upload final em modo --simular (dry-run).")
    args = parser.parse_args()

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / f"pipeline_youtube_{datetime.now().strftime('%Y%m%d')}.log"

    if not _adquirir_lock():
        msg = f"[{datetime.now().strftime('%H:%M:%S')}] ⏸️ Outra instância do pipeline_youtube já está em execução. Abortando.\n"
        print(msg, end="")
        with log_file.open("a", encoding="utf-8") as lf:
            lf.write(msg)
        sys.exit(0)

    py = sys.executable
    banner = (
        "\n=========================================================================\n"
        f"🚀 PIPELINE YOUTUBE INICIADO — {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
        "=========================================================================\n"
    )
    print(banner, end="", flush=True)
    with log_file.open("a", encoding="utf-8") as lf:
        lf.write(banner)

    try:
        if not args.sem_metricas:
            _executar_etapa(
                "1/6 Auditoria de Métricas e Retroalimentação (YouTube)",
                [py, "avaliar_metricas.py", "--silencioso"],
                log_file,
            )

        _executar_etapa(
            "2/6 Monitoramento e Download de Novos Vídeos",
            [py, "download.py", "--monitor"],
            log_file,
        )

        _executar_etapa(
            "3/6 Transcrição Automática em Lote (Whisper)",
            [py, "gerador_srt.py", args.modelo_whisper],
            log_file,
        )

        _executar_etapa(
            "4/6 Curadoria IA + Validação Packaging CTR (Gemini)",
            [py, "analisar_srt.py", "--novos"],
            log_file,
        )

        _executar_etapa(
            f"5/6 Renderização Vertical FFmpeg (Modo {args.modo})",
            [py, "cortes.py", "--modo", str(args.modo)],
            log_file,
        )

        cmd_pub = [
            py, "publicar_youtube.py",
            "--todos",
            "--por-dia", str(args.por_dia),
            "--limite", str(args.limite),
        ]
        if args.simular:
            cmd_pub.append("--simular")

        _executar_etapa(
            f"6/6 Publicação e Agendamento Anti-Canibalização (YouTube, máx {args.limite})",
            cmd_pub,
            log_file,
        )
    finally:
        _liberar_lock()
        rodape = (
            "\n=========================================================================\n"
            f"🏁 PIPELINE YOUTUBE FINALIZADO — {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
            f"📄 Log completo: {log_file}\n"
            "=========================================================================\n"
        )
        print(rodape, end="", flush=True)
        with log_file.open("a", encoding="utf-8") as lf:
            lf.write(rodape)


if __name__ == "__main__":
    main()
