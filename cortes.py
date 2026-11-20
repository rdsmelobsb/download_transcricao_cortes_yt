import argparse
import sys
from pathlib import Path

import ffmpeg

import manifesto

# =====================================================================
# 1. CONFIGURAÇÃO DE DIRETÓRIOS
# =====================================================================

BASE_DIR = Path(__file__).resolve().parent
TEMP_DIR = BASE_DIR / "temp"
OUTPUT_DIR = BASE_DIR / "cortes_prontos"

SUFIXOS_MODO = {
    "1": "vertical_intermed",
    "2": "original",
    "3": "com_blur",
    "4": "vertical_com_blur",
    "5": "vertical_tela_cheia",
}


def localizar_video(video_path_str: str) -> Path:
    """
    Procura o arquivo de vídeo automaticamente:
    1. No caminho exato informado
    2. Dentro da pasta 'temp/'
    3. Na pasta raiz do projeto
    4. Por correspondência parcial (ex.: ID do vídeo) dentro de 'temp/'
    """
    caminho_informado = Path(video_path_str)
    nome_arquivo = caminho_informado.name

    candidatos = [
        caminho_informado,
        TEMP_DIR / nome_arquivo,
        BASE_DIR / caminho_informado,
        BASE_DIR / nome_arquivo,
    ]

    for candidato in candidatos:
        if candidato.exists() and candidato.is_file():
            return candidato.resolve()

    # Busca flexível em temp/ caso tenha sido informado apenas parte do nome ou ID
    if TEMP_DIR.exists():
        correspondencias = [
            p for p in TEMP_DIR.iterdir()
            if p.is_file()
            and not p.name.lower().startswith("corte_")
            and p.suffix.lower() in {".mp4", ".mkv", ".mov", ".webm"}
            and video_path_str.lower() in p.name.lower()
        ]
        if len(correspondencias) == 1:
            return correspondencias[0].resolve()

    return (TEMP_DIR / nome_arquivo).resolve()


# =====================================================================
# 2. FUNÇÃO PARA PERGUNTAR O FORMATO AO USUÁRIO
# =====================================================================

def perguntar_modo_de_corte() -> str:
    print("===================================================")
    print("          ESCOLHA O MODO DE CORTE DO VÍDEO         ")
    print("===================================================")
    print("[1] Vertical intermediário (9:16 com respiro/faixas)")
    print("[2] Formato original (Apenas início e fim)")
    print("[3] Remover/Borrar marca d'água (delogo)")
    print("[4] Vertical intermediário + Borrar marca d'água")
    print("[5] Vertical TELA CHEIA (9:16 Puro sem faixas pretas)")
    print("===================================================")

    while True:
        escolha = input("Digite o número da opção desejada (1 a 5): ").strip()
        if escolha in SUFIXOS_MODO:
            return escolha
        print("⚠️ Opção inválida! Digite um número de 1 a 5.\n")


# =====================================================================
# 3. SELEÇÃO DAS TAREFAS A RENDERIZAR (LIDAS DO MANIFESTO)
# =====================================================================

def selecionar_tarefas(
    tarefas: list[dict],
    ids: list[str] | None,
    todos: bool,
) -> list[dict]:
    """
    Por padrão renderiza apenas os cortes 'pendente'.
    --id  : renderiza os ids informados (qualquer status, exceto inexistentes).
    --todos: renderiza todos os cortes não publicados.
    """
    if ids:
        por_id = {t["id"]: t for t in tarefas}
        inexistentes = [i for i in ids if i not in por_id]
        if inexistentes:
            print(f"⚠️ Ids não encontrados no manifesto: {', '.join(inexistentes)}")
        return [por_id[i] for i in ids if i in por_id]

    if todos:
        return [t for t in tarefas if t.get("status") != manifesto.STATUS_PUBLICADO]

    return [t for t in tarefas if t.get("status") == manifesto.STATUS_PENDENTE]


# =====================================================================
# 4. FUNÇÃO PRINCIPAL DE PROCESSAMENTO DOS CORTES
# =====================================================================

