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

BASE_DIR = Path(__file__).resolve().parent
TEMP_DIR = BASE_DIR / "temp"
OUTPUT_DIR = BASE_DIR / "cortes_prontos"
CORTES_PY_FILE = BASE_DIR / "cortes.py"
TAREFAS_JSON_FILE = TEMP_DIR / "tarefas_corte.json"
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

    prompt = f"""
Você é o estrategista e editor-chefe do canal **Política Direta** (focado exclusivamente em **YouTube Shorts** e **Kwai**).
Analise a transcrição SRT completa abaixo (originada do vídeo '{video_filename}') e extraia exatamente {max_cortes} cortes virais de alta retenção, juntamente com o Kit de Publicação completo de cada corte.

### 1. CURADORIA EDITORIAL E LIMPEZA DA TRANSCRIÇÃO
- Priorize temas de alto engajamento e compartilhamento: impacto direto no bolso do trabalhador, direitos trabalhistas e sociais, soberania nacional, economia real, defesa da democracia, geopolítica e combate à desinformação.
- Selecione exatamente **{max_cortes} cortes principais**, com duração alvo entre **45 e 100 segundos** (ajustando se o vídeo original for mais curto ou se um argumento central exigir alguns segundos extras para não cortar no meio da frase).
- Escolha trechos que comecem com um gancho forte nos primeiros 3 segundos e terminem com fechamento conclusivo.
- Corrija erros típicos de transcrição automática (nomes próprios, siglas, cifras e palavras distorcidas pelo STT) nos títulos e textos de publicação, sem alterar o sentido original da fala nem os timestamps reais do `.srt`.
- Evite repetir o mesmo intervalo de áudio em dois cortes distintos, a menos que o vídeo original tenha menos de 2 minutos no total.

### 2. DISTRIBUIÇÃO NA GRADE DIÁRIA
Atribua cada um dos cortes à grade fixa do canal, combinando o perfil do corte com o comportamento da audiência no YouTube Shorts e no Kwai:
1. **Ordem 1 (`"11:30"`):** Pauta de utilidade pública, economia, medidas práticas ou impacto direto no cotidiano (pico do almoço).
2. **Ordem 2 (`"17:30"`):** Debate quente, análise política, cobrança ou contraponto estratégico (fim de expediente).
3. **Ordem 3 (`"20:30"`):** Corte de maior carga emocional, posicionamento firme, valorização institucional ou alto potencial de compartilhamento orgânico (horário nobre).

### 3. REGRAS DE PRECISÃO E RESTRIÇÕES
- **Português do Brasil (PT-BR):** Escreva todos os títulos, legendas e descrições estritamente em português brasileiro natural (evite termos de PT-PT).
- **Plataformas ativas:** O projeto opera apenas no **YouTube Shorts** e no **Kwai**. Nunca mencione, recomende ou formate entregas para o TikTok.
- **Precisão dos timestamps:** Use EXATAMENTE os números em segundos decimais (`float`) que aparecem entre colchetes `[inicio_s --> fim_s]` na transcrição para preencher `start` e `end`.

### 4. ESTRUTURA DE CADA OBJETO NO ARRAY JSON DE SAÍDA
Retorne APENAS um array JSON válido onde cada objeto contenha exatamente as chaves abaixo:
- `"ordem"`: Inteiro (1, 2 ou 3) correspondente à posição na grade diária.
- `"horario_sugerido"`: String (`"11:30"`, `"17:30"` ou `"20:30"`).
- `"nome"`: Título curto sem acentos, sem cedilha e sem caracteres especiais para nome de arquivo (ex: `"Titulo Curto Sem Acentos"`).
- `"title"`: Título otimizado para SEO e retenção no YouTube Shorts e Kwai (com acentuação normal em PT-BR).
- `"start"`: Número float em segundos exatos do início do corte (ex: `120.500`).
- `"end"`: Número float em segundos exatos do fim do corte (ex: `195.240`).
- `"titulo_capa"`: Frase curta para Título na tela / Capa com selo de impacto em caixa alta no início (ex: `"RECADO DIRETO: '...'"`, `"UTILIDADE PÚBLICA: '...'"`, `"ALERTA URGENTE: '...'"`) pensada para segurar o scroll.
- `"texto_publicacao"`: Texto completo da publicação estruturado em 4 partes curtas (separadas por quebra de linha `\\n\\n`): (1) contextualização rápida em uma frase, (2) citação limpa e fluente dos melhores trechos da fala, (3) fecho analítico reforçando o impacto prático e (4) CTA direto incentivando comentários (algoritmo do YouTube) e compartilhamento em grupos (alcance no Kwai).
- `"hashtags"`: Array ou string com exatamente 5 hashtags, sempre começando com `#PolíticaDireta` seguida por 4 tags específicas de alto volume do tema.

TRANSCRIÇÃO SRT ANOTADA:
{srt_anotado}
""".strip()

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
            "ordem_local": idx,
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
# 4. ATUALIZAÇÃO DO CORTES.PY, MANIFESTO JSON E KIT DE PUBLICAÇÃO (.MD)
# =====================================================================

