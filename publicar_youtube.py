"""
Publicador de Vídeos no YouTube via YouTube Data API v3 com Agendador Inteligente.

Lê os cortes com status 'renderizado' em temp/tarefas_corte.json, calcula uma
agenda livre de colisões via agendador.py (respeitando slots ocupados, espaçamento
mínimo entre Shorts e diversidade temática), faz o upload via API oficial e
atualiza o manifesto com data/hora exata de publicação.
"""

import argparse
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload

import agendador
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

        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
        print("✅ Autenticação realizada e salva em 'token.json'!\n")

    return googleapiclient.discovery.build(
        API_SERVICE_NAME, API_VERSION, credentials=creds
    )


# =====================================================================
# 3. UTILITÁRIOS DE METADADOS
# =====================================================================

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


def localizar_arquivo_video(tarefa: dict[str, Any]) -> Optional[Path]:
    """Localiza o arquivo .mp4 renderizado correspondente à tarefa."""
    if tarefa.get("arquivo_final"):
        candidato = BASE_DIR / tarefa["arquivo_final"]
        if candidato.exists():
            return candidato

    id_tarefa = tarefa["id"]
    for p in OUTPUT_DIR.glob(f"corte_{id_tarefa}_*"):
        if p.suffix.lower() == ".mp4":
            return p
    return None


# =====================================================================
# 4. UPLOAD DO VÍDEO NO YOUTUBE
# =====================================================================

