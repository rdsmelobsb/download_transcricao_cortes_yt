import argparse
import json
import unicodedata
import uuid
from pathlib import Path
from typing import Optional
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

# Define os caminhos padrão na mesma pasta do script
COOKIES_FILE = BASE_DIR / "cookies.txt"
CANAIS_FILE = BASE_DIR / "canais.json"
ARCHIVE_FILE = BASE_DIR / "historico_downloads.txt"


# =====================================================================
# 2. CONFIGURAÇÃO BASE E FILTROS DO YT-DLP
# =====================================================================

def _opcoes_base_ydl(output_template: str) -> dict:
    """Retorna as opções comuns do yt-dlp, incluindo autenticação via cookies."""
    ydl_opts = {
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "outtmpl": output_template,
        "quiet": False,
        "no_warnings": False,
        "js_runtimes": {"deno": {"path": None}, "node": {"path": None}},
        "remote_components": ["ejs:github"],
        "extractor_args": {"youtubetab": {"skip": ["authcheck"]}},
    }

    if COOKIES_FILE.exists():
        ydl_opts["cookiefile"] = str(COOKIES_FILE)
        print(f"-> Usando cookies de autenticação em: {COOKIES_FILE.name}")
    else:
        print(f"-> Aviso: '{COOKIES_FILE.name}' não encontrado em {BASE_DIR}.")
        print("-> Tentando baixar sem cookies...")

    return ydl_opts


def _normalizar_texto(texto: str) -> str:
    """Remove acentos e converte para minúsculas para comparação editorial segura."""
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode("ascii")
    return sem_acento.lower().strip()


def criar_filtro_video(
    duracao_min: Optional[int] = None,
    duracao_max: Optional[int] = None,
    palavras_bloqueadas: Optional[list[str]] = None,
    palavras_obrigatorias: Optional[list[str]] = None,
):
    """
    Cria uma função match_filter para o yt-dlp ignorar lives, filtrar por duração
    e barrar vídeos fora da linha editorial (blacklist/whitelist no título) antes do download.
    """
    bloqueadas_norm = [_normalizar_texto(p) for p in (palavras_bloqueadas or []) if p and p.strip()]
    obrigatorias_norm = [_normalizar_texto(p) for p in (palavras_obrigatorias or []) if p and p.strip()]

    def _filtro(info: dict, *, incomplete: bool) -> Optional[str]:
        if incomplete:
            return None

        if info.get("is_live") or info.get("live_status") == "is_live":
            return "Ignorado: transmissão ao vivo em andamento."

        duracao = info.get("duration")
        if duracao is not None:
            if duracao_min is not None and duracao < duracao_min:
                return f"Ignorado: duração ({duracao}s) menor que o mínimo ({duracao_min}s)."
            if duracao_max is not None and duracao > duracao_max:
                return f"Ignorado: duração ({duracao}s) maior que o máximo ({duracao_max}s)."

        titulo_norm = _normalizar_texto(info.get("title") or "")
        if titulo_norm:
            for termo in bloqueadas_norm:
                if termo in titulo_norm:
                    return f"Ignorado (filtro editorial — bloqueado '{termo}'): {info.get('title')}"

            if obrigatorias_norm and not any(termo in titulo_norm for termo in obrigatorias_norm):
                return f"Ignorado (filtro editorial — fora do nicho): {info.get('title')}"

        return None

    return _filtro


# =====================================================================
# 3. FUNÇÃO DE DOWNLOAD MANUAL (VÍDEO ÚNICO)
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
    output_template = str(TEMP_DIR / f"{job_id}_raw.%(ext)s")
    ydl_opts = _opcoes_base_ydl(output_template)
    ydl_opts["noplaylist"] = True

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info(youtube_url, download=True)

    final_path = TEMP_DIR / f"{job_id}_raw.mp4"

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
# 4. MONITORAMENTO AUTOMÁTICO DE CANAIS (VIA CANAIS.JSON)
# =====================================================================

