import os
import re
from pathlib import Path
import ffmpeg

# =====================================================================
# 1. CONFIGURAÇÃO DE DIRETÓRIOS E LISTA DE TAREFAS
# =====================================================================

BASE_DIR = Path(__file__).resolve().parent
TEMP_DIR = BASE_DIR / "temp"
OUTPUT_DIR = BASE_DIR / "cortes_prontos"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


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

TAREFAS_DE_CORTE = [
    {
        "id": 1,
        "ordem": 1,
        "horario_sugerido": "11:30",
        "nome": "GTA 6 Custo Beneficio E Valor Do Trabalho",
        "video_path": "20261119_sfLJF0hS_5c_GTA_6_e_lancado_em_todo_o_mundo_e_jogadores_exploram_Vice.mp4",
        "title": "GTA 6: O Custo-Benefício do Lazer e o Valor do Trabalho na Perspectiva dos Jogadores!",
        "start": 135.100,  # 00:02:15,100
        "end": 199.200     # 00:03:19,200
    },
    {
        "id": 2,
        "ordem": 2,
        "horario_sugerido": "17:30",
        "nome": "GTA 6 Numeros Recordes E Poder De Mercado",
        "video_path": "20261119_sfLJF0hS_5c_GTA_6_e_lancado_em_todo_o_mundo_e_jogadores_exploram_Vice.mp4",
        "title": "GTA 6: Análise dos Números Recordes e o Poder de Mercado da Indústria de Games!",
        "start": 61.500,  # 00:01:01,500
        "end": 133.600     # 00:02:13,600
    },
    {
        "id": 3,
        "ordem": 3,
        "horario_sugerido": "20:30",
        "nome": "GTA 6 Lancamento Global E Impacto Cultural",
        "video_path": "20261119_sfLJF0hS_5c_GTA_6_e_lancado_em_todo_o_mundo_e_jogadores_exploram_Vice.mp4",
        "title": "GTA 6: O Lançamento Global que Redefine a Economia do Entretenimento e o Impacto Cultural!",
        "start": 0.000,  # 00:00:00,000
        "end": 55.800     # 00:00:55,800
    },
    {
        "id": 4,
        "ordem": 4,
        "horario_sugerido": "11:30",
        "nome": "PF Explica Relatorios Vazamento",
        "video_path": "20261119_VpwyEyqk2k0_Relatorios_da_PF_sobre_o_Master_sao_entregues_e_podem.mp4",
        "title": "ESCÂNDALO DO VAZAMENTO: PF explica por que relatórios do Caso Master foram refeitos!",
        "start": 307.520,  # 00:05:07,520
        "end": 366.800     # 00:06:06,800
    },
    {
        "id": 5,
        "ordem": 5,
        "horario_sugerido": "17:30",
        "nome": "PF Desmente Afastamento Delegados",
        "video_path": "20261119_VpwyEyqk2k0_Relatorios_da_PF_sobre_o_Master_sao_entregues_e_podem.mp4",
        "title": "PF DESMENTE: NENHUM DELEGADO AFASTADO no Caso Master! Andrei Rodrigues esclarece",
        "start": 175.280,  # 00:02:55,280
        "end": 231.720     # 00:03:51,720
    },
    {
        "id": 6,
        "ordem": 6,
        "horario_sugerido": "20:30",
        "nome": "Eliziane Gama Impeachment Ministros STF",
        "video_path": "20261119_VpwyEyqk2k0_Relatorios_da_PF_sobre_o_Master_sao_entregues_e_podem.mp4",
        "title": "IMPEACHMENT NO STF? Senadora Eliziane Gama vibra com possibilidade de 6 ministros!",
        "start": 611.280,  # 00:10:11,280
        "end": 698.680     # 00:11:38,680
    },
    {
        "id": 7,
        "ordem": 7,
        "horario_sugerido": "11:30",
        "nome": "Erika Hilton Consciencia Negra",
        "video_path": "20261119_i7iPCEI3thk_Celia_Xabriaba_consegue_tirar_Bilynskyj_do_eixo_todos.mp4",
        "title": "Erika Hilton (PSOL) celebra Consciência Negra e a luta das mulheres contra o racismo e feminicídio",
        "start": 644.200,  # 00:10:44,200
        "end": 693.200     # 00:11:33,200
    },
    {
        "id": 8,
        "ordem": 8,
        "horario_sugerido": "17:30",
        "nome": "Melchionna Critica Obstrucao PL",
        "video_path": "20261119_i7iPCEI3thk_Celia_Xabriaba_consegue_tirar_Bilynskyj_do_eixo_todos.mp4",
        "title": "Fernanda Melchionna (PSOL) detona PL por obstrução e desrespeito na Comissão da Mulher",
        "start": 80.920,  # 00:01:20,920
        "end": 163.840     # 00:02:43,840
    },
    {
        "id": 9,
        "ordem": 9,
        "horario_sugerido": "20:30",
        "nome": "Celia Xakriaba Detona Bilynskyj",
        "video_path": "20261119_i7iPCEI3thk_Celia_Xabriaba_consegue_tirar_Bilynskyj_do_eixo_todos.mp4",
        "title": "Célia Xakriabá (PSOL) detona Bilynskyj: 'O problema do senhor não é ser homem, mas acho que o sonho do senhor é ser mulher!'",
        "start": 380.640,  # 00:06:20,640
        "end": 427.160     # 00:07:07,160
    },
    {
        "id": 10,
        "ordem": 10,
        "horario_sugerido": "11:30",
        "nome": "Fim Da Escala 6x1 Lula Assina Decreto",
        "video_path": "20261119_hImP-YloAm8_Fim_da_escala_6x1_tem_data_para_comecar_e_marca_primeir.mp4",
        "title": "Fim da Escala 6x1: Lula Assina Decreto e 14 Milhões de Trabalhadores Serão Impactados!",
        "start": 0.000,  # 00:00:00,000
        "end": 96.000     # 00:01:36,000
    },
    {
        "id": 11,
        "ordem": 11,
        "horario_sugerido": "17:30",
        "nome": "Lula Rebate Criticas Fim Escala 6x1",
        "video_path": "20261119_hImP-YloAm8_Fim_da_escala_6x1_tem_data_para_comecar_e_marca_primeir.mp4",
        "title": "Lula Rebate Críticas sobre Fim da Escala 6x1: 'Ingratidão!' e Ataca Extrema Direita!",
        "start": 155.000,  # 00:02:35,000
        "end": 240.000     # 00:04:00,000
    },
    {
        "id": 12,
        "ordem": 12,
        "horario_sugerido": "20:30",
        "nome": "Impacto Fim Escala 6x1 Mulheres",
        "video_path": "20261119_hImP-YloAm8_Fim_da_escala_6x1_tem_data_para_comecar_e_marca_primeir.mp4",
        "title": "Impacto do Fim da Escala 6x1 nas Mulheres: 'Sociedade Naturalizou o Cansaço Feminino!'",
        "start": 334.000,  # 00:05:34,000
        "end": 407.000     # 00:06:47,000
    }
]
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
        if escolha in ("1", "2", "3", "4", "5"):
            return escolha
        print("⚠️ Opção inválida! Digite um número de 1 a 5.\n")


