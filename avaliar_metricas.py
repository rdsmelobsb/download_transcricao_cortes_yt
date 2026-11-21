"""
Módulo de Avaliação de Desempenho e Inteligência do YouTube (Retroalimentação).

Audita em paralelo todos os cortes publicados no YouTube Shorts, coleta
métricas reais de visualizações, curtidas e comentários, salva os dados no manifesto
(temp/tarefas_corte.json), gera relatórios em Markdown e exporta padrões vencedores
(prompts/padroes_vencedores.json) para retroalimentar a curadoria IA (analisar_srt.py).
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yt_dlp

import manifesto

# =====================================================================
# 1. CONFIGURAÇÕES E DIRETÓRIOS
# =====================================================================

BASE_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = BASE_DIR / "prompts"
CORTES_PRONTOS_DIR = BASE_DIR / "cortes_prontos"
RELATORIO_MD = CORTES_PRONTOS_DIR / "relatorio_desempenho_yt.md"
PADROES_JSON = PROMPTS_DIR / "padroes_vencedores.json"


# =====================================================================
# 2. COLETA DE MÉTRICAS EM PARALELO (YT-DLP)
# =====================================================================

def extrair_metricas_video(tarefa: dict[str, Any]) -> dict[str, Any]:
    """
    Consulta o YouTube via yt-dlp sem baixar mídias e sem gastar cota de API.
    Identifica se o vídeo está público, privado (agendado) ou indisponível.
    """
    video_id = tarefa.get("youtube_video_id")
    url = tarefa.get("youtube_url") or f"https://www.youtube.com/shorts/{video_id}"

    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "js_runtimes": {"node": {"path": None}},
        "remote_components": ["ejs:github"],
    }

    resultado = {
        "id": tarefa["id"],
        "video_id": video_id,
        "url": url,
        "title": tarefa.get("title", ""),
        "horario_sugerido": tarefa.get("horario_sugerido", ""),
        "titulo_capa": tarefa.get("titulo_capa", ""),
        "duracao": round(tarefa.get("end", 0) - tarefa.get("start", 0), 1),
        "video_origem": tarefa.get("video_path", ""),
        "views": 0,
        "likes": 0,
        "comments": 0,
        "status_video": "desconhecido",
        "atualizado_em": manifesto.agora_iso(),
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            resultado["views"] = int(info.get("view_count") or 0)
            resultado["likes"] = int(info.get("like_count") or 0)
            resultado["comments"] = int(info.get("comment_count") or 0)
            resultado["status_video"] = "publico"
    except Exception as e:
        erro_msg = str(e).lower()
        if "private video" in erro_msg:
            # Vídeo agendado no YouTube Shorts permanece 'Private' até a data/hora programada
            resultado["status_video"] = "agendado"
        elif "video unavailable" in erro_msg:
            resultado["status_video"] = "indisponivel"
        else:
            resultado["status_video"] = "erro_leitura"
            resultado["erro"] = str(e)[:120]

    return resultado


def auditar_cortes_youtube(
    tarefas: list[dict[str, Any]],
    max_workers: int = 6,
    silencioso: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Filtra os cortes com status 'publicado' no YouTube e coleta métricas em paralelo.
    Retorna (tarefas_atualizadas, resultados_metricas).
    """
    alvos = [
        t for t in tarefas
        if t.get("status") == manifesto.STATUS_PUBLICADO and t.get("youtube_video_id")
    ]

    if not alvos:
        if not silencioso:
            print("⚠️ Nenhum corte publicado no YouTube encontrado no manifesto!")
        return tarefas, []

    if not silencioso:
        print(f"📊 Auditando métricas de {len(alvos)} vídeos no YouTube Shorts (paralelo {max_workers} threads)...")

    mapa_resultados: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futuros = {executor.submit(extrair_metricas_video, t): t["id"] for t in alvos}
        concluidos = 0
        for f in as_completed(futuros):
            r = f.result()
            mapa_resultados[r["id"]] = r
            concluidos += 1
            if not silencioso:
                status_emoji = "🟢" if r["status_video"] == "publico" else "⏳" if r["status_video"] == "agendado" else "🔴"
                print(f"  [{concluidos}/{len(alvos)}] {status_emoji} {r['id']} | {r['status_video'].upper()} | {r['views']} views | {r['title'][:45]}")

    # Atualiza o bloco 'metricas_yt' de cada tarefa correspondente
    for t in tarefas:
        t_id = t.get("id")
        if t_id in mapa_resultados:
            m = mapa_resultados[t_id]
            t["metricas_yt"] = {
                "views": m["views"],
                "likes": m["likes"],
                "comments": m["comments"],
                "status_video": m["status_video"],
                "atualizado_em": m["atualizado_em"],
            }

    resultados_lista = list(mapa_resultados.values())
    return tarefas, resultados_lista


