"""
Manifesto de cortes: fonte única de verdade entre analisar_srt.py e cortes.py.

Arquivo: temp/tarefas_corte.json  (lista JSON acumulativa)

Cada item possui:
    id               str   Estável: "<video_id>_<n>" (ex.: "JHIJDjlMYNQ_1")
    ordem            int   Posição na grade diária do vídeo (1, 2, 3)
    horario_sugerido str   "11:30" | "17:30" | "20:30"
    nome             str   Nome curto sem acentos (usado no nome do arquivo)
    video_path       str   Nome do arquivo de vídeo de origem em temp/
    title            str
    start / end      float Segundos
    titulo_capa, texto_publicacao, hashtags
    status           str   "pendente" | "renderizado" | "publicado"
    criado_em        str   ISO 8601
    arquivo_final    str|None  Caminho relativo do último corte renderizado
    modo             str|None  Modo FFmpeg usado na última renderização
"""

import hashlib
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

BASE_DIR = Path(__file__).resolve().parent
TEMP_DIR = BASE_DIR / "temp"
OUTPUT_DIR = BASE_DIR / "cortes_prontos"
MANIFESTO_FILE = TEMP_DIR / "tarefas_corte.json"
MANIFESTO_LEGADO_FILE = TEMP_DIR / "tarefas_corte.legacy.json"

STATUS_PENDENTE = "pendente"
STATUS_RENDERIZADO = "renderizado"
STATUS_PUBLICADO = "publicado"

# Nomes gerados pelo download.py: <YYYYMMDD>_<video_id_11_chars>_<titulo>.mp4
_PADRAO_ID_YOUTUBE = re.compile(r"^\d{8}_([A-Za-z0-9_-]{11})_")


# =====================================================================
# 1. IDS ESTÁVEIS E NOMES
# =====================================================================

def agora_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def chave_video(video_path: str) -> str:
    """
    Extrai uma chave estável do vídeo de origem.
    - '<YYYYMMDD>_<id>_<titulo>.mp4' -> '<id>' (ID do YouTube)
    - '<job_id>_raw.mp4'             -> '<job_id>'
    - Outros nomes                   -> 'v' + hash curto do nome
    """
    stem = Path(video_path).stem
    match = _PADRAO_ID_YOUTUBE.match(stem)
    if match:
        return match.group(1)
    if stem.endswith("_raw"):
        return stem[: -len("_raw")]
    return "v" + hashlib.sha1(stem.encode("utf-8")).hexdigest()[:8]


def gerar_id(video_path: str, n: int) -> str:
    return f"{chave_video(video_path)}_{n}"


def nome_arquivo_limpo(nome: str) -> str:
    """Mesma regra histórica usada pelo cortes.py para nomear os arquivos."""
    return re.sub(r'[\\/*?:"<>|]', "", nome).lower().replace(" ", "_")


# =====================================================================
# 2. LEITURA, ESCRITA E MIGRAÇÃO
# =====================================================================

def salvar(tarefas: list[dict[str, Any]]) -> None:
    """Grava o manifesto de forma atômica (evita arquivo corrompido se interrompido)."""
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    tmp = MANIFESTO_FILE.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(tarefas, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    os.replace(tmp, MANIFESTO_FILE)


def _e_legado(tarefa: dict[str, Any]) -> bool:
    return not isinstance(tarefa.get("id"), str) or "status" not in tarefa


def _procurar_saida_legada(id_antigo: Any, nome: str) -> Optional[Path]:
    """Procura um corte já renderizado no formato antigo: corte_<idNumerico>_<modo>_<nome>.mp4"""
    if not OUTPUT_DIR.exists() or id_antigo is None:
        return None
    sufixo = f"_{nome_arquivo_limpo(nome)}.mp4"
    try:
        for p in OUTPUT_DIR.glob(f"corte_{id_antigo}_*"):
            if p.name.endswith(sufixo):
                return p
    except (OSError, ValueError):
        return None
    return None


def _migrar_legado(tarefas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Converte ids numéricos globais para ids estáveis por vídeo e infere o status."""
    contagem: dict[str, int] = {}
    migradas = []
    for t in tarefas:
        video = t["video_path"]
        contagem[video] = contagem.get(video, 0) + 1
        n = contagem[video]

        novo = dict(t)
        id_antigo = t.get("id")
        novo["id"] = gerar_id(video, n)
        novo["ordem"] = n
        novo.setdefault("status", STATUS_PENDENTE)
        novo.setdefault("criado_em", agora_iso())
        novo.setdefault("arquivo_final", None)
        novo.setdefault("modo", None)

        saida = _procurar_saida_legada(id_antigo, t.get("nome", ""))
        if saida is not None and novo["status"] == STATUS_PENDENTE:
            novo["status"] = STATUS_RENDERIZADO
            novo["arquivo_final"] = str(saida.relative_to(BASE_DIR))

        migradas.append(novo)
    return migradas


def carregar() -> list[dict[str, Any]]:
    """Carrega o manifesto (migrando automaticamente o formato antigo, com backup)."""
    if not MANIFESTO_FILE.exists():
        return []

    dados = json.loads(MANIFESTO_FILE.read_text(encoding="utf-8"))
    if not isinstance(dados, list):
        raise ValueError(f"'{MANIFESTO_FILE.name}' deve conter uma lista JSON.")

    if any(_e_legado(t) for t in dados):
        if not MANIFESTO_LEGADO_FILE.exists():
            shutil.copy2(MANIFESTO_FILE, MANIFESTO_LEGADO_FILE)
        dados = _migrar_legado(dados)
        salvar(dados)
        print(
            f"ℹ️  Manifesto antigo migrado para ids estáveis "
            f"(backup: {MANIFESTO_LEGADO_FILE.name})."
        )
    return dados


# =====================================================================
# 3. OPERAÇÕES DE ALTO NÍVEL
# =====================================================================

def substituir_cortes_do_video(
    tarefas: list[dict[str, Any]],
    video_path: str,
    cortes: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Substitui os cortes de UM vídeo, preservando os de todos os outros.

    - Cortes já 'publicado' do mesmo vídeo nunca são removidos (evita republicar).
    - Retorna (nova_lista, sobrescritas), onde 'sobrescritas' são os cortes já
      'renderizado' que foram substituídos (para avisar o usuário).
    """
    do_video = [t for t in tarefas if t["video_path"] == video_path]
    publicados = [t for t in do_video if t.get("status") == STATUS_PUBLICADO]
    removidas = [t for t in do_video if t.get("status") != STATUS_PUBLICADO]
    sobrescritas = [t for t in removidas if t.get("status") == STATUS_RENDERIZADO]

    restantes = [t for t in tarefas if t["video_path"] != video_path] + publicados

    offset = len(publicados)
    novas = []
    for i, corte in enumerate(cortes, start=1):
        novas.append({
            "id": gerar_id(video_path, offset + i),
            "ordem": i,
            "horario_sugerido": corte["horario_sugerido"],
            "nome": corte["nome"],
            "video_path": video_path,
            "title": corte["title"],
            "start": corte["start"],
            "end": corte["end"],
            "titulo_capa": corte.get("titulo_capa", ""),
            "texto_publicacao": corte.get("texto_publicacao", ""),
            "hashtags": corte.get("hashtags", ""),
            "status": STATUS_PENDENTE,
            "criado_em": agora_iso(),
            "arquivo_final": None,
            "modo": None,
        })

    return restantes + novas, sobrescritas
