"""
Módulo de Avaliação de Desempenho e Inteligência do Kwai via Android ADB.

Conecta ao celular USB ou emulador (BlueStacks) via publicar_kwai.conectar_dispositivo(),
navega pela grade de publicações do perfil no app Kwai (com.kwai.video), coleta
visualizações, curtidas, comentários e compartilhamentos de cada corte publicado,
salva os dados no manifesto (temp/tarefas_corte.json), gera o relatório executivo
(cortes_prontos/relatorio_desempenho_kwai.md) e exporta padrões vencedores
(prompts/padroes_vencedores_kwai.json) para retroalimentar a curadoria IA.
"""

import argparse
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import manifesto
import publicar_kwai

# =====================================================================
# 1. CONFIGURAÇÕES E CAMINHOS
# =====================================================================

BASE_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = BASE_DIR / "prompts"
CORTES_PRONTOS_DIR = BASE_DIR / "cortes_prontos"
RELATORIO_KWAI_MD = CORTES_PRONTOS_DIR / "relatorio_desempenho_kwai.md"
PADROES_KWAI_JSON = PROMPTS_DIR / "padroes_vencedores_kwai.json"

KWAI_PACKAGE = "com.kwai.video"


# =====================================================================
# 2. PARSERS DE NÚMEROS E XML DO KWAI
# =====================================================================

def parsear_numero_kwai(texto: str) -> int:
    """
    Converte textos do Kwai PT-BR para inteiro:
    - '284 Visualizações' -> 284
    - '1,5 mil Visualizações' -> 1500
    - '176,1 mil' -> 176100
    - '1,2 mi' / '1.2M' -> 1200000
    - 'Comentar' / 'Compartilhar' / '' -> 0
    """
    if not texto:
        return 0
    t = texto.strip().lower()
    t = t.replace("visualizações", "").replace("visualização", "").strip()
    if not t or any(p in t for p in ["comentar", "compartilhar", "curtir", "seja o primeiro"]):
        return 0

    multiplicador = 1
    if "mi" in t and "mil" not in t:
        multiplicador = 1_000_000
        t = t.replace("mi", "").strip()
    elif "m" in t and "mil" not in t:
        multiplicador = 1_000_000
        t = t.replace("m", "").strip()
    elif "mil" in t:
        multiplicador = 1_000
        t = t.replace("mil", "").strip()
    elif "k" in t:
        multiplicador = 1_000
        t = t.replace("k", "").strip()

    # Normaliza separadores decimais (ex: '176,1' -> '176.1')
    m = re.search(r"[\d.,]+", t)
    if not m:
        return 0
    num_str = m.group(0)
    if multiplicador > 1:
        num_str = num_str.replace(",", ".")
    else:
        num_str = num_str.replace(".", "").replace(",", "")

    try:
        return int(round(float(num_str) * multiplicador))
    except ValueError:
        return 0


def parsear_bounds(bounds_str: str) -> tuple[int, int, int, int]:
    """Converte '[x1,y1][x2,y2]' em (x1, y1, x2, y2)."""
    nums = list(map(int, re.findall(r"\d+", bounds_str)))
    if len(nums) == 4:
        return nums[0], nums[1], nums[2], nums[3]
    return 0, 0, 0, 0


def extrair_metricas_tela_player(xml: str) -> dict[str, Any]:
    """Extrai views, likes, comments, shares e legenda da hierarquia XML do player Kwai."""
    root = ET.fromstring(xml)
    views = 0
    likes = 0
    comments = 0
    shares = 0
    legenda = ""

    for node in root.iter("node"):
        rid = (node.attrib.get("resource-id") or "").strip()
        txt = (node.attrib.get("text") or "").strip()

        if rid == "com.kwai.video.basis:id/bottom_browse_record_text":
            views = parsear_numero_kwai(txt)
        elif rid == "com.kwai.video.basis:id/like_count_view":
            likes = parsear_numero_kwai(txt)
        elif rid == "com.kwai.video.basis:id/comment_count_view":
            comments = parsear_numero_kwai(txt)
        elif rid == "com.kwai.video.basis:id/forward_count":
            shares = parsear_numero_kwai(txt)
        elif rid == "com.kwai.video.basis:id/slide_play_tv_user_info_desc" and txt:
            legenda = txt

    return {
        "views": views,
        "likes": likes,
        "comments": comments,
        "shares": shares,
        "legenda": legenda,
    }


