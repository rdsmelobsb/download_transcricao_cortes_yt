# Pipeline Automatizado: Download, Transcrição, Curadoria IA e Cortes de Vídeos 🎬✂️🤖

Pipeline completo em Python para automatizar a produção de cortes de vídeos para **YouTube Shorts** e **Kwai**: monitoramento automático de canais do YouTube, download em alta resolução (`yt-dlp`), transcrição de áudio para legendas `.srt` (`OpenAI Whisper`), curadoria automatizada de cortes e textos de publicação via **Gemini API**, e renderização com **FFmpeg**.

---

## 🚀 Funcionalidades

1. **Coleta e Monitoramento de Canais (`download.py` & `canais.json`):**
   * **Modo Monitoramento (`--monitor`):** Verifica rotineiramente uma lista de canais configurados em `canais.json`, ignora transmissões ao vivo em andamento (`is_live`), filtra vídeos por duração mínima/máxima e baixa apenas vídeos inéditos na melhor qualidade (`bestvideo+bestaudio`).
   * **Histórico Anti-Duplicidade:** Registra cada vídeo baixado em `historico_downloads.txt` (`download_archive` do `yt-dlp`) para nunca baixar o mesmo vídeo duas vezes.
   * **Modo Manual:** Permite colar o link de um vídeo avulso diretamente no terminal.
   * **Suporte a Autenticação e Desafio JS:** Compatível com `cookies.txt` e resolução automática de desafios JavaScript (`n challenge`) via Node.js + EJS.

2. **Transcrição Automatizada em Lote (`gerador_srt.py`):**
   * Vasculha automaticamente a pasta `temp/` (e a raiz) em busca de vídeos que ainda não possuem arquivo `.srt` correspondente.
   * Carrega o modelo do **OpenAI Whisper** uma única vez e transcreve todos os vídeos pendentes em sequência (em português), salvando o `.srt` ao lado de cada vídeo.

3. **Curadoria de Cortes e Kit de Publicação via Gemini API (`analisar_srt.py`):**
   * Lê as transcrições `.srt` em `temp/`, pré-anota cada timestamp com o valor exato em segundos decimais (`float`) para evitar erros de cálculo e envia ao modelo `gemini-2.5-flash`.
   * Seleciona os **3 melhores cortes** por vídeo (45s a 100s, com gancho forte nos primeiros 3 segundos) distribuídos nos horários estratégicos da grade diária (`11:30`, `17:30` e `20:30`).
   * Lê o prompt editorial de `prompts/politica_direta.md` (edite esse arquivo para ajustar a curadoria, sem mexer no código).
   * Registra os cortes no **manifesto acumulativo** `temp/tarefas_corte.json`, com **ids estáveis** por vídeo (ex.: `JHIJDjlMYNQ_1`) e `status` (`pendente` → `renderizado` → `publicado`). Reanalisar um vídeo substitui só os cortes dele.
   * Gera o **Kit de Publicação** completo em `cortes_prontos/kit_publicacao.md` (com Título de Capa, Texto de Publicação em 4 partes e 5 Hashtags).

4. **Recorte e Enquadramento Vertical (`cortes.py`):**
   * Localiza automaticamente os vídeos de origem dentro da pasta `temp/` (pelo nome completo ou ID do vídeo).
   * Oferece **5 modos de renderização via FFmpeg**, incluindo formatos verticais `9:16` (`1080x1920` com respiro ou tela cheia) e filtros de remoção de marca d'água (`delogo`).

---

## 📋 Pré-requisitos

1. **Python 3.10 ou superior**
2. **Node.js** instalado no sistema (utilizado pelo `yt-dlp` para resolver desafios JavaScript do player do YouTube ao usar `cookies.txt`).
3. **FFmpeg** instalado no sistema operacional e adicionado ao `PATH`:
   * **Windows:**
     ```powershell
     winget install Gyan.FFmpeg
     ```
   * **Linux (Ubuntu/Debian):**
     ```bash
     sudo apt update && sudo apt install ffmpeg
     ```
   * **macOS:**
     ```bash
     brew install ffmpeg
     ```

