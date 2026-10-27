import uuid
from pathlib import Path
import yt_dlp

# =====================================================================
# 1. CONFIGURAÇÃO DE DIRETÓRIOS E ARQUIVOS
# =====================================================================

# Identifica a pasta exata onde este arquivo (download.py) está salvo
BASE_DIR = Path(__file__).resolve().parent

# Se o script já estiver dentro da pasta 'temp', usa a própria pasta.
# Caso contrário, cria/usa uma subpasta chamada 'temp'.
if BASE_DIR.name.lower() == "temp":
    TEMP_DIR = BASE_DIR
else:
    TEMP_DIR = BASE_DIR / "temp"
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Define o caminho do arquivo de cookies na mesma pasta do script
COOKIES_FILE = BASE_DIR / "cookies.txt"


# =====================================================================
# 2. FUNÇÃO PRINCIPAL DE DOWNLOAD
# =====================================================================

def download_youtube_video(youtube_url: str, job_id: str) -> Path:
    """
    Baixa um vídeo do YouTube na melhor qualidade disponível e salva em MP4.

    Parâmetros:
        youtube_url (str): O link completo do vídeo do YouTube.
        job_id (str): Um código único para dar nome ao arquivo baixado.

    Retorna:
        Path: O caminho completo do arquivo de vídeo salvo no computador.
    """
    # Define o modelo de nome do arquivo. Exemplo: "a1b2c3d4_raw.mp4"
    # O termo %(ext)s é preenchido automaticamente pelo yt-dlp com a extensão correta.
    output_template = str(TEMP_DIR / f"{job_id}_raw.%(ext)s")

    # Dicionário de configurações que controla como o yt-dlp vai trabalhar
    ydl_opts = {
        # Parâmetro ajustável: escolhe a melhor qualidade de vídeo + áudio disponível
        "format": "bestvideo+bestaudio/best",
        
        # Parâmetro ajustável: une o áudio e o vídeo gerando um arquivo final .mp4
        "merge_output_format": "mp4",
        
        # Define onde o arquivo será salvo e com qual nome
        "outtmpl": output_template,
        
        # Parâmetros de visualização no terminal (False = mostra tudo na tela)
        "quiet": False,
        "no_warnings": False,
        
        # Evita baixar uma playlist inteira se o link tiver uma lista anexada
        "noplaylist": True,
    }

    # Verifica se o arquivo cookies.txt existe antes de enviá-lo ao yt-dlp
    if COOKIES_FILE.exists():
        ydl_opts["cookiefile"] = str(COOKIES_FILE)
        print(f"-> Usando cookies de autenticação em: {COOKIES_FILE.name}")
    else:
        print(f"-> Aviso: '{COOKIES_FILE.name}' não encontrado em {BASE_DIR}.")
        print("-> Tentando baixar sem cookies...")

    # Inicia o yt-dlp com as configurações acima e faz o download do vídeo
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info(youtube_url, download=True)

    # =================================================================
    # 3. VERIFICAÇÃO DO ARQUIVO BAIXADO
    # =================================================================
    
    # Procura pelo arquivo .mp4 esperado
    final_path = TEMP_DIR / f"{job_id}_raw.mp4"
    
    # Caso tenha sido salvo com outra extensão, localiza o arquivo pelo job_id
    if not final_path.exists():
        arquivos_encontrados = list(TEMP_DIR.glob(f"{job_id}_raw.*"))
        if arquivos_encontrados:
            final_path = arquivos_encontrados[0]
        else:
            raise FileNotFoundError(
                f"Falha ao localizar o vídeo baixado na pasta: {TEMP_DIR}"
            )

    return final_path


# =====================================================================
# 4. PONTO DE PARTIDA DO PROGRAMA (EXECUÇÃO NO TERMINAL)
# =====================================================================

if __name__ == "__main__":
    print("--- BAIXADOR DE VÍDEOS DO YOUTUBE ---")
    
    # Solicita o link ao usuário e remove espaços em branco extras (.strip())
    url_input = input("Digite o link do vídeo do YouTube: ").strip()

    # Validação simples para garantir que o usuário digitou algo
    if not url_input:
        print("Erro: Nenhum link foi fornecido.")
    else:
        # Cria um código único de 8 letras/números (ex: '4f8a9d12')
        unique_job_id = str(uuid.uuid4())[:8]
        print(f"\nIniciando download (ID: {unique_job_id})...")
        print(f"Pasta de destino: {TEMP_DIR}\n")

        # O bloco try/except captura erros para o programa não fechar de forma brusca
        try:
            video_path = download_youtube_video(url_input, unique_job_id)
            print("\n✅ Download concluído com sucesso!")
            print(f"📁 Arquivo salvo em: {video_path}")
        except Exception as e:
            print(f"\n❌ Ocorreu um erro no download: {e}")