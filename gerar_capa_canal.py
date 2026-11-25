"""
Script para geração profissional da Capa Oficial do canal 'Política Direta'
compatível com todas as Safe Areas do YouTube (TV, Desktop, Tablet, Celular).
"""

import os
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
COLOR_WHITE   = (255, 255, 255)
COLOR_TEXT_P1 = (248, 250, 252)   # #F8FAFC
COLOR_TEXT_P2 = (203, 213, 225)   # #CBD5E1
COLOR_TEXT_MUT= (148, 163, 184)   # #94A3B8
COLOR_CRIMSON = (225, 29, 72)     # #E11D48 (Ponto focal / Notícias)
COLOR_ROSE_TXT= (251, 113, 133)   # #FB7185 (Destaque legível em fundo escuro)

# Fontes Windows
FONT_HEAVY = r"C:\Windows\Fonts\seguibl.ttf"     # Segoe UI Black
FONT_BOLD  = r"C:\Windows\Fonts\segoeuib.ttf"    # Segoe UI Bold
FONT_REG   = r"C:\Windows\Fonts\segoeui.ttf"     # Segoe UI Regular


def extrair_monograma():
    """Recorta o monograma PD com canal alfa ultra limpo a partir de logo_opcao_1."""
    logo_path = os.path.join(OUTPUT_DIR, "logo_opcao_1_monograma_pd.jpg")
    im = Image.open(logo_path).convert("RGBA")
    arr = np.array(im, dtype=float)

    crop = arr[290:730, 210:935].copy()
    bg = np.array([15.0, 26.0, 46.0, 255.0])

    diff = np.sqrt(np.sum((crop[:, :, :3] - bg[:3]) ** 2, axis=2))
    alpha = np.clip((diff - 22.0) / (65.0 - 22.0), 0.0, 1.0) * 255.0
    crop[:, :, 3] = alpha

    non_zero = np.where(alpha > 15)
    r_min, r_max = non_zero[0].min(), non_zero[0].max()
    c_min, c_max = non_zero[1].min(), non_zero[1].max()

    return Image.fromarray(crop[r_min:r_max + 1, c_min:c_max + 1].astype(np.uint8), mode="RGBA")


