"""
Publicador de Vídeos no Kwai via Android (ADB + uiautomator2).

Conecta ao celular Android (via USB) ou emulador com ADB ativado, seleciona
os melhores cortes usando o Motor de Pontuação Inteligente (Score Kwai),
envia o arquivo .mp4 para a galeria do aparelho e automatiza a postagem no app Kwai.
"""

import argparse
import random
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

import adbutils
import uiautomator2 as u2

import manifesto

# =====================================================================
# 1. CONFIGURAÇÕES GERAIS
# =====================================================================

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "cortes_prontos"
KWAI_PACKAGE = "com.kwai.video"
KWAI_SHARE_ACTIVITY = "com.kwai.video/com.kscorp.oversea.platform.router.ui.UriRouterActivity"
ANDROID_DEST_DIR = "/sdcard/Movies/PoliticaDireta"


# =====================================================================
# 2. MOTOR DE PONTUAÇÃO INTELIGENTE (SCORE KWAI)
# =====================================================================

def calcular_score_kwai(tarefa: dict[str, Any]) -> float:
    """
    Pontua o potencial de viralização e retenção do corte especificamente no Kwai:
    - Faixa de duração ideal (45s a 75s): pontuação máxima
    - Gatilhos de impacto no título de capa (urgência, dinheiro, denúncia, utilidade)
    - Presença de CTA para grupos / compartilhamento
    """
    score = 50.0

    duracao = tarefa.get("end", 0) - tarefa.get("start", 0)
    if 45 <= duracao <= 75:
        score += 30.0
    elif 75 < duracao <= 95:
        score += 20.0
    elif 35 <= duracao < 45:
        score += 15.0
    else:
        score += 5.0

    capa = tarefa.get("titulo_capa", "").upper()
    if any(g in capa for g in ["ALERTA URGENTE", "DENÚNCIA", "GRAVE", "ESCÂNDALO"]):
        score += 20.0
    elif any(g in capa for g in ["RECADO DIRETO", "DEBATE QUENTE", "ESMAGA", "REBATE"]):
        score += 18.0
    elif any(g in capa for g in ["UTILIDADE PÚBLICA", "BOLSO", "R$", "SALÁRIO", "BENEFÍCIO"]):
        score += 15.0

    texto = tarefa.get("texto_publicacao", "").lower()
    if "grupo" in texto or "compartilhe" in texto:
        score += 5.0

    return round(score, 1)


def selecionar_melhores_cortes(
    tarefas_disponiveis: list[dict[str, Any]],
    quantidade: int = 3
) -> list[dict[str, Any]]:
    """
    Classifica os cortes pelo Score Kwai garantindo diversidade temática
    (evita selecionar múltiplos cortes da mesma notícia no mesmo dia).
    """
    for t in tarefas_disponiveis:
        t["_kwai_score"] = calcular_score_kwai(t)

    ordenadas = sorted(tarefas_disponiveis, key=lambda x: x["_kwai_score"], reverse=True)

    selecionadas = []
    videos_usados = set()

    for t in ordenadas:
        v_origem = t.get("video_path")
        if v_origem not in videos_usados:
            selecionadas.append(t)
            videos_usados.add(v_origem)
            if len(selecionadas) == quantidade:
                break

    if len(selecionadas) < quantidade:
        for t in ordenadas:
            if t not in selecionadas:
                selecionadas.append(t)
                if len(selecionadas) == quantidade:
                    break

    return selecionadas


# =====================================================================
# 3. CONEXÃO ANDROID (ADB + UIAUTOMATOR2) E TRANSFERÊNCIA DE VÍDEO
# =====================================================================

def conectar_dispositivo(serial: Optional[str] = None):
    """Conecta ao primeiro dispositivo Android autorizado via ADB."""
    dispositivos = adbutils.adb.list()
    autorizados = [d for d in dispositivos if d.state == "device"]

    if not autorizados:
        if dispositivos:
            print("⚠️ Dispositivo detectado, mas ainda não autorizado:")
            for d in dispositivos:
                print(f"   - {d.serial} ({d.state})")
            print("-> Desbloqueie o celular e toque em 'Permitir depuração USB'.")
        else:
            print("❌ Nenhum dispositivo Android conectado via ADB.")
            print("-> Conecte o celular via cabo USB (ou abra o emulador com ADB ativado).")
        sys.exit(1)

    alvo = serial or autorizados[0].serial
    print(f"📱 Conectando ao dispositivo Android: {alvo} ...")
    device = u2.connect(alvo)
    device.screen_on()
    return device, alvo