def recortar_videos_locais(modo: str, tarefas_a_renderizar: list[dict], manifesto_completo: list[dict]) -> list[dict]:
    print("Iniciando o processamento dos cortes locais...\n")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    sufixo_formato = SUFIXOS_MODO.get(modo, "corte")

    filtro_blur_centro = "delogo=x=280:y=520:w=520:h=60:show=0"
    filtro_blur_rodape = "delogo=x=300:y=1750:w=480:h=70:show=0"

    # Enquadramento intermediário (com barras)
    fator_largura = 1.05
    filtro_vertical_intermed = (
        f"crop='min(iw,ih*{fator_largura})':ih,"
        "scale=1080:1920:force_original_aspect_ratio=decrease,"
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2"
    )

    # 9:16 tela cheia real (preenche todo o visor sem barras)
    filtro_tela_cheia = "crop='min(iw,ih*9/16)':'min(ih,iw*16/9)',scale=1080:1920"

    resultados = []

    for tarefa in tarefas_a_renderizar:
        caminho_video_resolvido = localizar_video(tarefa["video_path"])
        caminho_video = str(caminho_video_resolvido)
        nome_tarefa = tarefa["nome"]
        inicio = float(tarefa["start"])
        fim = float(tarefa["end"])
        duracao = fim - inicio

        nome_limpo = manifesto.nome_arquivo_limpo(nome_tarefa)
        saida = OUTPUT_DIR / f"corte_{tarefa['id']}_{sufixo_formato}_{nome_limpo}.mp4"

        if not caminho_video_resolvido.exists():
            print(f"[{tarefa['id']}] ❌ Erro: Vídeo '{tarefa['video_path']}' não encontrado em 'temp/' nem na raiz.")
            resultados.append((tarefa, None, "vídeo de origem não encontrado"))
            continue

        print(f"[{tarefa['id']}] 🎬 Processando '{nome_tarefa}' ({sufixo_formato}) a partir de '{caminho_video_resolvido.name}'...")

        opcoes_ffmpeg = {
            "vcodec": "libx264",
            "acodec": "aac",
            "video_bitrate": "4M",
            "audio_bitrate": "192k",
            "preset": "fast",
            "movflags": "+faststart"
        }

        if modo == "1":
            opcoes_ffmpeg["vf"] = filtro_vertical_intermed
        elif modo == "3":
            opcoes_ffmpeg["vf"] = f"scale=1080:1920,{filtro_blur_centro},{filtro_blur_rodape}"
        elif modo == "4":
            opcoes_ffmpeg["vf"] = f"{filtro_vertical_intermed},{filtro_blur_centro},{filtro_blur_rodape}"
        elif modo == "5":
            opcoes_ffmpeg["vf"] = filtro_tela_cheia

        try:
            stream = ffmpeg.input(caminho_video, ss=inicio, t=duracao)
            stream = ffmpeg.output(stream, str(saida), **opcoes_ffmpeg)
            ffmpeg.overwrite_output(stream).run(quiet=True)
            print(f" ✅ Sucesso! Vídeo salvo em: {saida.resolve()}\n")

            # Atualiza o manifesto imediatamente (não perde progresso se interrompido)
            tarefa["status"] = manifesto.STATUS_RENDERIZADO
            tarefa["arquivo_final"] = str(saida.relative_to(BASE_DIR))
            tarefa["modo"] = modo
            manifesto.salvar(manifesto_completo)
            resultados.append((tarefa, saida, None))
        except ffmpeg.Error as e:
            erro_detalhe = e.stderr.decode("utf-8", errors="ignore") if e.stderr else str(e)
            print(f" ❌ Erro no FFmpeg ao gerar '{nome_tarefa}':\n{erro_detalhe}\n")
            resultados.append((tarefa, None, "erro no FFmpeg"))
        except Exception as e:
            print(f" ❌ Erro ao gerar o corte '{nome_tarefa}': {e}\n")
            resultados.append((tarefa, None, str(e)))

    return resultados


def imprimir_resumo(resultados: list[tuple], modo: str) -> None:
    sufixo = SUFIXOS_MODO.get(modo, "corte")
    ok = [r for r in resultados if r[1] is not None]
    falhas = [r for r in resultados if r[1] is None]

    print("===================================================")
    print(f"🏁 Processo concluído! Modo {modo} ({sufixo}) | ✅ {len(ok)} | ❌ {len(falhas)}")
    print("===================================================")
    for tarefa, saida, _ in ok:
        print(f" • [{tarefa['horario_sugerido']}] {tarefa['id']}: {saida.name}")
    for tarefa, _, motivo in falhas:
        print(f" ✖ {tarefa['id']}: {motivo}")
    if ok:
        print("\nOs vídeos estão na pasta 'cortes_prontos/'.")


# =====================================================================
# 5. PONTO DE PARTIDA DO PROGRAMA
# =====================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Renderiza os cortes pendentes listados em temp/tarefas_corte.json."
    )
    parser.add_argument(
        "--modo",
        choices=sorted(SUFIXOS_MODO),
        help="Modo de corte (1 a 5). Sem esta opção, pergunta no terminal.",
    )
    parser.add_argument(
        "--id",
        action="append",
        dest="ids",
        help="Renderiza apenas este id do manifesto (pode repetir: --id A_1 --id A_2).",
    )
    parser.add_argument(
        "--todos",
        action="store_true",
        help="Re-renderiza todos os cortes não publicados (não só os pendentes).",
    )
    args = parser.parse_args()

    try:
        tarefas = manifesto.carregar()
    except Exception as e:
        print(f"❌ Não foi possível ler o manifesto: {e}")
        sys.exit(1)

    if not tarefas:
        print(f"❌ Manifesto vazio ou inexistente: {manifesto.MANIFESTO_FILE}")
        print("-> Execute primeiro: python analisar_srt.py")
        sys.exit(1)

    a_renderizar = selecionar_tarefas(tarefas, args.ids, args.todos)
    if not a_renderizar:
        print("✅ Nenhum corte pendente para renderizar.")
        print("-> Use --todos para re-renderizar ou --id <id> para um corte específico.")
        sys.exit(0)

    print(f"🎞️  {len(a_renderizar)} corte(s) para renderizar:")
    for t in a_renderizar:
        print(f"   - {t['id']} [{t.get('status')}] {t['nome']}")
    print()

    modo = args.modo or perguntar_modo_de_corte()
    resultados = recortar_videos_locais(modo, a_renderizar, tarefas)
    imprimir_resumo(resultados, modo)


if __name__ == "__main__":
    main()
