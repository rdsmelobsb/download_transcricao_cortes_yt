# Pipeline Automatizado de Produção e Publicação de Cortes 🎬✂️🤖

Pipeline completo em Python para automação ponta a ponta de canais de cortes de vídeos para **YouTube Shorts** e **Kwai**: desde o monitoramento de canais do YouTube e download em alta resolução (`yt-dlp`), passando por transcrição de áudio (`OpenAI Whisper`), curadoria editorial automatizada via IA (`Gemini API`), renderização e enquadramento vertical com **FFmpeg**, até a **publicação/agendamento oficial no YouTube** e a **postagem automatizada no app Kwai via Android ADB**.

---

## 🚀 Funcionalidades Principais

1. **Coleta e Monitoramento Inteligente (`download.py` & `canais.json`):**
   * **Modo Monitoramento (`--monitor`):** Monitora periodicamente os canais configurados em `canais.json`, ignora transmissões ao vivo (`is_live`), filtra por duração mínima/máxima e baixa vídeos inéditos na melhor qualidade (`bestvideo+bestaudio`).
   * **Histórico Anti-Duplicidade:** Mantém `historico_downloads.txt` (`download_archive` do `yt-dlp`) para nunca baixar o mesmo vídeo duas vezes.
   * **Modo Manual:** Permite baixar qualquer vídeo avulso fornecendo a URL no terminal.
   * **Resolução JS e Autenticação:** Suporte a `cookies.txt` e resolução automática de desafios JavaScript (`n challenge`) via Node.js + EJS (`ejs:github`).

2. **Transcrição Automatizada em Lote (`gerador_srt.py`):**
   * Varre automaticamente a pasta `temp/` identificando vídeos `.mp4` pendentes de legenda.
   * Carrega o modelo do **OpenAI Whisper** uma única vez e gera os arquivos `.srt` em sequência (em português), otimizado para CPU ou aceleração por GPU NVIDIA (CUDA).

3. **Curadoria Editorial IA e Kit de Publicação (`analisar_srt.py`):**
   * Lê as transcrições `.srt` em `temp/`, calcula os timestamps exatos em segundos decimais (`float`) e envia para análise com `gemini-2.5-flash`.
   * **Critérios Editoriais (Padrão Política Direta):** Seleciona os **3 melhores cortes** por vídeo (45s a 100s, gancho forte nos primeiros 3 segundos, conclusão clara e foco em impacto social, econômico e político).
   * **Distribuição na Grade Diária:**
     * `11:30` — Utilidade pública, economia real e medidas práticas para o cidadão.
     * `17:30` — Debate quente, contraponto estratégico e cobrança institucional.
     * `20:30` — Carga emocional, posições firmes e alto engajamento comunitário.
   * **Prompt Desacoplado:** Carrega as instruções de `prompts/politica_direta.md` (ajustes editoriais são feitos no Markdown, sem alterar código).
   * **Manifesto Centralizado (`temp/tarefas_corte.json`):** Fonte única de verdade de todo o pipeline com IDs estáveis (`<video_id>_<n>`) e controle de ciclo de vida (`pendente` → `renderizado` → `publicado`).
   * **Kit de Publicação (`cortes_prontos/kit_publicacao.md`):** Gera Título de Capa com selos em caixa alta, Texto de Publicação em 4 partes (contextualização, citação limpa, fecho analítico e CTA) e 5 hashtags estratégicas.

4. **Recorte e Renderização Vertical (`cortes.py`):**
   * Lê o manifesto `temp/tarefas_corte.json` e renderiza automaticamente apenas os cortes com status `pendente`.
   * Oferece **5 modos de renderização via FFmpeg**:
     * `Modo 1` (`vertical_intermed`): 9:16 (1080x1920) com barras/respiro lateral.
     * `Modo 2` (`original`): Mantém a proporção de origem, recortando início e fim.
     * `Modo 3` (`com_blur`): Enquadramento 9:16 com filtros `delogo` para marcas d'água.
     * `Modo 4` (`vertical_com_blur`): Modo 1 combinado com filtros `delogo`.
     * `Modo 5` (`vertical_tela_cheia`): Crop vertical 9:16 puro (1080x1920 sem faixas pretas).