---

## 🛠️ Instalação e Configuração

1. **Clone o repositório e acesse a pasta do projeto:**
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
   pip install yt-dlp openai-whisper ffmpeg-python google-generativeai python-dotenv
   ```
   *(Opcional)* Para acelerar a transcrição Whisper com GPU NVIDIA (CUDA):
   ```bash
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
   ```

4. **Configure a chave da API do Gemini (`.env`):**
   Crie um arquivo `.env` na raiz do projeto com a sua chave do [Google AI Studio](https://aistudio.google.com/):
   ```env
   GEMINI_API_KEY=AIzaSySuaChaveAqui...
   ```

---

## 📖 Fluxo de Uso Passo a Passo

### Etapa 1: Download / Monitoramento de Vídeos (`download.py`)

#### A) Modo Monitoramento Automático (`canais.json`)
Edite o arquivo `canais.json` na raiz do projeto com os canais que deseja monitorar:

```json
[
  {
    "nome": "Canal Exemplo",
    "url": "https://www.youtube.com/@CanalExemplo/videos",
    "ativo": true,
    "max_recentes": 3,
    "duracao_min_segundos": 180,
    "duracao_max_segundos": null
  }
]
```

> **Direitos autorais:** monitore apenas canais cujo conteúdo você tem licença/autorização para reutilizar (ex.: material de domínio público ou liberado pelo autor). Reupar conteúdo de terceiros pode violar direitos autorais e as políticas de conteúdo reutilizado do YouTube.

> **Dica:** Caso algum handle `@canal/videos` retorne erro `404` no YouTube, utilize a URL canônica com o ID do canal (`https://www.youtube.com/channel/<CHANNEL_ID>/videos`).

* **Simular verificação (sem baixar arquivos):**
  ```powershell
  python download.py --monitor --dry-run
  ```
* **Baixar vídeos novos dos canais ativos:**
  ```powershell
  python download.py --monitor
  ```

#### B) Modo Manual (Vídeo Avulso)
```powershell
python download.py
```
Cole a URL do vídeo quando solicitado. Os vídeos baixados ficam salvos na pasta `temp/`.

---

### Etapa 2: Geração Automática de Legendas (`gerador_srt.py`)

Transcreve automaticamente todos os vídeos da pasta `temp/` que ainda não possuem arquivo `.srt`:

* **Modo automático (modelo padrão `base`):**
  ```powershell
  python gerador_srt.py
  ```
* **Modo automático escolhendo o modelo Whisper (`tiny`, `base`, `small`, `medium`, `large`, `turbo`):**
  ```powershell
  python gerador_srt.py small
  ```
* **Transcrever um vídeo específico:**
  ```powershell
  python gerador_srt.py nome_do_video.mp4 small
  ```

---

### Etapa 3: Análise do `.srt` e Curadoria de Cortes com IA (`analisar_srt.py`)

Analisa as transcrições `.srt` em `temp/` via Gemini API, registra os cortes no manifesto `temp/tarefas_corte.json` e gera o Kit de Publicação em `cortes_prontos/kit_publicacao.md`:

* **Modo interativo** (lista os `.srt` de `temp/`, indicando quais são `[NOVO]` ou `[JÁ ANALISADO]`):
  ```powershell
  python analisar_srt.py
  ```
* **Modo 100% automático em lote** (processa todos os `.srt` inéditos sem confirmação manual):
  ```powershell
  python analisar_srt.py --novos
  ```
* **Analisar um vídeo específico (por nome ou ID do YouTube):**
  ```powershell
  python analisar_srt.py 5SJYESoWnvI
  ```

**Saídas geradas automaticamente por esta etapa:**
1. Manifesto acumulativo em `temp/tarefas_corte.json` (fonte única de verdade lida pelo `cortes.py`).
2. Kit de Publicação em `cortes_prontos/kit_publicacao.md` com todos os cortes ainda não publicados.
3. Para cada corte:
   * Horário estratégico sugerido (`11:30`, `17:30`, `20:30`)
   * Título otimizado (SEO/retenção)
   * Título de capa / tela com selo de impacto
   * Texto da publicação estruturado em 4 blocos (contextualização, citação, fecho analítico e CTA)
   * 5 hashtags estratégicas

