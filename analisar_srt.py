import argparse
import json
import os
import re
import sys
import unicodedata
import warnings
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
with warnings.catch_warnings():
    warnings.simplefilter("ignore", FutureWarning)
    import google.generativeai as genai

# =====================================================================
# 1. CONFIGURAÇÃO DE DIRETÓRIOS E CONSTANTES
# =====================================================================

import manifesto

BASE_DIR = Path(__file__).resolve().parent
TEMP_DIR = BASE_DIR / "temp"
OUTPUT_DIR = BASE_DIR / "cortes_prontos"
PROMPT_FILE = BASE_DIR / "prompts" / "politica_direta.md"
PADROES_VENCEDORES_FILE = BASE_DIR / "prompts" / "padroes_vencedores.json"
PADROES_VENCEDORES_KWAI_FILE = BASE_DIR / "prompts" / "padroes_vencedores_kwai.json"
KIT_PUBLICACAO_MD_FILE = OUTPUT_DIR / "kit_publicacao.md"
HISTORICO_SRT_FILE = BASE_DIR / "historico_srt_analisados.txt"
ENV_FILE = BASE_DIR / ".env"

HORARIOS_ESTRATEGICOS = ["11:30", "17:30", "20:30"]
MODELO_PADRAO = "gemini-2.5-flash"


# =====================================================================
# 2. UTILITÁRIOS DE TEMPO, TEXTO E PRÉ-PROCESSAMENTO SRT
# =====================================================================

def srt_time_to_seconds(srt_time: str) -> float:
    """Converte 'HH:MM:SS,mmm' para segundos (float com 3 casas)."""
    srt_time = srt_time.strip().replace(".", ",")
    partes = srt_time.split(",")
    hms = partes[0].split(":")
    ms = int(partes[1]) if len(partes) > 1 else 0
    horas, minutos, segundos = int(hms[0]), int(hms[1]), int(hms[2])
    total = horas * 3600 + minutos * 60 + segundos + (ms / 1000.0)
    return round(total, 3)


def seconds_to_srt_time(seconds: float) -> str:
    """Converte segundos (float) para 'HH:MM:SS,mmm' (para comentários no cortes.py e kit)."""
    if seconds < 0:
        seconds = 0.0
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1_000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def limpar_nome_curto(texto: str) -> str:
    """Remove acentos, cedilhas e caracteres especiais para o campo 'nome'."""
    normalizado = unicodedata.normalize("NFKD", texto)
    sem_acentos = "".join(c for c in normalizado if not unicodedata.combining(c))
    limpo = re.sub(r"[^A-Za-z0-9 ]+", "", sem_acentos)
    return re.sub(r"\s+", " ", limpo).strip()


def normalizar_hashtags(hashtags_raw: Any) -> str:
    """Garante exatamente 5 hashtags começando por #PolíticaDireta."""
    if isinstance(hashtags_raw, list):
        tags = [str(t).strip() for t in hashtags_raw if str(t).strip()]
    else:
        tags = [t.strip() for t in str(hashtags_raw or "").split() if t.strip()]

    tags_formatadas = []
    for t in tags:
        if not t.startswith("#"):
            t = f"#{t}"
        tags_formatadas.append(t)

    # Garante #PolíticaDireta na primeira posição
    tags_sem_principal = [
        t for t in tags_formatadas
        if t.lower() not in {"#políticadireta", "#politicadireta"}
    ]
    resultado = ["#PolíticaDireta"] + tags_sem_principal[:4]
    while len(resultado) < 5:
        padroes = ["#Política", "#Brasil", "#Notícias", "#Economia"]
        for p in padroes:
            if p not in resultado and len(resultado) < 5:
                resultado.append(p)
    return " ".join(resultado[:5])