5. **Publicação e Agendamento no YouTube Shorts (`publicar_youtube.py`):**
   * Integração direta com a **YouTube Data API v3 oficial** via OAuth2 (`client_secrets.json` e `token.json`).
   * Agenda os vídeos automaticamente nos horários da grade (`11:30`, `17:30`, `20:30` - Horário de Brasília UTC-3), convertendo para UTC (`publishAt`).
   * Se o horário do dia já passou, o agendamento é programado automaticamente para o dia seguinte.
   * Respeita a cota diária gratuita do YouTube (1.600 unidades por upload; até 6 vídeos por dia).
   * Atualiza o manifesto com `status: "publicado"`, `youtube_video_id` e link direto `youtube_url`.

6. **Publicação Automatizada no Kwai via Android ADB (`publicar_kwai.py`):**
   * **Automação Nativa:** Como o Kwai não oferece portal web aberto de publicação (`kwai.com/creator` é 404), a publicação é feita diretamente no app Android oficial (`com.kwai.video`) via **ADB + `uiautomator2`**.
   * **Motor de Pontuação Inteligente (Score Kwai):** Classifica os cortes com maior potencial de retenção e viralização (duração de 45s a 75s, gatilhos no título de capa e CTAs), garantindo diversidade temática (evita postar o mesmo tema em sequência).
   * **Fluxo Determinístico via `ACTION_SEND`:** Transfere o `.mp4` para o celular via `adb push`, consulta o MediaStore do Android para obter a URI exata (`content://media/external/video/media/<id>`) e dispara um Intent direto para o Kwai. **Elimina completamente duplicatas ou seleções erradas da galeria**.
   * **Digitação Confiável com Acentos:** Copia a legenda para a área de transferência do Android (`set_clipboard`) e cola via `KEYCODE_PASTE` (evento 279), preservando 100% dos acentos em português.
   * **Remoção de Áudio Indesejado:** Detecta e fecha automaticamente músicas de fundo que o Kwai sugere na tela de edição, preservando o áudio original do corte.
   * **Modo `--preparar` e Lote Automático:** Permite preparar a postagem na tela do celular para revisão humana antes do clique em Publicar (com confirmação no terminal para marcar no manifesto) ou rodar em lote com intervalo anti-bot.

---

## 📋 Pré-requisitos do Sistema

1. **Python 3.10 ou superior**
2. **Node.js** instalado (necessário para o `yt-dlp` resolver desafios JS do player do YouTube).
3. **FFmpeg** instalado e adicionado ao `PATH`:
   * **Windows:** `winget install Gyan.FFmpeg`
   * **Linux (Ubuntu/Debian):** `sudo apt update && sudo apt install ffmpeg`
   * **macOS:** `brew install ffmpeg`
4. **Celular Android (para publicação no Kwai):**
   * Conectado ao computador via cabo USB.
   * **"Depuração USB"** ativada nas *Opções do Desenvolvedor*.
   * App oficial do Kwai instalado e com login ativo.

---

## 🛠️ Instalação e Configuração

1. **Clone o repositório:**
   ```bash
   git clone https://github.com/rdsmelobsb/download_transcricao_cortes_yt.git
   cd download_transcricao_cortes_yt
   ```

2. **Crie e ative o ambiente virtual (`venv`):**
   * **Windows (PowerShell):**
     ```powershell
     python -m venv venv
     .\venv\Scripts\Activate.ps1
     ```
   * **Linux / macOS:**
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

3. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   ```
   *(Opcional - GPU NVIDIA):* Para acelerar o Whisper com CUDA:
   ```bash
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
   ```

4. **Configure as Credenciais de API:**

   * **Gemini API (Curadoria IA):** Crie um arquivo `.env` na raiz do projeto:
     ```env
     GEMINI_API_KEY=AIzaSySuaChaveDoGoogleAIStudio...
     ```

   * **YouTube Data API v3 (Publicação no YouTube):**
     1. Acesse o [Google Cloud Console](https://console.cloud.google.com/), crie um projeto e ative a **YouTube Data API v3**.
     2. Crie uma credencial do tipo **OAuth 2.0 Client ID (Desktop App)**.
     3. Baixe o JSON e salve-o na raiz do projeto com o nome exato **`client_secrets.json`**.
     4. Na primeira execução do `publicar_youtube.py`, uma janela do navegador abrirá para autorizar o canal. O token salvo ficará em `token.json` (ambos protegidos no `.gitignore`).

---

## 📖 Fluxo Operacional Passo a Passo

### Etapa 1: Coleta e Monitoramento (`download.py`)

* **Monitoramento Automático de Canais:**
  Edite `canais.json` com os canais desejados:
  ```json
  [
    {
      "nome": "TV BRASIL",
      "url": "https://www.youtube.com/@tvbrasil/videos",
      "ativo": true,
      "max_recentes": 3,
      "duracao_min_segundos": 180,
      "duracao_max_segundos": null
    }
  ]
  ```
  Execute o monitoramento:
  ```powershell
  python download.py --monitor
  ```
  *(Dica: use `python download.py --monitor --dry-run` para apenas simular sem baixar).*

* **Modo Manual:**
  ```powershell
  python download.py
  ```
  Cole a URL do vídeo desejado. O vídeo é salvo em `temp/`.

---

### Etapa 2: Transcrição em Legendas SRT (`gerador_srt.py`)

Transcreve os vídeos da pasta `temp/` que ainda não possuem arquivo `.srt`:

```powershell
python gerador_srt.py          # utiliza o modelo 'base' (padrão)
python gerador_srt.py small    # modelos: tiny, base, small, medium, large, turbo
```

---

### Etapa 3: Curadoria IA e Kit de Publicação (`analisar_srt.py`)

Analisa as transcrições via Gemini API, atualiza o manifesto `temp/tarefas_corte.json` e gera `cortes_prontos/kit_publicacao.md`:

```powershell
python analisar_srt.py --novos          # processa automaticamente todos os .srt inéditos
python analisar_srt.py                  # modo interativo para escolher o vídeo
python analisar_srt.py <video_id>       # analisa um vídeo específico (ex: python analisar_srt.py JHIJDjlMYNQ)
```

---

### Etapa 4: Renderização dos Cortes com FFmpeg (`cortes.py`)

Lê o manifesto e renderiza os cortes com status `pendente`:

```powershell
python cortes.py --modo 5                       # renderiza em tela cheia (9:16) sem interrupções
python cortes.py                                # pergunta o modo (1 a 5)
python cortes.py --modo 5 --id JHIJDjlMYNQ_1   # renderiza apenas um corte específico
python cortes.py --modo 5 --todos              # re-renderiza todos os cortes não publicados
```

Os arquivos prontos são salvos na pasta `cortes_prontos/`.

---

### Etapa 5: Publicação e Agendamento Anti-Canibalização no YouTube (`publicar_youtube.py` + `agendador.py`)

Distribui os cortes renderizados em uma fila de slots livres ao longo dos dias (evitando que múltiplos Shorts caiam no mesmo horário), intercalando vídeos de origens diferentes no mesmo dia e respeitando um espaçamento mínimo de 2h entre publicações:

```powershell
python publicar_youtube.py --simular                      # visualiza a grade antes de subir qualquer vídeo
python publicar_youtube.py --agenda                       # lista todos os vídeos futuros já programados
python publicar_youtube.py --todos --por-dia 3 --limite 6 # sobe até 6 cortes (cota diária), distribuindo 3/dia sem colisões
python publicar_youtube.py --todos --por-dia 5            # modo alto volume: 5 slots/dia (09:00, 12:00, 15:30, 18:30, 21:30)
python publicar_youtube.py --slots "09:00,13:00,18:00"    # define horários customizados em BRT
python publicar_youtube.py                                # modo interativo (escolhe quais postar)
python publicar_youtube.py --imediato                     # publica imediatamente como público (sem agendamento)
python publicar_youtube.py --privado                      # sobe como privado para revisão manual no YouTube Studio
python publicar_youtube.py --amanha                       # inicia o preenchimento da grade a partir de amanhã
```

---

### Etapa 6: Publicação no Kwai via Android ADB (`publicar_kwai.py`)

Seleciona os melhores cortes pelo **Score Kwai**, envia para o celular Android via USB e publica no app do Kwai:

```powershell
python publicar_kwai.py --top 1 --preparar   # envia, preenche a legenda e pausa para você revisar
python publicar_kwai.py --top 3              # publica os TOP 3 cortes automaticamente com intervalo anti-bot
python publicar_kwai.py --inspecionar        # inspeciona botões e IDs da tela atual do celular (calibração)
```

> **Nota:** No modo `--preparar`, após revisar na tela do celular e tocar em Publicar, confirme `[S]` no terminal para que o corte seja marcado no manifesto e o arquivo temporário seja limpo do celular.

---

### Etapa 7: Auditoria de Desempenho e Retroalimentação IA (`avaliar_metricas.py`)

Audita em paralelo todos os vídeos postados no YouTube Shorts, coleta visualizações, curtidas e comentários, salva o histórico no manifesto e retroalimenta o Gemini com os padrões vencedores:

```powershell
python avaliar_metricas.py            # executa a auditoria em paralelo de todos os cortes
python avaliar_metricas.py --workers 8  # define 8 threads paralelas
```

**O que esta etapa faz automaticamente:**
1. Atualiza `temp/tarefas_corte.json` com o bloco `metricas_yt` de cada vídeo.
2. Gera o painel executivo em Markdown em `cortes_prontos/relatorio_desempenho_yt.md`.
3. Clusteriza os fatores de sucesso (duração mais assistida, selos de capa com maior conversão e horários de pico) e exporta para `prompts/padroes_vencedores.json`.
4. O `analisar_srt.py` consome essa inteligência automaticamente na próxima curadoria, instruindo o Gemini a priorizar falas e ganchos com as características que mais funcionaram com o seu público real.

---

## ⏰ Agendamento no Windows (Task Scheduler)

Para rodar o pipeline no **Agendador de Tarefas do Windows** (`taskschd.msc`):

* **Programa/script:**
  `C:\caminho\para\download_transcricao_cortes_yt\venv\Scripts\python.exe`
* **Argumentos:**
  `download.py --monitor` *(ou qualquer etapa desejada)*
* **Iniciar em:**
  `C:\caminho\para\download_transcricao_cortes_yt`

---

## 📁 Estrutura do Projeto

```text
├── .agent/skills/                  # Diretrizes e arquitetura operacional das skills de IA
├── prompts/
│   ├── politica_direta.md          # Diretrizes editoriais e contrato JSON da curadoria IA
│   └── padroes_vencedores.json     # Inteligência e diretrizes de retroalimentação extraídas das métricas
├── cortes_prontos/                 # Vídeos verticais renderizados, kit_publicacao.md e relatórios (ignorado no Git)
│   └── relatorio_desempenho_yt.md  # Dashboard executivo de métricas e ranking do YouTube
├── temp/                           # Vídeos brutos (.mp4), legendas (.srt) e manifesto de tarefas (ignorado no Git)
│   └── tarefas_corte.json          # Fonte única de verdade de todo o pipeline
├── analisar_srt.py                 # Curadoria de cortes com retroalimentação contínua via Gemini API
├── avaliar_metricas.py             # Auditoria de métricas reais do YouTube e motor de feedback loop
├── canais.json                     # Lista de canais do YouTube monitorados e filtros de duração
├── cortes.py                       # Renderização automatizada em 5 modos FFmpeg
├── download.py                     # Download manual e monitoramento em lote via yt-dlp
├── gerador_srt.py                  # Transcrição de áudio em lote via OpenAI Whisper
├── manifesto.py                    # Gerenciador atômico do ciclo de vida dos cortes
├── publicar_youtube.py             # Upload e agendamento nativo via YouTube Data API v3
├── publicar_kwai.py                # Publicação no Kwai via Android ADB (uiautomator2 + ACTION_SEND)
├── requirements.txt                # Dependências Python do projeto
├── .env                            # Chave GEMINI_API_KEY (ignorado no Git)
├── client_secrets.json             # Credenciais OAuth2 do Google Cloud (ignorado no Git)
├── token.json                      # Token de sessão da YouTube API (ignorado no Git)
├── cookies.txt                     # Cookies de sessão para o yt-dlp (ignorado no Git)
├── historico_downloads.txt         # Arquivo de controle do yt-dlp anti-duplicatas (ignorado no Git)
├── historico_srt_analisados.txt    # Controle de transcrições já processadas (ignorado no Git)
├── .gitignore                      # Regras de exclusão do Git
└── README.md                       # Documentação completa do projeto
```

---

## 🔒 Segurança e Governança

* **Proteção de Credenciais:** Arquivos de chaves (`.env`, `client_secrets.json`, `token.json`, `cookies.txt`) são permanentemente ignorados no `.gitignore` e nunca devem ser versionados.
* **Integridade de Mídias:** As pastas `temp/` e `cortes_prontos/` contêm mídias pesadas de trabalho e nunca são sincronizadas no repositório.
* **Direitos Autorais:** Certifique-se sempre de que os canais monitorados autorizam a reutilização ou disponibilizam conteúdo sob domínio público / Creative Commons.
