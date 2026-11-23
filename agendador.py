"""
Motor de Agendamento Inteligente baseado em Slots (Anti-Canibalização).

Garante que o alto volume de produção de cortes nunca gere colisões de horário
no YouTube Shorts. Distribui automaticamente o estoque de cortes ao longo dos
próximos dias respeitando:
  1. Slots ocupados já registrados no manifesto (memória persistente de agenda).
  2. Espaçamento mínimo obrigatório entre publicações (padrão: 2h / 120 min).
  3. Intercalação temática (Round-Robin por vídeo de origem) para evitar repetir
     o mesmo assunto no mesmo dia.
  4. Transbordo automático para os dias seguintes conforme o estoque cresce.
"""

from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any, Optional

# Grades diárias pré-calibradas para YouTube Shorts (Horário de Brasília - UTC-3).
# Todas garantem no mínimo 2h30 a 3h de respiro entre Shorts para o algoritmo
# testar cada vídeo isoladamente no feed sem canibalização.
GRADES_POR_DIA: dict[int, list[str]] = {
    1: ["17:30"],
    2: ["11:30", "19:30"],
    3: ["11:30", "17:30", "20:30"],
    4: ["09:30", "13:00", "17:30", "21:00"],
    5: ["09:00", "12:00", "15:30", "18:30", "21:30"],
    6: ["08:30", "11:30", "14:30", "17:30", "20:00", "22:30"],
}

INTERVALO_MINIMO_PADRAO_MIN = 120  # 2 horas mínimas entre quaisquer dois vídeos
FOLGA_MINIMA_AGORA_MIN = 30        # Nunca agendar para menos de 30 min a partir de agora
DIAS_SEMANA_PT = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


def parsear_slots_customizados(slots_str: str) -> list[str]:
    """Valida e ordena uma string de horários separados por vírgula (ex: '09:00,13:30,19:00')."""
    slots = []
    for item in slots_str.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            h, m = map(int, item.split(":"))
            if not (0 <= h <= 23 and 0 <= m <= 59):
                raise ValueError
            slots.append(f"{h:02d}:{m:02d}")
        except ValueError:
            raise ValueError(f"Horário inválido em --slots: '{item}'. Use formato HH:MM.")
    if not slots:
        raise ValueError("Nenhum horário válido informado em --slots.")
    return sorted(set(slots))


def obter_grade_horarios(por_dia: int = 3, slots_custom: Optional[str] = None) -> list[str]:
    """Retorna a lista ordenada de horários diários (HH:MM) conforme a configuração."""
    if slots_custom:
        return parsear_slots_customizados(slots_custom)
    if por_dia not in GRADES_POR_DIA:
        raise ValueError(f"--por-dia deve estar entre 1 e {max(GRADES_POR_DIA)} (recebido: {por_dia}).")
    return list(GRADES_POR_DIA[por_dia])


def brt_para_utc_iso(dt_brt: datetime) -> str:
    """Converte datetime local (Brasília UTC-3) para ISO 8601 UTC (publishAt do YouTube)."""
    dt_utc = dt_brt + timedelta(hours=3)
    return dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def extrair_slots_ocupados(tarefas: list[dict[str, Any]], agora: Optional[datetime] = None) -> list[datetime]:
    """
    Lê o manifesto e retorna todos os datetimes (BRT) já ocupados por vídeos
    agendados (futuros ou recentes).
    """
    agora = agora or datetime.now()
    limite_passado = agora - timedelta(hours=4)
    ocupados: list[datetime] = []

    for t in tarefas:
        agendado_brt = t.get("agendado_para_brt")
        if agendado_brt:
            try:
                dt = datetime.strptime(agendado_brt, "%Y-%m-%d %H:%M")
                if dt >= limite_passado:
                    ocupados.append(dt)
                continue
            except ValueError:
                pass

        agendado_utc = t.get("agendado_para_utc")
        if agendado_utc:
            try:
                dt_utc = datetime.strptime(agendado_utc, "%Y-%m-%dT%H:%M:%SZ")
                dt_brt = dt_utc - timedelta(hours=3)
                if dt_brt >= limite_passado:
                    ocupados.append(dt_brt)
            except ValueError:
                pass

    return sorted(ocupados)