def abrir_perfil_kwai(device) -> None:
    """Garante que o app Kwai está em primeiro plano e posicionado na aba 'Perfil'."""
    atual = device.app_current()
    if atual.get("package") != KWAI_PACKAGE:
        print("🚀 Abrindo app Kwai (com.kwai.video)...")
        device.app_start(KWAI_PACKAGE)
        time.sleep(5.0)

    # Sai de telas React Native / popups (ex: KwaiRnActivity / moedas)
    for _ in range(5):
        atual = device.app_current()
        if "KwaiRnActivity" in (atual.get("activity") or ""):
            device.press("back")
            time.sleep(1.2)
        else:
            break

    # Pula possível splash ad inicial
    for skip_txt in ("Pular", "Skip", "Fechar"):
        el = device(textContains=skip_txt)
        if el.exists:
            el.click()
            time.sleep(1.5)
            break

    # Clica na aba 'Perfil' caso não esteja vendo os thumbs do perfil
    if not device(resourceId="com.kwai.video.basis_extension:id/thumb").exists:
        for _ in range(5):
            aba_perfil = device(resourceId="com.kwai.video.basis:id/consume_tab_text", text="Perfil")
            if aba_perfil.exists:
                aba_perfil.click()
                time.sleep(2.5)
                break
            device.press("back")
            time.sleep(1.2)

    # Garante que estamos no topo do perfil e depois desce só o suficiente para expor a grade
    w, h = device.window_size()
    device.swipe(int(w * 0.5), int(h * 0.30), int(w * 0.5), int(h * 0.85), duration=0.3)
    time.sleep(1.0)
    device.swipe(int(w * 0.5), int(h * 0.78), int(w * 0.5), int(h * 0.28), duration=0.35)
    time.sleep(1.2)


