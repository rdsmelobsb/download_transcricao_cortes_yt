---
name: pipeline-cortes-youtube-kwai
description: Orquestra o pipeline completo de produção e postagem de cortes (YouTube Shorts e Kwai) cobrindo monitoramento (download.py), transcrição (gerador_srt.py), curadoria IA (analisar_srt.py), renderização (cortes.py), publicação no YouTube (publicar_youtube.py) e publicação no Kwai via Android ADB (publicar_kwai.py). Use sempre que o usuário pedir para monitorar canais, transcrever, analisar, renderizar ou publicar cortes.
---

# Pipeline Automatizado de Cortes (YouTube Shorts & Kwai)

Esta skill define a arquitetura, os contratos de dados e as regras operacionais do projeto `download_transcricao_cortes_yt`. **Não altere nomes de pastas, assinaturas de funções ou filtros FFmpeg já estabelecidos sem autorização explícita do usuário.**

## 1. Estrutura de Diretórios e Arquivos

* `temp/`: Diretório central de entrada e trabalho. Armazena vídeos baixados (`<YYYYMMDD>_<video_id>_<titulo>.mp4` ou `<job_id>_raw.mp4`) e suas transcrições correspondentes (`.srt`).
* `temp/tarefas_corte.json`: **Manifesto acumulativo e fonte única de verdade** dos cortes. Gerado pelo `analisar_srt.py`, atualizado pelo `cortes.py` e finalizado pelo `publicar_youtube.py` / `publicar_kwai.py`. Cada item tem `id` estável (`<video_id>_<n>`), `ordem`, `horario_sugerido`, `nome`, `video_path`, `title`, `start`, `end`, `titulo_capa`, `texto_publicacao`, `hashtags`, `status` (`pendente` → `renderizado` → `publicado`), `criado_em`, `arquivo_final`, `modo`, `youtube_video_id`, `youtube_url`, `publicado_kwai` e `kwai_publicado_em`.
* `publicar_youtube.py`: Script de upload e agendamento nativo no YouTube via YouTube Data API v3 oficial (OAuth2).
* `publicar_kwai.py`: Script de publicação no app Android do Kwai (`com.kwai.video`) via ADB + `uiautomator2` com ranking inteligente (**Score Kwai**) e envio determinístico via `ACTION_SEND`.
* `client_secrets.json` e `token.json`: Credenciais OAuth da Google API (protegidas no `.gitignore`).
* `prompts/politica_direta.md`: Prompt editorial lido pelo `analisar_srt.py` (placeholders `{{VIDEO_FILENAME}}`, `{{MAX_CORTES}}`, `{{TRANSCRICAO_SRT}}`). Ajustes de curadoria devem ser feitos neste arquivo, nunca no código.
* `cortes_prontos/`: Diretório de saída dos cortes renderizados (`corte_<id>_<sufixo_formato>_<nome_limpo>.mp4`).
* `cortes_prontos/kit_publicacao.md`: Documento Markdown regenerado pelo `analisar_srt.py` com o Kit de Publicação de todos os cortes ainda não `publicado` (título de capa, texto em 4 partes e 5 hashtags iniciadas por `#PolíticaDireta`).
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
  * **Invariante de Precisão:** O prompt editorial vem de `prompts/politica_direta.md` (3 cortes entre 45s e 100s distribuídos por perfil nos horários `11:30`, `17:30` e `20:30`; ver skill [politica-direta-cortes](../politica-direta-cortes/SKILL.md)). O script pré-processa o `.srt` anotando cada linha de timestamp com os segundos exatos em float (`[inicio_s --> fim_s]`), sanitiza o campo `"nome"`, **atualiza o manifesto `temp/tarefas_corte.json` (sem tocar em `cortes.py`)** e regenera o Kit de Publicação em `cortes_prontos/kit_publicacao.md`.
  * **Reanálise de um vídeo:** substitui apenas os cortes daquele vídeo (cortes `publicado` são preservados; cortes já `renderizado` substituídos geram aviso). Cortes de outros vídeos nunca são alterados.

Ao analisar um arquivo `.srt` (via script ou diretamente pelo agente, seguindo a skill [politica-direta-cortes](../politica-direta-cortes/SKILL.md)):