def preparar_srt_com_segundos(conteudo_srt: str) -> str:
    """
    Anota cada linha de timestamp do SRT com o valor exato em segundos (float).
    Isso evita que a LLM erre a conversão matemática de minutos para segundos.
    """
    padrao_tempo = re.compile(
        r"(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})"
    )
    linhas_processadas = []
    for linha in conteudo_srt.splitlines():
        match = padrao_tempo.search(linha)
        if match:
            ini_str, fim_str = match.group(1), match.group(2)
            ini_seg = srt_time_to_seconds(ini_str)
            fim_seg = srt_time_to_seconds(fim_str)
            linhas_processadas.append(
                f"[{ini_seg:.3f}s --> {fim_seg:.3f}s] ({ini_str} --> {fim_str})"
            )
        else:
            linhas_processadas.append(linha)
    return "\n".join(linhas_processadas)


# =====================================================================
# 3. INTEGRAÇÃO COM A API DO GEMINI (SKILL POLÍTICA DIRETA)
# =====================================================================

def configurar_api_gemini() -> None:
    """Carrega a GEMINI_API_KEY do .env ou variável de ambiente."""
    load_dotenv(ENV_FILE)
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or api_key == "COLE_SUA_GEMINI_API_KEY_AQUI":
        print("❌ Chave GEMINI_API_KEY não configurada!")
        print(f"-> Abra o arquivo '{ENV_FILE}' e cole sua chave do Google AI Studio:")
        print("   GEMINI_API_KEY=AIzaSy...")
        sys.exit(1)
    genai.configure(api_key=api_key)


def carregar_diretriz_padroes_vencedores() -> str:
    """
    Lê prompts/padroes_vencedores.json (YouTube) e prompts/padroes_vencedores_kwai.json (Kwai)
    e retorna o bloco unificado de inteligência editorial para retroalimentar a IA.
    """
    blocos: list[str] = []

    if PADROES_VENCEDORES_KWAI_FILE.exists():
        try:
            dados_kwai = json.loads(PADROES_VENCEDORES_KWAI_FILE.read_text(encoding="utf-8"))
            diretriz_kwai = dados_kwai.get("diretriz_retroalimentacao", "").strip()
            if diretriz_kwai and dados_kwai.get("total_auditados", 0) > 0:
                blocos.append(diretriz_kwai)
        except Exception as e:
            print(f"⚠️ Aviso ao carregar padrões vencedores do Kwai: {e}")

    if PADROES_VENCEDORES_FILE.exists():
        try:
            dados = json.loads(PADROES_VENCEDORES_FILE.read_text(encoding="utf-8"))
            diretriz = dados.get("diretriz_retroalimentacao", "").strip()
            if diretriz and dados.get("total_publicos", 0) > 0:
                blocos.append(diretriz)
        except Exception as e:
            print(f"⚠️ Aviso ao carregar padrões vencedores do YouTube: {e}")

    return ("\n\n" + "\n\n".join(blocos) + "\n") if blocos else ""


def carregar_prompt(video_filename: str, max_cortes: int, srt_anotado: str) -> str:
    """Lê prompts/politica_direta.md e preenche os placeholders {{...}}."""
    if not PROMPT_FILE.exists():
        raise FileNotFoundError(
            f"Prompt editorial não encontrado: {PROMPT_FILE}\n"
            "-> Restaure o arquivo prompts/politica_direta.md."
        )
    texto = PROMPT_FILE.read_text(encoding="utf-8")
    padroes_texto = carregar_diretriz_padroes_vencedores()
    substituicoes = {
        "{{VIDEO_FILENAME}}": video_filename,
        "{{MAX_CORTES}}": str(max_cortes),
        "{{TRANSCRICAO_SRT}}": srt_anotado,
        "{{PADROES_VENCEDORES}}": padroes_texto,
    }
    for chave, valor in substituicoes.items():
        texto = texto.replace(chave, valor)
    return texto.strip()