---

### Etapa 4: Renderização dos Cortes (`cortes.py`)

O `cortes.py` lê o manifesto `temp/tarefas_corte.json` e renderiza **apenas os cortes `pendente`**, marcando cada um como `renderizado` ao concluir:

```powershell
python cortes.py                 # pergunta o modo (1 a 5)
python cortes.py --modo 5        # sem perguntas (ideal para agendar)
python cortes.py --modo 5 --id JHIJDjlMYNQ_1   # apenas um corte
python cortes.py --modo 5 --todos              # re-renderiza todos os não publicados
```

Modos de corte:
* `[1]` **Vertical intermediário (9:16 - 1080x1920 com respiro/faixas):** Ideal para entrevistas e planos abertos onde cortar as laterais perderia contexto.
* `[2]` **Formato original:** Mantém a proporção original do vídeo, recortando apenas início e fim.
* `[3]` **Remover/Borrar marca d'água (`delogo`):** Aplica filtro de desfoque em marcas d'água centrais/rodapé.
* `[4]` **Vertical intermediário + Borrar marca d'água:** Combina o enquadramento do modo `[1]` com os filtros `delogo` do modo `[3]`.
* `[5]` **Vertical TELA CHEIA (9:16 puro - 1080x1920 sem faixas pretas):** Preenche toda a tela vertical. Ideal para enquadramentos centralizados.

Os vídeos finais são salvos em `cortes_prontos/`.

---

## ⏰ Agendamento no Windows (Task Scheduler)

Para executar o monitoramento de canais automaticamente em horários fixos ou a cada *X* horas no **Agendador de Tarefas do Windows** (`taskschd.msc`):

* **Programa/script:**
  `C:\caminho\para\download_transcricao_cortes_yt\venv\Scripts\python.exe`
* **Adicione argumentos:**
  `download.py --monitor`
* **Iniciar em:**
  `C:\caminho\para\download_transcricao_cortes_yt`

---

## 📁 Estrutura de Arquivos

```text
├── .agent/skills/                  # Skills e diretrizes operacionais do agente IA
├── prompts/
│   └── politica_direta.md          # Prompt editorial lido pelo analisar_srt.py
├── cortes_prontos/                 # Vídeos finais renderizados e kit_publicacao.md (ignorado no Git)
├── temp/                           # Vídeos brutos (.mp4), legendas (.srt) e tarefas_corte.json (ignorado no Git)
├── analisar_srt.py                 # Curadoria de cortes e kit de publicação via Gemini API
├── manifesto.py                    # Leitura/escrita do manifesto, ids estáveis e status dos cortes
├── canais.json                     # Configuração de canais monitorados e filtros de duração
├── cortes.py                       # Renderiza os cortes pendentes do manifesto via FFmpeg
├── download.py                     # Download manual e monitoramento automático via yt-dlp
├── gerador_srt.py                  # Transcrição automática de áudio para SRT via Whisper
├── .env                            # Chave GEMINI_API_KEY (ignorado no Git)
├── cookies.txt                     # Cookies de autenticação do YouTube (ignorado no Git)
├── historico_downloads.txt         # Controle de vídeos já baixados (ignorado no Git)
├── historico_srt_analisados.txt    # Controle de transcrições já analisadas (ignorado no Git)
├── .gitignore                      # Regras de exclusão do Git
└── README.md                       # Documentação do projeto
```

---

## 🔒 Segurança e Versionamento

Arquivos sensíveis e temporários como `.env`, `cookies.txt`, arquivos de histórico (`*.txt`), ambiente virtual (`venv/`), pasta de trabalho (`temp/`) e vídeos renderizados (`cortes_prontos/`) estão configurados no `.gitignore` para não serem enviados ao repositório público.