def localizar_primeiro_video_nao_fixado(device) -> Optional[tuple[int, int]]:
    """
    Analisa a grade do perfil do Kwai e encontra o centro (x, y) do primeiro
    vídeo NÃO fixado no topo (ou seja, o corte mais recente postado).
    """
    abrir_perfil_kwai(device)
    w, h = device.window_size()

    # Tenta até 4 rolagens leves para encontrar cards não fixados visíveis
    for tentativa in range(4):
        xml = device.dump_hierarchy()
        root = ET.fromstring(xml)

        fixados_bounds: list[tuple[int, int, int, int]] = []
        thumbs_bounds: list[tuple[int, int, int, int]] = []

        for node in root.iter("node"):
            rid = (node.attrib.get("resource-id") or "").strip()
            bounds = parsear_bounds(node.attrib.get("bounds", ""))
            if rid == "com.kwai.video.basis_extension:id/top_label":
                fixados_bounds.append(bounds)
            elif rid == "com.kwai.video.basis_extension:id/thumb":
                # Ignora cards cortados demais na borda inferior (< 120px altura)
                if (bounds[3] - bounds[1]) >= 120:
                    thumbs_bounds.append(bounds)

        # Ordena por linha (y1 // 50) e depois coluna (x1) -> ordem de leitura da grade
        thumbs_bounds.sort(key=lambda b: (b[1] // 50, b[0]))

        for tb in thumbs_bounds:
            x1, y1, x2, y2 = tb
            eh_fixado = False
            for fb in fixados_bounds:
                fx1, fy1, fx2, fy2 = fb
                # Se o selo 'Fixado no topo' cai dentro do retângulo deste thumb
                if fx1 >= x1 - 10 and fx2 <= x2 + 10 and fy1 >= y1 - 10 and fy2 <= y2 + 10:
                    eh_fixado = True
                    break
            if not eh_fixado:
                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2
                # Evita clicar na área do widget flutuante de moedas (topo esquerdo) ou barra inferior
                if int(h * 0.36) <= cy <= int(h * 0.88):
                    return cx, cy

        # Se só havia fixados ou cabeçalho visível, rola um pouco para baixo
        device.swipe(int(w * 0.5), int(h * 0.78), int(w * 0.5), int(h * 0.30), duration=0.35)
        time.sleep(1.2)

    return None


# =====================================================================
# 3. COLETA SEQUENCIAL NO APP KWAI
# =====================================================================

def coletar_metricas_kwai(
    device,
    tarefas_kwai: list[dict[str, Any]],
    limite: Optional[int] = None,
) -> list[dict[str, Any]]:
    """
    Abre o corte mais recente não-fixado no perfil do Kwai e desliza para cima
    coletando views, curtidas, comentários e compartilhamentos de cada corte.
    """
    alvo_lista = tarefas_kwai[:limite] if (limite and limite > 0) else tarefas_kwai
    total = len(alvo_lista)

    if total == 0:
        print("⚠️ Nenhum corte marcado como publicado no Kwai encontrado no manifesto.")
        return []

    print(f"🔎 Localizando o corte mais recente no perfil do Kwai ({total} vídeos para auditar)...")
    coord = localizar_primeiro_video_nao_fixado(device)
    if not coord:
        print("❌ Não foi possível localizar a grade de vídeos no perfil do Kwai.")
        print("-> Abra o app Kwai na aba 'Perfil' e tente novamente.")
        return []

    cx, cy = coord
    print(f"🎬 Abrindo o vídeo mais recente na grade ({cx}, {cy})...")
    device.click(cx, cy)
    time.sleep(2.5)

    # Verifica se entrou efetivamente no player do vídeo (evita coletar zeros fora do player)
    if not (
        device(resourceId="com.kwai.video.basis:id/bottom_browse_record_text").exists
        or device(resourceId="com.kwai.video.basis:id/like_count_view").exists
    ):
        print("⚠️ Player ainda não abriu, tentando novo toque...")
        device.click(cx, cy)
        time.sleep(2.5)
        if not (
            device(resourceId="com.kwai.video.basis:id/bottom_browse_record_text").exists
            or device(resourceId="com.kwai.video.basis:id/like_count_view").exists
        ):
            print("❌ Não foi possível abrir o player do vídeo no Kwai (verifique se a tela está desbloqueada).")
            return []

    w, h = device.window_size()
    coletados: list[dict[str, Any]] = []

    for idx, tarefa in enumerate(alvo_lista, start=1):
        xml = device.dump_hierarchy()
        m = extrair_metricas_tela_player(xml)

        # Retry rápido se a barra inferior ainda estiver carregando
        if m["views"] == 0 and m["likes"] == 0:
            time.sleep(1.2)
            xml = device.dump_hierarchy()
            m = extrair_metricas_tela_player(xml)

        engajamento = (
            round(((m["likes"] + m["comments"] + m["shares"]) / m["views"]) * 100, 2)
            if m["views"] > 0
            else 0.0
        )

        duracao = round(tarefa.get("end", 0) - tarefa.get("start", 0), 1)
        registro = {
            "id": tarefa["id"],
            "title": tarefa.get("title", ""),
            "titulo_capa": tarefa.get("titulo_capa", ""),
            "duracao": duracao,
            "kwai_publicado_em": tarefa.get("kwai_publicado_em", ""),
            "views": m["views"],
            "likes": m["likes"],
            "comments": m["comments"],
            "shares": m["shares"],
            "engajamento_pct": engajamento,
            "atualizado_em": manifesto.agora_iso(),
        }
        coletados.append(registro)

        print(
            f"  [{idx:02d}/{total:02d}] 👁️ {m['views']:>5} views | ❤️ {m['likes']:>3} | "
            f"💬 {m['comments']:>2} | ↗️ {m['shares']:>2} | {engajamento:>5.2f}% | "
            f"[{tarefa['id']}] {tarefa.get('title', '')[:42]}"
        )

        if idx < total:
            device.swipe(int(w * 0.5), int(h * 0.80), int(w * 0.5), int(h * 0.18), duration=0.22)
            time.sleep(1.3)

    # Volta para a tela do perfil para deixar o app limpo
    device.press("back")
    time.sleep(1.0)
    return coletados


# =====================================================================
# 4. INTELIGÊNCIA, PADRÕES VENCEDORES E RELATÓRIO MARKDOWN
# =====================================================================

def extrair_selo_capa(titulo_capa: str) -> str:
    if not titulo_capa:
        return "OUTROS"
    m = re.match(r"^([A-ZÀ-Ú\s]{3,25}):", titulo_capa.strip())
    if m:
        return m.group(1).strip()
    for selo in ["UTILIDADE PÚBLICA", "ALERTA URGENTE", "RECADO DIRETO", "DEBATE QUENTE", "DENÚNCIA"]:
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
        return "90s a 100s+"


def analisar_padroes_kwai(coletados: list[dict[str, Any]]) -> dict[str, Any]:
    total_views = sum(r["views"] for r in coletados)
    total_likes = sum(r["likes"] for r in coletados)
    total_comments = sum(r["comments"] for r in coletados)
    total_shares = sum(r["shares"] for r in coletados)
    media_views = round(total_views / len(coletados), 1) if coletados else 0.0

    # Por faixa de duração
    por_duracao = defaultdict(lambda: {"views": 0, "likes": 0, "qtd": 0})
    for r in coletados:
        f = classificar_faixa_duracao(r["duracao"])
        por_duracao[f]["views"] += r["views"]
        por_duracao[f]["likes"] += r["likes"]
        por_duracao[f]["qtd"] += 1

    ranking_duracao = sorted(
        [
            {
                "faixa": f,
                "media_views": round(d["views"] / d["qtd"], 1),
                "total_views": d["views"],
                "total_likes": d["likes"],
                "qtd": d["qtd"],
            }
            for f, d in por_duracao.items()
        ],
        key=lambda x: x["media_views"],
        reverse=True,
    )

    # Por selo de capa
    por_selo = defaultdict(lambda: {"views": 0, "likes": 0, "qtd": 0})
    for r in coletados:
        s = extrair_selo_capa(r["titulo_capa"])
        por_selo[s]["views"] += r["views"]
        por_selo[s]["likes"] += r["likes"]
        por_selo[s]["qtd"] += 1

    ranking_selos = sorted(
        [
            {
                "selo": s,
                "media_views": round(d["views"] / d["qtd"], 1),
                "total_views": d["views"],
                "total_likes": d["likes"],
                "qtd": d["qtd"],
            }
            for s, d in por_selo.items()
        ],
        key=lambda x: x["media_views"],
        reverse=True,
    )

    top_videos = sorted(coletados, key=lambda x: (x["views"], x["likes"]), reverse=True)
    melhor_faixa = ranking_duracao[0]["faixa"] if ranking_duracao else "60s a 75s"
    melhores_selos = [s["selo"] for s in ranking_selos[:3] if s["selo"] != "OUTROS"] or [
        "UTILIDADE PÚBLICA",
        "ALERTA URGENTE",
    ]

    top_txt = "\n".join(
        f"  * \"{v['title']}\" ({v['views']} views, {v['likes']} likes, {v['duracao']}s, selo: {extrair_selo_capa(v['titulo_capa'])})"
        for v in top_videos[:5]
    )

    diretriz = (
        f"### 📊 INTELIGÊNCIA DE AUDIÊNCIA NO KWAI (DADOS REAIS DE {len(coletados)} CORTES):\n"
        f"- Média atual do canal no Kwai: **{media_views} views/vídeo** ({total_views} views totais, {total_likes} curtidas).\n"
        f"- Faixa de duração com maior retenção no Kwai: **{melhor_faixa}**.\n"
        f"- Selos de capa com maior tração: **{', '.join(melhores_selos)}**.\n"
        f"- Top cortes campeões de audiência no Kwai:\n{top_txt}"
    )

    return {
        "atualizado_em": manifesto.agora_iso(),
        "total_auditados": len(coletados),
        "total_views": total_views,
        "media_views": media_views,
        "total_likes": total_likes,
        "total_comments": total_comments,
        "total_shares": total_shares,
        "melhor_faixa_duracao": melhor_faixa,
        "melhores_selos": melhores_selos,
        "ranking_duracao": ranking_duracao,
        "ranking_selos": ranking_selos,
        "top_videos": top_videos[:15],
        "diretriz_retroalimentacao": diretriz,
    }


def salvar_relatorio_kwai(padroes: dict[str, Any]) -> None:
    CORTES_PRONTOS_DIR.mkdir(parents=True, exist_ok=True)
    linhas = [
        "# 📈 Relatório de Desempenho e Inteligência — Kwai",
        "",
        f"> **Perfil:** Política Direta (`rdsdogsLover`) | **Data da Auditoria:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
        "",
        "---",
        "",
        "## 1. Visão Geral",
        "",
        f"- **Cortes auditados:** `{padroes['total_auditados']}`",
        f"- **Visualizações totais:** `{padroes['total_views']}` views (média: `{padroes['media_views']}` views/vídeo)",
        f"- **Curtidas totais:** `{padroes['total_likes']}`",
        f"- **Comentários:** `{padroes['total_comments']}`",
        f"- **Compartilhamentos:** `{padroes['total_shares']}`",
        "",
        "---",
        "",
        "## 2. Desempenho por Faixa de Duração",
        "",
        "| Faixa de Duração | Média Views | Total Views | Likes | Amostra |",
        "|---|---|---|---|---|",
    ]
    for d in padroes["ranking_duracao"]:
        linhas.append(
            f"| **{d['faixa']}** | **{d['media_views']}** | {d['total_views']} | {d['total_likes']} | {d['qtd']} vídeos |"
        )

    linhas.extend([
        "",
        "## 3. Desempenho por Selo de Capa",
        "",
        "| Selo / Categoria | Média Views | Total Views | Likes | Qtd |",
        "|---|---|---|---|---|",
    ])
    for s in padroes["ranking_selos"]:
        linhas.append(
            f"| **{s['selo']}** | **{s['media_views']}** | {s['total_views']} | {s['total_likes']} | {s['qtd']} vídeos |"
        )

    linhas.extend([
        "",
        "---",
        "",
        "## 4. Top Cortes Mais Assistidos no Kwai",
        "",
        "| # | Views | Likes | Com. | Comp. | Engaj. | Duração | Título |",
        "|---|---|---|---|---|---|---|---|",
    ])
    for idx, v in enumerate(padroes["top_videos"], start=1):
        linhas.append(
            f"| `#{idx}` | **{v['views']}** | {v['likes']} | {v['comments']} | {v['shares']} | {v['engajamento_pct']}% | {v['duracao']}s | {v['title']} |"
        )

    RELATORIO_KWAI_MD.write_text("\n".join(linhas), encoding="utf-8")
    print(f"📄 Relatório Kwai salvo em: {RELATORIO_KWAI_MD}")


# =====================================================================
# 5. PONTO DE ENTRADA
# =====================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Coleta métricas dos cortes publicados no Kwai via Android ADB (celular ou BlueStacks)."
    )
    parser.add_argument(
        "--limite",
        type=int,
        default=0,
        help="Quantidade máxima de vídeos recentes para auditar (0 = todos os publicados no manifesto).",
    )
    parser.add_argument(
        "--serial",
        help="Serial ou endereço TCP ADB específico (ex: 127.0.0.1:6610).",
    )
    args = parser.parse_args()

    try:
        tarefas = manifesto.carregar()
    except Exception as e:
        print(f"❌ Erro ao ler manifesto: {e}")
        sys.exit(1)

    tarefas_kwai = [t for t in tarefas if t.get("publicado_kwai")]
    tarefas_kwai.sort(key=lambda x: x.get("kwai_publicado_em", ""), reverse=True)

    if not tarefas_kwai:
        print("⚠️ Nenhum corte publicado no Kwai registrado no manifesto.")
        sys.exit(0)

    device, _serial = publicar_kwai.conectar_dispositivo(args.serial)
    coletados = coletar_metricas_kwai(device, tarefas_kwai, limite=args.limite)

    if not coletados:
        sys.exit(1)

    # Grava no manifesto
    mapa = {c["id"]: c for c in coletados}
    for t in tarefas:
        if t.get("id") in mapa:
            c = mapa[t["id"]]
            t["metricas_kwai"] = {
                "views": c["views"],
                "likes": c["likes"],
                "comments": c["comments"],
                "shares": c["shares"],
                "engajamento_pct": c["engajamento_pct"],
                "atualizado_em": c["atualizado_em"],
            }

    manifesto.salvar(tarefas)
    print(f"💾 Manifesto atualizado com métricas do Kwai de {len(coletados)} corte(s)!")

    padroes = analisar_padroes_kwai(coletados)
    salvar_relatorio_kwai(padroes)

    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    PADROES_KWAI_JSON.write_text(json.dumps(padroes, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"🧠 Padrões Kwai exportados em: {PADROES_KWAI_JSON}")

    print("\n===================================================")
    print("🏆 AUDITORIA KWAI CONCLUÍDA:")
    print(f"   - Cortes auditados: {padroes['total_auditados']}")
    print(f"   - Views totais: {padroes['total_views']} (média: {padroes['media_views']}/vídeo)")
    print(f"   - Curtidas: {padroes['total_likes']} | Comentários: {padroes['total_comments']} | Compartilhamentos: {padroes['total_shares']}")
    print(f"   - Melhor faixa de duração: {padroes['melhor_faixa_duracao']}")
    print(f"   - Melhores selos: {', '.join(padroes['melhores_selos'])}")
    print("===================================================\n")


if __name__ == "__main__":
    main()