def monitorar_canais(config_path: Path = CANAIS_FILE, dry_run: bool = False) -> None:
    """Lê a lista de canais do JSON e baixa apenas os vídeos novos dentro dos filtros."""
    if not config_path.exists():
        print(f"❌ Arquivo de configuração não encontrado: {config_path}")
        return

    with config_path.open("r", encoding="utf-8") as f:
        canais = json.load(f)

    if not isinstance(canais, list):
        print(f"❌ O arquivo '{config_path.name}' deve conter uma lista JSON de canais.")
        return

    canais_ativos = [c for c in canais if c.get("ativo", True)]
    if not canais_ativos:
        print(f"⚠️ Nenhum canal ativo encontrado em '{config_path.name}'.")
        print("-> Edite o arquivo e defina \"ativo\": true nos canais que deseja monitorar.")
        return

    print(f"🔎 Iniciando verificação de {len(canais_ativos)} canal(is)...")
    if dry_run:
        print("🧪 Modo simulação (--dry-run): nenhum vídeo será baixado.\n")

    for canal in canais_ativos:
        nome = canal.get("nome") or canal.get("url", "Canal sem nome")
        url = (canal.get("url") or "").strip()
        if not url:
            print(f"⚠️ Canal '{nome}' sem URL configurada. Pulando...")
            continue

        max_recentes = int(canal.get("max_recentes", 3))
        duracao_min = canal.get("duracao_min_segundos")
        duracao_max = canal.get("duracao_max_segundos")
        palavras_bloqueadas = canal.get("palavras_bloqueadas") or []
        palavras_obrigatorias = canal.get("palavras_obrigatorias") or []

        print(f"\n=== Verificando: {nome} (últimos {max_recentes} vídeos) ===")

        output_template = str(
            TEMP_DIR / "%(upload_date)s_%(id)s_%(title).60B.%(ext)s"
        )
        ydl_opts = _opcoes_base_ydl(output_template)
        ydl_opts.update({
            "noplaylist": False,
            "playlistend": max_recentes,
            "ignoreerrors": True,
            "restrictfilenames": True,
            "download_archive": str(ARCHIVE_FILE),
            "match_filter": criar_filtro_video(
                duracao_min,
                duracao_max,
                palavras_bloqueadas=palavras_bloqueadas,
                palavras_obrigatorias=palavras_obrigatorias,
            ),
        })

        if dry_run:
            ydl_opts["simulate"] = True

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception as e:
            print(f"❌ Erro ao verificar o canal '{nome}': {e}")

    print("\n🏁 Verificação de canais concluída!")


# =====================================================================
# 5. PONTO DE PARTIDA DO PROGRAMA
# =====================================================================

def executar_modo_manual() -> None:
    print("--- BAIXADOR DE VÍDEOS DO YOUTUBE ---")
    url_input = input("Digite o link do vídeo do YouTube: ").strip()

    if not url_input:
        print("Erro: Nenhum link foi fornecido.")
        return

    unique_job_id = str(uuid.uuid4())[:8]
    print(f"\nIniciando download (ID: {unique_job_id})...")
    print(f"Pasta de destino: {TEMP_DIR}\n")

    try:
        video_path = download_youtube_video(url_input, unique_job_id)
        print("\n✅ Download concluído com sucesso!")
        print(f"📁 Arquivo salvo em: {video_path}")
    except Exception as e:
        print(f"\n❌ Ocorreu um erro no download: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Baixador de vídeos do YouTube (modo manual ou monitor de canais)."
    )
    parser.add_argument(
        "--monitor",
        action="store_true",
        help="Verifica automaticamente os canais listados em canais.json.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=CANAIS_FILE,
        help="Caminho para o arquivo JSON de canais (padrão: canais.json).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula a verificação sem baixar os vídeos nem gravar no histórico.",
    )

    args = parser.parse_args()

    if args.monitor:
        monitorar_canais(config_path=args.config, dry_run=args.dry_run)
    else:
        executar_modo_manual()
