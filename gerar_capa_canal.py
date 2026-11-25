"""
Script para geração profissional da Capa Oficial do canal 'Política Direta'
compatível com todas as Safe Areas do YouTube (TV, Desktop, Tablet, Celular)
e versão otimizada para o Kwai.
"""

import os
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUTPUT_DIR = "identidade_visual"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Dimensões Oficiais YouTube
YT_W, YT_H = 2560, 1440

# Safe Area YouTube (Tudo que celular/qualquer tela vê)
SAFE_X1, SAFE_X2 = 507, 2053  # Largura: 1546 px
SAFE_Y1, SAFE_Y2 = 508, 931   # Altura: 423 px

# Desktop Área
DESK_X1, DESK_X2 = 0, 2560
DESK_Y1, DESK_Y2 = 508, 931

# Tablet Área
TAB_X1, TAB_X2 = 352, 2207
TAB_Y1, TAB_Y2 = 508, 931

# Paleta Editorial Política Direta (Baseada na Opção 1)
COLOR_BG_BASE = (8, 14, 26)       # #080E1A (Navy profundo)
COLOR_BG_GRAD = (15, 23, 42)      # #0F172A (Slate Navy)
COLOR_CARD_BG = (23, 37, 84, 160) # #172554 semi-transparente
COLOR_WHITE   = (255, 255, 255)
COLOR_TEXT_P1 = (248, 250, 252)   # #F8FAFC
COLOR_TEXT_P2 = (203, 213, 225)   # #CBD5E1
COLOR_TEXT_MUT= (148, 163, 184)   # #94A3B8
COLOR_CRIMSON = (225, 29, 72)     # #E11D48 (Ponto focal / Notícias)
COLOR_CRIMSON_GLOW = (225, 29, 72, 80)
COLOR_BORDER  = (51, 65, 85)      # #334155
COLOR_PILL_BG = (30, 41, 59)      # #1E293B

# Fontes Windows
FONT_HEAVY = r"C:\Windows\Fonts\seguibl.ttf"     # Segoe UI Black
FONT_BOLD  = r"C:\Windows\Fonts\segoeuib.ttf"    # Segoe UI Bold
FONT_REG   = r"C:\Windows\Fonts\segoeui.ttf"     # Segoe UI Regular

def extrair_monograma():
    """Recorta o monograma PD com canal alfa ultra limpo a partir de logo_opcao_1."""
    logo_path = os.path.join(OUTPUT_DIR, "logo_opcao_1_monograma_pd.jpg")
    im = Image.open(logo_path).convert("RGBA")
    arr = np.array(im, dtype=float)
    
    # Recorte focado no símbolo
    crop = arr[290:730, 210:935].copy()
    bg = np.array([15.0, 26.0, 46.0, 255.0])
    
    # Distância Euclidiana de cor
    diff = np.sqrt(np.sum((crop[:, :, :3] - bg[:3])**2, axis=2))
    
    # Máscara suave anti-aliased
    alpha = np.clip((diff - 22.0) / (65.0 - 22.0), 0.0, 1.0) * 255.0
    crop[:, :, 3] = alpha
    
    # Recortar bordas vazias
    non_zero = np.where(alpha > 15)
    r_min, r_max = non_zero[0].min(), non_zero[0].max()
    c_min, c_max = non_zero[1].min(), non_zero[1].max()
    
    final_symbol = Image.fromarray(crop[r_min:r_max+1, c_min:c_max+1].astype(np.uint8), mode="RGBA")
    return final_symbol