def enviar_video_para_android(serial: str, caminho_local: Path) -> tuple[str, str]:
    """
    Envia o arquivo .mp4 para o celular via ADB push, dispara o MediaScanner
    e consulta o MediaStore do Android para retornar (caminho_remoto, content_uri)
    exclusivo deste arquivo exato (impossível confundir com duplicatas na galeria).
    """
    adb_exe = adbutils.adb_path()
    destino_remoto = f"{ANDROID_DEST_DIR}/{caminho_local.name}"

    subprocess.run(
        [adb_exe, "-s", serial, "shell", "mkdir", "-p", ANDROID_DEST_DIR],
        check=True,
        capture_output=True,
    )

    print(f"📲 Enviando '{caminho_local.name}' para o celular...")
    subprocess.run(
        [adb_exe, "-s", serial, "push", str(caminho_local.resolve()), destino_remoto],
        check=True,
    )

    # Notifica o Android MediaStore para indexar o vídeo
    subprocess.run(
        [
            adb_exe, "-s", serial, "shell", "am", "broadcast",
            "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
            "-d", f"file://{destino_remoto}",
        ],
        check=False,
        capture_output=True,
    )

    # Aguarda o MediaStore indexar e devolver o _id exato deste arquivo
    content_uri = ""
    for _ in range(15):
        q = subprocess.run(
            [
                adb_exe, "-s", serial, "shell", "content", "query",
                "--uri", "content://media/external/video/media",
                "--projection", "_id:_display_name",
                "--where", f"\"_display_name='{caminho_local.name}'\"",
            ],
            capture_output=True,
            text=True,
        )
        m = re.search(r"_id=(\d+)", q.stdout)
        if m:
            content_uri = f"content://media/external/video/media/{m.group(1)}"
            break
        time.sleep(1)

    if not content_uri:
        raise RuntimeError(
            f"O Android MediaStore não indexou '{caminho_local.name}' a tempo."
        )

    print(f"🆔 Vídeo indexado no MediaStore: {content_uri}")
    return destino_remoto, content_uri


def remover_video_temporario_android(serial: str, destino_remoto: str) -> None:
    """Remove o .mp4 temporário da pasta PoliticaDireta no celular após publicar."""
    adb_exe = adbutils.adb_path()
    subprocess.run(
        [adb_exe, "-s", serial, "shell", "rm", "-f", destino_remoto],
        check=False,
        capture_output=True,
    )


# =====================================================================
# 4. FORMATAÇÃO DA LEGENDA E INTERAÇÃO COM O APP KWAI
# =====================================================================

def formatar_legenda_kwai(tarefa: dict[str, Any]) -> str:
    """Prepara o texto de publicação e hashtags otimizado para o Kwai."""
    titulo = tarefa.get("title", "")
    capa = tarefa.get("titulo_capa", "")
    hashtags = tarefa.get("hashtags", "#PolíticaDireta #Notícias #Brasil")

    partes = []
    if capa:
        partes.append(capa)
    elif titulo:
        partes.append(titulo)

    texto = tarefa.get("texto_publicacao", "")
    citacoes = re.findall(r'"([^"]*)"', texto)
    if citacoes:
        partes.append(f'"{citacoes[0][:150]}..."')

    partes.append(f"\n{hashtags}")
    return "\n\n".join(partes)[:500]


def clicar_por_id_ou_texto(
    device,
    resource_id: Optional[str] = None,
    textos: Optional[list[str]] = None,
    timeout: float = 8.0,
) -> bool:
    """Procura e clica preferencialmente pelo resource-id nativo do Kwai, com fallback por texto."""
    fim = time.time() + timeout
    while time.time() < fim:
        if resource_id:
            el = device(resourceId=resource_id)
            if el.exists:
                el.click()
                return True
        for txt in (textos or []):
            el = device(textContains=txt)
            if el.exists:
                el.click()
                return True
            el_desc = device(descriptionContains=txt)
            if el_desc.exists:
                el_desc.click()
                return True
        time.sleep(0.5)
    return False


def localizar_arquivo_corte(tarefa: dict[str, Any]) -> Optional[Path]:
    if tarefa.get("arquivo_final"):
        candidato = BASE_DIR / tarefa["arquivo_final"]
        if candidato.exists():
            return candidato
    id_tarefa = tarefa["id"]
    for p in OUTPUT_DIR.glob(f"corte_{id_tarefa}_*"):
        if p.suffix.lower() == ".mp4":
            return p
    return None


