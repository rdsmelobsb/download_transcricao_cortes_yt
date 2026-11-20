"""
Publicador de Vídeos no YouTube via YouTube Data API v3.

Lê os cortes com status 'renderizado' em temp/tarefas_corte.json, faz o upload
como Shorts, agenda a publicação conforme o horário sugerido e atualiza o manifesto.
"""

import argparse
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload

import manifesto

# =====================================================================
# 1. CONFIGURAÇÃO E ESCOPO OAUTH
# =====================================================================

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "cortes_prontos"
CLIENT_SECRETS_FILE = BASE_DIR / "client_secrets.json"
TOKEN_FILE = BASE_DIR / "token.json"

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"


# =====================================================================
# 2. AUTENTICAÇÃO OAUTH2 (GOOGLE)
# =====================================================================

def obter_servico_youtube():
    """Autentica o usuário via OAuth2 gerando e reutilizando o token.json."""
    if not CLIENT_SECRETS_FILE.exists():
        print(f"❌ Arquivo '{CLIENT_SECRETS_FILE.name}' não encontrado na raiz do projeto!")
        print("-> Baixe o JSON de credenciais OAuth (Desktop) no Google Cloud Console.")
        sys.exit(1)

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"⚠️ Erro ao renovar token expirado: {e}")
                creds = None

        if not creds:
            print("\n🔑 Iniciando autorização OAuth com a conta Google do YouTube...")
            print("-> Uma janela do navegador será aberta para você confirmar a permissão.")
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                str(CLIENT_SECRETS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Salva o token para as próximas execuções
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
        print("✅ Autenticação realizada e salva em 'token.json'!\n")

    return googleapiclient.discovery.build(
        API_SERVICE_NAME, API_VERSION, credentials=creds
    )


# =====================================================================
# 3. UTILITÁRIOS DE METADADOS E AGENDAMENTO
# =====================================================================

def calcular_data_agendamento(horario_sugerido: str, offset_dias: int = 0) -> str:
    """
    Calcula a data e horário no formato ISO 8601 UTC (ex: 2026-11-20T14:30:00Z)
    para o agendamento no YouTube.
    O horário sugerido é considerado no fuso horário local de Brasília (UTC-3).
    """
    agora = datetime.now()
    try:
        horas, minutos = map(int, horario_sugerido.split(":"))
    except ValueError:
        horas, minutos = 11, 30

    data_alvo = agora.replace(hour=horas, minute=minutos, second=0, microsecond=0)
    data_alvo += timedelta(days=offset_dias)

    # Se o horário para hoje já passou (com folga de 15 minutos), joga para amanhã
    if offset_dias == 0 and data_alvo <= agora + timedelta(minutes=15):
        data_alvo += timedelta(days=1)

    # Conversão de horário local (Brasília UTC-3) para UTC (+3h)
    data_utc = data_alvo + timedelta(hours=3)
    return data_utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def formatar_titulo_shorts(titulo: str) -> str:
    """Garante a tag #Shorts no título e respeita o limite de 100 caracteres."""
    t = titulo.strip()
    if "#Shorts" not in t and "#shorts" not in t:
        if len(t) + len(" #Shorts") <= 100:
            t = f"{t} #Shorts"
    return t[:100]


def formatar_descricao_completa(tarefa: dict[str, Any]) -> str:
    """Monta a descrição do vídeo com contextualização, citações e hashtags."""
    partes = []
    titulo_capa = tarefa.get("titulo_capa", "").strip()
    if titulo_capa:
        partes.append(f"{titulo_capa}\n")

    texto_pub = tarefa.get("texto_publicacao", "").strip()
    if texto_pub:
        partes.append(texto_pub)

    hashtags = tarefa.get("hashtags", "").strip()
    if hashtags:
        partes.append(f"\n{hashtags} #Shorts")
    else:
        partes.append("\n#PolíticaDireta #Shorts")

    return "\n\n".join(partes)


# =====================================================================
# 4. UPLOAD DO VÍDEO NO YOUTUBE
# =====================================================================

def fazer_upload_corte(
    youtube,
    tarefa: dict[str, Any],
    agendar: bool = True,
    privado: bool = False,
    offset_dias: int = 0
) -> Optional[str]:
    """
    Envia o corte para o YouTube via API e retorna o ID do vídeo publicado/agendado.
    """
    caminho_video = None
    if tarefa.get("arquivo_final"):
        candidato = BASE_DIR / tarefa["arquivo_final"]
        if candidato.exists():
            caminho_video = candidato

    if not caminho_video:
        # Tenta localizar na pasta cortes_prontos pelo id da tarefa
        id_tarefa = tarefa["id"]
        for p in OUTPUT_DIR.glob(f"corte_{id_tarefa}_*"):
            if p.suffix.lower() == ".mp4":
                caminho_video = p
                break

    if not caminho_video or not caminho_video.exists():
        print(f"❌ Erro [{tarefa['id']}]: Arquivo de vídeo renderizado não encontrado!")
        return None

    titulo_final = formatar_titulo_shorts(tarefa.get("title", "Corte Política Direta"))
    descricao_final = formatar_descricao_completa(tarefa)

    # Extrai tags para os metadados internos do YouTube
    tags_brutas = re.findall(r"#(\w+)", tarefa.get("hashtags", ""))
    tags = list(dict.fromkeys(tags_brutas + ["PolíticaDireta", "Shorts"]))

    body = {
        "snippet": {
            "title": titulo_final,
            "description": descricao_final,
            "tags": tags,
            "categoryId": "25",  # Categoria 25: Notícias e Política (News & Politics)
            "defaultLanguage": "pt",
            "defaultAudioLanguage": "pt",
        },
        "status": {
            "selfDeclaredMadeForKids": False,
        }
    }

    horario_sugerido = tarefa.get("horario_sugerido", "11:30")

    if privado:
        body["status"]["privacyStatus"] = "private"
        print(f"🔒 Status: Privado (sem agendamento)")
    elif agendar:
        data_iso_utc = calcular_data_agendamento(horario_sugerido, offset_dias=offset_dias)
        body["status"]["privacyStatus"] = "private"
        body["status"]["publishAt"] = data_iso_utc
        print(f"📅 Agendando para: {horario_sugerido} ({data_iso_utc} UTC)")
    else:
        body["status"]["privacyStatus"] = "public"
        print(f"📢 Status: Público imediato")

    print(f"📤 Fazendo upload de '{caminho_video.name}'...")
    print(f"📌 Título: {titulo_final}")

    media = MediaFileUpload(
        str(caminho_video),
        mimetype="video/mp4",
        resumable=True,
        chunksize=1024 * 1024 * 4  # Chunks de 4MB
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            progresso = int(status.progress() * 100)
            print(f"   Progresso do envio: {progresso}%", end="\r")

    video_id = response.get("id")
    print(f"\n✅ Upload concluído com sucesso!")
    print(f"🔗 Link do Short: https://youtube.com/shorts/{video_id}\n")
    return video_id


# =====================================================================
# 5. FLUXO PRINCIPAL
# =====================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Publica/Agenda cortes renderizados no YouTube via API oficial."
    )
    parser.add_argument(
        "--id",
        action="append",
        dest="ids",
        help="Publica apenas este ID do manifesto (pode repetir: --id A_1 --id A_2).",
    )
    parser.add_argument(
        "--todos",
        action="store_true",
        help="Publica todos os cortes renderizados pendentes de publicação.",
    )
    parser.add_argument(
        "--privado",
        action="store_true",
        help="Sobe como privado sem data de agendamento.",
    )
    parser.add_argument(
        "--imediato",
        action="store_true",
        help="Publica como público imediatamente (sem agendar).",
    )
    parser.add_argument(
        "--amanha",
        action="store_true",
        help="Força o agendamento para o dia de amanhã.",
    )

    args = parser.parse_args()

    # Carrega manifesto
    try:
        tarefas = manifesto.carregar()
    except Exception as e:
        print(f"❌ Erro ao ler manifesto: {e}")
        sys.exit(1)

    # Filtra tarefas prontas para publicação
    renderizadas = [
        t for t in tarefas
        if t.get("status") == manifesto.STATUS_RENDERIZADO
    ]

    if not renderizadas:
        print("⚠️ Nenhum corte com status 'renderizado' encontrado no manifesto!")
        print("-> Execute primeiro: python cortes.py para gerar os arquivos de vídeo.")
        sys.exit(0)

    if args.ids:
        por_id = {t["id"]: t for t in renderizadas}
        selecionadas = [por_id[i] for i in args.ids if i in por_id]
        if not selecionadas:
            print(f"❌ Nenhum corte renderizado encontrado para os IDs informados: {args.ids}")
            sys.exit(1)
    else:
        # Se não especificou --todos nem --id, mostra interativo
        print("===================================================")
        print("       CORTES PRONTOS PARA POSTAR NO YOUTUBE       ")
        print("===================================================")
        for idx, t in enumerate(renderizadas, start=1):
            print(f"[{idx}] {t['id']} ({t['horario_sugerido']}): {t['title']}")
        print("===================================================")
        print("Opções:")
        print(" - Digite o número do corte (ou vários, ex: 1,2,3)")
        print(" - Pressione ENTER para postar TODOS os listados")
        print("===================================================")

        escolha = input("Sua escolha: ").strip()
        if not escolha:
            selecionadas = renderizadas
        else:
            selecionadas = []
            for p in escolha.split(","):
                p = p.strip()
                if p.isdigit() and 1 <= int(p) <= len(renderizadas):
                    selecionadas.append(renderizadas[int(p) - 1])

    if not selecionadas:
        print("Nenhum corte selecionado.")
        sys.exit(0)

    # Conecta à API do YouTube
    youtube = obter_servico_youtube()

    offset_dias = 1 if args.amanha else 0
    agendar = not args.imediato and not args.privado
    publicados_com_sucesso = 0

    print(f"\n🚀 Iniciando upload de {len(selecionadas)} corte(s)...\n")

    for tarefa in selecionadas:
        video_id = fazer_upload_corte(
            youtube,
            tarefa,
            agendar=agendar,
            privado=args.privado,
            offset_dias=offset_dias
        )

        if video_id:
            tarefa["status"] = manifesto.STATUS_PUBLICADO
            tarefa["youtube_video_id"] = video_id
            tarefa["youtube_url"] = f"https://youtube.com/shorts/{video_id}"
            tarefa["publicado_em"] = manifesto.agora_iso()
            manifesto.salvar(tarefas)
            publicados_com_sucesso += 1

            # Pausa de 3 segundos entre chamadas de API por cortesia
            time.sleep(3)

    print("===================================================")
    print(f"🏁 Processo finalizado! {publicados_com_sucesso} vídeo(s) enviado(s) ao YouTube.")
    print(f"📦 Manifesto atualizado com status 'publicado'.")
    print("===================================================")


if __name__ == "__main__":
    main()