1. **Seleção de Trechos (Padrão Política Direta):** Selecionar exatamente **3 cortes principais** por arquivo (duração alvo entre **45s e 100s**), com gancho forte nos primeiros 3 segundos, fechamento conclusivo e correção de distorções do STT nos títulos/textos. Priorizar impacto no bolso do trabalhador, direitos sociais, soberania nacional, economia real, democracia e combate à desinformação.
2. **Distribuição na Grade Diária:**
   * **Ordem 1 (`"11:30"`):** Utilidade pública, economia, medidas práticas ou impacto direto no cotidiano.
   * **Ordem 2 (`"17:30"`):** Debate quente, análise política, cobrança ou contraponto estratégico.
   * **Ordem 3 (`"20:30"`):** Maior carga emocional, posicionamento firme, valorização institucional ou alto compartilhamento orgânico.
3. **Kit de Publicação Obrigatório:** Para cada corte, entregar título de capa com selo em caixa alta (`"RECADO DIRETO: '...'"`, `"UTILIDADE PÚBLICA: '...'"`), texto de publicação em 4 partes (contextualização, citação limpa, fecho analítico e CTA para comentários no YouTube e grupos no Kwai) e exatamente 5 hashtags iniciadas por `#PolíticaDireta` (salvo em `cortes_prontos/kit_publicacao.md`).
4. **Contrato do Manifesto (`temp/tarefas_corte.json`):** Nunca editar código Python para registrar cortes. Cada item segue o esquema abaixo (ids estáveis `<video_id>_<n>`; `status`: `pendente` → `renderizado` → `publicado`):

```json
{
  "id": "JHIJDjlMYNQ_1",
  "ordem": 1,
  "horario_sugerido": "11:30",
  "nome": "Nome Curto Sem Acentos Ou Caracteres Especiais",
  "video_path": "nome_exato_do_arquivo_em_temp.mp4",
  "title": "Título magnético com gancho para publicação",
  "start": 251.120,
  "end": 312.240,
  "titulo_capa": "...", "texto_publicacao": "...", "hashtags": "#PolíticaDireta ...",
  "status": "pendente", "criado_em": "...", "arquivo_final": null, "modo": null
}
```

*Nota:* O campo `video_path` deve conter o nome do arquivo dentro de `temp/` (a função `localizar_video()` resolve automaticamente em `temp/`).

### Etapa 4: Escolha do Modo de Corte e Renderização (`cortes.py`)

* O `cortes.py` lê `temp/tarefas_corte.json` e renderiza por padrão **apenas os cortes `pendente`**, marcando-os como `renderizado` (com `arquivo_final` e `modo`) ao concluir cada um.
* **Interativo:** `python cortes.py` (pergunta o modo 1 a 5).
* **Automático (agendável):** `python cortes.py --modo 5`.
* **Corte específico:** `python cortes.py --modo 5 --id JHIJDjlMYNQ_1` (repetível). **Re-renderizar tudo não publicado:** `--todos`.

Selecionar o modo adequado ao vídeo:

* **Modo `1` (`vertical_intermed`):** Vertical 9:16 (1080x1920) com respiro/barras (`fator_largura = 1.05`). Ideal para entrevistas/coletivas onde cortar as laterais perderia contexto.
* **Modo `2` (`original`):** Mantém proporção original, apenas recorta início e fim.
* **Modo `3` (`com_blur`):** Aplica escala 1080x1920 com `delogo` no centro (`x=280:y=520:w=520:h=60`) e rodapé (`x=300:y=1750:w=480:h=70`).
* **Modo `4` (`vertical_com_blur`):** Combina Modo `1` + filtros `delogo` do Modo `3`. Ideal para vídeos reaproveitados com marcas d'água centrais/inferiores.
* **Modo `5` (`vertical_tela_cheia`):** Crop 9:16 puro em tela cheia (1080x1920) sem barras pretas. Ideal para falas solo centralizadas.

### Etapa 5: Publicação e Agendamento Automático no YouTube (`publicar_youtube.py`)

* **Autenticação:** Lê `client_secrets.json` na primeira execução e salva a sessão em `token.json`.
* **Interativo:** `python publicar_youtube.py` (lista os vídeos `renderizado`, permitindo escolher quais postar ou apertar ENTER para postar todos).
* **Automático em lote (agendado):** `python publicar_youtube.py --todos` (faz upload de todos os cortes renderizados e agenda nos horários correspondentes da grade diária: `11:30`, `17:30`, `20:30`).
* **Opções adicionais:** `--privado` (sobe sem data de agendamento), `--imediato` (torna público na hora) e `--amanha` (força a grade para o dia seguinte).
* **Atualização de Estado:** Após o upload com sucesso, atualiza o corte no manifesto para `status: "publicado"`, preenche `youtube_video_id` e link `youtube_url`.
* **Cota da API do YouTube:** Cada upload consome 1.600 unidades da cota diária (10.000 unidades). Limite máximo gratuito: **6 vídeos por dia**.
* **Regra de Agendamento:** Horários sugeridos (`11:30`, `17:30`, `20:30` - Brasília UTC-3) são convertidos para UTC (+3h) para o campo `publishAt`. Se o horário de hoje já passou, o agendamento vai automaticamente para o dia seguinte.