def publicar_no_app_kwai(
    device,
    serial: str,
    tarefa: dict[str, Any],
    apenas_preparar: bool = False,
) -> tuple[bool, Optional[str]]:
    """
    Envia o vídeo ao celular, obtém o content:// URI exato no MediaStore e
    dispara o Intent nativo ACTION_SEND diretamente para o Kwai (sem abrir galeria
    e sem risco de duplicar ou selecionar vídeo errado).
    Retorna (sucesso: bool, destino_remoto: Optional[str]).
    """
    caminho_video = localizar_arquivo_corte(tarefa)
    if not caminho_video or not caminho_video.exists():
        print(f"❌ Erro [{tarefa['id']}]: Arquivo de vídeo renderizado não encontrado!")
        return False, None

    legenda = formatar_legenda_kwai(tarefa)

    # 1. Envia o vídeo para o celular e obtém o content:// URI exclusivo dele
    destino_remoto, content_uri = enviar_video_para_android(serial, caminho_video)

    # 2. Copia a legenda com acentos perfeitos para a área de transferência do Android
    device.set_clipboard(legenda, "legenda_kwai")
    print("📋 Legenda copiada para a área de transferência do celular!")

    # 3. Compartilha o vídeo EXATO direto para o Kwai via Android ACTION_SEND
    print(f"🚀 Compartilhando vídeo exato direto para o Kwai ({KWAI_SHARE_ACTIVITY})...")
    device.app_stop(KWAI_PACKAGE)
    time.sleep(1)

    adb_exe = adbutils.adb_path()
    subprocess.run(
        [
            adb_exe, "-s", serial, "shell", "am", "start",
            "-a", "android.intent.action.SEND",
            "-t", "video/mp4",
            "--eu", "android.intent.extra.STREAM", content_uri,
            "-n", KWAI_SHARE_ACTIVITY,
            "-f", "0x1",  # FLAG_GRANT_READ_URI_PERMISSION
        ],
        check=True,
        capture_output=True,
    )
    time.sleep(4)

    # 4. Tela de corte/ajuste inicial ('Próximo' -> v_cut_next)
    if clicar_por_id_ou_texto(
        device,
        resource_id="com.kwai.video.ca_product:id/v_cut_next",
        textos=["Próximo", "Avançar"],
        timeout=12.0,
    ):
        print("✂️  Tela de corte confirmada ('Próximo').")
        time.sleep(4)

    # 5. Remove música de fundo automática caso o Kwai tenha anexado na tela de edição
    if clicar_por_id_ou_texto(
        device,
        resource_id="com.kwai.video.basis_extension:id/music_close_view",
        timeout=2.5,
    ):
        print("🔇 Música automática removida para preservar o áudio original.")
        time.sleep(1)

    # 6. Avança da tela de edição para a tela de publicação ('Próximo' -> edit_next_button)
    if not clicar_por_id_ou_texto(
        device,
        resource_id="com.kwai.video.ca_product:id/edit_next_button",
        textos=["Próximo", "Avançar"],
        timeout=10.0,
    ):
        print("⚠️ Botão 'Próximo' não encontrado na tela de edição.")
        return False, destino_remoto
    time.sleep(3)

    # 7. Aguarda a tela de publicação carregar e cola a legenda (Ctrl+V / KEYCODE_PASTE)
    campo_texto = None
    fim_espera = time.time() + 20.0
    while time.time() < fim_espera:
        for seletor in (
            device(resourceId="com.kwai.video.basis:id/editor"),
            device(textContains="Descreva sua publicação"),
            device(className="android.widget.EditText"),
        ):
            if seletor.exists:
                campo_texto = seletor
                break
        if campo_texto is not None:
            break
        time.sleep(0.5)

    if campo_texto is not None:
        campo_texto.click()
        time.sleep(1)
        device.shell("input keyevent 279")  # KEYCODE_PASTE
        time.sleep(1.5)

        texto_atual = (campo_texto.get_text() or "").strip()
        if not texto_atual or "Descreva sua publicação" in texto_atual:
            campo_texto.set_text(legenda)
            time.sleep(1)

        print("✍️ Legenda e hashtags coladas na tela de publicação do Kwai!")
        device.press("back")  # Recolhe o teclado para liberar o botão Publicar
        time.sleep(1.5)
    else:
        print("⚠️ Campo de legenda não encontrado (a legenda já está no Ctrl+V do celular).")

    if apenas_preparar:
        print("⏸️  Modo --preparar ativo: revise na tela do celular e toque em 'Publicar' manualmente.")
        return True, destino_remoto

    # 8. Clica no botão 'Publicar'
    if clicar_por_id_ou_texto(
        device,
        resource_id="com.kwai.video.basis:id/post",
        textos=["Publicar"],
        timeout=8.0,
    ):
        print("✅ Botão 'Publicar' acionado no Kwai! Aguardando envio...")
        time.sleep(10)
        remover_video_temporario_android(serial, destino_remoto)
        return True, destino_remoto

    print("⚠️ Botão 'Publicar' não localizado automaticamente. Finalize tocando em Publicar no celular.")
    return False, destino_remoto