def formatar_bloco_tarefas_python(tarefas: list[dict[str, Any]]) -> str:
    """Gera o código Python formatado da variável TAREFAS_DE_CORTE com comentários de tempo."""
    linhas = ["TAREFAS_DE_CORTE = ["]
    total = len(tarefas)

    for idx, t in enumerate(tarefas, start=1):
        virgula_obj = "," if idx < total else ""
        comment_start = seconds_to_srt_time(t["start"])
        comment_end = seconds_to_srt_time(t["end"])

        linhas.append("    {")
        linhas.append(f'        "id": {t["id"]},')
        linhas.append(f'        "ordem": {t["ordem"]},')
        linhas.append(f'        "horario_sugerido": {json.dumps(t["horario_sugerido"], ensure_ascii=False)},')
        linhas.append(f'        "nome": {json.dumps(t["nome"], ensure_ascii=False)},')
        linhas.append(f'        "video_path": {json.dumps(t["video_path"], ensure_ascii=False)},')
        linhas.append(f'        "title": {json.dumps(t["title"], ensure_ascii=False)},')
        linhas.append(f'        "start": {t["start"]:.3f},  # {comment_start}')
        linhas.append(f'        "end": {t["end"]:.3f}     # {comment_end}')
        linhas.append(f"    }}{virgula_obj}")

    linhas.append("]")
    return "\n".join(linhas)


def formatar_kit_publicacao_markdown(tarefas: list[dict[str, Any]]) -> str:
    """
    Formata o documento completo contendo o bloco Python TAREFAS_DE_CORTE
    seguido do Kit de Publicação (YouTube Shorts e Kwai) no padrão Política Direta.
    """
    bloco_python = formatar_bloco_tarefas_python(tarefas)
    partes = [
        "# Planejamento de Cortes — Política Direta (YouTube Shorts & Kwai)\n",
        "```python",
        bloco_python,
        "```\n",
        "---\n",
    ]

    for t in tarefas:
        ts_ini = seconds_to_srt_time(t["start"])
        ts_fim = seconds_to_srt_time(t["end"])
        duracao = round(t["end"] - t["start"], 1)

        partes.append(
            f"### Corte {t['id']} (Ordem: {t['ordem']} | Horário Sugerido: {t['horario_sugerido']})"
        )
        partes.append(f"**{t['title']}** (`{ts_ini} --> {ts_fim}` | `{duracao}s` | Origem: `{t['video_path']}`)\n")
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


def atualizar_arquivos_saida(tarefas: list[dict[str, Any]]) -> None:
    """
    1. Substitui TAREFAS_DE_CORTE em cortes.py
    2. Salva o manifesto completo (com kit de publicação) em temp/tarefas_corte.json
    3. Salva o Kit de Publicação formatado em cortes_prontos/kit_publicacao.md
    """
    if not CORTES_PY_FILE.exists():
        raise FileNotFoundError(f"Arquivo '{CORTES_PY_FILE}' não encontrado.")

    conteudo = CORTES_PY_FILE.read_text(encoding="utf-8")
    novo_bloco = formatar_bloco_tarefas_python(tarefas)

    padrao = re.compile(
        r"TAREFAS_DE_CORTE\s*=\s*\[.*?\n\]",
        re.DOTALL,
    )

    if not padrao.search(conteudo):
        raise RuntimeError("Não foi possível localizar o bloco TAREFAS_DE_CORTE em cortes.py.")

    novo_conteudo = padrao.sub(lambda _: novo_bloco, conteudo, count=1)
    CORTES_PY_FILE.write_text(novo_conteudo, encoding="utf-8")

    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    TAREFAS_JSON_FILE.write_text(
        json.dumps(tarefas, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    kit_md = formatar_kit_publicacao_markdown(tarefas)
    KIT_PUBLICACAO_MD_FILE.write_text(kit_md, encoding="utf-8")


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

    todas_tarefas: list[dict[str, Any]] = []
    contador_id = 1

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

        for corte in cortes_gerados:
            tarefa = {
                "id": contador_id,
                "ordem": contador_id,
                "horario_sugerido": corte["horario_sugerido"],
                "nome": corte["nome"],
                "video_path": corte["video_path"],
                "title": corte["title"],
                "start": corte["start"],
                "end": corte["end"],
                "titulo_capa": corte["titulo_capa"],
                "texto_publicacao": corte["texto_publicacao"],
                "hashtags": corte["hashtags"],
            }
            todas_tarefas.append(tarefa)
            duracao = round(corte["end"] - corte["start"], 1)
            print(
                f"   ✅ Corte #{contador_id} ({duracao}s | {corte['horario_sugerido']}): "
                f"{corte['nome']}\n"
                f"      📌 Título: {corte['title']}\n"
                f"      🖼️  Capa  : {corte['titulo_capa']}\n"
                f"      #️⃣  Tags  : {corte['hashtags']}"
            )
            contador_id += 1

        registrar_srt_analisado(srt_path.name)
        print()

    if not todas_tarefas:
        print("⚠️ Nenhuma tarefa de corte foi gerada.")
        sys.exit(1)

    atualizar_arquivos_saida(todas_tarefas)
    print("===================================================")
    print(f"🎯 {len(todas_tarefas)} corte(s) 'Política Direta' gravado(s) com sucesso!")
    print(f"📝 Atualizado        : {CORTES_PY_FILE}")
    print(f"📦 Manifesto JSON    : {TAREFAS_JSON_FILE}")
    print(f"📋 Kit de Publicação : {KIT_PUBLICACAO_MD_FILE}")
    print("===================================================")
    print("Próximo passo: execute 'python cortes.py' para renderizar os vídeos.")


if __name__ == "__main__":
    main()