def intercalar_por_origem(tarefas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Reordena a fila de cortes em Round-Robin agrupando por vídeo de origem (video_path).
    Isso garante diversidade temática no canal: evita publicar 3 cortes da mesma
    notícia/entrevista no mesmo dia.
    """
    grupos: dict[str, deque[dict[str, Any]]] = defaultdict(deque)
    ordem_chaves: list[str] = []

    for t in tarefas:
        chave = t.get("video_path") or t.get("id", "").split("_")[0] or "desconhecido"
        if chave not in grupos:
            ordem_chaves.append(chave)
        grupos[chave].append(t)

    resultado: list[dict[str, Any]] = []
    while any(grupos[k] for k in ordem_chaves):
        for k in ordem_chaves:
            if grupos[k]:
                resultado.append(grupos[k].popleft())
    return resultado


def _tem_conflito(
    candidato: datetime,
    ocupados: list[datetime],
    intervalo_min_minutos: int,
) -> bool:
    """Retorna True se o candidato colide ou está perto demais de algum slot já ocupado."""
    for dt_ocupado in ocupados:
        diff_min = abs((candidato - dt_ocupado).total_seconds()) / 60.0
        if diff_min < intervalo_min_minutos:
            return True
    return False


def _gerar_proximos_slots_livres(
    grade: list[str],
    ocupados: list[datetime],
    quantidade: int,
    agora: datetime,
    offset_dias: int = 0,
    intervalo_min_minutos: int = INTERVALO_MINIMO_PADRAO_MIN,
) -> list[datetime]:
    """Gera os próximos N slots cronológicos livres sem qualquer colisão."""
    livres: list[datetime] = []
    todos_ocupados = list(ocupados)
    dia_cursor = (agora + timedelta(days=offset_dias)).date()
    limite_minimo = agora + timedelta(minutes=FOLGA_MINIMA_AGORA_MIN)

    # Limite de segurança de 365 dias para nunca entrar em loop infinito
    for _ in range(365):
        if len(livres) >= quantidade:
            break
        for horario in grade:
            if len(livres) >= quantidade:
                break
            h, m = map(int, horario.split(":"))
            candidato = datetime(dia_cursor.year, dia_cursor.month, dia_cursor.day, h, m, 0)
            if candidato < limite_minimo:
                continue
            if not _tem_conflito(candidato, todos_ocupados, intervalo_min_minutos):
                livres.append(candidato)
                todos_ocupados.append(candidato)
        dia_cursor += timedelta(days=1)

    return livres


def planejar_agenda(
    tarefas_manifesto: list[dict[str, Any]],
    tarefas_selecionadas: list[dict[str, Any]],
    por_dia: int = 3,
    slots_custom: Optional[str] = None,
    offset_dias: int = 0,
    intervalo_min_minutos: int = INTERVALO_MINIMO_PADRAO_MIN,
    intercalar: bool = True,
    agora: Optional[datetime] = None,
) -> list[tuple[dict[str, Any], datetime, str]]:
    """
    Calcula o calendário sem colisões para todos os cortes selecionados.

    Estratégia:
      - Intercala cortes por vídeo de origem (diversidade diária).
      - Se a grade ativa for a padrão de 3/dia (11:30, 17:30, 20:30), tenta
        respeitar o 'horario_sugerido' de cada corte alocando-o no primeiro dia
        em que aquele horário esteja livre (e sem conflito).
      - Para outras grades (alto volume: 4, 5, 6/dia ou custom), preenche os
        próximos slots cronológicos livres sem deixar buracos.

    Retorna uma lista ordenada cronologicamente de tuplas:
      (tarefa, datetime_brt, iso_utc_publish_at)
    """
    agora = agora or datetime.now()
    grade = obter_grade_horarios(por_dia=por_dia, slots_custom=slots_custom)
    ocupados = extrair_slots_ocupados(tarefas_manifesto, agora=agora)

    fila = intercalar_por_origem(tarefas_selecionadas) if intercalar else list(tarefas_selecionadas)
    plano: list[tuple[dict[str, Any], datetime, str]] = []

    usar_afinidade_horario = (grade == GRADES_POR_DIA[3])

    if usar_afinidade_horario:
        limite_minimo = agora + timedelta(minutes=FOLGA_MINIMA_AGORA_MIN)
        todos_ocupados = list(ocupados)

        # Agrupa por horario_sugerido e aplica rotação cíclica entre as faixas (11:30, 17:30, 20:30)
        # para garantir que o mesmo dia receba 3 vídeos de origens/temas diferentes!
        por_faixa: dict[str, list[dict[str, Any]]] = {h: [] for h in grade}
        for tarefa in fila:
            horario_pref = tarefa.get("horario_sugerido", "11:30")
            if horario_pref not in por_faixa:
                horario_pref = grade[0]
            por_faixa[horario_pref].append(tarefa)

        fila_balanceada: list[tuple[str, dict[str, Any]]] = []
        for idx_faixa, horario_pref in enumerate(grade):
            bucket = por_faixa[horario_pref]
            if intercalar and len(bucket) > 1:
                shift = idx_faixa % len(bucket)
                bucket = bucket[shift:] + bucket[:shift]
            for tarefa in bucket:
                fila_balanceada.append((horario_pref, tarefa))

        for horario_pref, tarefa in fila_balanceada:
            h, m = map(int, horario_pref.split(":"))
            dia_cursor = (agora + timedelta(days=offset_dias)).date()
            alocado: Optional[datetime] = None

            for _ in range(365):
                candidato = datetime(dia_cursor.year, dia_cursor.month, dia_cursor.day, h, m, 0)
                if candidato >= limite_minimo and not _tem_conflito(
                    candidato, todos_ocupados, intervalo_min_minutos
                ):
                    alocado = candidato
                    todos_ocupados.append(candidato)
                    break
                dia_cursor += timedelta(days=1)

            if alocado is None:
                raise RuntimeError(f"Não foi possível encontrar slot livre para {tarefa['id']}.")

            plano.append((tarefa, alocado, brt_para_utc_iso(alocado)))
    else:
        slots_livres = _gerar_proximos_slots_livres(
            grade=grade,
            ocupados=ocupados,
            quantidade=len(fila),
            agora=agora,
            offset_dias=offset_dias,
            intervalo_min_minutos=intervalo_min_minutos,
        )
        for tarefa, dt_brt in zip(fila, slots_livres):
            plano.append((tarefa, dt_brt, brt_para_utc_iso(dt_brt)))

    # Ordena o plano cronologicamente para que os primeiros uploads sejam os mais urgentes
    plano.sort(key=lambda item: item[1])
    return plano


def formatar_data_br(dt: datetime) -> str:
    dia_sem = DIAS_SEMANA_PT[dt.weekday()]
    return f"{dia_sem} {dt.strftime('%d/%m/%Y')} às {dt.strftime('%H:%M')}"


def imprimir_plano_agenda(
    plano: list[tuple[dict[str, Any], datetime, str]],
    titulo: str = "CALENDÁRIO PLANEJADO DE PUBLICAÇÃO (SEM COLISÕES)",
) -> None:
    """Exibe o cronograma agrupado por dia de forma clara no terminal."""
    print("=========================================================================")
    print(f"  📅 {titulo}")
    print("=========================================================================")

    if not plano:
        print("  (Nenhum corte agendado)")
        print("=========================================================================")
        return

    por_dia: dict[str, list[tuple[dict[str, Any], datetime, str]]] = defaultdict(list)
    for item in plano:
        chave_dia = item[1].strftime("%Y-%m-%d")
        por_dia[chave_dia].append(item)

    for chave_dia in sorted(por_dia.keys()):
        itens = por_dia[chave_dia]
        dt_ref = itens[0][1]
        dia_sem = DIAS_SEMANA_PT[dt_ref.weekday()]
        print(f"\n🗓️  {dia_sem}, {dt_ref.strftime('%d/%m/%Y')} ({len(itens)} corte(s)):")
        for tarefa, dt_brt, _iso_utc in itens:
            dur = round(tarefa.get("end", 0) - tarefa.get("start", 0), 0)
            origem_curta = (tarefa.get("video_path") or "")[:28]
            print(
                f"   • {dt_brt.strftime('%H:%M')} BRT | [{tarefa['id']}] ({int(dur)}s) "
                f"{tarefa.get('title', '')[:48]}"
            )
            if origem_curta:
                print(f"       ↳ origem: {origem_curta}...")

    total_dias = len(por_dia)
    print("\n=========================================================================")
    print(f"  Total: {len(plano)} corte(s) distribuído(s) ao longo de {total_dias} dia(s).")
    print("=========================================================================\n")


def imprimir_agenda_atual(tarefas_manifesto: list[dict[str, Any]]) -> None:
    """Mostra todos os cortes já agendados para o futuro no manifesto."""
    agora = datetime.now()
    futuros: list[tuple[dict[str, Any], datetime, str]] = []

    for t in tarefas_manifesto:
        agendado_brt = t.get("agendado_para_brt")
        agendado_utc = t.get("agendado_para_utc", "")
        if not agendado_brt:
            continue
        try:
            dt = datetime.strptime(agendado_brt, "%Y-%m-%d %H:%M")
            if dt >= agora:
                futuros.append((t, dt, agendado_utc))
        except ValueError:
            continue

    futuros.sort(key=lambda item: item[1])
    imprimir_plano_agenda(futuros, titulo="AGENDA ATUAL DE CORTES PROGRAMADOS NO YOUTUBE")