def fazer_upload_corte(
    youtube,
    tarefa: dict[str, Any],
    agendar: bool = True,
    privado: bool = False,
    dt_brt: Optional[datetime] = None,
    iso_utc: Optional[str] = None,
) -> Optional[str]:
    """
    Envia o corte para o YouTube via API e retorna o ID do vídeo publicado/agendado.
    """
    caminho_video = localizar_arquivo_video(tarefa)
    if not caminho_video or not caminho_video.exists():
        print(f"❌ Erro [{tarefa['id']}]: Arquivo de vídeo renderizado não encontrado!")
        return None

    titulo_final = formatar_titulo_shorts(tarefa.get("title", "Corte Política Direta"))
    descricao_final = formatar_descricao_completa(tarefa)

    tags_brutas = re.findall(r"#(\w+)", tarefa.get("hashtags", ""))
    tags = list(dict.fromkeys(tags_brutas + ["PolíticaDireta", "Shorts"]))

    body: dict[str, Any] = {
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
        },
    }

    if privado:
        body["status"]["privacyStatus"] = "private"
        print("🔒 Status: Privado (sem agendamento)")
    elif agendar and iso_utc and dt_brt:
        body["status"]["privacyStatus"] = "private"
        body["status"]["publishAt"] = iso_utc
        print(f"📅 Agendando para: {agendador.formatar_data_br(dt_brt)} ({iso_utc})")
    else:
        body["status"]["privacyStatus"] = "public"
        print("📢 Status: Público imediato")

    print(f"📤 Fazendo upload de '{caminho_video.name}'...")
    print(f"📌 Título: {titulo_final}")

    media = MediaFileUpload(
        str(caminho_video),
        mimetype="video/mp4",
        resumable=True,
        chunksize=1024 * 1024 * 4,  # Chunks de 4MB
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            progresso = int(status.progress() * 100)
            print(f"   Progresso do envio: {progresso}%", end="\r")

    video_id = response.get("id")
    print("\n✅ Upload concluído com sucesso!")
    print(f"🔗 Link do Short: https://youtube.com/shorts/{video_id}\n")
    return video_id


# =====================================================================
# 5. FLUXO PRINCIPAL
# =====================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Publica/Agenda cortes renderizados no YouTube sem colisões de horário."
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
        help="Publica automaticamente todos os cortes renderizados pendentes sem perguntar.",
    )
    parser.add_argument(
        "--por-dia",
        type=int,
        default=3,
        help="Quantidade de Shorts por dia na grade automática (1 a 6; padrão: 3).",
    )
    parser.add_argument(
        "--slots",
        type=str,
        default=None,
        help="Horários customizados em BRT separados por vírgula (ex: '09:00,13:00,18:00,21:00').",
    )
    parser.add_argument(
        "--limite",
        type=int,
        default=0,
        help="Limite máximo de vídeos enviados nesta execução (ex: --limite 6 para respeitar cota diária).",
    )
    parser.add_argument(
        "--intervalo-min",
        type=int,
        default=agendador.INTERVALO_MINIMO_PADRAO_MIN,
        help="Intervalo mínimo em minutos entre quaisquer dois Shorts (padrão: 120 min).",
    )
    parser.add_argument(
        "--sem-intercalar",
        action="store_true",
        help="Desativa o Round-Robin por vídeo de origem.",
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
        help="Começa a preencher slots apenas a partir de amanhã.",
    )
    parser.add_argument(
        "--simular",
        "--dry-run",
        dest="simular",
        action="store_true",
        help="Simula e exibe o calendário de agendamento sem fazer upload nem alterar o manifesto.",
    )
    parser.add_argument(
        "--agenda",
        action="store_true",
        help="Exibe os cortes futuros já agendados no manifesto e encerra.",
    )
    parser.add_argument(
        "--min-afinidade",
        type=int,
        default=75,
        help="Nota mínima de afinidade editorial (0-100) para publicar no YouTube (padrão: 75).",
    )

    args = parser.parse_args()

    # 1. Carrega manifesto
    try:
        tarefas = manifesto.carregar()
    except Exception as e:
        print(f"❌ Erro ao ler manifesto: {e}")
        sys.exit(1)

    if args.agenda:
        agendador.imprimir_agenda_atual(tarefas)
        sys.exit(0)

    # Valida grade de horários antes de qualquer ação
    try:
        grade = agendador.obter_grade_horarios(por_dia=args.por_dia, slots_custom=args.slots)
    except ValueError as e:
        print(f"❌ Configuração de grade inválida: {e}")
        sys.exit(1)

    # 2. Filtra tarefas prontas para publicação (ignorando 'renderizado' cujo .mp4 já foi removido)
    todas_renderizadas = [
        t for t in tarefas
        if t.get("status") == manifesto.STATUS_RENDERIZADO
    ]
    renderizadas_com_arquivo = [t for t in todas_renderizadas if localizar_arquivo_video(t) is not None]
    fantasmas = len(todas_renderizadas) - len(renderizadas_com_arquivo)
    if fantasmas > 0:
        print(f"ℹ️  Ignorando {fantasmas} corte(s) com status 'renderizado' cujo arquivo .mp4 não existe mais em cortes_prontos/.")

    # Portão editorial antes da publicação (bloqueia cortes com baixa afinidade ou FORA_DO_NICHO)
    def _passa_afinidade_yt(tarefa: dict[str, Any]) -> bool:
        if args.ids:
            return True  # Seleção explícita por --id sempre respeita o comando manual
        if tarefa.get("categoria_editorial") == "FORA_DO_NICHO":
            return False
        nota = tarefa.get("nota_afinidade")
        if nota is None:
            return True  # Cortes legados (anteriores ao portão editorial) seguem liberados
        return int(nota) >= args.min_afinidade

    renderizadas = [t for t in renderizadas_com_arquivo if _passa_afinidade_yt(t)]
    barrados_afinidade = len(renderizadas_com_arquivo) - len(renderizadas)
    if barrados_afinidade > 0:
        print(f"🛡️  Portão editorial: {barrados_afinidade} corte(s) retido(s) por afinidade < {args.min_afinidade}/100.")

    # Prioriza os cortes mais alinhados (60% afinidade editorial + 40% packaging CTR)
    def _score_prioridade_yt(tarefa: dict[str, Any]) -> tuple[float, str]:
        afin = float(tarefa.get("nota_afinidade") if tarefa.get("nota_afinidade") is not None else 80)
        pack = float(tarefa.get("packaging_score") if tarefa.get("packaging_score") is not None else 85)
        return (round(0.6 * afin + 0.4 * pack, 2), str(tarefa.get("criado_em", "")))

    renderizadas.sort(key=_score_prioridade_yt, reverse=True)

    if not renderizadas:
        print("⚠️ Nenhum corte elegível com status 'renderizado' encontrado no manifesto!")
        print("-> Execute primeiro: python cortes.py para gerar os arquivos de vídeo.")
        sys.exit(0)

    if args.ids:
        por_id = {t["id"]: t for t in renderizadas}
        selecionadas = [por_id[i] for i in args.ids if i in por_id]
        if not selecionadas:
            print(f"❌ Nenhum corte renderizado encontrado para os IDs informados: {args.ids}")
            sys.exit(1)
    elif args.todos or args.simular:
        selecionadas = renderizadas
    else:
        print("===================================================")
        print("       CORTES PRONTOS PARA POSTAR NO YOUTUBE       ")
        print("===================================================")
        for idx, t in enumerate(renderizadas, start=1):
            afin_txt = f" | afin {t['nota_afinidade']}/100" if t.get("nota_afinidade") is not None else ""
            cat_txt = f" [{t['categoria_editorial']}]" if t.get("categoria_editorial") else ""
            print(f"[{idx}] {t['id']} ({t.get('horario_sugerido', '11:30')}{afin_txt}){cat_txt}: {t['title']}")
        print("===================================================")
        print(f"Grade ativa ({len(grade)}/dia): {', '.join(grade)} | Respiro mínimo: {args.intervalo_min} min")
        print("Opções:")
        print(" - Digite o número do corte (ou vários, ex: 1,2,3)")
        print(" - Pressione ENTER para agendar TODOS na fila sem colisões")
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

    offset_dias = 1 if args.amanha else 0
    agendar = not args.imediato and not args.privado

    # 3. Planeja a agenda sem colisões
    if agendar:
        plano = agendador.planejar_agenda(
            tarefas_manifesto=tarefas,
            tarefas_selecionadas=selecionadas,
            por_dia=args.por_dia,
            slots_custom=args.slots,
            offset_dias=offset_dias,
            intervalo_min_minutos=args.intervalo_min,
            intercalar=not args.sem_intercalar,
        )
        if args.limite and args.limite > 0:
            plano = plano[:args.limite]

        agendador.imprimir_plano_agenda(
            plano,
            titulo=f"CALENDÁRIO PLANEJADO ({len(grade)}/DIA: {', '.join(grade)} | MÍN. {args.intervalo_min}m)",
        )
    else:
        itens_envio = selecionadas[:args.limite] if (args.limite and args.limite > 0) else selecionadas
        plano = [(t, None, None) for t in itens_envio]

    if args.simular:
        print("🧪 Modo --simular ativo: nenhum upload foi realizado e o manifesto não foi alterado.")
        sys.exit(0)

    if not args.todos and not args.ids:
        confirma = input(f"Confirmar o envio de {len(plano)} corte(s) acima para o YouTube? [S/n]: ").strip().lower()
        if confirma not in ["", "s", "sim"]:
            print("Operação cancelada.")
            sys.exit(0)

    # 4. Conecta à API do YouTube e executa os envios
    youtube = obter_servico_youtube()
    publicados_com_sucesso = 0

    print(f"\n🚀 Iniciando upload de {len(plano)} corte(s)...\n")

    for tarefa, dt_brt, iso_utc in plano:
        try:
            video_id = fazer_upload_corte(
                youtube,
                tarefa,
                agendar=agendar,
                privado=args.privado,
                dt_brt=dt_brt,
                iso_utc=iso_utc,
            )
        except googleapiclient.errors.HttpError as e:
            erro_str = str(e)
            if "quotaExceeded" in erro_str or "uploadLimitExceeded" in erro_str:
                print("\n⚠️ LIMITE DIÁRIO DA API DO YOUTUBE ATINGIDO!")
                print(
                    f"-> {publicados_com_sucesso} corte(s) já foram salvos e agendados com sucesso."
                )
                print(
                    "-> Os cortes restantes continuam como 'renderizado' no manifesto e serão "
                    "agendados a partir do próximo slot livre quando você rodar novamente amanhã."
                )
                break
            print(f"❌ Erro HTTP da API do YouTube em [{tarefa['id']}]: {e}")
            continue
        except Exception as e:
            print(f"❌ Erro inesperado ao enviar [{tarefa['id']}]: {e}")
            continue

        if video_id:
            tarefa["status"] = manifesto.STATUS_PUBLICADO
            tarefa["youtube_video_id"] = video_id
            tarefa["youtube_url"] = f"https://youtube.com/shorts/{video_id}"
            tarefa["publicado_em"] = manifesto.agora_iso()
            if agendar and dt_brt and iso_utc:
                tarefa["agendado_para_brt"] = dt_brt.strftime("%Y-%m-%d %H:%M")
                tarefa["agendado_para_utc"] = iso_utc
            manifesto.salvar(tarefas)
            publicados_com_sucesso += 1

            # Pausa de 3 segundos entre chamadas de API por cortesia
            time.sleep(3)

    print("===================================================")
    print(f"🏁 Processo finalizado! {publicados_com_sucesso} vídeo(s) enviado(s) ao YouTube.")
    print("📦 Manifesto atualizado com status 'publicado' e horários sem colisão.")
    print("===================================================")


if __name__ == "__main__":
    main()
