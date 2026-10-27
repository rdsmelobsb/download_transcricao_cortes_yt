# Download, Transcrição e Cortes de Vídeos do YouTube 🎬✂️

Pipeline em Python para automatizar o fluxo completo de produção de cortes e conteúdo em vídeo: download do YouTube em alta resolução, transcrição de áudio para legendas `.srt` com o OpenAI Whisper e extração automatizada de cortes (proporção original ou vertical 9:16 para Shorts/Reels/TikTok) utilizando FFmpeg.

---

## 🚀 Funcionalidades

* **Download Automatizado (`download.py`):** Baixa vídeos do YouTube combinando automaticamente as melhores faixas de vídeo e áudio via `yt-dlp`. Suporta autenticação opcional via arquivo `cookies.txt` para vídeos com restrição de idade ou validação de bot.
* **Geração de Legendas SRT (`gerador_srt.py`):** Transcreve o áudio de arquivos de vídeo locais gerando arquivos `.srt` compatíveis com qualquer player ou editor, utilizando os modelos Whisper da OpenAI.
* **Corte e Enquadramento (`cortes.py`):** Recorta trechos exatos baseados em timestamps com opção de exportação em proporção original ou enquadramento vertical 9:16 (1080x1920) pronto para redes sociais.

---

## 📋 Pré-requisitos

1. **Python 3.10 ou superior**
2. **FFmpeg instalado no sistema operacional e adicionado ao `PATH`:**
   * **Windows:**
     ```bash
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

1. Clone o repositório ou acesse a pasta do projeto:
   ```bash
   git clone https://github.com/rdsmelobsb/download_transcricao_cortes_yt.git
   cd download_transcricao_cortes_yt
   ```

2. Crie e ative um ambiente virtual:
   * **Windows:**
     ```bash
     python -m venv venv
     .\venv\Scripts\activate
     ```
   * **Linux / macOS:**
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

3. Instale as bibliotecas necessárias:
   ```bash
   pip install yt-dlp openai-whisper ffmpeg-python
   ```

*(Opcional)* Para acelerar a transcrição com GPU NVIDIA (CUDA):
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

---

## 📖 Instruções de Uso

### 1. Download de Vídeos (`download.py`)

Execute o script e cole o link do vídeo:
```bash
python download.py
```
* O vídeo será salvo na pasta atual (ou subpasta `temp`) no formato `<job_id>_raw.mp4`.
* Se o vídeo exigir login ou validação, adicione o arquivo `cookies.txt` na mesma pasta do script.

---

### 2. Geração de Legendas (`gerador_srt.py`)

Gera o arquivo de legendas `.srt` a partir do áudio do vídeo:

* **Modo padrão** (procura o primeiro vídeo disponível na pasta e usa o modelo `base`):
  ```bash
  python gerador_srt.py
  ```

* **Passando parâmetros customizados:**
  ```bash
  python gerador_srt.py nome_do_video.mp4 small
  ```
  *Modelos Whisper disponíveis:* `tiny`, `base`, `small`, `medium`, `large`.

---

### 3. Execução dos Cortes (`cortes.py`)

1. Edite o array `TAREFAS_DE_CORTE` dentro de `cortes.py` informando os tempos em segundos:
   ```python
   TAREFAS_DE_CORTE = [
       {
           "id": 1,
           "nome": "Meu Primeiro Corte",
           "video_path": "video_exemplo.mp4",
           "start": 120.000,  # 02:00
           "end": 180.000     # 03:00
       }
   ]
   ```

2. Execute o script:
   ```bash
   python cortes.py
   ```

3. Selecione o formato no prompt interativo:
   * `[1]` **Vertical (9:16 - 1080x1920):** Formato otimizado para Shorts/Reels/TikTok.
   * `[2]` **Formato original:** Mantém as dimensões de captura do vídeo base.

Os vídeos finais serão renderizados na pasta `cortes_prontos/`.

---

## 📁 Estrutura de Arquivos

```text
├── cortes.py            # Recorte e renderização via FFmpeg
├── download.py          # Download com resolução máxima via yt-dlp
├── gerador_srt.py       # Transcrição de áudio e geração de SRT via Whisper
├── .gitignore           # Exclusão de venv, temporários e credenciais
└── README.md            # Documentação do projeto
```

---

## 🔒 Segurança

Arquivos de sessão como `cookies.txt`, diretórios de ambientes virtuais (`venv/`) e mídias geradas (`cortes_prontos/`) estão listados no `.gitignore` e não devem ser versionados publicamente.