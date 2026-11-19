---
name: politica-direta-cortes
description: Processa transcrições SRT de conteúdo político (discursos, entrevistas, coletivas, debates e noticiários) para o canal Política Direta no YouTube Shorts e Kwai. Gera o bloco Python TAREFAS_DE_CORTE pronto para automação com 3 cortes diários, timestamps em segundos decimais, ordem de publicação, horários estratégicos (11:30, 17:30 e 20:30), títulos de capa, textos de publicação e hashtags. Use sempre que o usuário enviar um arquivo .srt político ou pedir cortes, legendas, títulos, planejamento ou peças visuais para o canal Política Direta.
---

# politica-direta-cortes

Extrai cortes virais de alta retenção a partir de transcrições `.srt` de conteúdo político para o canal **Política Direta** (focado exclusivamente em **YouTube Shorts** e **Kwai**), entregando código Python pronto para automação e kit completo de publicação.

## Quando Usar

- O usuário enviar um arquivo `.srt` (ou transcrição com timestamps) de discurso, entrevista, coletiva, debate ou boletim político.
- O usuário pedir para gerar cortes, JSON/Python de corte (`TAREFAS_DE_CORTE`), títulos, descrições ou hashtags para o canal Política Direta.
- O usuário solicitar prompts visuais, capas ou artes alinhadas à identidade visual do canal.

## Etapas do Fluxo

### 1. Curadoria Editorial e Limpeza da Transcrição

Analise a transcrição completa antes de escolher os trechos.

- Priorize temas de alto engajamento e compartilhamento: impacto direto no bolso do trabalhador, direitos trabalhistas e sociais, soberania nacional, economia real, defesa da democracia, geopolítica e combate à desinformação.
- Selecione exatamente **3 cortes principais** por arquivo, com duração alvo entre **45 e 100 segundos** (ajustando se o vídeo original for mais curto ou se um argumento central exigir alguns segundos extras para não cortar no meio da frase).
- Escolha trechos que comecem com um gancho forte nos primeiros 3 segundos e terminem com fechamento conclusivo.
- Corrija erros típicos de transcrição automática (nomes próprios, siglas, cifras e palavras distorcidas pelo STT) nos títulos e textos de publicação, sem alterar o sentido original da fala nem os timestamps reais do `.srt`.

### 2. Distribuição na Grade Diária

Atribua cada um dos 3 cortes à grade fixa do canal, combinando o perfil do corte com o comportamento da audiência no YouTube Shorts e no Kwai:

1. **Ordem 1 (`11:30`):** Pauta de utilidade pública, economia, medidas práticas ou impacto direto no cotidiano (pico do almoço).
2. **Ordem 2 (`17:30`):** Debate quente, análise política, cobrança ou contraponto estratégico (fim de expediente).
3. **Ordem 3 (`20:30`):** Corte de maior carga emocional, posicionamento firme, valorização institucional ou alto potencial de compartilhamento orgânico (horário nobre).

### 3. Bloco Python de Automação (`TAREFAS_DE_CORTE`)

Inicie a resposta diretamente com o bloco de código Python contendo a lista `TAREFAS_DE_CORTE` (sem saudações ou preâmbulos). Converta todos os timestamps de `HH:MM:SS,mmm` para segundos decimais (`float`) com precisão de 3 casas decimais, mantendo o timestamp original comentado ao lado.

Use exatamente esta estrutura de campos:

```python
TAREFAS_DE_CORTE = [
    {
        "id": 1,
        "ordem": 1,
        "horario_sugerido": "11:30",
        "nome": "Titulo Curto Sem Acentos Para Nome de Arquivo",
        "video_path": "nome_descritivo_do_video.mp4",
        "title": "Título otimizado para SEO e retenção no YouTube Shorts e Kwai",
        "start": 120.500,  # 00:02:00,500
        "end": 195.240     # 00:03:15,240
    },
    {
        "id": 2,
        "ordem": 2,
        "horario_sugerido": "17:30",
        "nome": "Segundo Corte Sem Acentos",
        "video_path": "nome_descritivo_do_video.mp4",
        "title": "Título chamativo do corte 2",
        "start": 310.000,  # 00:05:10,000
        "end": 385.400     # 00:06:25,400
    },
    {
        "id": 3,
        "ordem": 3,
        "horario_sugerido": "20:30",
        "nome": "Terceiro Corte Sem Acentos",
        "video_path": "nome_descritivo_do_video.mp4",
        "title": "Título de alto impacto do corte 3",
        "start": 500.120,  # 00:08:20,120
        "end": 580.800     # 00:09:40,800
    }
]
```

### 4. Kit de Publicação (YouTube Shorts e Kwai)

Após uma linha horizontal (`---`), apresente os detalhes de publicação de cada corte em ordem crescente (`Corte 1`, `Corte 2`, `Corte 3`), seguindo este padrão:

- **Cabeçalho:** `### Corte X (Ordem: X | Horário Sugerido: HH:MM)` seguido do título em negrito e timestamp original entre parênteses.
- **Título na tela / Capa:** Frase curta com selo de impacto em caixa alta no início (ex.: `"RECADO DIRETO: '...'"`, `"UTILIDADE PÚBLICA: '...'"`, `"ALERTA URGENTE: '...'"`) pensada para segurar o scroll.
- **Texto da publicação (em blockquote `>`):** Estruture em 4 partes curtas: (1) contextualização rápida em uma frase, (2) citação limpa e fluente dos melhores trechos da fala, (3) fecho analítico reforçando o impacto prático e (4) CTA direto incentivando comentários (algoritmo do YouTube) e compartilhamento em grupos (alcance no Kwai).
- **Hashtags:** Exatamente 5 hashtags, sempre começando com `#PolíticaDireta` seguida por 4 tags específicas de alto volume do tema.

### 5. Identidade Visual (Quando Solicitada)

Sempre que o usuário pedir prompts de imagem, thumbnails, banners ou artes para o canal, mantenha o padrão oficial do **Política Direta**:

- **Paleta oficial:** Azul-profundo (`#0A1F3D`), verde-escuro vibrante (`#0E4D2B`), amarelo-ouro (`#FFB800`) para destaque e branco puro para leitura de alto contraste.
- **Estilo:** Vetorial 3D sutil, alto contraste, legível em telas pequenas de celular, tipografia sans-serif extra-negrito inclinada (itálico) e elementos que remetam a comunicação direta e progresso.

## Cuidados e Restrições

- **Português do Brasil (PT-BR):** Escreva todos os títulos, legendas e descrições estritamente em português brasileiro natural, evitando termos ou conjugações de português europeu.
- **Plataformas ativas:** O projeto opera apenas no **YouTube Shorts** e no **Kwai**. Nunca mencione, recomende ou formate entregas para o TikTok.
- **Precisão dos timestamps:** Confira o cálculo da conversão para segundos (`horas * 3600 + minutos * 60 + segundos`) para garantir que o script de corte não recorte trechos errados.
- **Campo `nome` limpo:** Mantenha o campo `nome` dentro de `TAREFAS_DE_CORTE` sem acentos, cedilhas ou caracteres especiais, pois ele pode ser usado diretamente na geração de nomes de arquivos pelo pipeline Python.
- **Sem sobreposição desnecessária:** Evite repetir o mesmo intervalo de áudio em dois cortes distintos, a menos que o vídeo original tenha menos de 2 minutos no total.
