---
name: pipeline-cortes-youtube-kwai
description: Orquestra o pipeline local de monitoramento, download, transcrição Whisper, análise de cortes via Gemini API e renderização automatizada de vídeos (YouTube Shorts e Kwai) usando download.py, gerador_srt.py, analisar_srt.py e cortes.py. Use sempre que o usuário pedir para monitorar canais, baixar vídeos, transcrever arquivos em temp/, analisar arquivos .srt para gerar cortes, atualizar TAREFAS_DE_CORTE ou renderizar vídeos finais.
---

# Pipeline Automatizado de Cortes (YouTube Shorts & Kwai)

Esta skill define a arquitetura, os contratos de dados e as regras operacionais do projeto `download_transcricao_cortes_yt`. **Não altere nomes de pastas, assinaturas de funções ou filtros FFmpeg já estabelecidos sem autorização explícita do usuário.**

## 1. Estrutura de Diretórios e Arquivos

* `temp/`: Diretório central de entrada e trabalho. Armazena vídeos baixados (`<YYYYMMDD>_<video_id>_<titulo>.mp4` ou `<job_id>_raw.mp4`) e suas transcrições correspondentes (`.srt`).
* `temp/tarefas_corte.json`: Manifesto JSON gerado pelo `analisar_srt.py` espelhando `TAREFAS_DE_CORTE` e incluindo o Kit de Publicação (`titulo_capa`, `texto_publicacao`, `hashtags`) para futura automação de postagem.
* `cortes_prontos/`: Diretório de saída dos cortes renderizados (`corte_<id>_<sufixo_formato>_<nome_limpo>.mp4`).
* `cortes_prontos/kit_publicacao.md`: Documento Markdown gerado pelo `analisar_srt.py` com o bloco `TAREFAS_DE_CORTE` e o Kit de Publicação completo (título de capa, texto em 4 partes e 5 hashtags iniciadas por `#PolíticaDireta`).
* `canais.json`: Lista de canais monitorados (`nome`, `url`, `ativo`, `max_recentes`, `duracao_min_segundos`, `duracao_max_segundos`).
* `historico_downloads.txt`: Arquivo de controle do `yt-dlp` (`download_archive`) para evitar downloads duplicados.
* `historico_srt_analisados.txt`: Arquivo de controle dos `.srt` já processados pelo `analisar_srt.py`.
* `cookies.txt`: Autenticação opcional na raiz do projeto.
* `.env`: Contém a chave `GEMINI_API_KEY` do Google AI Studio utilizada pelo `analisar_srt.py`.

## 2. Etapas do Fluxo Operacional

### Etapa 1: Coleta e Monitoramento (`download.py`)

* **Modo Monitoramento:** Executar `python download.py --monitor` (ou `--dry-run` para simulação). Lê `canais.json`, ignora transmissões ao vivo (`is_live`) e aplica os filtros de duração mínima/máxima.
* **Modo Manual:** Executar `python download.py` e fornecer a URL quando solicitado.
* **Requisito Técnico do `yt-dlp` (Node.js + EJS + `youtubetab`):** Ao utilizar `cookies.txt`, a função `_opcoes_base_ydl()` deve sempre manter `"js_runtimes": {"deno": {"path": None}, "node": {"path": None}}`, `"remote_components": ["ejs:github"]` e `"extractor_args": {"youtubetab": {"skip": ["authcheck"]}}`.
* **Troubleshooting de URLs de Canais (`[youtube:tab]` 404 / `Failed to resolve url`):** Alguns handles com caracteres especiais ou sufixos gerados pelo YouTube (ex.: `@MidiaNINJA-p1k/videos`) retornam HTTP 404 na extração de aba. Sempre que isso ocorrer, descubra o `channel_id` oficial com `.\venv\Scripts\yt-dlp.exe --print "%(channel_id)s" "ytsearch1:<Nome do Canal>"` e atualize a URL no `canais.json` para o formato canônico `https://www.youtube.com/channel/<CHANNEL_ID>/videos`.

### Etapa 2: Transcrição (`gerador_srt.py`)

* Executar `python gerador_srt.py [modelo]` (padrão: `base`; opções: `tiny`, `base`, `small`, `medium`, `large`, `large-v1`, `large-v2`, `large-v3`, `turbo`).
* O script varre automaticamente `temp/` (e a raiz) buscando vídeos sem `.srt` correspondente, ignorando arquivos iniciados por `corte_`.
* Idioma fixo: `pt` (`fp16=False`).

### Etapa 3: Análise do `.srt` e Geração de Tarefas (`analisar_srt.py` ou Agente Analista)