def analisar_srt_com_gemini(
    srt_path: Path,
    max_cortes: int = 3,
    modelo_nome: str = MODELO_PADRAO,
) -> list[dict[str, Any]]:
    """
    Envia a transcrição SRT anotada ao Gemini aplicando integralmente
    a diretriz editorial do canal 'Política Direta' (YouTube Shorts e Kwai).
    """
    conteudo_srt = srt_path.read_text(encoding="utf-8", errors="replace")
    srt_anotado = preparar_srt_com_segundos(conteudo_srt)
    video_filename = srt_path.with_suffix(".mp4").name

    prompt = carregar_prompt(video_filename, max_cortes, srt_anotado)

    generation_config = {
        "temperature": 0.3,
        "response_mime_type": "application/json",
    }

    modelo = genai.GenerativeModel(
        model_name=modelo_nome,
        generation_config=generation_config,
    )

    resposta = modelo.generate_content(prompt)
    texto_json = (resposta.text or "").strip()

    if texto_json.startswith("```"):
        texto_json = re.sub(r"^```(?:json)?\s*", "", texto_json)
        texto_json = re.sub(r"\s*```$", "", texto_json)

    dados = json.loads(texto_json)
    if isinstance(dados, dict) and "cortes" in dados:
        dados = dados["cortes"]

    if not isinstance(dados, list):
        raise ValueError(f"Resposta inesperada da API para '{srt_path.name}'.")

    # Ordena pela ordem sugerida (1, 2, 3) caso o modelo retorne fora de ordem
    dados_ordenados = sorted(
        dados[:max_cortes],
        key=lambda x: int(x.get("ordem", 99)) if str(x.get("ordem", "")).isdigit() else 99,
    )

    cortes_normalizados = []
    for idx, item in enumerate(dados_ordenados, start=1):
        start_val = round(float(item["start"]), 3)
        end_val = round(float(item["end"]), 3)
        if end_val <= start_val:
            continue

        horario_padrao = HORARIOS_ESTRATEGICOS[(idx - 1) % len(HORARIOS_ESTRATEGICOS)]
        horario = str(item.get("horario_sugerido") or horario_padrao).strip()
        if horario not in HORARIOS_ESTRATEGICOS:
            horario = horario_padrao

        cortes_normalizados.append({
            "horario_sugerido": horario,
            "nome": limpar_nome_curto(str(item.get("nome", f"Corte {idx}"))),
            "video_path": video_filename,
            "title": str(item.get("title", "")).strip(),
            "start": start_val,
            "end": end_val,
            "titulo_capa": str(item.get("titulo_capa", "")).strip(),
            "texto_publicacao": str(item.get("texto_publicacao", "")).strip(),
            "hashtags": normalizar_hashtags(item.get("hashtags")),
        })

    return cortes_normalizados


# =====================================================================
# 4. MANIFESTO (temp/tarefas_corte.json) E KIT DE PUBLICAÇÃO (.MD)
# =====================================================================

def formatar_kit_publicacao_markdown(tarefas: list[dict[str, Any]]) -> str:
    """
    Kit de Publicação (YouTube Shorts e Kwai) no padrão Política Direta,
    com todos os cortes que ainda não foram publicados.
    """
    partes = [
        "# Kit de Publicação — Política Direta (YouTube Shorts & Kwai)\n",
        "> Gerado a partir de `temp/tarefas_corte.json` (cortes com status diferente de `publicado`).\n",
        "---\n",
    ]

    for t in tarefas:
        ts_ini = seconds_to_srt_time(t["start"])
        ts_fim = seconds_to_srt_time(t["end"])
        duracao = round(t["end"] - t["start"], 1)

        partes.append(
            f"### Corte `{t['id']}` (Ordem: {t['ordem']} | Horário Sugerido: {t['horario_sugerido']} "
            f"| Status: {t.get('status', manifesto.STATUS_PENDENTE)})"
        )
        partes.append(f"**{t['title']}** (`{ts_ini} --> {ts_fim}` | `{duracao}s` | Origem: `{t['video_path']}`)\n")
        if t.get("arquivo_final"):
            partes.append(f"* **Arquivo renderizado:** `{t['arquivo_final']}`")
        partes.append(f"* **Título na tela / Capa:** {t.get('titulo_capa', '')}")
        partes.append("* **Texto da publicação:**")

        texto_pub = t.get("texto_publicacao", "").strip()
        for paragrafo in texto_pub.splitlines():
            if paragrafo.strip():
                partes.append(f"> {paragrafo.strip()}")
            else:
                partes.append(">")

        partes.append(f"\n* **Hashtags:** `{t.get('hashtags', '#PolíticaDireta')}`\n")

    return "\n".join(partes)