def criar_fundo_cinematico(w, h):
    """Gera fundo com gradientes, grade técnica jornalística e iluminação atmosférica."""
    base = Image.new("RGBA", (w, h), COLOR_BG_BASE + (255,))
    draw = ImageDraw.Draw(base)

    for y in range(h):
        factor = abs(y - h // 2) / (h // 2)
        r = int(COLOR_BG_BASE[0] * factor + COLOR_BG_GRAD[0] * (1 - factor))
        g = int(COLOR_BG_BASE[1] * factor + COLOR_BG_GRAD[1] * (1 - factor))
        b = int(COLOR_BG_BASE[2] * factor + COLOR_BG_GRAD[2] * (1 - factor))
        draw.line([(0, y), (w, y)], fill=(r, g, b, 255))

    grid_overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    grid_draw = ImageDraw.Draw(grid_overlay)

    grid_color = (255, 255, 255, 10)
    grid_accent = (59, 130, 246, 18)

    for x in range(0, w, 128):
        c = grid_accent if (x // 128) % 4 == 0 else grid_color
        grid_draw.line([(x, 0), (x, h)], fill=c, width=1)

    for y in range(0, h, 72):
        c = grid_accent if (y // 72) % 4 == 0 else grid_color
        grid_draw.line([(0, y), (w, y)], fill=c, width=1)

    base = Image.alpha_composite(base, grid_overlay)

    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    cx, cy = w // 2, h // 2

    for r in range(520, 0, -25):
        alpha_val = int(24 * (1 - (r / 520) ** 1.5))
        glow_draw.ellipse([cx - r * 2.1, cy - r * 0.75, cx + r * 2.1, cy + r * 0.75], fill=(30, 58, 138, alpha_val))

    for r in range(260, 0, -20):
        alpha_val = int(18 * (1 - (r / 260) ** 2))
        glow_draw.ellipse([820 - r, cy - r, 820 + r, cy + r], fill=(225, 29, 72, alpha_val))

    glow = glow.filter(ImageFilter.GaussianBlur(radius=32))
    base = Image.alpha_composite(base, glow)

    tv_decor = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    tv_draw = ImageDraw.Draw(tv_decor)

    for offset_y in [180, 220, 260]:
        tv_draw.arc([w // 2 - 900, offset_y, w // 2 + 900, offset_y + 400], start=180, end=360, fill=(255, 255, 255, 14), width=1)

    f_tv = ImageFont.truetype(FONT_BOLD, 22)
    tv_draw.text((w // 2, 280), "POLÍTICA DIRETA  |  CANAL OFICIAL", font=f_tv, fill=(148, 163, 184, 85), anchor="mm")
    tv_draw.text((w // 2, 1180), "TRANSMISSÃO DIGITAL  •  COBERTURA COMPLETA  •  BRASÍLIA - DF", font=f_tv, fill=(148, 163, 184, 85), anchor="mm")

    return Image.alpha_composite(base, tv_decor)


def renderizar_banner():
    print("Iniciando renderização da Capa Oficial (Calendário 6x/dia)...")
    base = criar_fundo_cinematico(YT_W, YT_H)

    monograma = extrair_monograma()
    mono_h = 204
    mono_w = int(monograma.width * (mono_h / monograma.height))
    monograma_resized = monograma.resize((mono_w, mono_h), Image.Resampling.LANCZOS)

    # Fontes
    font_badge = ImageFont.truetype(FONT_BOLD, 18)
    font_title = ImageFont.truetype(FONT_HEAVY, 64)
    font_tagline = ImageFont.truetype(FONT_BOLD, 24)
    font_topics = ImageFont.truetype(FONT_BOLD, 18)
    font_sched = ImageFont.truetype(FONT_BOLD, 18)

    # Textos oficiais (sem Kwai, com grade 6 vídeos/dia)
    badge_text = "JORNALISMO DIRETO AO PONTO  •  SEM ENROLAÇÃO"
    title_text = "POLÍTICA DIRETA"
    tagline_text = "O que acontece em Brasília, sem filtro e sem amarras."
    topics_text = "NOTÍCIAS  •  DECISÕES DO PODER  •  ECONOMIA  •  BASTIDORES"
    sched_text = "6 VÍDEOS POR DIA  |  08:30 • 11:30 • 14:30 • 17:30 • 20:00 • 22:30"

    # Medir largura máxima do bloco de texto para centralizar perfeitamente na Safe Area
    def text_w(txt, font):
        b = font.getbbox(txt)
        return b[2] - b[0]

    sched_box_w = text_w(sched_text, font_sched) + 52
    badge_box_w = text_w(badge_text, font_badge) + 50
    max_text_w = max(
        badge_box_w,
        text_w(title_text, font_title),
        text_w(tagline_text, font_tagline),
        text_w(topics_text, font_topics),
        sched_box_w,
    )

    card_pad_x = 26
    card_pad_y = 20
    card_w = mono_w + card_pad_x * 2
    gap_div = 34

    # Largura total do bloco [Card + Divisória + Textos]
    total_content_w = card_w + gap_div + 2 + gap_div + max_text_w
    safe_center_x = (SAFE_X1 + SAFE_X2) // 2  # 1280
    safe_center_y = (SAFE_Y1 + SAFE_Y2) // 2  # 719

    start_x = safe_center_x - (total_content_w // 2)
    mono_x = start_x + card_pad_x
    mono_y = safe_center_y - (mono_h // 2)

    card_box = [
        start_x,
        mono_y - card_pad_y,
        start_x + card_w,
        mono_y + mono_h + card_pad_y,
    ]

    # Card do monograma
    card_overlay = Image.new("RGBA", (YT_W, YT_H), (0, 0, 0, 0))
    card_draw = ImageDraw.Draw(card_overlay)
    card_draw.rounded_rectangle(card_box, radius=24, fill=(15, 23, 42, 225), outline=(51, 65, 85, 210), width=2)
    base = Image.alpha_composite(base, card_overlay)
    base.alpha_composite(monograma_resized, (mono_x, mono_y))

    # Divisória vertical
    div_x = start_x + card_w + gap_div
    div_y1 = card_box[1] + 10
    div_y2 = card_box[3] - 10

    div_overlay = Image.new("RGBA", (YT_W, YT_H), (0, 0, 0, 0))
    div_draw = ImageDraw.Draw(div_overlay)
    div_draw.line([(div_x, div_y1), (div_x, div_y2)], fill=(51, 65, 85, 190), width=2)
    div_draw.line([(div_x, safe_center_y - 24), (div_x, safe_center_y + 24)], fill=COLOR_CRIMSON, width=3)
    base = Image.alpha_composite(base, div_overlay)

    # Bloco de texto centralizado verticalmente junto ao card
    text_x = div_x + gap_div
    text_overlay = Image.new("RGBA", (YT_W, YT_H), (0, 0, 0, 0))
    t_draw = ImageDraw.Draw(text_overlay)

    # Altura total dos 5 elementos de texto = ~256 px; alinhar com safe_center_y
    top_y = safe_center_y - 128

    # 1. Pill Badge
    badge_h = 32
    pill_box = [text_x, top_y, text_x + badge_box_w, top_y + badge_h]
    t_draw.rounded_rectangle(pill_box, radius=16, fill=(30, 41, 59, 235), outline=(71, 85, 105, 190), width=1)
    t_draw.ellipse([text_x + 14, top_y + 11, text_x + 24, top_y + 21], fill=COLOR_CRIMSON)
    t_draw.text((text_x + 32, top_y + 5), badge_text, font=font_badge, fill=COLOR_TEXT_P1)

    # 2. Título Principal
    title_y = top_y + badge_h + 8
    t_draw.text((text_x + 2, title_y + 2), title_text, font=font_title, fill=(0, 0, 0, 170))
    t_draw.text((text_x, title_y), title_text, font=font_title, fill=COLOR_WHITE)

    # 3. Tagline
    tagline_y = title_y + 72
    t_draw.text((text_x, tagline_y), tagline_text, font=font_tagline, fill=COLOR_TEXT_P2)

    # 4. Pilares
    topics_y = tagline_y + 36
    t_draw.text((text_x, topics_y), topics_text, font=font_topics, fill=COLOR_TEXT_MUT)

    # 5. Barra de Calendário 6x/dia (com ícone Play vetorial limpo em vez de emoji quebrado)
    sched_y = topics_y + 34
    sched_h = 36
    sched_box = [text_x, sched_y, text_x + sched_box_w, sched_y + sched_h]
    t_draw.rounded_rectangle(sched_box, radius=9, fill=(15, 23, 42, 235), outline=(225, 29, 72, 185), width=1)

    # Triângulo "Play" vetorial crimson dentro da barra
    px = text_x + 16
    py = sched_y + sched_h // 2
    t_draw.polygon([(px, py - 6), (px, py + 6), (px + 10, py)], fill=COLOR_CRIMSON)

    t_draw.text((text_x + 35, sched_y + 7), sched_text, font=font_sched, fill=COLOR_ROSE_TXT)

    base = Image.alpha_composite(base, text_overlay)

    banner_path = os.path.join(OUTPUT_DIR, "banner_youtube_politica_direta.png")
    base.convert("RGB").save(banner_path, "PNG", quality=95)
    print(f"Capa oficial gerada: {banner_path}")
    print(f"Conteudo ocupa X: {start_x}..{start_x + total_content_w} (margem dentro da safe area: {start_x - SAFE_X1}px esq / {SAFE_X2 - (start_x + total_content_w)}px dir)")

    gerar_gabarito(base)
    gerar_recortes(base)


def gerar_gabarito(base_img):
    """Cria cópia do banner com marcações de Safe Area (sem emojis quebrados)."""
    gab = base_img.copy().convert("RGBA")
    overlay = Image.new("RGBA", (YT_W, YT_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    f_label = ImageFont.truetype(FONT_BOLD, 21)
    f_sub = ImageFont.truetype(FONT_REG, 17)

    d.rectangle([DESK_X1, DESK_Y1, DESK_X2, DESK_Y2], outline=(59, 130, 246, 190), width=2)
    d.text((DESK_X1 + 24, DESK_Y1 + 16), "[DESKTOP / NOTEBOOK] 2560 x 423 px", font=f_label, fill=(96, 165, 250, 245))

    d.rectangle([TAB_X1, TAB_Y1, TAB_X2, TAB_Y2], outline=(168, 85, 247, 190), width=2)
    d.text((TAB_X1 + 20, DESK_Y2 - 34), "[TABLET] 1855 x 423 px", font=f_label, fill=(192, 132, 252, 245))

    mask_out = Image.new("RGBA", (YT_W, YT_H), (0, 0, 0, 85))
    d_mask = ImageDraw.Draw(mask_out)
    d_mask.rectangle([SAFE_X1, SAFE_Y1, SAFE_X2, SAFE_Y2], fill=(0, 0, 0, 0))
    overlay = Image.alpha_composite(overlay, mask_out)
    d = ImageDraw.Draw(overlay)

    d.rectangle([SAFE_X1, SAFE_Y1, SAFE_X2, SAFE_Y2], outline=(34, 197, 94, 255), width=3)
    d.text((SAFE_X1 + 20, SAFE_Y1 + 14), "[CELULAR / SAFE AREA UNIVERSAL] 1546 x 423 px", font=f_label, fill=(74, 222, 128, 255))
    d.text((SAFE_X1 + 20, SAFE_Y1 + 42), "100% visivel em qualquer celular, tablet, desktop ou TV", font=f_sub, fill=(187, 247, 208, 240))

    d.text((50, 55), "[SMART TV] 2560 x 1440 px - Tela Inteira", font=f_label, fill=(203, 213, 225, 210))

    final_gab = Image.alpha_composite(gab, overlay)
    gab_path = os.path.join(OUTPUT_DIR, "banner_youtube_com_gabarito.png")
    final_gab.convert("RGB").save(gab_path, "PNG", quality=95)
    print(f"Gabarito gerado: {gab_path}")


def gerar_recortes(base_img):
    """Gera os recortes exatos para visualização mobile e desktop."""
    crop_mobile = base_img.crop((SAFE_X1, SAFE_Y1, SAFE_X2, SAFE_Y2))
    mob_path = os.path.join(OUTPUT_DIR, "preview_mobile_1546x423.png")
    crop_mobile.convert("RGB").save(mob_path, "PNG", quality=95)

    crop_desk = base_img.crop((DESK_X1, DESK_Y1, DESK_X2, DESK_Y2))
    desk_path = os.path.join(OUTPUT_DIR, "preview_desktop_2560x423.png")
    crop_desk.convert("RGB").save(desk_path, "PNG", quality=95)
    print("Previews mobile e desktop gerados.")


if __name__ == "__main__":
    renderizar_banner()