# =====================================================================
# 3. FUNÇÃO PRINCIPAL DE PROCESSAMENTO DOS CORTES
# =====================================================================

def recortar_videos_locais(modo: str):
    print("Iniciando o processamento dos cortes locais...\n")

    sufixos = {
        "1": "vertical_intermed",
        "2": "original",
        "3": "com_blur",
        "4": "vertical_com_blur",
        "5": "vertical_tela_cheia"
    }
    sufixo_formato = sufixos.get(modo, "corte")

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

    for tarefa in TAREFAS_DE_CORTE:
        caminho_video_resolvido = localizar_video(tarefa["video_path"])
        caminho_video = str(caminho_video_resolvido)
        nome_tarefa = tarefa["nome"]
        inicio = float(tarefa["start"])
        fim = float(tarefa["end"])
        duracao = fim - inicio
        
        nome_limpo = re.sub(r'[\\/*?:"<>|]', "", nome_tarefa).lower().replace(" ", "_")
        saida = OUTPUT_DIR / f"corte_{tarefa['id']}_{sufixo_formato}_{nome_limpo}.mp4"

        if not caminho_video_resolvido.exists():
            print(f"[{nome_tarefa}] ❌ Erro: Vídeo '{tarefa['video_path']}' não encontrado em 'temp/' nem na raiz.")
            continue

        print(f"[{nome_tarefa}] 🎬 Processando ({sufixo_formato}) a partir de '{caminho_video_resolvido.name}'...")

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
        except ffmpeg.Error as e:
            erro_detalhe = e.stderr.decode("utf-8", errors="ignore") if e.stderr else str(e)
            print(f" ❌ Erro no FFmpeg ao gerar '{nome_tarefa}':\n{erro_detalhe}\n")
        except Exception as e:
            print(f" ❌ Erro ao gerar o corte '{nome_tarefa}': {e}\n")

    print("🏁 Processo concluído! Os vídeos estão na pasta 'cortes_prontos/'.")


# =====================================================================
# 4. PONTO DE PARTIDA DO PROGRAMA
# =====================================================================

if __name__ == "__main__":
    modo_escolhido = perguntar_modo_de_corte()
    recortar_videos_locais(modo=modo_escolhido)