### Etapa 6: Publicação Automatizada no Kwai via Android (`publicar_kwai.py`)

* **Por que Android ADB e não Web:** O Kwai não oferece portal web aberto de upload (`kwai.com/creator` retorna 404). O script usa `uiautomator2` + `adbutils` (que já inclui `adb.exe` embutido no `venv`).
* **Seleção Inteligente (Score Kwai):** Pontua cortes pendentes (`publicado_kwai != true`) priorizando duração entre 45s e 75s, gatilhos de capa e diversidade temática (evita múltiplos cortes do mesmo vídeo de origem no mesmo lote).
* **Fluxo Determinístico (`ACTION_SEND` + MediaStore):**
  1. Envia o `.mp4` via `adb push` para `/sdcard/Movies/PoliticaDireta/` e consulta o MediaStore (`content://media/external/video/media/<_id>`). **Nunca selecionar vídeos pela galeria do Kwai**, pois o app salva cópias exportadas com timestamp mais recente causando duplicatas.
  2. Dispara `am start -a android.intent.action.SEND -t video/mp4 --eu android.intent.extra.STREAM <content_uri> -n com.kwai.video/com.kscorp.oversea.platform.router.ui.UriRouterActivity -f 0x1`.
  3. **Resource-IDs nativos calibrados (`com.kwai.video`):** `v_cut_next` (Próximo no corte) → `music_close_view` (remove música automática) → `edit_next_button` (Próximo na edição) → `editor` (cola legenda via `set_clipboard` + `input keyevent 279` / `KEYCODE_PASTE` para manter acentos PT-BR, depois `back`) → `post` (Publicar).
  4. Atualiza `publicado_kwai: true` e `kwai_publicado_em` no manifesto e remove o `.mp4` temporário da pasta `/sdcard/Movies/PoliticaDireta/`.
* **Comandos:**
  * `python publicar_kwai.py --top 1 --preparar` (envia e cola legenda, pausando antes de publicar)
  * `python publicar_kwai.py --top 3` (publicação automática em lote com intervalo anti-bot)
  * `python publicar_kwai.py --inspecionar` (lista textos e resource-ids da tela atual do celular)

## 3. Regras de Segurança e Governança

* Nunca apagar arquivos da pasta `temp/` nem limpar `historico_downloads.txt` ou `historico_srt_analisados.txt` sem solicitação explícita.
* **Scripts em execução:** se o usuário avisar que está executando um script, limitar-se a leitura e diagnóstico; não editar arquivos nem rodar comandos que interfiram até ele liberar.
* **Fontes de conteúdo:** ao adicionar ou ativar canais em `canais.json`, lembrar o usuário de confirmar que tem licença/autorização para reutilizar o conteúdo (direitos autorais e política de conteúdo reutilizado do YouTube).
* **Git:** o agente pode preparar `git add`/`git commit`, mas **nunca deve executar `git push`** (o Git Credential Manager aguarda login interativo e trava em background); entregar o comando `git push origin main` para o usuário rodar no próprio terminal. Ao criar `requirements.txt`, acrescentar `!requirements.txt` ao `.gitignore` (a regra `*.txt` o ignoraria).
* **Execução fora do sandbox:** comandos que gravam em `.git` (`git add`, `git commit`), acesso à rede (`yt-dlp`, Gemini API, YouTube API) e comunicação ADB (`127.0.0.1:5037` / USB) precisam de `BypassSandbox`.
* **Segurança de Credenciais:** `client_secrets.json` e `token.json` nunca devem ser versionados no Git (sempre protegidos no `.gitignore`).
* **Idioma e Plataformas:** Escrever todos os títulos e textos estritamente em Português do Brasil (PT-BR) e direcionar entregas exclusivamente para **YouTube Shorts** e **Kwai** (nunca mencionar ou formatar para TikTok).
* Sempre validar se o `video_path` de cada item do manifesto `temp/tarefas_corte.json` corresponde a um arquivo existente em `temp/` antes de executar `cortes.py`. Nunca editar `cortes.py` para registrar cortes.
* Ao finalizar um lote de cortes, apresentar um resumo claro listando: vídeo de origem, modo FFmpeg aplicado, horários sugeridos e caminhos dos arquivos gerados em `cortes_prontos/`.
