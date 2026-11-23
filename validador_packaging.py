"""
Validador de Packaging (Título + Capa) em PT-BR para YouTube Shorts e Kwai.

Inspirado no linter 'yt-package/title.py', adaptado para Português do Brasil:
  - Verifica se Título e Título de Capa são COMPLEMENTARES (sem repetir as mesmas palavras).
  - Checa truncamento em feed mobile (40 chars) e busca desktop (60 chars).
  - Controla excesso de CAIXA ALTA, palavras genéricas/vagas e tamanho da capa.
  - Valoriza números concretos (R$, %, datas), nomes próprios e perguntas abertas.
"""

import re
import unicodedata
from typing import Any, Optional

DESKTOP_IDEAL = 65
MOBILE_HEAD = 42
LIMITE_SHORTS = 92  # Deixa margem para " #Shorts" (8 chars) caber nos 100 do YouTube

STOPWORDS_PT = {
    "a", "as", "o", "os", "um", "uma", "uns", "umas", "de", "da", "do", "das", "dos",
    "em", "no", "na", "nos", "nas", "para", "pra", "por", "pelo", "pela", "com", "sem",
    "que", "e", "ou", "mas", "se", "ao", "aos", "como", "sobre", "mais", "menos", "muito",
    "ja", "so", "seu", "sua", "seus", "suas", "esse", "essa", "este", "esta", "isso",
    "isto", "ele", "ela", "eles", "elas", "voce", "nao", "sim", "vai", "foi", "sao",
    "esta", "tem", "ter", "ser", "faz", "fez", "diz", "disse", "apos", "entre", "ate",
    "todo", "toda", "todos", "todas", "pais", "brasil", "video", "corte", "shorts",
}

VAGAS_PT = {
    "incrivel", "chocante", "absurdo", "insano", "loucura", "surreal", "epico",
    "imperdivel", "bombastico", "inacreditavel", "impressionante", "sensacional",
}


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return sem_acento.lower()


def _palavras_relevantes(texto: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", _normalizar(texto))
    return [w for w in tokens if len(w) > 2 and w not in STOPWORDS_PT]


def _extrair_corpo_capa(titulo_capa: str) -> str:
    """Remove o selo inicial (ex: 'UTILIDADE PÚBLICA:') para medir apenas a frase da capa."""
    return re.sub(r"^[A-ZÀ-Ú\s]{3,28}:\s*", "", titulo_capa.strip()).strip(" '\"")


def avaliar_par(title: str, titulo_capa: Optional[str] = None) -> dict[str, Any]:
    """
    Avalia a qualidade de CTR do par (title, titulo_capa) e retorna:
    {score (0-100), chars, alertas [(codigo, msg)], pontos_fortes [msg]}.
    """
    t = (title or "").strip()
    n = len(t)
    alertas: list[tuple[str, str]] = []
    pontos_fortes: list[str] = []

    # 1. Tamanho do título
    if n > LIMITE_SHORTS:
        alertas.append(("tamanho", f"{n} chars — excede margem segura de {LIMITE_SHORTS} (+ '#Shorts' <= 100)"))
    elif n > DESKTOP_IDEAL:
        alertas.append(("desktop", f"{n} chars — busca desktop pode truncar após ~{DESKTOP_IDEAL} chars"))
    else:
        pontos_fortes.append(f"{n} chars (cabe inteiro na busca desktop)")

    # 2. Excesso de CAIXA ALTA
    palavras_caps = [w.strip(".,!?:;'\"()") for w in t.split() if len(w.strip(".,!?:;'\"()")) > 2]
    caps = [w for w in palavras_caps if w.isupper() and w not in {"STF", "PGR", "PEC", "INSS", "MEI", "PIX", "EAD", "CPF", "SUS", "AGU", "EBC", "ONU", "COP", "CPI", "BNDES", "IBGE", "PIB", "BC", "PF", "PM", "DF", "RJ", "SP", "MG", "RS"}]
    if len(caps) > 3:
        alertas.append(("caps", f"{len(caps)} palavras em CAIXA ALTA — use no máximo 2 para destaque"))
    elif 1 <= len(caps) <= 2:
        pontos_fortes.append(f"ênfase equilibrada ({len(caps)} palavra(s) em caixa alta)")

    # 3. Palavras vagas/clickbait vazio
    vagas = [w for w in re.findall(r"[a-z]+", _normalizar(t)) if w in VAGAS_PT]
    if vagas:
        alertas.append(("vago", f"termo genérico ({', '.join(sorted(set(vagas)))}) — troque por dado concreto"))

    # 4. Números / concretude / pergunta
    nums = re.findall(r"(?:R\$\s*)?\d[\d.,]*%?", t)
    if nums:
        pontos_fortes.append(f"traz dado concreto ({', '.join(nums[:2])})")
    if t.endswith("?"):
        pontos_fortes.append("usa pergunta aberta que gera curiosidade")

    # 5. Complementaridade Título vs Capa (principal regra do yt-package)
    if titulo_capa:
        corpo_capa = _extrair_corpo_capa(titulo_capa)
        tw = set(_palavras_relevantes(t))
        hw = set(_palavras_relevantes(corpo_capa))
        compartilhadas = tw & hw

        taxa_overlap = (len(compartilhadas) / len(hw)) if hw else 0.0
        if len(compartilhadas) >= 2 and taxa_overlap >= 0.40:
            alertas.append((
                "duplicado",
                f"capa repete o título em ({', '.join(sorted(compartilhadas))}) — capa deve complementar, não repetir",
            ))
        else:
            pontos_fortes.append("título e capa são complementares (sem redundância)")

        qtd_palavras_capa = len(re.findall(r"[a-zA-ZÀ-Úà-ú0-9]+", corpo_capa))
        if qtd_palavras_capa > 8:
            alertas.append(("capa-longa", f"frase da capa tem {qtd_palavras_capa} palavras (ideal <= 6–7 para leitura rápida)"))
        elif qtd_palavras_capa > 0:
            pontos_fortes.append(f"capa curta e legível ({qtd_palavras_capa} palavras)")

    score = max(0, min(100, 92 - 14 * len(alertas) + 4 * len(pontos_fortes)))
    return {
        "title": t,
        "chars": n,
        "score": score,
        "alertas": alertas,
        "pontos_fortes": pontos_fortes,
    }


def imprimir_relatorio_lote(cortes: list[dict[str, Any]]) -> None:
    """Imprime um resumo compacto do score de packaging (CTR) dos cortes analisados."""
    print("🎯 Validação de Packaging (Título × Capa — yt-package PT-BR):")
    for c in cortes:
        r = avaliar_par(c.get("title", ""), c.get("titulo_capa", ""))
        c["packaging_score"] = r["score"]
        selo = "🟢" if r["score"] >= 80 else "🟡" if r["score"] >= 65 else "🔴"
        print(f"   {selo} [{c.get('horario_sugerido', '--:--')}] Score {r['score']:>3}/100 ({r['chars']} chars) | {c.get('title', '')[:58]}")
        for cod, msg in r["alertas"]:
            print(f"       ⚠️  [{cod}] {msg}")