def criar_fundo_cinematico(w, h):
    """Gera um fundo com gradientes esféricos, linhas de grade jornalísticas e brilho atmosférico."""
    base = Image.new("RGBA", (w, h), COLOR_BG_BASE + (255,))
    draw = ImageDraw.Draw(base)
    
    # 1. Gradiente vertical sutil
    for y in range(h):
        factor = abs(y - h // 2) / (h // 2)
        r = int(COLOR_BG_BASE[0] * factor + COLOR_BG_GRAD[0] * (1 - factor))
        g = int(COLOR_BG_BASE[1] * factor + COLOR_BG_GRAD[1] * (1 - factor))
        b = int(COLOR_BG_BASE[2] * factor + COLOR_BG_GRAD[2] * (1 - factor))
        draw.line([(0, y), (w, y)], fill=(r, g, b, 255))
        
    # 2. Grade técnica sutil (grid de redação / jornalismo de dados)
    grid_overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    grid_draw = ImageDraw.Draw(grid_overlay)
    
    grid_color = (255, 255, 255, 10)  # 4% de opacidade
    grid_accent = (59, 130, 246, 18)   # Toque azul bem sutil
    
    for x in range(0, w, 128):
        c = grid_accent if (x // 128) % 4 == 0 else grid_color
        grid_draw.line([(x, 0), (x, h)], fill=c, width=1)
        
    for y in range(0, h, 72):
        c = grid_accent if (y // 72) % 4 == 0 else grid_color
        grid_draw.line([(0, y), (w, y)], fill=c, width=1)
        
    base = Image.alpha_composite(base, grid_overlay)
    
    # 3. Glow radial suave no centro (onde fica o conteúdo da Safe Area)
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    cx, cy = w // 2, h // 2
    
    # Esferas de luz
    for r in range(500, 0, -25):
        alpha_val = int(22 * (1 - (r / 500)**1.5))
        glow_draw.ellipse([cx - r*2.2, cy - r*0.8, cx + r*2.2, cy + r*0.8], fill=(30, 58, 138, alpha_val))
        
    # Glow vermelho sutil na esquerda inferior do símbolo
    for r in range(250, 0, -20):
        alpha_val = int(18 * (1 - (r / 250)**2))
        glow_draw.ellipse([750 - r, cy - r, 750 + r, cy + r], fill=(225, 29, 72, alpha_val))
        
    glow = glow.filter(ImageFilter.GaussianBlur(radius=30))
    base = Image.alpha_composite(base, glow)
    
    # 4. Elementos estéticos para TVs 4K (topo e rodapé elegantes, fora da faixa desktop)
    tv_decor = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    tv_draw = ImageDraw.Draw(tv_decor)
    
    # Curvas sutis de arquitetura de Brasília / Congresso Nacional estilizado no topo (TV)
    for offset_y in [180, 220, 260]:
        tv_draw.arc([w//2 - 900, offset_y, w//2 + 900, offset_y + 400], start=180, end=360, fill=(255, 255, 255, 12), width=1)
        
    # Marca sutil na área de TV superior
    f_tv = ImageFont.truetype(FONT_BOLD, 22)
    tv_draw.text((w // 2, 280), "POLÍTICA DIRETA  |  CANAL OFICIAL DE CORTES", font=f_tv, fill=(148, 163, 184, 80), anchor="mm")
    
    # Marca sutil na área de TV inferior
    tv_draw.text((w // 2, 1180), "TRANSMISSÃO DIGITAL  •  COBERTURA COMPLETA  •  BRASÍLIA - DF", font=f_tv, fill=(148, 163, 184, 80), anchor="mm")
    
    base = Image.alpha_composite(base, tv_decor)
    return base

def renderizar_banner():
    print("Iniciando renderização da Capa Oficial...")
    base = criar_fundo_cinematico(YT_W, YT_H)
    draw = ImageDraw.Draw(base)
    
    # Obter Monograma Transparente
    monograma = extrair_monograma()
    
    # Redimensionar Monograma para altura ideal na Safe Area
    # Altura da safe area é 423. Altura de 220 deixa 100px margem vertical.
    mono_h = 220
    mono_w = int(monograma.width * (mono_h / monograma.height))
    monograma_resized = monograma.resize((mono_w, mono_h), Image.Resampling.LANCZOS)
    
    # Posições dentro da Safe Area (X: 507 a 2053, Y: 508 a 931)
    # Centro vertical Y = 720
    # Posicionar bloco de forma equilibrada e ultra segura:
    # Conteúdo total ocupará de X ≈ 600 a X ≈ 1950 (reserva de 93px em cada lado!)
    
    mono_x = 590
    mono_y = (SAFE_Y1 + SAFE_Y2) // 2 - (mono_h // 2)  # Centralizado verticalmente
    
    # Efeito Card / Moldura sutil atrás do monograma
    card_margin_x = 28
    card_margin_y = 20
    card_box = [
        mono_x - card_margin_x,
        mono_y - card_margin_y,
        mono_x + mono_w + card_margin_x,
        mono_y + mono_h + card_margin_y
    ]
    
    # Desenhar card de vidro para ancorar a marca
    card_overlay = Image.new("RGBA", (YT_W, YT_H), (0, 0, 0, 0))
    card_draw = ImageDraw.Draw(card_overlay)
    card_draw.rounded_rectangle(card_box, radius=24, fill=(15, 23, 42, 220), outline=(51, 65, 85, 200), width=2)
    # Detalhe crimson no card
    card_draw.line([(card_box[0] + 30, card_box[3]), (card_box[0] + 120, card_box[3])], fill=COLOR_CRIMSON, width=3)
    base = Image.alpha_composite(base, card_overlay)
    
    # Colar Monograma
    base.alpha_composite(monograma_resized, (mono_x, mono_y))
    
    # Linha divisória vertical elegante
    div_x = mono_x + mono_w + card_margin_x + 35
    div_y1 = mono_y - 10
    div_y2 = mono_y + mono_h + 10
    
    div_overlay = Image.new("RGBA", (YT_W, YT_H), (0, 0, 0, 0))
    div_draw = ImageDraw.Draw(div_overlay)
    div_draw.line([(div_x, div_y1), (div_x, div_y2)], fill=(51, 65, 85, 180), width=2)
    div_draw.line([(div_x, (div_y1 + div_y2)//2 - 25), (div_x, (div_y1 + div_y2)//2 + 25)], fill=COLOR_CRIMSON, width=3)
    base = Image.alpha_composite(base, div_overlay)
    
    # Bloco de Texto (À direita da divisória)
    text_x = div_x + 35
    
    # Fontes
    font_badge = ImageFont.truetype(FONT_BOLD, 19)
    font_title = ImageFont.truetype(FONT_HEAVY, 66)
    font_tagline = ImageFont.truetype(FONT_BOLD, 25)
    font_topics = ImageFont.truetype(FONT_BOLD, 18)
    font_sched = ImageFont.truetype(FONT_BOLD, 19)
    
    text_overlay = Image.new("RGBA", (YT_W, YT_H), (0, 0, 0, 0))
    t_draw = ImageDraw.Draw(text_overlay)
    
    # 1. Pill Badge Superior: "● JORNALISMO DIRETO AO PONTO"
    badge_text = "JORNALISMO DIRETO AO PONTO  •  SEM ENROLAÇÃO"
    badge_y = mono_y - 2
    
    # Calcular pill box
    bbox_badge = font_badge.getbbox(badge_text)
    badge_w = bbox_badge[2] - bbox_badge[0] + 50
    badge_h = 32
    pill_box = [text_x, badge_y, text_x + badge_w, badge_y + badge_h]
    
    t_draw.rounded_rectangle(pill_box, radius=16, fill=(30, 41, 59, 230), outline=(71, 85, 105, 180), width=1)
    # Ponto vermelho "AO VIVO / URGENTE"
    t_draw.ellipse([text_x + 14, badge_y + 11, text_x + 24, badge_y + 21], fill=COLOR_CRIMSON)
    t_draw.text((text_x + 32, badge_y + 6), badge_text, font=font_badge, fill=COLOR_TEXT_P1)
    
    # 2. Nome do Canal: "POLÍTICA DIRETA"
    title_text = "POLÍTICA DIRETA"
    title_y = badge_y + badge_h + 8
    
    # Sombra sutil no título
    t_draw.text((text_x + 2, title_y + 2), title_text, font=font_title, fill=(0, 0, 0, 160))
    t_draw.text((text_x, title_y), title_text, font=font_title, fill=COLOR_WHITE)
    
    # 3. Slogan / Proposta de Valor
    tagline_text = "O que acontece em Brasília, sem filtro e sem amarras."
    tagline_y = title_y + 74
    t_draw.text((text_x, tagline_y), tagline_text, font=font_tagline, fill=COLOR_TEXT_P2)
    
    # 4. Pilares Temáticos (Tags)
    topics_text = "NOTÍCIAS  •  DECISÕES DO PODER  •  ECONOMIA  •  BASTIDORES"
    topics_y = tagline_y + 36
    t_draw.text((text_x, topics_y), topics_text, font=font_topics, fill=COLOR_TEXT_MUT)
    
    # 5. Barra de Frequência & Horários
    sched_y = topics_y + 34
    sched_text = "VÍDEOS TODOS OS DIAS  |  11:30 • 17:30 • 20:30  •  SHORTS & KWAI"
    bbox_sched = font_sched.getbbox(sched_text)
    sched_w = bbox_sched[2] - bbox_sched[0] + 44
    sched_h = 34
    
    sched_box = [text_x, sched_y, text_x + sched_w, sched_y + sched_h]
    t_draw.rounded_rectangle(sched_box, radius=8, fill=(15, 23, 42, 230), outline=(225, 29, 72, 160), width=1)
    # Ponto de destaque no início
    t_draw.text((text_x + 14, sched_y + 6), "⚡ " + sched_text, font=font_sched, fill=(244, 63, 94))
    
    base = Image.alpha_composite(base, text_overlay)
    
    # Salvar Master Oficial Limpo (Pronto para Upload)
    banner_path = os.path.join(OUTPUT_DIR, "banner_youtube_politica_direta.png")
    base.convert("RGB").save(banner_path, "PNG", quality=95)
    print(f"✅ Capa oficial master gerada com sucesso: {banner_path}")
    
    # Gerar Versão com Gabarito Visual Multi-Dispositivo
    gerar_gabarito(base)
    
    # Gerar Previews Recortados para Celular e Desktop
    gerar_recortes(base)
    
    # Gerar Banner Otimizado para Kwai
    gerar_banner_kwai(monograma)

def gerar_gabarito(base_img):
    """Cria uma cópia do banner com marcações de Safe Area de cada dispositivo."""
    gab = base_img.copy().convert("RGBA")
    overlay = Image.new("RGBA", (YT_W, YT_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    
    f_label = ImageFont.truetype(FONT_BOLD, 22)
    f_sub = ImageFont.truetype(FONT_REG, 17)
    
    # 1. Faixa Desktop (2560 x 423)
    d.rectangle([DESK_X1, DESK_Y1, DESK_X2, DESK_Y2], outline=(59, 130, 246, 180), width=2)
    d.text((DESK_X1 + 20, DESK_Y1 + 15), "🖥️ DESKTOP / NOTEBOOK (2560 × 423 px)", font=f_label, fill=(96, 165, 250, 240))
    
    # 2. Faixa Tablet (1855 x 423)
    d.rectangle([TAB_X1, TAB_Y1, TAB_X2, TAB_Y2], outline=(168, 85, 247, 180), width=2)
    d.text((TAB_X1 + 20, TAB_Y2 - 35), "📱 TABLET (1855 × 423 px)", font=f_label, fill=(192, 132, 252, 240))
    
    # 3. Faixa Celular / Safe Area Universal (1546 x 423)
    # Efeito escurecido fora da safe area para destacar
    mask_out = Image.new("RGBA", (YT_W, YT_H), (0, 0, 0, 90))
    d_mask = ImageDraw.Draw(mask_out)
    d_mask.rectangle([SAFE_X1, SAFE_Y1, SAFE_X2, SAFE_Y2], fill=(0, 0, 0, 0))
    overlay = Image.alpha_composite(overlay, mask_out)
    d = ImageDraw.Draw(overlay)
    
    # Borda verde fluorescente na Safe Area
    d.rectangle([SAFE_X1, SAFE_Y1, SAFE_X2, SAFE_Y2], outline=(34, 197, 94, 255), width=3)
    d.text((SAFE_X1 + 20, SAFE_Y1 + 14), "📱 CELULAR / SAFE AREA UNIVERSAL (1546 × 423 px)", font=f_label, fill=(74, 222, 128, 255))
    d.text((SAFE_X1 + 20, SAFE_Y1 + 42), "TUDO AQUI DENTRO É 100% VISÍVEL EM QUALQUER APARELHO DO MUNDO", font=f_sub, fill=(187, 247, 208, 240))
    
    # Linha TV
    d.text((50, 60), "📺 SMART TV (2560 × 1440 px - Tela Inteira)", font=f_label, fill=(203, 213, 225, 200))
    
    final_gab = Image.alpha_composite(gab, overlay)
    gab_path = os.path.join(OUTPUT_DIR, "banner_youtube_com_gabarito.png")
    final_gab.convert("RGB").save(gab_path, "PNG", quality=95)
    print(f"✅ Gabarito com marcações gerado: {gab_path}")

def gerar_recortes(base_img):
    """Gera os recortes exatos do que cada usuário vê na prática."""
    # Recorte Mobile (1546 x 423)
    crop_mobile = base_img.crop((SAFE_X1, SAFE_Y1, SAFE_X2, SAFE_Y2))
    mob_path = os.path.join(OUTPUT_DIR, "preview_mobile_1546x423.png")
    crop_mobile.convert("RGB").save(mob_path, "PNG", quality=95)
    print(f"✅ Preview Mobile gerado: {mob_path}")
    
    # Recorte Desktop (2560 x 423)
    crop_desk = base_img.crop((DESK_X1, DESK_Y1, DESK_X2, DESK_Y2))
    desk_path = os.path.join(OUTPUT_DIR, "preview_desktop_2560x423.png")
    crop_desk.convert("RGB").save(desk_path, "PNG", quality=95)
    print(f"✅ Preview Desktop gerado: {desk_path}")

def gerar_banner_kwai(monograma):
    """Gera versão adaptada para o cabeçalho do perfil do Kwai (1080 x 450 px)."""
    KW_W, KW_H = 1080, 450
    base = criar_fundo_cinematico(KW_W, KW_H)
    draw = ImageDraw.Draw(base)
    
    # Monograma adaptado
    mono_h = 140
    mono_w = int(monograma.width * (mono_h / monograma.height))
    mono_resized = monograma.resize((mono_w, mono_h), Image.Resampling.LANCZOS)
    
    mono_x = 55
    mono_y = (KW_H - mono_h) // 2
    
    # Moldura monograma
    card_margin_x, card_margin_y = 18, 12
    card_box = [
        mono_x - card_margin_x,
        mono_y - card_margin_y,
        mono_x + mono_w + card_margin_x,
        mono_y + mono_h + card_margin_y
    ]
    card_overlay = Image.new("RGBA", (KW_W, KW_H), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card_overlay)
    cd.rounded_rectangle(card_box, radius=16, fill=(15, 23, 42, 220), outline=(51, 65, 85, 200), width=2)
    cd.line([(card_box[0] + 20, card_box[3]), (card_box[0] + 80, card_box[3])], fill=COLOR_CRIMSON, width=3)
    base = Image.alpha_composite(base, card_overlay)
    base.alpha_composite(mono_resized, (mono_x, mono_y))
    
    # Divisória
    div_x = mono_x + mono_w + card_margin_x + 22
    div_overlay = Image.new("RGBA", (KW_W, KW_H), (0, 0, 0, 0))
    dd = ImageDraw.Draw(div_overlay)
    dd.line([(div_x, mono_y - 5), (div_x, mono_y + mono_h + 5)], fill=(51, 65, 85, 180), width=2)
    dd.line([(div_x, KW_H // 2 - 15), (div_x, KW_H // 2 + 15)], fill=COLOR_CRIMSON, width=3)
    base = Image.alpha_composite(base, div_overlay)
    
    # Tipografia Kwai
    text_x = div_x + 24
    f_badge = ImageFont.truetype(FONT_BOLD, 14)
    f_title = ImageFont.truetype(FONT_HEAVY, 42)
    f_tag = ImageFont.truetype(FONT_BOLD, 17)
    f_sub = ImageFont.truetype(FONT_BOLD, 14)
    
    t_overlay = Image.new("RGBA", (KW_W, KW_H), (0, 0, 0, 0))
    td = ImageDraw.Draw(t_overlay)
    
    # Badge
    badge_text = "JORNALISMO DIRETO AO PONTO"
    b_y = mono_y - 2
    td.rounded_rectangle([text_x, b_y, text_x + 260, b_y + 24], radius=12, fill=(30, 41, 59, 230), outline=(71, 85, 105, 180), width=1)
    td.ellipse([text_x + 10, b_y + 7, text_x + 18, b_y + 15], fill=COLOR_CRIMSON)
    td.text((text_x + 24, b_y + 4), badge_text, font=f_badge, fill=COLOR_TEXT_P1)
    
    # Título
    t_y = b_y + 28
    td.text((text_x, t_y), "POLÍTICA DIRETA", font=f_title, fill=COLOR_WHITE)
    
    # Tagline
    tag_y = t_y + 48
    td.text((text_x, tag_y), "O que acontece em Brasília, sem filtro e sem enrolação.", font=f_tag, fill=COLOR_TEXT_P2)
    
    # Horários
    sched_y = tag_y + 28
    td.text((text_x, sched_y), "⚡ CORTES DIÁRIOS  •  11:30 • 17:30 • 20:30", font=f_sub, fill=(244, 63, 94))
    
    base = Image.alpha_composite(base, t_overlay)
    kw_path = os.path.join(OUTPUT_DIR, "banner_kwai_politica_direta.png")
    base.convert("RGB").save(kw_path, "PNG", quality=95)
    print(f"✅ Banner Kwai gerado com sucesso: {kw_path}")

if __name__ == "__main__":
    renderizar_banner()