# =====================================================================
# 3. MOTOR DE INTELIGÊNCIA: ANÁLISE DE PADRÕES VENCEDORES
# =====================================================================

def extrair_selo_capa(titulo_capa: str) -> str:
    """Extrai o selo de categoria do título de capa (ex: 'UTILIDADE PÚBLICA', 'ALERTA URGENTE')."""
    if not titulo_capa:
        return "OUTROS"
    m = re.match(r"^([A-ZÀ-Ú\s]{3,25}):", titulo_capa.strip())
    if m:
        return m.group(1).strip()
    for selo in ["UTILIDADE PÚBLICA", "ALERTA URGENTE", "RECADO DIRETO", "DEBATE QUENTE", "MOMENTO HISTÓRICO", "DENÚNCIA"]:
        if selo in titulo_capa.upper():
            return selo
    return "OUTROS"


def classificar_faixa_duracao(duracao: float) -> str:
    if duracao < 60:
        return "45s a 60s"
    elif duracao <= 75:
        return "60s a 75s"
    elif duracao <= 90:
        return "75s a 90s"
    else:
        return "90s a 100s"


def analisar_padroes_vencedores(resultados: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Clusteriza as métricas por faixa de duração, selo de capa, horário da grade
    e canal de origem para extrair os fatores de maior audiência.
    """
    publicos = [r for r in resultados if r["status_video"] == "publico"]
    agendados = [r for r in resultados if r["status_video"] == "agendado"]
    total_views = sum(r["views"] for r in publicos)
    total_likes = sum(r["likes"] for r in publicos)
    total_comments = sum(r["comments"] for r in publicos)

    # 1. Padrão por Faixa de Duração
    views_por_duracao = defaultdict(lambda: {"total_views": 0, "qtd": 0})
    for r in publicos:
        faixa = classificar_faixa_duracao(r["duracao"])
        views_por_duracao[faixa]["total_views"] += r["views"]
        views_por_duracao[faixa]["qtd"] += 1

    ranking_duracao = []
    for faixa, dados in views_por_duracao.items():
        media = round(dados["total_views"] / dados["qtd"], 1) if dados["qtd"] > 0 else 0
        ranking_duracao.append({
            "faixa": faixa,
            "media_views": media,
            "total_views": dados["total_views"],
            "qtd": dados["qtd"],
        })
    ranking_duracao.sort(key=lambda x: x["media_views"], reverse=True)

    # 2. Padrão por Selo de Capa
    views_por_selo = defaultdict(lambda: {"total_views": 0, "qtd": 0})
    for r in publicos:
        selo = extrair_selo_capa(r["titulo_capa"])
        views_por_selo[selo]["total_views"] += r["views"]
        views_por_selo[selo]["qtd"] += 1

    ranking_selos = []
    for selo, dados in views_por_selo.items():
        media = round(dados["total_views"] / dados["qtd"], 1) if dados["qtd"] > 0 else 0
        ranking_selos.append({
            "selo": selo,
            "media_views": media,
            "total_views": dados["total_views"],
            "qtd": dados["qtd"],
        })
    ranking_selos.sort(key=lambda x: x["media_views"], reverse=True)

    # 3. Padrão por Horário da Grade
    views_por_horario = defaultdict(lambda: {"total_views": 0, "qtd": 0})
    for r in publicos:
        horario = r["horario_sugerido"] or "Não Definido"
        views_por_horario[horario]["total_views"] += r["views"]
        views_por_horario[horario]["qtd"] += 1

    ranking_horarios = []
    for hor, dados in views_por_horario.items():
        media = round(dados["total_views"] / dados["qtd"], 1) if dados["qtd"] > 0 else 0
        ranking_horarios.append({
            "horario": hor,
            "media_views": media,
            "total_views": dados["total_views"],
            "qtd": dados["qtd"],
        })
    ranking_horarios.sort(key=lambda x: x["media_views"], reverse=True)

    # 4. Top Vídeos
    top_videos = sorted(publicos, key=lambda x: (x["views"], x["likes"]), reverse=True)[:10]

    melhor_faixa = ranking_duracao[0]["faixa"] if ranking_duracao else "60s a 75s"
    melhores_selos = [s["selo"] for s in ranking_selos[:3] if s["selo"] != "OUTROS"]
    if not melhores_selos:
        melhores_selos = ["UTILIDADE PÚBLICA", "ALERTA URGENTE"]

    melhor_horario = ranking_horarios[0]["horario"] if ranking_horarios else "17:30"

    # Monta a diretriz de retroalimentação em texto natural para o Gemini
    top_exemplos_txt = "\n".join(
        f"  * \"{v['title']}\" ({v['views']} views, {v['duracao']}s, selo: {extrair_selo_capa(v['titulo_capa'])})"
        for v in top_videos[:3]
    )

    diretriz_retroalimentacao = (
        f"### 📊 INTELIGÊNCIA EDITORIAL BASEADA EM DESEMPENHO REAL DO CANAL:\n"
        f"- Faixa de duração mais assistida pela audiência recente: **{melhor_faixa}** (priorize cortes nesta faixa).\n"
        f"- Selos de título de capa com maior engajamento comprovado: **{', '.join(melhores_selos)}**.\n"
        f"- Horário com maior retenção orgânica na grade: **{melhor_horario}**.\n"
        f"- Exemplos reais de cortes com melhor engajamento recente no canal (inspire-se na estrutura, tom e temática):\n"
        f"{top_exemplos_txt}\n"
        f"-> Na seleção dos trechos, dê preferência a falas com dinâmicas, ganchos e densidade argumentativa semelhantes aos campeões de visualizações."
    )

    return {
        "atualizado_em": manifesto.agora_iso(),
        "total_auditados": len(resultados),
        "total_publicos": len(publicos),
        "total_agendados": len(agendados),
        "total_views": total_views,
        "total_likes": total_likes,
        "total_comments": total_comments,
        "melhor_faixa_duracao": melhor_faixa,
        "melhores_selos": melhores_selos,
        "melhor_horario": melhor_horario,
        "ranking_duracao": ranking_duracao,
        "ranking_selos": ranking_selos,
        "ranking_horarios": ranking_horarios,
        "top_videos": top_videos,
        "diretriz_retroalimentacao": diretriz_retroalimentacao,
    }


# =====================================================================
# 4. GERAÇÃO DE RELATÓRIO E EXPORTAÇÃO
# =====================================================================

def salvar_relatorio_markdown(padroes: dict[str, Any], resultados: list[dict[str, Any]]) -> None:
    """Gera um relatório legível e detalhado em Markdown em cortes_prontos/."""
    CORTES_PRONTOS_DIR.mkdir(parents=True, exist_ok=True)

    linhas = [
        "# 📈 Relatório de Desempenho e Inteligência — YouTube Shorts",
        "",
        f"> **Canal:** Política Direta | **Data da Auditoria:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
        "",
        "---",
        "",
        "## 1. Visão Geral da Operação",
        "",
        f"- **Total de cortes analisados:** `{padroes['total_auditados']}`",
        f"- **Cortes já públicos (no ar):** `{padroes['total_publicos']}`",
        f"- **Cortes agendados (programados na grade):** `{padroes['total_agendados']}`",
        f"- **Visualizações acumuladas nos vídeos públicos:** `{padroes['total_views']}` views",
        f"- **Curtidas acumuladas:** `{padroes['total_likes']}` likes",
        f"- **Comentários:** `{padroes['total_comments']}` comentários",
        "",
        "---",
        "",
        "## 2. Padrões Vencedores Identificados",
        "",
        f"🎯 **Duração com Maior Retenção Média:** `{padroes['melhor_faixa_duracao']}`",
        f"🏷️ **Selos de Capa com Maior Conversão:** `{', '.join(padroes['melhores_selos'])}`",
        f"⏰ **Melhor Horário de Engajamento:** `{padroes['melhor_horario']}`",
        "",
        "### Desempenho por Faixa de Duração",
        "| Faixa de Duração | Média de Views | Total Views | Amostra |",
        "|---|---|---|---|",
    ]

    for d in padroes.get("ranking_duracao", []):
        linhas.append(f"| **{d['faixa']}** | **{d['media_views']}** | {d['total_views']} | {d['qtd']} vídeos |")

    linhas.extend([
        "",
        "### Desempenho por Selo de Capa",
        "| Selo / Categoria | Média de Views | Total Views | Qtd |",
        "|---|---|---|---|",
    ])
    for s in padroes.get("ranking_selos", []):
        linhas.append(f"| **{s['selo']}** | **{s['media_views']}** | {s['total_views']} | {s['qtd']} vídeos |")

    linhas.extend([
        "",
        "---",
        "",
        "## 3. Top Cortes Mais Assistidos no YouTube",
        "",
        "| Ranking | Views | Likes | Duração | Horário | Título / Corte |",
        "|---|---|---|---|---|---|",
    ])

    for idx, v in enumerate(padroes.get("top_videos", [])[:10], start=1):
        linhas.append(
            f"| `#{idx}` | **{v['views']}** | {v['likes']} | {v['duracao']}s | `{v['horario_sugerido']}` | [{v['title']}]({v['url']}) |"
        )

    linhas.extend([
        "",
        "---",
        "",
        "## 4. Diretriz Ativa de Retroalimentação IA",
        "",
        "Esta diretriz foi exportada para `prompts/padroes_vencedores.json` e será consumida automaticamente pelo `analisar_srt.py` na próxima curadoria:",
        "",
        "```markdown",
        padroes["diretriz_retroalimentacao"],
        "```",
    ])

    RELATORIO_MD.write_text("\n".join(linhas), encoding="utf-8")
    print(f"📄 Relatório Markdown atualizado: {RELATORIO_MD}")


def exportar_padroes_json(padroes: dict[str, Any]) -> None:
    """Exporta o JSON de inteligência para consumo direto pelo analisar_srt.py."""
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    PADROES_JSON.write_text(json.dumps(padroes, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"🧠 Padrões vencedores exportados: {PADROES_JSON}")


# =====================================================================
# 5. PONTO DE ENTRADA
# =====================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Auditoria de métricas do YouTube e motor de retroalimentação IA."
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=6,
        help="Quantidade de requisições simultâneas ao YouTube (padrão: 6).",
    )
    parser.add_argument(
        "--silencioso",
        action="store_true",
        help="Executa sem imprimir cada vídeo auditado no terminal.",
    )

    args = parser.parse_args()

    # 1. Carrega o manifesto
    try:
        tarefas = manifesto.carregar()
    except Exception as e:
        print(f"❌ Erro ao ler manifesto: {e}")
        sys.exit(1)

    # 2. Audita as métricas dos vídeos no YouTube
    tarefas_atualizadas, resultados = auditar_cortes_youtube(
        tarefas,
        max_workers=args.workers,
        silencioso=args.silencioso,
    )

    if not resultados:
        sys.exit(0)

    # 3. Salva os dados atualizados no manifesto temp/tarefas_corte.json
    manifesto.salvar(tarefas_atualizadas)
    print(f"💾 Manifesto atualizado com as métricas mais recentes de {len(resultados)} vídeos!")

    # 4. Extrai a inteligência e os padrões de sucesso
    padroes = analisar_padroes_vencedores(resultados)

    # 5. Gera relatório visual e arquivo JSON de inteligência
    salvar_relatorio_markdown(padroes, resultados)
    exportar_padroes_json(padroes)

    print("\n===================================================")
    print(f"🏆 AUDITORIA CONCLUÍDA:")
    print(f"   - Total auditados: {padroes['total_auditados']} | Públicos: {padroes['total_publicos']} | Agendados: {padroes['total_agendados']}")
    print(f"   - Visualizações acumuladas: {padroes['total_views']} views")
    print(f"   - Duração ideal identificada: {padroes['melhor_faixa_duracao']}")
    print(f"   - Selos de maior tração: {', '.join(padroes['melhores_selos'])}")
    print("===================================================\n")


if __name__ == "__main__":
    main()
