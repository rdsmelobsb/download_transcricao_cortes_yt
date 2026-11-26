"""
Pipeline Automatizado do Kwai via Android ADB — Mathilda News.

Orquestra as etapas do Kwai (conectando automaticamente no celular USB ou BlueStacks):
  1. Publicação dos TOP N melhores cortes pendentes (publicar_kwai.py --top 3 --sim)
     com envio determinístico via ACTION_SEND + espaçamento anti-bot
  2. Coleta de métricas reais do perfil no Kwai (avaliar_metricas_kwai.py --limite 20)
     para retroalimentar a curadoria IA (prompts/padroes_vencedores_kwai.json)

Projetado para rodar diariamente às 09:00 e 18:00 via Agendador de Tarefas do Windows,
com lockfile anti-sobreposição e logs persistentes em logs/pipeline_kwai_YYYYMMDD.log.
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"
LOCK_FILE = BASE_DIR / "temp" / ".pipeline_kwai.lock"


def _adquirir_lock() -> bool:
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    if LOCK_FILE.exists():
        idade_seg = datetime.now().timestamp() - LOCK_FILE.stat().st_mtime
        if idade_seg < 2 * 3600:
            return False
    LOCK_FILE.write_text(f"{os.getpid()} | {datetime.now().isoformat()}", encoding="utf-8")
    return True


def _liberar_lock() -> None:
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
    except OSError:
        pass


def _executar_etapa(nome: str, cmd: list[str], log_file: Path) -> bool:
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
    return ret == 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline diário automatizado do Kwai (ADB).")
    parser.add_argument("--top", type=int, default=3, help="Quantidade dos melhores cortes para postar por execução (padrão: 3).")
    parser.add_argument("--serial", help="Serial ou endereço TCP ADB específico (ex: 127.0.0.1:6610). Se omitido, detecta automaticamente.")
    parser.add_argument("--limite-metricas", type=int, default=20, help="Quantidade de vídeos recentes para auditar métricas (padrão: 20).")
    parser.add_argument("--sem-metricas", action="store_true", help="Pula a coleta de métricas após publicar.")
    args = parser.parse_args()

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / f"pipeline_kwai_{datetime.now().strftime('%Y%m%d')}.log"

    if not _adquirir_lock():
        msg = f"[{datetime.now().strftime('%H:%M:%S')}] ⏸️ Outra instância do pipeline_kwai já está em execução. Abortando.\n"
        print(msg, end="")
        with log_file.open("a", encoding="utf-8") as lf:
            lf.write(msg)
        sys.exit(0)

    py = sys.executable
    banner = (
        "\n=========================================================================\n"
        f"🚀 PIPELINE KWAI INICIADO — {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
        "=========================================================================\n"
    )
    print(banner, end="", flush=True)
    with log_file.open("a", encoding="utf-8") as lf:
        lf.write(banner)

    try:
        cmd_pub = [py, "publicar_kwai.py", "--top", str(args.top), "--sim"]
        if args.serial:
            cmd_pub.extend(["--serial", args.serial])

        _executar_etapa(
            f"1/2 Publicação Automática no Kwai (TOP {args.top})",
            cmd_pub,
            log_file,
        )

        if not args.sem_metricas:
            cmd_met = [py, "avaliar_metricas_kwai.py", "--limite", str(args.limite_metricas)]
            if args.serial:
                cmd_met.extend(["--serial", args.serial])

            _executar_etapa(
                f"2/2 Auditoria de Métricas e Retroalimentação (Kwai, últimos {args.limite_metricas})",
                cmd_met,
                log_file,
            )
    finally:
        _liberar_lock()
        rodape = (
            "\n=========================================================================\n"
            f"🏁 PIPELINE KWAI FINALIZADO — {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
            f"📄 Log completo: {log_file}\n"
            "=========================================================================\n"
        )
        print(rodape, end="", flush=True)
        with log_file.open("a", encoding="utf-8") as lf:
            lf.write(rodape)


if __name__ == "__main__":
    main()
