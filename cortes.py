import os
from pathlib import Path
import ffmpeg

# =====================================================================
# 1. CONFIGURAÇÃO DE DIRETÓRIOS E LISTA DE TAREFAS
# =====================================================================

# Define a pasta onde os cortes prontos serão salvos e cria a pasta se não existir
OUTPUT_DIR = Path("cortes_prontos")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Lista de cortes a serem realizados.
# Parâmetros ajustáveis:
# - "id": número do corte para organização
# - "nome": nome que dará origem ao arquivo salvo
# - "video_path": nome ou caminho do arquivo de vídeo original
# - "start": tempo inicial do corte em segundos (ex: 311.000 = 5 min e 11 seg)
# - "end": tempo final do corte em segundos (ex: 354.000 = 5 min e 54 seg)


TAREFAS_DE_CORTE = [
    {
        "id": 1,
        "nome": "Beneficiario Final dos Escandalos",
        "video_path": "icl_pos_eleicao.mp4",
        "title": "Paulo Motoryn: Flávio é o beneficiário final do Master e do INSS",
        "start": 793.900,  # 00:13:13,900
        "end": 845.900     # 00:14:05,900
    },
    {
        "id": 2,
        "nome": "Juventude e Fim da Escala 6x1",
        "video_path": "icl_pos_eleicao.mp4",
        "title": "Estudante da UFF: 'O povo organizado conquistou o fim da escala 6x1'",
        "start": 5523.900, # 01:32:03,900
        "end": 5575.000    # 01:32:55,000
    },
    {
        "id": 3,
        "nome": "Investimento Recorde e Confianca em Lula",
        "video_path": "icl_pos_eleicao.mp4",
        "title": "Prof. Trevisan: Investimento estrangeiro bate recorde histórico com Lula",
        "start": 6168.900, # 01:42:48,900
        "end": 6226.000    # 01:43:46,000
    }
]

# =====================================================================
# 2. FUNÇÃO PARA PERGUNTAR O FORMATO AO USUÁRIO
# =====================================================================

def perguntar_modo_de_corte() -> bool:
    """
    Exibe um menu no terminal perguntando ao usuário qual formato deseja.
    
    Retorna:
        bool: True se o usuário quiser o corte vertical (9:16),
              False se quiser apenas cortar o tempo mantendo o formato original.
    """
    print("===================================================")
    print("         ESCOLHA O MODO DE CORTE DO VÍDEO          ")
    print("===================================================")
    print("[1] Cortar no formato vertical (9:16 - 1080x1920 para Shorts/Reels)")
    print("[2] Apenas cortar início e fim (Manter o formato original do vídeo)")
    print("===================================================")

    # Repete a pergunta até que o usuário digite 1 ou 2
    while True:
        escolha = input("Digite o número da opção desejada (1 ou 2): ").strip()
        
        if escolha == "1":
            print("\n-> Modo selecionado: CORTE VERTICAL (9:16)\n")
            return True
        elif escolha == "2":
            print("\n-> Modo selecionado: MANTER FORMATO ORIGINAL\n")
            return False
        else:
            print("⚠️ Opção inválida! Por favor, digite apenas 1 ou 2.\n")


# =====================================================================
# 3. FUNÇÃO PRINCIPAL DE PROCESSAMENTO DOS CORTES
# =====================================================================

def recortar_videos_locais(aplicar_corte_vertical: bool):
    """
    Percorre a lista TAREFAS_DE_CORTE e gera os vídeos cortados usando FFmpeg.

    Parâmetros:
        aplicar_corte_vertical (bool): Define se o vídeo será redimensionado para 9:16 (True)
                                       ou se manterá a proporção original (False).
    """
    print("Iniciando o processamento dos cortes locais (sem legendas)...\n")

    # Define um sufixo para organizar o nome do arquivo de saída
    sufixo_formato = "vertical" if aplicar_corte_vertical else "original"

    for tarefa in TAREFAS_DE_CORTE:
        # Extrai os dados de cada tarefa da lista
        caminho_video = tarefa["video_path"]
        nome_tarefa = tarefa["nome"]
        inicio = tarefa["start"]
        fim = tarefa["end"]
        
        # Calcula a duração exata do corte em segundos
        duracao = fim - inicio
        
        # Monta o nome do arquivo final sem espaços e tudo em minúsculo
        nome_limpo = nome_tarefa.lower().replace(" ", "_")
        saida = OUTPUT_DIR / f"corte_{tarefa['id']}_{sufixo_formato}_{nome_limpo}.mp4"

        # Verifica se o vídeo original existe antes de tentar cortar
        if not os.path.exists(caminho_video):
            print(f"[{nome_tarefa}] ❌ Erro: Vídeo não encontrado em '{caminho_video}'.")
            continue

        print(f"[{nome_tarefa}] 🎬 Processando ({sufixo_formato})...")

        # Configurações padrão de qualidade de vídeo e áudio do FFmpeg
        # Parâmetros ajustáveis:
        # - video_bitrate: qualidade da imagem ("4M" = 4 Megabits por segundo)
        # - audio_bitrate: qualidade do som ("192k" = alta qualidade)
        # - preset: velocidade de conversão ("fast" equilibra rapidez e qualidade)
        opcoes_ffmpeg = {
            "vcodec": "libx264",
            "acodec": "aac",
            "video_bitrate": "4M",
            "audio_bitrate": "192k",
            "preset": "fast",
            "movflags": "+faststart"
        }

        # Se o usuário escolheu a opção 1 (Vertical), adiciona o filtro de corte 9:16
        if aplicar_corte_vertical:
            #opcoes_ffmpeg["vf"] = "crop='min(iw,ih*9/16)':'min(ih,iw*16/9)',scale=1080:1920"
            opcoes_ffmpeg["vf"] = (
                "scale=1080:1920:force_original_aspect_ratio=decrease,"
                "pad=1080:1920:(ow-iw)/2:(oh-ih)/2"
            )

        try:
            # 1. Carrega o vídeo no ponto inicial (ss) pela duração calculada (t)
            stream = ffmpeg.input(caminho_video, ss=inicio, t=duracao)
            
            # 2. Aplica as configurações (com ou sem o filtro vertical, dependendo da escolha)
            # O operador **opcoes_ffmpeg repassa todas as configurações do dicionário acima
            stream = ffmpeg.output(stream, str(saida), **opcoes_ffmpeg)
            
            # 3. Executa o corte sobrescrevendo arquivos antigos de mesmo nome
            ffmpeg.overwrite_output(stream).run(quiet=True)
            
            print(f" ✅ Sucesso! Vídeo salvo em: {saida.resolve()}\n")
        except Exception as e:
            print(f" ❌ Erro ao gerar o corte '{nome_tarefa}': {e}\n")

    print("🏁 Processo concluído! Os vídeos estão na pasta 'cortes_prontos/'.")


# =====================================================================
# 4. PONTO DE PARTIDA DO PROGRAMA
# =====================================================================

if __name__ == "__main__":
    # Passo 1: Pergunta ao usuário como ele quer cortar os vídeos
    modo_vertical = perguntar_modo_de_corte()
    
    # Passo 2: Executa a função de recorte passando a resposta do usuário
    recortar_videos_locais(aplicar_corte_vertical=modo_vertical)