* **Modo Automatizado via Gemini API (`analisar_srt.py`):**
  * Requer `GEMINI_API_KEY` configurada no arquivo `.env`.
  * **Interativo:** `python analisar_srt.py` (lista os `.srt` de `temp/` identificando `[NOVO]` vs `[JÁ ANALISADO]`).
  * **Automático em lote:** `python analisar_srt.py --novos` (processa todos os `.srt` pendentes sem interação).
  * **Arquivo específico:** `python analisar_srt.py <nome_ou_id_do_video>` (opções adicionais: `--max-cortes 3`, `--modelo gemini-2.5-flash`).
  * **Invariante de Precisão:** O script aplica integralmente a skill [politica-direta-cortes](../politica-direta-cortes/SKILL.md) (3 cortes entre 45s e 100s distribuídos por perfil nos horários `11:30`, `17:30` e `20:30`), pré-processa o `.srt` anotando cada linha de timestamp com os segundos exatos em float (`[inicio_s --> fim_s]`) antes de enviar ao Gemini, sanitiza o campo `"nome"` (sem acentos/caracteres especiais), atualiza `TAREFAS_DE_CORTE` diretamente em `cortes.py`, salva `temp/tarefas_corte.json` e gera o Kit de Publicação completo em `cortes_prontos/kit_publicacao.md`.

Ao analisar um arquivo `.srt` (via script ou diretamente pelo agente, seguindo a skill [politica-direta-cortes](../politica-direta-cortes/SKILL.md)):

1. **Seleção de Trechos (Padrão Política Direta):** Selecionar exatamente **3 cortes principais** por arquivo (duração alvo entre **45s e 100s**), com gancho forte nos primeiros 3 segundos, fechamento conclusivo e correção de distorções do STT nos títulos/textos. Priorizar impacto no bolso do trabalhador, direitos sociais, soberania nacional, economia real, democracia e combate à desinformação.
2. **Distribuição na Grade Diária:**
   * **Ordem 1 (`"11:30"`):** Utilidade pública, economia, medidas práticas ou impacto direto no cotidiano.
   * **Ordem 2 (`"17:30"`):** Debate quente, análise política, cobrança ou contraponto estratégico.
   * **Ordem 3 (`"20:30"`):** Maior carga emocional, posicionamento firme, valorização institucional ou alto compartilhamento orgânico.
3. **Kit de Publicação Obrigatório:** Para cada corte, entregar título de capa com selo em caixa alta (`"RECADO DIRETO: '...'"`, `"UTILIDADE PÚBLICA: '...'"`), texto de publicação em 4 partes (contextualização, citação limpa, fecho analítico e CTA para comentários no YouTube e grupos no Kwai) e exatamente 5 hashtags iniciadas por `#PolíticaDireta` (salvo em `cortes_prontos/kit_publicacao.md`).
4. **Contrato da Lista `TAREFAS_DE_CORTE` em `cortes.py`:** Atualizar a variável `TAREFAS_DE_CORTE` mantendo estritamente o esquema abaixo:

```python
TAREFAS_DE_CORTE = [
    {
        "id": 1,
        "ordem": 1,
        "horario_sugerido": "11:30",
        "nome": "Nome Curto Sem Acentos Ou Caracteres Especiais",
        "video_path": "nome_exato_do_arquivo_em_temp.mp4",
        "title": "Título magnético com gancho para publicação",
        "start": 251.120,  # float em segundos exatos
        "end": 312.240     # float em segundos exatos
    }
]
```

*Nota:* O campo `video_path` deve conter o nome do arquivo dentro de `temp/` (a função `localizar_video()` resolve automaticamente em `temp/`).

### Etapa 4: Escolha do Modo de Corte e Renderização (`cortes.py`)

Ao preparar ou executar `cortes.py`, selecionar o modo adequado ao vídeo:

* **Modo `1` (`vertical_intermed`):** Vertical 9:16 (1080x1920) com respiro/barras (`fator_largura = 1.05`). Ideal para entrevistas/coletivas onde cortar as laterais perderia contexto.
* **Modo `2` (`original`):** Mantém proporção original, apenas recorta início e fim.
* **Modo `3` (`com_blur`):** Aplica escala 1080x1920 com `delogo` no centro (`x=280:y=520:w=520:h=60`) e rodapé (`x=300:y=1750:w=480:h=70`).
* **Modo `4` (`vertical_com_blur`):** Combina Modo `1` + filtros `delogo` do Modo `3`. Ideal para vídeos reaproveitados com marcas d'água centrais/inferiores.
* **Modo `5` (`vertical_tela_cheia`):** Crop 9:16 puro em tela cheia (1080x1920) sem barras pretas. Ideal para falas solo centralizadas.

## 3. Regras de Segurança e Governança

* Nunca apagar arquivos da pasta `temp/` nem limpar `historico_downloads.txt` ou `historico_srt_analisados.txt` sem solicitação explícita.
* **Idioma e Plataformas:** Escrever todos os títulos e textos estritamente em Português do Brasil (PT-BR) e direcionar entregas exclusivamente para **YouTube Shorts** e **Kwai** (nunca mencionar ou formatar para TikTok).
* Sempre validar se o `video_path` inserido em `TAREFAS_DE_CORTE` corresponde a um arquivo existente em `temp/` antes de executar `cortes.py`.
* Ao finalizar um lote de cortes, apresentar um resumo claro listando: vídeo de origem, modo FFmpeg aplicado, horários sugeridos e caminhos dos arquivos gerados em `cortes_prontos/`.