def inspecionar_tela(device) -> None:
    """Imprime os textos e resource-ids visíveis na tela atual do celular (útil para calibração)."""
    xml = device.dump_hierarchy()
    itens = re.findall(r'text="([^"]+)"[^>]*resource-id="([^"]*)"', xml)
    print("\n=== ELEMENTOS VISÍVEIS NA TELA ATUAL ===")
    vistos = set()
    for txt, rid in itens:
        chave = (txt.strip(), rid.strip())
        if chave[0] and chave not in vistos:
            vistos.add(chave)
            print(f" - text='{chave[0]}' | id='{chave[1]}'")
    print("========================================\n")


# =====================================================================
# 5. PONTO DE PARTIDA DO PROGRAMA
# =====================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Publicador inteligente de vídeos no Kwai via Android (ADB + uiautomator2)."
    )
    parser.add_argument(
        "--top",
        type=int,
        default=3,
        help="Quantidade dos melhores cortes para selecionar (padrão: 3).",
    )
    parser.add_argument(
        "--preparar",
        action="store_true",
        help="Envia o vídeo, abre o Kwai e preenche a legenda, mas pausa antes de clicar em Publicar.",
    )
    parser.add_argument(
        "--inspecionar",
        action="store_true",
        help="Mostra os botões/textos da tela atual do celular (para calibração).",
    )
    parser.add_argument(
        "--serial",
        help="Serial específico do dispositivo ADB (opcional).",
    )

    args = parser.parse_args()
    device, serial = conectar_dispositivo(args.serial)

    if args.inspecionar:
        inspecionar_tela(device)
        sys.exit(0)

    try:
        tarefas = manifesto.carregar()
    except Exception as e:
        print(f"❌ Erro ao ler manifesto: {e}")
        sys.exit(1)

    disponiveis = [
        t for t in tarefas
        if t.get("status") in [manifesto.STATUS_RENDERIZADO, manifesto.STATUS_PUBLICADO]
        and not t.get("publicado_kwai", False)
        and localizar_arquivo_corte(t) is not None
    ]

    if not disponiveis:
        print("⚠️ Nenhum corte renderizado pendente de publicação no Kwai!")
        sys.exit(0)

    selecionadas = selecionar_melhores_cortes(disponiveis, quantidade=args.top)

    print("===================================================")
    print("      RANKING DE MELHORES CORTES PARA O KWAI       ")
    print("===================================================")
    for idx, t in enumerate(selecionadas, start=1):
        duracao = round(t.get("end", 0) - t.get("start", 0), 1)
        print(f"[{idx}] ⭐ {t['_kwai_score']} pts | {duracao}s | {t['id']}")
        print(f"    📌 {t['title']}")
        print(f"    🖼️  {t.get('titulo_capa', '')}")
    print("===================================================")
    confirma = input(f"Deseja iniciar o envio dos TOP {len(selecionadas)} cortes no celular? [S/n]: ").strip().lower()

    if confirma not in ["", "s", "sim"]:
        print("Operação cancelada.")
        sys.exit(0)

    postados = 0
    for idx, tarefa in enumerate(selecionadas, start=1):
        sucesso, destino_remoto = publicar_no_app_kwai(
            device,
            serial,
            tarefa,
            apenas_preparar=args.preparar,
        )
        if sucesso:
            marcar = False
            if not args.preparar:
                marcar = True
            else:
                resp = input(
                    f"\n📱 Você concluiu a publicação de [{tarefa['id']}] no celular? Deseja marcar como publicado? [S/n]: "
                ).strip().lower()
                if resp in ["", "s", "sim"]:
                    marcar = True
                    if destino_remoto:
                        remover_video_temporario_android(serial, destino_remoto)

            if marcar:
                tarefa["publicado_kwai"] = True
                tarefa["kwai_publicado_em"] = manifesto.agora_iso()
                manifesto.salvar(tarefas)
                postados += 1
                print(f"✅ Corte [{tarefa['id']}] registrado como publicado no manifesto!")

            if not args.preparar and idx < len(selecionadas):
                intervalo = random.randint(120, 240)
                print(f"\n☕ Aguardando {intervalo}s antes do próximo envio (proteção anti-bot)...")
                time.sleep(intervalo)

    print("===================================================")
    print(f"🏁 Finalizado! {postados} vídeo(s) publicado(s) no Kwai.")
    print("===================================================")


if __name__ == "__main__":
    main()