def gravar_kit_publicacao(tarefas: list[dict[str, Any]]) -> None:
    """Regenera cortes_prontos/kit_publicacao.md com os cortes ainda não publicados."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    abertos = [t for t in tarefas if t.get("status") != manifesto.STATUS_PUBLICADO]
    KIT_PUBLICACAO_MD_FILE.write_text(
        formatar_kit_publicacao_markdown(abertos),
        encoding="utf-8",
    )


# =====================================================================
# 5. DESCOBERTA E SELEÇÃO DE ARQUIVOS .SRT EM TEMP/
# =====================================================================

def carregar_historico_analisados() -> set[str]:
    if not HISTORICO_SRT_FILE.exists():
        return set()
    return {
        linha.strip()
        for linha in HISTORICO_SRT_FILE.read_text(encoding="utf-8").splitlines()
        if linha.strip()
    }


def registrar_srt_analisado(nome_srt: str) -> None:
    analisados = carregar_historico_analisados()
    if nome_srt not in analisados:
        with HISTORICO_SRT_FILE.open("a", encoding="utf-8") as f:
            f.write(f"{nome_srt}\n")


def listar_srts_em_temp() -> list[Path]:
    if not TEMP_DIR.exists():
        return []
    return sorted(
        (p for p in TEMP_DIR.iterdir() if p.is_file() and p.suffix.lower() == ".srt"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def resolver_srt_informado(termo: str) -> Path:
    candidatos = [
        Path(termo),
        TEMP_DIR / termo,
        TEMP_DIR / f"{Path(termo).stem}.srt",
        BASE_DIR / termo,
    ]
    for c in candidatos:
        if c.exists() and c.is_file() and c.suffix.lower() == ".srt":
            return c.resolve()

    correspondencias = [
        p for p in listar_srts_em_temp()
        if termo.lower() in p.name.lower()
    ]
    if len(correspondencias) == 1:
        return correspondencias[0].resolve()
    if len(correspondencias) > 1:
        raise ValueError(
            f"Mais de um arquivo .srt corresponde a '{termo}': "
            + ", ".join(p.name for p in correspondencias)
        )
    raise FileNotFoundError(f"Nenhum arquivo .srt encontrado para: '{termo}'")


def selecionar_srts_interativo(srts: list[Path], analisados: set[str]) -> list[Path]:
    print("===================================================")
    print("       ARQUIVOS .SRT DISPONÍVEIS EM TEMP/          ")
    print("===================================================")
    for idx, p in enumerate(srts, start=1):
        status = "✅ [JÁ ANALISADO]" if p.name in analisados else "🆕 [NOVO]"
        print(f"[{idx:2d}] {status} {p.name}")
    print("===================================================")
    print("Opções:")
    print(" - Digite o número do vídeo (ou vários separados por vírgula, ex: 1,2)")
    print(" - Pressione ENTER para analisar todos os marcados como [NOVO]")
    print("===================================================")

    escolha = input("Sua escolha: ").strip()
    if not escolha:
        novos = [p for p in srts if p.name not in analisados]
        return novos if novos else [srts[0]]

    selecionados = []
    for parte in escolha.split(","):
        parte = parte.strip()
        if parte.isdigit():
            indice = int(parte)
            if 1 <= indice <= len(srts):
                selecionados.append(srts[indice - 1])
    return selecionados


# =====================================================================
# 6. FLUXO PRINCIPAL
# =====================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Analisa arquivos .srt em temp/ via Gemini API com a skill 'politica-direta-cortes', "
            "atualiza TAREFAS_DE_CORTE em cortes.py e gera o Kit de Publicação."
        )
    )
    parser.add_argument(
        "srt",
        nargs="?",
        help="Nome, caminho ou ID do arquivo .srt específico para analisar (opcional).",
    )
    parser.add_argument(
        "--novos",
        action="store_true",
        help="Analisa automaticamente todos os arquivos .srt ainda não analisados em temp/.",
    )
    parser.add_argument(
        "--max-cortes",
        type=int,
        default=3,
        help="Quantidade de cortes por vídeo (padrão: 3 - grade diária 11:30, 17:30, 20:30).",
    )
    parser.add_argument(
        "--modelo",
        default=MODELO_PADRAO,
        help=f"Modelo Gemini a utilizar (padrão: {MODELO_PADRAO}).",
    )

    args = parser.parse_args()
    configurar_api_gemini()

    srts_disponiveis = listar_srts_em_temp()
    if not srts_disponiveis and not args.srt:
        print(f"❌ Nenhum arquivo .srt encontrado em '{TEMP_DIR}'.")
        print("-> Execute primeiro: python gerador_srt.py")
        sys.exit(1)

    analisados = carregar_historico_analisados()

    if args.srt:
        try:
            alvos = [resolver_srt_informado(args.srt)]
        except Exception as e:
            print(f"❌ {e}")
            sys.exit(1)
    elif args.novos:
        alvos = [p for p in srts_disponiveis if p.name not in analisados]
        if not alvos:
            print("✅ Todos os arquivos .srt em 'temp/' já foram analisados!")
            sys.exit(0)
    else:
        alvos = selecionar_srts_interativo(srts_disponiveis, analisados)
        if not alvos:
            print("⚠️ Nenhum arquivo válido selecionado.")
            sys.exit(0)

    try:
        tarefas = manifesto.carregar()
    except Exception as e:
        print(f"❌ Não foi possível ler o manifesto: {e}")
        sys.exit(1)

    novos_cortes = 0
    print(f"\n🤖 Iniciando curadoria 'Política Direta' com o modelo '{args.modelo}'...\n")

    for srt_path in alvos:
        print(f"📄 Analisando: {srt_path.name} ...")
        try:
            cortes_gerados = analisar_srt_com_gemini(
                srt_path=srt_path,
                max_cortes=args.max_cortes,
                modelo_nome=args.modelo,
            )
        except Exception as e:
            print(f" ❌ Erro ao analisar '{srt_path.name}': {e}\n")
            continue

        if not cortes_gerados:
            print(f" ⚠️ Nenhum corte retornado para '{srt_path.name}'.\n")
            continue

        video_path = srt_path.with_suffix(".mp4").name
        tarefas, sobrescritas = manifesto.substituir_cortes_do_video(
            tarefas, video_path, cortes_gerados
        )
        # Salva a cada vídeo: se uma análise posterior falhar, nada se perde.
        manifesto.salvar(tarefas)

        if sobrescritas:
            print(
                f" ⚠️ {len(sobrescritas)} corte(s) já renderizado(s) deste vídeo foram "
                "substituídos pela nova análise (os arquivos em cortes_prontos/ foram mantidos)."
            )

        for t in (x for x in tarefas if x["video_path"] == video_path and x["status"] == manifesto.STATUS_PENDENTE):
            duracao = round(t["end"] - t["start"], 1)
            print(
                f"   ✅ Corte {t['id']} ({duracao}s | {t['horario_sugerido']}): {t['nome']}\n"
                f"      📌 Título: {t['title']}\n"
                f"      🖼️  Capa  : {t['titulo_capa']}\n"
                f"      #️⃣  Tags  : {t['hashtags']}"
            )
            novos_cortes += 1

        registrar_srt_analisado(srt_path.name)
        print()

    if not novos_cortes:
        print("⚠️ Nenhuma tarefa de corte foi gerada.")
        sys.exit(1)

    gravar_kit_publicacao(tarefas)
    print("===================================================")
    print(f"🎯 {novos_cortes} corte(s) 'Política Direta' gravado(s) com sucesso!")
    print(f"📦 Manifesto         : {manifesto.MANIFESTO_FILE}")
    print(f"📋 Kit de Publicação : {KIT_PUBLICACAO_MD_FILE}")
    print("===================================================")
    print("Próximo passo: execute 'python cortes.py' para renderizar os cortes pendentes.")


if __name__ == "__main__":
    main()
