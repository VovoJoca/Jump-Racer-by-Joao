"""
SUPER JUMP RACER
-----------------
Corrida em cima de molas contra 3 adversários controlados por IA,
todos na MESMA pista! Escolha a cor do seu robô e a dificuldade na
tela de título, depois segure a seta direita pra avançar pulando de
mola em mola. Trilha sonora rock pesado (chiptune) com harmonias, e
um equalizador em pixel art!

CONTROLES:
  Na tela de título:
    - SETA ESQUERDA / DIREITA -> escolher a cor do robô
    - SETA CIMA / BAIXO       -> escolher a dificuldade
    - T                       -> avançar pra próxima pista (das 12)
    - SHIFT + T               -> voltar pra pista anterior
    - ENTER / ESPAÇO          -> começar a corrida
    (também dá pra clicar com o mouse nas opções)

  Durante a corrida:
    - SETA DIREITA / D  -> segure para avançar (pular pra frente)
    - SETA CIMA    / W  -> mover para cima na pista
    - SETA BAIXO   / S  -> mover para baixo na pista
    - M                 -> ligar/desligar a música
    - R                 -> reiniciar depois da corrida (volta pra tela de título)
    - ESC                -> sair

REGRAS:
  - Se você não segurar a seta direita, o robô fica parado.
  - ESTRELA  -> aumenta sua velocidade por um tempo (boost)!
  - ESPINHO/OBSTÁCULO -> reduz sua velocidade por um instante — desvie
    mudando de posição na pista!
  - No modo FÁCIL os adversários correm na mesma velocidade que você.
    No modo DIFÍCIL eles são um pouco mais rápidos.
  - São 12 pistas temáticas (Cidade, Deserto, Neve, Caverna, Vulcão,
    Castelo, Floresta, Comida, Praia, Casa Assombrada, Lua, Céu), cada
    uma um pouco mais difícil que a anterior (adversários mais rápidos
    e mais obstáculos pelo caminho).
  - Cada pista pode ter sua própria música: coloque arquivos chamados
    custom_theme01.mp3 até custom_theme12.mp3 na pasta assets/ (veja
    mais detalhes no código, na seção "MÚSICA PERSONALIZADA").

REQUISITOS:
  pip install pygame numpy

COMO RODAR:
  python super_jump_racer.py

Os sprites em pixel art e a trilha sonora são gerados automaticamente
na pasta assets/ na primeira execução.

NOTAS TÉCNICAS (v5):
- O jogo agora roda com movimento baseado em tempo real (delta-time),
  não mais "por frame fixo" — se o computador engasgar por um
  instante, a corrida não fica mais lenta pra todo mundo.
- A colisão com estrelas/espinhos usa um teste de "segmento percorrido"
  no frame, então mesmo que o jogo pule um pedaço maior da pista de
  uma vez (engasgo momentâneo), a estrela/espinho ainda é detectado
  corretamente.
- A música agora toca a partir de um som totalmente pré-carregado na
  memória (em vez de ficar lendo o arquivo aos poucos), o que evita
  qualquer soluço no momento em que a faixa reinicia o loop.
"""

import os
import sys

# python-for-android define essa variável de ambiente automaticamente
# quando o jogo roda dentro de um APK Android — assim conseguimos
# mostrar os controles de toque só quando fizer sentido (no Android),
# sem precisar de um código-fonte separado pra cada plataforma.
IS_ANDROID = "ANDROID_ARGUMENT" in os.environ
import math
import random
import wave
import pygame

# --------------------------------------------------------------------------
# CONFIGURAÇÃO GERAL
# --------------------------------------------------------------------------
WIDTH, HEIGHT = 960, 600
FPS = 60

SKY_TOP = (120, 200, 255)
SKY_BOTTOM = (200, 235, 255)
TRACK_TOP = 150
TRACK_BOTTOM = 560
POSITIONS = 4
POS_H = (TRACK_BOTTOM - TRACK_TOP) // POSITIONS

TRACK_LENGTH = 8000.0
PLAYER_ANCHOR_X = 230

BASE_SPEED = 4.8          # unidades de mundo por "frame de 1/60s" (nominal)
BOOST_MULT = 1.7
BOOST_SECONDS = 2.5        # duração do boost em segundos (tempo real)
STUN_MULT = 0.35
STUN_SECONDS = 0.75        # duração do atordoamento em segundos (tempo real)
RUBBER_BAND = 0.0007
BOB_HEIGHT = 16
MAX_DT = 1.0 / 20.0        # trava o passo de tempo (evita saltos grandes em engasgos)
COLLIDE_RADIUS = 24        # raio de detecção de estrela/espinho (mundo)

RACER_COLORS = ["yellow", "blue", "red", "green"]
COLOR_LABELS = {"yellow": "Amarelo", "blue": "Azul", "red": "Vermelho", "green": "Verde"}

# faixas de velocidade da IA por dificuldade (relativas à sua velocidade base)
DIFFICULTY_SKILL = {
    "facil":   (0.97, 1.03),
    "dificil": (1.15, 1.28),
}

# ---- as 12 pistas, em ordem de dificuldade crescente ----
# "skill_bonus" soma à velocidade da IA e "obstacle_prob" é a chance de
# espinho/obstáculo por trecho da pista — ambos crescem com o número
# da pista, deixando as últimas pistas mais difíceis que as primeiras.
TRACKS = [
    {"key": "cidade",     "n": 1,  "label": "1. Cidade",
     "sky_top": (150, 190, 220), "sky_bottom": (210, 225, 235),
     "side_color": (120, 128, 132), "track_color": (90, 95, 100), "track_edge": (60, 64, 68),
     "lane_line": (240, 220, 90), "obstacle_sprite": "spike", "decor": "cidade"},

    {"key": "deserto",    "n": 2,  "label": "2. Deserto",
     "sky_top": (255, 196, 120), "sky_bottom": (255, 232, 180),
     "side_color": (216, 178, 110), "track_color": (223, 186, 128), "track_edge": (176, 138, 84),
     "lane_line": (255, 250, 235), "obstacle_sprite": "cactus", "decor": "deserto"},

    {"key": "neve",       "n": 3,  "label": "3. Neve",
     "sky_top": (210, 230, 245), "sky_bottom": (240, 248, 255),
     "side_color": (235, 240, 248), "track_color": (200, 215, 230), "track_edge": (160, 180, 200),
     "lane_line": (140, 170, 200), "obstacle_sprite": "neve", "decor": "neve"},

    {"key": "caverna",    "n": 4,  "label": "4. Caverna",
     "sky_top": (35, 30, 45), "sky_bottom": (65, 55, 75),
     "side_color": (45, 38, 52), "track_color": (55, 48, 62), "track_edge": (30, 25, 35),
     "lane_line": (150, 130, 170), "obstacle_sprite": "spike", "decor": "caverna"},

    {"key": "vulcao",     "n": 5,  "label": "5. Vulcão",
     "sky_top": (80, 30, 25), "sky_bottom": (200, 90, 40),
     "side_color": (55, 30, 25), "track_color": (65, 35, 30), "track_edge": (35, 18, 15),
     "lane_line": (255, 150, 60), "obstacle_sprite": "vulcao", "decor": "vulcao"},

    {"key": "castelo",    "n": 6,  "label": "6. Castelo",
     "sky_top": (120, 100, 150), "sky_bottom": (200, 175, 200),
     "side_color": (100, 95, 105), "track_color": (115, 108, 118), "track_edge": (75, 70, 78),
     "lane_line": (230, 210, 160), "obstacle_sprite": "spike", "decor": "castelo"},

    {"key": "floresta",   "n": 7,  "label": "7. Floresta",
     "sky_top": (140, 210, 150), "sky_bottom": (215, 240, 200),
     "side_color": (55, 120, 60), "track_color": (110, 90, 60), "track_edge": (75, 60, 40),
     "lane_line": (235, 220, 140), "obstacle_sprite": "floresta", "decor": "floresta"},

    {"key": "comida",     "n": 8,  "label": "8. Comida",
     "sky_top": (255, 210, 230), "sky_bottom": (255, 240, 210),
     "side_color": (240, 200, 150), "track_color": (250, 225, 180), "track_edge": (210, 170, 120),
     "lane_line": (230, 90, 90), "obstacle_sprite": "comida", "decor": "comida"},

    {"key": "praia",      "n": 9,  "label": "9. Praia",
     "sky_top": (130, 210, 240), "sky_bottom": (210, 240, 250),
     "side_color": (240, 220, 165), "track_color": (245, 230, 185), "track_edge": (200, 180, 130),
     "lane_line": (60, 150, 190), "obstacle_sprite": "cactus", "decor": "praia"},

    {"key": "assombrada", "n": 10, "label": "10. Casa Assombrada",
     "sky_top": (30, 28, 40), "sky_bottom": (60, 55, 75),
     "side_color": (40, 45, 42), "track_color": (48, 44, 55), "track_edge": (25, 22, 30),
     "lane_line": (150, 200, 150), "obstacle_sprite": "assombrada", "decor": "assombrada"},

    {"key": "lua",        "n": 11, "label": "11. Lua",
     "sky_top": (10, 10, 25), "sky_bottom": (35, 30, 55),
     "side_color": (90, 90, 98), "track_color": (110, 108, 115), "track_edge": (70, 68, 76),
     "lane_line": (200, 200, 210), "obstacle_sprite": "spike", "decor": "lua"},

    {"key": "ceu",        "n": 12, "label": "12. Céu",
     "sky_top": (140, 200, 255), "sky_bottom": (255, 255, 255),
     "side_color": (255, 255, 255), "track_color": (225, 240, 255), "track_edge": (180, 210, 240),
     "lane_line": (255, 210, 90), "obstacle_sprite": "spike", "decor": "ceu"},
]
TRACKS_BY_KEY = {t["key"]: t for t in TRACKS}

def track_skill_bonus(track_cfg):
    """Bônus de velocidade da IA que cresce com o número da pista."""
    return (track_cfg["n"] - 1) * 0.018

def track_obstacle_prob(track_cfg):
    """Chance de obstáculo por trecho, crescendo com o número da pista."""
    return min(0.72, 0.42 + (track_cfg["n"] - 1) * 0.022)

# Quando rodando como script normal, os assets ficam ao lado do .py.
# Quando "congelado" pelo PyInstaller (executável), usamos a pasta ao
# lado do próprio executável (não a pasta temporária de extração),
# assim os assets (e uma eventual custom_theme.mp3) persistem entre
# execuções.
if getattr(sys, "frozen", False):
    _base_dir = os.path.dirname(os.path.abspath(sys.executable))
else:
    _base_dir = os.path.dirname(os.path.abspath(__file__))
ASSET_DIR = os.path.join(_base_dir, "assets")

# --------------------------------------------------------------------------
# GERAÇÃO DE SPRITES (pixel art)
# --------------------------------------------------------------------------
def ensure_sprites():
    needed = [f"robot_{c}.png" for c in RACER_COLORS] + \
              [f"robot_{c}_squash.png" for c in RACER_COLORS] + \
              ["star.png", "spike.png", "cactus.png", "sun.png", "spring_tile.png", "finish_flag.png",
               "obstacle_neve.png", "obstacle_vulcao.png", "obstacle_floresta.png",
               "obstacle_comida.png", "obstacle_assombrada.png"]
    if all(os.path.exists(os.path.join(ASSET_DIR, n)) for n in needed):
        return
    os.makedirs(ASSET_DIR, exist_ok=True)

    from PIL import Image, ImageDraw

    def save_sprite(rows, path, palette, scale=6):
        w = max(len(r) for r in rows)
        rows = [r.ljust(w, '.') for r in rows]
        h = len(rows)
        img = Image.new('RGBA', (w * scale, h * scale), (0, 0, 0, 0))
        px = img.load()
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                color = palette.get(ch, (0, 0, 0, 0))
                if color[3] == 0:
                    continue
                for dy in range(scale):
                    for dx in range(scale):
                        px[x * scale + dx, y * scale + dy] = color
        img.save(path)

    BASE_PALETTE = {
        '.': (0, 0, 0, 0), 'D': (35, 25, 15, 255),
        'Y': (255, 199, 38, 255), 'y': (255, 222, 110, 255),
        'G': (55, 215, 140, 255), 'g': (150, 255, 205, 255),
        'S': (188, 195, 205, 255), 's': (228, 232, 238, 255),
        'W': (255, 255, 255, 255), 'K': (25, 25, 30, 255),
        'O': (255, 150, 110, 255),
    }
    robot_rows = [
        "..........DDDD.........", "..........DSsD.........", "..........DDDD.........",
        "...........DD..........", "...........DD..........", ".........DDDDDD........",
        "........DYyyyyyD.......", "........DYyyyyyD.......", ".......DYWKDDWyYD......",
        ".......DYWKDDWyYD......", ".......DYyOyyOyYD......", ".......DYyyDDyyYD......",
        "........DYyyyyyD.......", ".........DDDDDD........", "SsD.....DDDDDDDD.....DsS",
        "SsDD...DYyyyyyyyD...DDsS", ".SsDD..DYyyGGGyyD..DDsS.", "..SsD..DYyyGGGyyD..DsS..",
        "...S...DYyyyyyyyD...S...", ".......DYyyyyyyyD......", "........DDD..DDD.......",
        "........DSD..DSD.......", "........DSD..DSD.......", "........DDD..DDD.......",
    ]
    robot_squash_rows = [
        "........DDDDDDDDDD.......", ".......DYyyyyyyyyyD......", "......DYWKDDDDWyYYD......",
        "......DYWKDDDDWyYYD......", "......DYyOyyyyOyYYD......", "......DYyyDDDDyyYYD......",
        ".......DYyyyyyyyyyD......", "........DDDDDDDDDD.......", "SsDD.....DDDDDDDDDD.....DDsS",
        "Ss......DYyyGGGGyyD......sS", ".......DYyyyGGyyyD.......", "........DYyyyyyyyD.......",
        ".........DDD..DDD........",
    ]
    VARIANTS = {
        "yellow": ((255, 199, 38, 255), (255, 222, 110, 255)),
        "blue":   ((60, 140, 235, 255), (140, 195, 250, 255)),
        "red":    ((230, 70, 60, 255),  (250, 140, 120, 255)),
        "green":  ((70, 190, 110, 255), (150, 235, 175, 255)),
    }
    for name, (main, hi) in VARIANTS.items():
        pal = dict(BASE_PALETTE)
        pal['Y'] = main
        pal['y'] = hi
        save_sprite(robot_rows, os.path.join(ASSET_DIR, f"robot_{name}.png"), pal, scale=6)
        save_sprite(robot_squash_rows, os.path.join(ASSET_DIR, f"robot_{name}_squash.png"), pal, scale=6)

    star_rows = ["....D....", "...DYD...", "..DYyYD..", "DDDYyYDDD", "DYyyyyyYD",
                 ".DYyyyYD.", "..DYyYD..", ".DYD.DYD.", "DYD...DYD"]
    star_pal = dict(BASE_PALETTE); star_pal['Y'] = (255, 199, 38, 255); star_pal['y'] = (255, 230, 140, 255)
    save_sprite(star_rows, os.path.join(ASSET_DIR, "star.png"), star_pal, scale=8)

    # ---- espinho (obstáculo em forma de ouriço/estrela pontiaguda) ----
    SPIKE_PAL = {
        '.': (0, 0, 0, 0), 'D': (30, 15, 35, 255),
        'P': (165, 70, 190, 255), 'p': (205, 130, 225, 255), 'K': (75, 35, 90, 255),
    }
    size = 17
    grid = [['.' for _ in range(size)] for _ in range(size)]
    cx = cy = size // 2
    for y in range(size):
        for x in range(size):
            d = math.hypot(x - cx, y - cy)
            if d <= 3.4:
                grid[y][x] = 'K'
            if d <= 2.6:
                grid[y][x] = 'P' if (x + y) % 2 == 0 else 'p'
    dirs = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
    for dx, dy in dirs:
        length = 5 if dx == 0 or dy == 0 else 3
        norm = math.hypot(dx, dy)
        ux, uy = dx / norm, dy / norm
        for i in range(3, 3 + length):
            x = int(round(cx + ux * i))
            y = int(round(cy + uy * i))
            if 0 <= x < size and 0 <= y < size:
                grid[y][x] = 'P'
                if dx == 0 and 0 <= x + 1 < size and grid[y][x + 1] == '.':
                    grid[y][x + 1] = 'p'
                if dy == 0 and 0 <= y + 1 < size and grid[y + 1][x] == '.':
                    grid[y + 1][x] = 'p'
    new_grid = [row[:] for row in grid]
    for y in range(size):
        for x in range(size):
            if grid[y][x] == '.':
                nb = []
                for ddy in (-1, 0, 1):
                    for ddx in (-1, 0, 1):
                        ny, nx = y + ddy, x + ddx
                        if 0 <= ny < size and 0 <= nx < size:
                            nb.append(grid[ny][nx])
                if any(v != '.' for v in nb):
                    new_grid[y][x] = 'D'
    spike_rows = [''.join(r) for r in new_grid]
    save_sprite(spike_rows, os.path.join(ASSET_DIR, "spike.png"), SPIKE_PAL, scale=8)

    # ---- cacto (obstáculo temático da pista deserto) ----
    CACTUS_PAL = {
        '.': (0, 0, 0, 0), 'D': (25, 50, 20, 255),
        'G': (60, 140, 70, 255), 'g': (95, 180, 105, 255),
        'F': (230, 90, 140, 255), 'f': (250, 150, 180, 255),
        'S': (235, 220, 150, 255),
    }
    cactus_rows = [
        "........DD.........", "........DFD........", ".......DFfFD.......",
        ".......DDDD........", "..DD....DD....DD...", ".DGD....DD....DGD..",
        ".DgD....DD....DgD..", ".DGD..DDDDDD..DGD..", ".DgDDDGggggGDDDgD..",
        ".DDGgggggggggGDD...", "..DGgSgGGgSggGD....", "..DGggggggggGD.....",
        "...DGgGggGgGD......", "...DGgggggggGD.....", "....DGGGGGGGGD.....",
        "....DGgggggggD.....", ".....DGGGGGGD......", ".....DDDDDDDD......",
    ]
    save_sprite(cactus_rows, os.path.join(ASSET_DIR, "cactus.png"), CACTUS_PAL, scale=7)

    # ---- bola de neve (pista Neve) ----
    SNOW_PAL = {'.': (0, 0, 0, 0), 'D': (150, 180, 210, 255), 'W': (255, 255, 255, 255),
                'w': (225, 240, 255, 255), 'I': (170, 220, 245, 255)}
    snow_rows = [
        "......DD......", ".....DIwID.....", "....DIWWWID....", "...DWWWWWWWD...",
        "..DWwWWWWwWD..", ".DWWWWWWWWWWD.", ".DWwWWWWWWwWD.", ".DWWWwWWwWWWD.",
        "..DWWWWWWWD...", "...DWWWWWD....", "....DDDDD.....",
    ]
    save_sprite(snow_rows, os.path.join(ASSET_DIR, "obstacle_neve.png"), SNOW_PAL, scale=8)

    # ---- pedra de lava (pista Vulcão) ----
    LAVA_PAL = {'.': (0, 0, 0, 0), 'D': (40, 15, 10, 255), 'R': (60, 30, 25, 255),
                'r': (90, 50, 40, 255), 'O': (255, 120, 30, 255), 'o': (255, 190, 60, 255)}
    lava_rows = [
        "....DD..DD.....", "...DrRD DRrD...", "..DRrRDDRrRD...", ".DRrOoORrOoRD..",
        ".DRoOOOOOOoRD..", "DRrOoO.OoOorRD.", "DRROOo.oOOoRRD.", ".DRrOOOOOorRD..",
        ".DRRrOOOorRRD..", "..DRRrrrRRDD...", "...DDDDDDD.....",
    ]
    save_sprite(lava_rows, os.path.join(ASSET_DIR, "obstacle_vulcao.png"), LAVA_PAL, scale=8)

    # ---- toco de árvore (pista Floresta) ----
    WOOD_PAL = {'.': (0, 0, 0, 0), 'D': (40, 25, 15, 255), 'B': (110, 70, 40, 255),
                'b': (145, 100, 60, 255), 'R': (200, 160, 110, 255)}
    wood_rows = [
        "..D..D..D......", "...D..D..D.....", "..DBD..DBD.....", ".DBbBDDBbBD....",
        "DBbbbBBbbbBD...", "DBbRRRRRbbBD...", "DBbRrRrRbbBD...", "DBbRRRRRbbBD...",
        "DBbbbbbbbbBD...", ".DBBBBBBBBD....", "..DDDDDDDD.....",
    ]
    save_sprite(wood_rows, os.path.join(ASSET_DIR, "obstacle_floresta.png"), WOOD_PAL, scale=8)

    # ---- pimenta (pista Comida) ----
    FOOD_PAL = {'.': (0, 0, 0, 0), 'D': (25, 60, 20, 255), 'G': (60, 150, 50, 255),
                'R': (210, 40, 35, 255), 'r': (240, 90, 70, 255), 'h': (255, 150, 120, 255)}
    food_rows = [
        "....DD.........", "...DGD.........", "..DGGD.........", "...DGD.........",
        "....DRD........", "....DRrD.......", "...DRrrRD......", "..DRrhhrRD.....",
        ".DRrhhhhrRD....", ".DRrhhhhrRD....", "..DRrrrrRD.....", "...DRRRRD......",
        "....DDDD.......",
    ]
    save_sprite(food_rows, os.path.join(ASSET_DIR, "obstacle_comida.png"), FOOD_PAL, scale=8)

    # ---- lápide (pista Casa Assombrada) ----
    GHOST_PAL = {'.': (0, 0, 0, 0), 'D': (30, 30, 35, 255), 'S': (140, 145, 155, 255),
                 's': (175, 180, 190, 255), 'X': (60, 65, 75, 255)}
    ghost_rows = [
        "....DDDDD......", "...DSssSD......", "..DSssssSD.....", ".DSsSsSsSsD....",
        ".DSssssssSD....", ".DSsXsXssSD....", ".DSsssssSSD....", ".DSsSXsSsSD....",
        ".DSssssssSD....", ".DSSSSSSSSD....", "DDDDDDDDDDDD...",
    ]
    save_sprite(ghost_rows, os.path.join(ASSET_DIR, "obstacle_assombrada.png"), GHOST_PAL, scale=8)

    # ---- sol (decoração da pista deserto) ----
    sun_size = 96
    sun_img = Image.new('RGBA', (sun_size, sun_size), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sun_img)
    scx, scy = sun_size // 2, sun_size // 2
    r_core, r_ray_in, r_ray_out = 22, 28, 44
    for i in range(8):
        ang = i * (360 / 8)
        a1 = math.radians(ang - 9)
        a2 = math.radians(ang + 9)
        p1 = (scx + r_ray_in * math.cos(a1), scy + r_ray_in * math.sin(a1))
        p2 = (scx + r_ray_in * math.cos(a2), scy + r_ray_in * math.sin(a2))
        p3 = (scx + r_ray_out * math.cos(math.radians(ang)), scy + r_ray_out * math.sin(math.radians(ang)))
        sd.polygon([p1, p2, p3], fill=(235, 150, 40, 255))
    sd.ellipse([scx - r_core - 4, scy - r_core - 4, scx + r_core + 4, scy + r_core + 4], fill=(255, 205, 60, 255))
    sd.ellipse([scx - r_core, scy - r_core, scx + r_core, scy + r_core], fill=(255, 225, 110, 255))
    small = sun_img.resize((28, 28), Image.NEAREST)
    pixelated = small.resize((sun_size, sun_size), Image.NEAREST)
    pixelated.save(os.path.join(ASSET_DIR, "sun.png"))

    spring_w, spring_h = 56, 34
    sp = Image.new('RGBA', (spring_w, spring_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(sp)
    ring_colors = [(224, 60, 55, 255), (250, 110, 95, 255)]
    n_rings = 3
    ring_h = spring_h // n_rings
    for i in range(n_rings):
        y0 = i * ring_h
        col = ring_colors[i % 2]
        d.ellipse([3, y0, spring_w - 3, y0 + ring_h + 6], outline=(35, 25, 15, 255), width=3)
        d.ellipse([7, y0 + 2, spring_w - 7, y0 + ring_h + 2], outline=col, width=3)
    sp.save(os.path.join(ASSET_DIR, "spring_tile.png"))

    flag = Image.new('RGBA', (32, 24), (0, 0, 0, 0))
    fd = ImageDraw.Draw(flag)
    cell = 6
    for j in range(4):
        for i in range(5):
            col = (25, 25, 30, 255) if (i + j) % 2 == 0 else (245, 245, 245, 255)
            fd.rectangle([i * cell, j * cell, i * cell + cell, j * cell + cell], fill=col)
    flag.save(os.path.join(ASSET_DIR, "finish_flag.png"))


# --------------------------------------------------------------------------
# GERAÇÃO DA TRILHA SONORA — rock pesado chiptune, com melodia e harmonia
# --------------------------------------------------------------------------
def ensure_music():
    mp3_path = os.path.join(ASSET_DIR, "rock_theme.mp3")
    wav_path = os.path.join(ASSET_DIR, "rock_theme.wav")
    if os.path.exists(mp3_path):
        return mp3_path
    if os.path.exists(wav_path):
        return wav_path
    os.makedirs(ASSET_DIR, exist_ok=True)

    import numpy as np
    SR = 44100

    def midi_to_freq(m):
        return 440.0 * (2.0 ** ((m - 69) / 12.0))

    def square(freq, t):
        phase = (t * freq) % 1.0
        return np.where(phase < 0.5, 1.0, -1.0)

    def saw(freq, t):
        phase = (t * freq) % 1.0
        return 2.0 * phase - 1.0

    def triangle(freq, t):
        phase = (t * freq) % 1.0
        return 2 * np.abs(2 * phase - 1) - 1

    def env_exp(n, k):
        t = np.arange(n) / SR
        return np.exp(-k * t)

    def kick(dur=0.16):
        n = int(SR * dur)
        t = np.arange(n) / SR
        freq_env = 140 * np.exp(-35 * t) + 45
        phase = 2 * np.pi * np.cumsum(freq_env) / SR
        return np.sin(phase) * env_exp(n, 22)

    def snare(dur=0.15):
        n = int(SR * dur)
        t = np.arange(n) / SR
        noise = np.random.uniform(-1, 1, n)
        env = env_exp(n, 26)
        tone = np.sin(2 * np.pi * 190 * t) * 0.35
        return (noise * 0.75 + tone) * env

    def hihat(dur=0.055, amp=0.45):
        n = int(SR * dur)
        noise = np.random.uniform(-1, 1, n)
        return noise * env_exp(n, 70) * amp

    def crash(dur=0.9, amp=0.5):
        n = int(SR * dur)
        noise = np.random.uniform(-1, 1, n)
        return noise * env_exp(n, 3.2) * amp

    def mix_at(buf, sig, start_sample):
        end = start_sample + len(sig)
        if end > len(buf):
            sig = sig[: len(buf) - start_sample]
            end = len(buf)
        if end > start_sample:
            buf[start_sample:end] += sig

    def pluck_gate(n, bar_dur, subdivisions, decay=38):
        gate = np.zeros(n)
        step = bar_dur / subdivisions
        for i in range(subdivisions):
            s = int(i * step * SR)
            seg_n = int(step * SR)
            seg_t = np.arange(seg_n) / SR
            pluck = np.exp(-decay * seg_t)
            e = min(s + seg_n, n)
            if e > s:
                gate[s:e] = pluck[: e - s]
        return gate

    def make_bar(root_midi, kick_pat, snare_pat, hat_pat, bar_dur,
                 melody_offsets=None, harmony_offsets=None, crash_hit=False, drive=3.2, energy=1.0):
        n = int(SR * bar_dur)
        buf = np.zeros(n)
        t = np.arange(n) / SR

        f_root = midi_to_freq(root_midi)
        f_fifth = midi_to_freq(root_midi + 7)
        f_oct = midi_to_freq(root_midi + 12)
        chord = (square(f_root, t) + square(f_root * 1.006, t) * 0.9
                 + square(f_fifth, t) * 0.7 + square(f_oct, t) * 0.5)
        chord /= 3.1
        gate8 = pluck_gate(n, bar_dur, 8, decay=38)
        chord *= gate8
        chord = np.tanh(chord * drive) / np.tanh(drive)

        bass = saw(f_root / 2, t) * gate8 * 0.9
        bass = np.tanh(bass * 2.2) / np.tanh(2.2)

        buf += (chord * 0.46 + bass * 0.42) * energy

        if melody_offsets:
            subdiv = len(melody_offsets)
            step = bar_dur / subdiv
            gate_lead = pluck_gate(n, bar_dur, subdiv, decay=14)
            lead = np.zeros(n)
            for i, semis in enumerate(melody_offsets):
                s = int(i * step * SR); e = min(int((i + 1) * step * SR), n)
                if e <= s:
                    continue
                f = midi_to_freq(root_midi + 12 + semis)
                lead[s:e] = triangle(f, t[s:e])
            lead *= gate_lead
            buf += lead * 0.30

            if harmony_offsets:
                harm = np.zeros(n)
                for i, semis in enumerate(harmony_offsets):
                    s = int(i * step * SR); e = min(int((i + 1) * step * SR), n)
                    if e <= s:
                        continue
                    f = midi_to_freq(root_midi + 12 + semis)
                    harm[s:e] = triangle(f, t[s:e]) * 0.8
                harm *= gate_lead
                buf += harm * 0.20

        pad = (triangle(f_root * 2, t) * 0.5 + triangle(f_fifth * 2, t) * 0.4)
        pad_env = 0.10 + 0.02 * np.sin(2 * np.pi * t / bar_dur)
        buf += pad * pad_env

        beat = bar_dur / 4
        for i in kick_pat:
            mix_at(buf, kick() * 0.9, int(i * beat * SR))
        for i in snare_pat:
            mix_at(buf, snare() * 0.8, int(i * beat * SR))
        for i in hat_pat:
            mix_at(buf, hihat(), int(i * beat * SR))
        if crash_hit:
            mix_at(buf, crash(), 0)
        return buf

    bpm = 150
    beat = 60 / bpm
    bar_dur = beat * 4
    kick_pat = [0, 0.5, 2, 2.5, 3.5]
    snare_pat = [1, 3]
    hat_pat = [i * 0.5 for i in range(8)]
    kick_pat_chorus = [0, 0.5, 1.5, 2, 2.5, 3, 3.5]
    hat_pat_chorus = [i * 0.25 for i in range(16)]

    melodies = [
        [0, 7, 12, 7, 0, 7, 10, 7],
        [0, 5, 12, 5, 0, 5, 8, 5],
        [0, 7, 9, 12, 9, 7, 4, 0],
        [0, 7, 12, 15, 12, 7, 3, 0],
    ]
    harmonies = [
        [3, 10, 15, 10, 3, 10, 13, 10],
        [3, 8, 15, 8, 3, 8, 11, 8],
        [3, 10, 12, 15, 12, 10, 7, 3],
        [3, 10, 15, 18, 15, 10, 6, 3],
    ]
    melodies_chorus = [
        [12, 15, 19, 15, 12, 15, 17, 15],
        [12, 14, 19, 14, 12, 14, 16, 14],
        [12, 15, 17, 19, 17, 15, 14, 12],
        [12, 15, 19, 22, 19, 15, 12, 10],
    ]
    harmonies_chorus = [
        [7, 10, 15, 10, 7, 10, 12, 10],
        [7, 9, 15, 9, 7, 9, 11, 9],
        [7, 10, 12, 15, 12, 10, 9, 7],
        [7, 10, 15, 17, 15, 10, 7, 5],
    ]

    # ESTROFE: i - VII - IV - i em Mi menor (8 compassos)
    verse_roots = [40, 38, 45, 40, 40, 38, 45, 40]
    # REFRÃO: VI - III - VII - i, mais denso e agudo (8 compassos)
    chorus_roots = [48, 43, 50, 40, 48, 43, 50, 40]

    bars = []
    for idx, r in enumerate(verse_roots):
        mel = melodies[idx % len(melodies)]
        harm = harmonies[idx % len(harmonies)]
        bars.append(make_bar(r, kick_pat, snare_pat, hat_pat, bar_dur,
                              melody_offsets=mel, harmony_offsets=harm,
                              crash_hit=(idx == 0), energy=1.0))
    for idx, r in enumerate(chorus_roots):
        mel = melodies_chorus[idx % len(melodies_chorus)]
        harm = harmonies_chorus[idx % len(harmonies_chorus)]
        bars.append(make_bar(r, kick_pat_chorus, snare_pat, hat_pat_chorus, bar_dur,
                              melody_offsets=mel, harmony_offsets=harm,
                              crash_hit=(idx == 0), drive=3.8, energy=1.12))

    track = np.concatenate(bars)
    peak = np.max(np.abs(track)) + 1e-9
    track = track / peak * 0.92
    stereo = np.stack([track, track], axis=1)
    pcm = (stereo * 32767).astype(np.int16)

    # grava um .wav temporário e converte pra .mp3 (arquivo bem menor)
    # usando o ffmpeg, se ele estiver disponível no sistema.
    tmp_wav = wav_path + ".tmp"
    with wave.open(tmp_wav, 'wb') as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm.tobytes())

    import subprocess
    import shutil as _shutil
    if _shutil.which("ffmpeg"):
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", tmp_wav,
                 "-codec:a", "libmp3lame", "-qscale:a", "2", mp3_path],
                check=True,
            )
            os.remove(tmp_wav)
            return mp3_path
        except (subprocess.CalledProcessError, OSError):
            pass  # cai no fallback abaixo

    # Fallback: sem ffmpeg disponível, mantém a trilha em .wav mesmo
    os.replace(tmp_wav, wav_path)
    return wav_path


# --------------------------------------------------------------------------
# MÚSICA PERSONALIZADA (uma trilha por pista!)
# --------------------------------------------------------------------------
# Cada uma das 12 pistas pode ter sua própria música. Para isso, coloque
# na pasta assets/ um arquivo pra cada pista, numerado de 01 a 12 na
# mesma ordem das pistas (1=Cidade, 2=Deserto, ... 12=Céu):
#   assets/custom_theme01.mp3   (Cidade)
#   assets/custom_theme02.mp3   (Deserto)
#   ...
#   assets/custom_theme12.mp3   (Céu)
# Também aceita .ogg/.wav no lugar de .mp3.
# Se não houver arquivo pra uma pista específica, o jogo tenta usar um
# "assets/custom_theme.mp3" genérico (a mesma música pra todas as
# pistas que não tiverem a numerada); se nem esse existir, usa a
# trilha chiptune padrão gerada automaticamente.
# (Por respeito a direitos autorais, este script nunca baixa, gera ou
# distribui músicas comerciais — você mesmo precisa colocar os
# arquivos, de cópias que já possua legalmente.)
CUSTOM_MUSIC_NAMES = ["custom_theme.mp3", "custom_theme.ogg", "custom_theme.wav"]

def find_custom_music():
    for name in CUSTOM_MUSIC_NAMES:
        p = os.path.join(ASSET_DIR, name)
        if os.path.exists(p):
            return p
    return None


def find_track_music(track_number):
    """Retorna o caminho da música específica da pista (custom_themeNN),
    ou o custom_theme.mp3 genérico, ou None (fallback pro padrão)."""
    for ext in ("mp3", "ogg", "wav"):
        p = os.path.join(ASSET_DIR, f"custom_theme{track_number:02d}.{ext}")
        if os.path.exists(p):
            return p
    return find_custom_music()


ensure_sprites()
_custom_music_path = find_custom_music()
MUSIC_PATH = _custom_music_path if _custom_music_path else ensure_music()

# --------------------------------------------------------------------------
# INICIALIZAÇÃO PYGAME
# --------------------------------------------------------------------------
pygame.init()
try:
    pygame.mixer.init()
    MUSIC_OK = True
except pygame.error:
    MUSIC_OK = False

if IS_ANDROID:
    # No Android, preenche a tela inteira do celular. O SCALED faz o
    # pygame esticar nosso jogo (pensado pra 960x600) pra caber
    # direitinho em qualquer tamanho de tela, mantendo a proporção.
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN | pygame.SCALED)
else:
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Super Jump Racer")
print("Janela do jogo aberta! Se o ENTER não responder na tela de "
      "título, clique uma vez dentro da janela do jogo pra dar foco "
      "a ela (o teclado só funciona se a janela do jogo, e não o "
      "terminal, estiver em primeiro plano) e tente de novo.")
clock = pygame.time.Clock()

def make_font(size, bold=False):
    """No Android, pygame.font.SysFont() tenta rodar o comando 'fc-list'
    do sistema pra descobrir as fontes instaladas — e o Android não
    tem esse comando nem permite esse tipo de execução, o que
    derrubava o app com PermissionError. Usamos a fonte embutida do
    próprio pygame nesse caso (não depende do sistema operacional);
    no Windows/Mac/Linux continuamos usando a Arial normalmente.
    """
    if IS_ANDROID:
        f = pygame.font.Font(None, size)
        f.set_bold(bold)
        return f
    return pygame.font.SysFont("arial", size, bold=bold)


font_big = make_font(56, bold=True)
font_med = make_font(28, bold=True)
font_small = make_font(19)
font_title = make_font(72, bold=True)
font_track_label = make_font(19, bold=True)

music_on = True
music_sound = None
music_channel = None
USING_CUSTOM_MUSIC = False
MUSIC_MODE = None  # "sound" (pré-carregado, sem soluço) ou "stream" (streaming)
CURRENT_MUSIC_PATH = None


def _try_play_preloaded(path):
    """Tenta carregar o áudio inteiro na memória e tocar em loop, sem
    nenhum soluço quando a faixa reinicia. Funciona pra .wav e, na
    maioria dos sistemas, também pra .mp3."""
    global music_sound, music_channel
    snd = pygame.mixer.Sound(path)
    snd.set_volume(0.55 if music_on else 0.0)
    ch = snd.play(loops=-1)
    music_sound, music_channel = snd, ch
    return True


def _try_play_streamed(path):
    """Alternativa via streaming (pygame.mixer.music) — usada só se o
    pré-carregamento acima não funcionar no sistema do usuário."""
    pygame.mixer.music.load(path)
    pygame.mixer.music.set_volume(0.55 if music_on else 0.0)
    pygame.mixer.music.play(loops=-1)
    return True


def switch_music(path):
    """Troca a música tocando agora pra outro arquivo (usado ao trocar
    de pista). Para o que estiver tocando e começa a nova faixa."""
    global music_sound, music_channel, USING_CUSTOM_MUSIC, MUSIC_MODE, MUSIC_OK, CURRENT_MUSIC_PATH
    if path == CURRENT_MUSIC_PATH:
        return
    if music_sound is not None:
        music_sound.stop()
        music_sound, music_channel = None, None
    try:
        pygame.mixer.music.stop()
    except pygame.error:
        pass

    try:
        _try_play_preloaded(path)
        MUSIC_MODE = "sound"
        MUSIC_OK = True
    except pygame.error:
        try:
            _try_play_streamed(path)
            MUSIC_MODE = "stream"
            MUSIC_OK = True
        except pygame.error as e:
            print(f"Não consegui tocar a música ({path}): {e}")
            MUSIC_OK = False
            MUSIC_MODE = None
    CURRENT_MUSIC_PATH = path
    USING_CUSTOM_MUSIC = (path != MUSIC_PATH)


switch_music(MUSIC_PATH)


def set_music_volume(v):
    if not MUSIC_OK:
        return
    if MUSIC_MODE == "stream":
        pygame.mixer.music.set_volume(v)
    elif music_sound is not None:
        music_sound.set_volume(v)




def load(name, size=None):
    img = pygame.image.load(os.path.join(ASSET_DIR, name)).convert_alpha()
    if size:
        img = pygame.transform.smoothscale(img, size)
    return img


ROBOT_IMG = {c: load(f"robot_{c}.png", (74, 74)) for c in RACER_COLORS}
ROBOT_SQUASH_IMG = {c: load(f"robot_{c}_squash.png", (84, 46)) for c in RACER_COLORS}
ROBOT_ICON = {c: load(f"robot_{c}.png", (56, 56)) for c in RACER_COLORS}
star_img = load("star.png", (32, 32))
spike_img = load("spike.png", (40, 40))
cactus_img = load("cactus.png", (46, 46))
neve_img = load("obstacle_neve.png", (40, 40))
vulcao_img = load("obstacle_vulcao.png", (44, 40))
floresta_img = load("obstacle_floresta.png", (42, 40))
comida_img = load("obstacle_comida.png", (36, 40))
assombrada_img = load("obstacle_assombrada.png", (40, 40))
sun_img = load("sun.png", (72, 72))
OBSTACLE_IMG = {
    "spike": spike_img, "cactus": cactus_img, "neve": neve_img,
    "vulcao": vulcao_img, "floresta": floresta_img, "comida": comida_img,
    "assombrada": assombrada_img,
}
spring_img = load("spring_tile.png", (48, 30))
flag_img = load("finish_flag.png", (32, 24))

BPM = 150
BEAT_DUR = 60.0 / BPM
BAR_DUR = BEAT_DUR * 4
KICK_BEATS = [0, 0.5, 2, 2.5, 3.5]
SNARE_BEATS = [1, 3]


# --------------------------------------------------------------------------
# GERAÇÃO DA PISTA
# --------------------------------------------------------------------------
def generate_track(seed=None, obstacle_prob=0.5):
    rng = random.Random(seed)
    obstacles, stars = [], []
    oid = 0
    x = 700.0
    while x < TRACK_LENGTH - 400:
        if rng.random() < obstacle_prob:
            pos = rng.randint(0, POSITIONS - 1)
            obstacles.append({"id": oid, "x": x, "pos": pos, "hit_by": set()})
            oid += 1
        if rng.random() < 0.5:
            pos = rng.randint(0, POSITIONS - 1)
            stars.append({"id": oid, "x": x + rng.uniform(60, 140), "pos": pos, "collected": False})
            oid += 1
        x += rng.uniform(160, 260)
    return obstacles, stars


# --------------------------------------------------------------------------
# CORREDOR
# --------------------------------------------------------------------------
class Racer:
    def __init__(self, color, name, pos, is_player=False, skill=1.0):
        self.color = color
        self.name = name
        self.pos = pos
        self.target_pos = pos
        self.pos_visual = float(pos)
        self.is_player = is_player
        self.skill = skill
        self.world_x = 0.0
        self.boost_timer = 0.0   # segundos restantes de boost (tempo real)
        self.stun_timer = 0.0    # segundos restantes de atordoamento (tempo real)
        self.bounce_phase = random.uniform(0, math.pi)
        self.squash_timer = 0
        self.finished = False
        self.finish_rank = None
        self.ai_decision_cooldown = 0
        self.just_boosted = False
        self.just_stunned = False

    def current_speed_mult(self):
        mult = 1.0
        if self.boost_timer > 0:
            mult *= BOOST_MULT
        if self.stun_timer > 0:
            mult *= STUN_MULT
        return mult

    def set_pos(self, pos):
        self.target_pos = max(0, min(POSITIONS - 1, pos))
        self.pos = self.target_pos

    def update(self, obstacles, stars, leader_world_x, dt, moving=True):
        self.just_boosted = False
        self.just_stunned = False
        if self.finished:
            return

        # velocidade em unidades de mundo por segundo (BASE_SPEED é por
        # "frame de 1/60s", então multiplicamos por 60 pra virar taxa/seg)
        if self.is_player:
            speed = (BASE_SPEED * 60.0 * self.skill * self.current_speed_mult()) if moving else 0.0
        else:
            base = BASE_SPEED * 60.0 * self.skill
            diff = leader_world_x - self.world_x
            base += max(-1.6, min(1.6, diff * RUBBER_BAND * BASE_SPEED)) * 60.0
            speed = base * self.current_speed_mult()

        prev_x = self.world_x
        self.world_x += speed * dt
        new_x = self.world_x

        if self.boost_timer > 0:
            self.boost_timer = max(0.0, self.boost_timer - dt)
        if self.stun_timer > 0:
            self.stun_timer = max(0.0, self.stun_timer - dt)

        self.pos_visual += (self.target_pos - self.pos_visual) * min(1.0, 0.22 * (dt * 60.0))

        prev_phase = self.bounce_phase
        idle_bounce = max(0.11 * (speed / (BASE_SPEED * 60.0)), 0.018)
        self.bounce_phase += idle_bounce * (dt * 60.0)
        if int(prev_phase / math.pi) != int(self.bounce_phase / math.pi):
            self.squash_timer = 6
        if self.squash_timer > 0:
            self.squash_timer -= 1

        if not self.is_player:
            self.ai_decision_cooldown -= dt * 60.0
            if self.ai_decision_cooldown <= 0:
                self.ai_decision_cooldown = 20
                lookahead = 220
                danger = any(
                    ob["pos"] == self.target_pos and 0 < ob["x"] - self.world_x < lookahead
                    for ob in obstacles
                )
                if danger:
                    free = [p for p in range(POSITIONS)
                            if not any(ob["pos"] == p and 0 < ob["x"] - self.world_x < lookahead for ob in obstacles)]
                    if free:
                        self.set_pos(random.choice(free))

        # Teste "à prova de pulo": verifica se o espinho/estrela caiu
        # dentro do trecho percorrido neste frame (prev_x -> new_x), não
        # só perto da posição final. Isso evita perder itens quando o
        # jogo engasga e avança um pedaço maior da pista de uma vez.
        seg_lo = min(prev_x, new_x) - COLLIDE_RADIUS
        seg_hi = max(prev_x, new_x) + COLLIDE_RADIUS

        for ob in obstacles:
            if ob["pos"] == self.target_pos and self.id_key() not in ob["hit_by"]:
                if seg_lo <= ob["x"] <= seg_hi:
                    ob["hit_by"].add(self.id_key())
                    self.stun_timer = STUN_SECONDS
                    self.just_stunned = True

        for st in stars:
            if st["collected"]:
                continue
            if st["pos"] == self.target_pos and seg_lo <= st["x"] <= seg_hi:
                st["collected"] = True
                self.boost_timer = BOOST_SECONDS
                self.just_boosted = True

        if self.world_x >= TRACK_LENGTH:
            self.world_x = TRACK_LENGTH
            self.finished = True

    def id_key(self):
        return self.color

    def bob_offset(self):
        return -abs(math.sin(self.bounce_phase)) * BOB_HEIGHT

    def screen_pos(self, cam_x):
        sx = PLAYER_ANCHOR_X + (self.world_x - cam_x)
        lane_y = TRACK_TOP + self.pos_visual * POS_H + POS_H * 0.72
        sy = lane_y + self.bob_offset()
        return sx, sy

    def draw(self, surf, cam_x):
        sx, sy = self.screen_pos(cam_x)
        if -80 < sx < WIDTH + 80:
            if self.squash_timer > 0:
                img = ROBOT_SQUASH_IMG[self.color]
                surf.blit(img, (sx - img.get_width() // 2, sy - img.get_height() + 10))
            else:
                img = ROBOT_IMG[self.color]
                surf.blit(img, (sx - img.get_width() // 2, sy - img.get_height()))
            if self.stun_timer > 0:
                dizzy = font_small.render("*", True, (255, 230, 60))
                surf.blit(dizzy, (sx + 20, sy - img.get_height() - 10))
            if self.boost_timer > 0:
                pygame.draw.polygon(surf, (255, 235, 80),
                                     [(sx - 40, sy - 30), (sx - 30, sy - 22), (sx - 40, sy - 14)])


# --------------------------------------------------------------------------
# DESENHO DE FUNDO / PISTA ÚNICA
# --------------------------------------------------------------------------
def draw_sky_decor(surf, cam_x, decor):
    """Decorações no céu (acima da faixa de chão), específicas de cada tema."""
    if decor == "cidade":
        off = int(cam_x * 0.1) % 260
        rng = random.Random(1)
        x = -260 + (-off)
        i = 0
        while x < WIDTH + 260:
            h = 20 + (i * 37) % 45
            w = 34
            col = (95, 100, 108) if i % 2 == 0 else (110, 115, 122)
            pygame.draw.rect(surf, col, (x, 60 - h, w, h))
            for wy in range(60 - h + 4, 58, 8):
                for wx2 in range(int(x) + 4, int(x) + w - 4, 10):
                    pygame.draw.rect(surf, (255, 230, 140), (wx2, wy, 4, 4))
            x += 46
            i += 1
    elif decor == "deserto":
        sun_x = 26 - int(cam_x * 0.02) % 20
        surf.blit(sun_img, (sun_x, 2))
        dune_off = int(cam_x * 0.12) % 480
        for i in range(-1, 3):
            dx = i * 480 - dune_off
            pygame.draw.ellipse(surf, (235, 200, 140), (dx, TRACK_TOP - 96, 340, 60))
            pygame.draw.ellipse(surf, (245, 215, 160), (dx + 160, TRACK_TOP - 80, 260, 46))
    elif decor == "neve":
        mtn_off = int(cam_x * 0.1) % 460
        for i in range(-1, 3):
            dx = i * 460 - mtn_off
            pygame.draw.polygon(surf, (225, 235, 245), [(dx, 60), (dx + 90, -20), (dx + 180, 60)])
            pygame.draw.polygon(surf, (255, 255, 255), [(dx + 55, 10), (dx + 90, -20), (dx + 125, 10)])
        snow_off = int(cam_x * 0.4) % 40
        for i in range(24):
            sx = (i * 83 - snow_off) % (WIDTH + 40) - 20
            sy = (i * 47) % 60
            pygame.draw.circle(surf, (255, 255, 255), (int(sx), int(sy)), 2)
    elif decor == "caverna":
        stal_off = int(cam_x * 0.15) % 140
        for i in range(-1, 8):
            dx = i * 140 - stal_off
            h = 30 + (i * 17) % 24
            pygame.draw.polygon(surf, (25, 20, 32), [(dx, 0), (dx + 18, 0), (dx + 9, h)])
        glow_off = int(cam_x * 0.2) % 300
        for i in range(-1, 3):
            dx = i * 300 - glow_off + 80
            pygame.draw.circle(surf, (170, 110, 220), (dx, 40), 5)
    elif decor == "vulcao":
        volc_off = int(cam_x * 0.1) % 500
        for i in range(-1, 2):
            dx = i * 500 - volc_off + 200
            pygame.draw.polygon(surf, (60, 30, 28), [(dx - 90, 62), (dx, -10), (dx + 90, 62)])
            pygame.draw.polygon(surf, (255, 140, 50), [(dx - 14, 4), (dx, -10), (dx + 14, 4)])
        smoke_off = int(cam_x * 0.08) % 500
        for i in range(-1, 2):
            dx = i * 500 - smoke_off + 200
            for k in range(3):
                pygame.draw.circle(surf, (90, 80, 80), (dx + k * 6, -6 - k * 10), 10 - k)
    elif decor == "castelo":
        cas_off = int(cam_x * 0.1) % 320
        for i in range(-1, 4):
            dx = i * 320 - cas_off
            pygame.draw.rect(surf, (95, 88, 100), (dx, 20, 26, 42))
            for bx in range(dx, dx + 26, 8):
                pygame.draw.rect(surf, (95, 88, 100), (bx, 14, 5, 8))
            pygame.draw.polygon(surf, (150, 60, 70), [(dx + 13, -2), (dx + 13, 16), (dx + 30, 8)])
    elif decor == "floresta":
        tree_off = int(cam_x * 0.15) % 130
        for i in range(-1, 8):
            dx = i * 130 - tree_off
            h = 24 + (i * 13) % 18
            pygame.draw.circle(surf, (70, 150, 80), (dx, 55 - h), 20)
            pygame.draw.circle(surf, (90, 175, 95), (dx - 8, 50 - h), 14)
    elif decor == "comida":
        off = int(cam_x * 0.12) % 220
        colors = [(255, 190, 210), (255, 225, 150), (190, 220, 255), (200, 255, 200)]
        for i in range(-1, 5):
            dx = i * 220 - off + 60
            col = colors[i % len(colors)]
            pygame.draw.circle(surf, col, (dx, 30), 22)
            pygame.draw.circle(surf, (255, 255, 255), (dx, 30), 22, width=2)
    elif decor == "praia":
        sun_x = 30 - int(cam_x * 0.02) % 20
        surf.blit(sun_img, (sun_x, 2))
        wave_off = int(cam_x * 0.3) % 40
        for wy in range(10, 55, 14):
            for wx in range(-40 + wave_off, WIDTH, 40):
                pygame.draw.arc(surf, (255, 255, 255), (wx, wy, 30, 12), 3.4, 6.0, 2)
    elif decor == "assombrada":
        pygame.draw.circle(surf, (225, 225, 200), (WIDTH - 70, 30), 22)
        bat_off = int(cam_x * 0.2) % 260
        for i in range(-1, 4):
            dx = i * 260 - bat_off + 40
            by = 20 + (i * 23) % 30
            pygame.draw.polygon(surf, (20, 18, 24), [(dx, by), (dx + 8, by - 5), (dx + 16, by),
                                                        (dx + 8, by + 3)])
    elif decor == "lua":
        rng_off = int(cam_x * 0.05)
        for i in range(30):
            sx = (i * 71 - rng_off) % (WIDTH + 20) - 10
            sy = (i * 53) % 58
            pygame.draw.circle(surf, (255, 255, 255), (int(sx), int(sy)), 1 + (i % 2))
        earth_x = WIDTH - 90 - int(cam_x * 0.03) % 30
        pygame.draw.circle(surf, (70, 130, 210), (earth_x, 32), 16)
        pygame.draw.circle(surf, (90, 180, 110), (earth_x - 5, 28), 6)
    elif decor == "ceu":
        cloud_off = int(cam_x * 0.14) % 220
        for i in range(-1, 5):
            cx = i * 220 - cloud_off + 100
            cy = 12 + (i % 3) * 16
            pygame.draw.ellipse(surf, (255, 255, 255), (cx, cy, 90, 30))
            pygame.draw.ellipse(surf, (255, 255, 255), (cx + 36, cy - 10, 60, 26))


def draw_ground_decor(surf, cam_x, decor):
    """Decorações coladas na faixa de chão nas bordas da pista."""
    spacing = 260
    start = int(cam_x // spacing) * spacing - spacing
    wx = start
    i = 0
    while wx < cam_x + WIDTH + spacing:
        sx = PLAYER_ANCHOR_X + (wx - cam_x)
        if -50 < sx < WIDTH + 50:
            if decor == "deserto" or decor == "praia":
                surf.blit(cactus_img, (sx - 23, TRACK_TOP - 62))
                surf.blit(cactus_img, (sx - 23, TRACK_BOTTOM + 22))
            elif decor == "neve":
                pygame.draw.polygon(surf, (60, 110, 90), [(sx, TRACK_TOP - 60), (sx - 16, TRACK_TOP - 12), (sx + 16, TRACK_TOP - 12)])
                pygame.draw.polygon(surf, (60, 110, 90), [(sx, TRACK_BOTTOM + 24), (sx - 16, TRACK_BOTTOM + 68), (sx + 16, TRACK_BOTTOM + 68)])
            elif decor == "caverna":
                pygame.draw.polygon(surf, (55, 48, 65), [(sx - 12, TRACK_TOP - 12), (sx + 12, TRACK_TOP - 12), (sx, TRACK_TOP - 40)])
                pygame.draw.polygon(surf, (55, 48, 65), [(sx - 12, TRACK_BOTTOM + 24), (sx + 12, TRACK_BOTTOM + 24), (sx, TRACK_BOTTOM + 52)])
            elif decor == "floresta":
                img = pygame.transform.smoothscale(floresta_img, (30, 30))
                surf.blit(img, (sx - 15, TRACK_TOP - 44))
                surf.blit(img, (sx - 15, TRACK_BOTTOM + 26))
            elif decor == "castelo":
                pygame.draw.rect(surf, (70, 55, 40), (sx - 2, TRACK_TOP - 40, 4, 30))
                pygame.draw.circle(surf, (255, 170, 60), (sx, TRACK_TOP - 42), 5)
            elif decor == "assombrada":
                img = pygame.transform.smoothscale(assombrada_img, (26, 26))
                surf.blit(img, (sx - 13, TRACK_TOP - 36))
                surf.blit(img, (sx - 13, TRACK_BOTTOM + 26))
            elif decor == "lua":
                pygame.draw.ellipse(surf, (75, 75, 82), (sx - 14, TRACK_TOP - 26, 28, 14))
                pygame.draw.ellipse(surf, (95, 95, 102), (sx - 14, TRACK_BOTTOM + 26, 28, 14))
            elif decor == "vulcao":
                pygame.draw.line(surf, (255, 120, 40), (sx - 14, TRACK_TOP - 14), (sx + 14, TRACK_TOP - 20), 3)
                pygame.draw.line(surf, (255, 120, 40), (sx - 14, TRACK_BOTTOM + 30), (sx + 14, TRACK_BOTTOM + 24), 3)
            elif decor == "comida":
                pygame.draw.circle(surf, (255, 200, 150), (sx, TRACK_TOP - 26), 10)
                pygame.draw.circle(surf, (255, 200, 150), (sx, TRACK_BOTTOM + 40), 10)
            elif decor == "cidade":
                pygame.draw.rect(surf, (70, 70, 75), (sx - 2, TRACK_TOP - 34, 4, 24))
                pygame.draw.circle(surf, (255, 235, 150), (sx, TRACK_TOP - 36), 6)
        wx += spacing
        i += 1


def draw_background(surf, cam_x, theme="cidade"):
    cfg = TRACKS_BY_KEY[theme]
    decor = cfg["decor"]
    sky_top, sky_bottom = cfg["sky_top"], cfg["sky_bottom"]
    for y in range(HEIGHT):
        t = y / HEIGHT
        color = tuple(int(sky_top[i] + (sky_bottom[i] - sky_top[i]) * t) for i in range(3))
        pygame.draw.line(surf, color, (0, y), (WIDTH, y))

    draw_sky_decor(surf, cam_x, decor)

    pygame.draw.rect(surf, cfg["track_color"], (0, TRACK_TOP - 10, WIDTH, TRACK_BOTTOM - TRACK_TOP + 20))
    pygame.draw.rect(surf, cfg["track_edge"], (0, TRACK_TOP - 10, WIDTH, 6))
    pygame.draw.rect(surf, cfg["track_edge"], (0, TRACK_BOTTOM + 14, WIDTH, 6))
    for i in range(1, POSITIONS):
        y = TRACK_TOP + i * POS_H
        dash_off = int(cam_x) % 44
        for x in range(-44 + dash_off, WIDTH, 44):
            pygame.draw.rect(surf, cfg["lane_line"], (x, y - 2, 26, 4))

    # faixa estreita de "chão" colada na pista (deixa o resto do céu
    # aberto e visível, com as decorações de fundo)
    TOP_MARGIN_H = 60
    pygame.draw.rect(surf, cfg["side_color"], (0, TRACK_TOP - 10 - TOP_MARGIN_H, WIDTH, TOP_MARGIN_H))
    pygame.draw.rect(surf, cfg["side_color"], (0, TRACK_BOTTOM + 20, WIDTH, HEIGHT - TRACK_BOTTOM - 20))

    draw_ground_decor(surf, cam_x, decor)

    spacing = 130
    start = int(cam_x // spacing) * spacing - spacing
    for pos in range(POSITIONS):
        lane_y = TRACK_TOP + pos * POS_H + POS_H * 0.86
        wx = start
        while wx < cam_x + WIDTH + spacing:
            sx = PLAYER_ANCHOR_X + (wx - cam_x)
            if -40 < sx < WIDTH + 40:
                surf.blit(spring_img, (sx - spring_img.get_width() // 2, lane_y - 14))
            wx += spacing

    fx = PLAYER_ANCHOR_X + (TRACK_LENGTH - cam_x)
    if -40 < fx < WIDTH + 40:
        pygame.draw.rect(surf, (60, 45, 30), (fx - 6, TRACK_TOP - 10, 12, TRACK_BOTTOM - TRACK_TOP + 20))
        for pos in range(POSITIONS):
            y0 = TRACK_TOP + pos * POS_H
            surf.blit(flag_img, (fx - 6, y0 + 4))
            surf.blit(flag_img, (fx - 6, y0 + POS_H - 28))


def draw_obstacles_and_stars(surf, cam_x, obstacles, stars, t, theme="cidade"):
    ob_img = OBSTACLE_IMG[TRACKS_BY_KEY[theme]["obstacle_sprite"]]
    for ob in obstacles:
        sx = PLAYER_ANCHOR_X + (ob["x"] - cam_x)
        if -60 < sx < WIDTH + 60:
            lane_y = TRACK_TOP + ob["pos"] * POS_H + POS_H * 0.78
            surf.blit(ob_img, (sx - ob_img.get_width() // 2, lane_y - ob_img.get_height() + 8))
    for st in stars:
        if st["collected"]:
            continue
        sx = PLAYER_ANCHOR_X + (st["x"] - cam_x)
        if -60 < sx < WIDTH + 60:
            lane_y = TRACK_TOP + st["pos"] * POS_H + POS_H * 0.5 + math.sin(t * 4 + st["x"]) * 6
            surf.blit(star_img, (sx - star_img.get_width() // 2, lane_y - star_img.get_height() // 2))


def draw_minimap(surf, racers):
    mx0, mx1 = 260, WIDTH - 40
    my = 30
    pygame.draw.rect(surf, (0, 0, 0), (mx0 - 10, my - 12, mx1 - mx0 + 20, 24), border_radius=10)
    pygame.draw.line(surf, (255, 255, 255), (mx0, my), (mx1, my), 4)
    dot_colors = {"yellow": (255, 205, 40), "blue": (70, 150, 240), "red": (235, 80, 70), "green": (80, 200, 120)}
    for r in racers:
        frac = min(1.0, r.world_x / TRACK_LENGTH)
        dx = mx0 + (mx1 - mx0) * frac
        pygame.draw.circle(surf, (30, 20, 10), (int(dx), my), 8)
        pygame.draw.circle(surf, dot_colors[r.color], (int(dx), my), 6)


# --------------------------------------------------------------------------
# EQUALIZADOR EM PIXEL ART
# --------------------------------------------------------------------------
N_BARS = 10
BAR_PIX = 6

# --------------------------------------------------------------------------
# CONTROLES POR TOQUE (celular/tablet sem teclado)
# --------------------------------------------------------------------------
def finger_event_to_logical_pos(event):
    """Converte a posição normalizada (0.0-1.0) de um toque (FINGERDOWN/
    FINGERUP) para coordenadas do NOSSO jogo (960x600). É preciso
    fazer essa conta manualmente porque, no modo tela cheia (SCALED),
    o pygame pode desenhar faixas pretas nas bordas (letterbox) quando
    a proporção da tela do celular é diferente da nossa — e os eventos
    de toque vêm relativos à tela FÍSICA inteira, não à área onde o
    jogo é desenhado de verdade."""
    win_w, win_h = pygame.display.get_window_size()
    scale = min(win_w / WIDTH, win_h / HEIGHT)
    drawn_w, drawn_h = WIDTH * scale, HEIGHT * scale
    offset_x, offset_y = (win_w - drawn_w) / 2, (win_h - drawn_h) / 2

    px, py = event.x * win_w, event.y * win_h
    lx = (px - offset_x) / scale
    ly = (py - offset_y) / scale
    return lx, ly


def race_touch_buttons():
    """Retângulos dos botões de toque durante a corrida."""
    return {
        "move": pygame.Rect(WIDTH - 190, HEIGHT - 190, 170, 170),
        "up": pygame.Rect(18, HEIGHT // 2 - 100, 84, 84),
        "down": pygame.Rect(18, HEIGHT // 2 + 16, 84, 84),
        "mute": pygame.Rect(WIDTH - 54, 54, 42, 42),
    }


def draw_race_touch_buttons(surf, moving, music_enabled):
    btns = race_touch_buttons()

    move = btns["move"]
    col = (90, 220, 140, 210) if moving else (255, 255, 255, 130)
    s = pygame.Surface((move.width, move.height), pygame.SRCALPHA)
    pygame.draw.circle(s, col, (move.width // 2, move.height // 2), move.width // 2)
    pygame.draw.circle(s, (40, 30, 20, 220), (move.width // 2, move.height // 2), move.width // 2, width=4)
    surf.blit(s, move.topleft)
    tri = [(move.centerx - 22, move.centery - 30), (move.centerx - 22, move.centery + 30),
           (move.centerx + 30, move.centery)]
    pygame.draw.polygon(surf, (40, 30, 20), tri)
    lbl = font_small.render("TOQUE", True, (40, 30, 20))
    surf.blit(lbl, lbl.get_rect(center=(move.centerx, move.bottom - 18)))

    for key, arrow in (("up", "▲"), ("down", "▼")):
        r = btns[key]
        s = pygame.Surface((r.width, r.height), pygame.SRCALPHA)
        pygame.draw.rect(s, (255, 255, 255, 140), s.get_rect(), border_radius=14)
        pygame.draw.rect(s, (40, 30, 20, 220), s.get_rect(), width=3, border_radius=14)
        surf.blit(s, r.topleft)
        lbl = font_med.render(arrow, True, (40, 30, 20))
        surf.blit(lbl, lbl.get_rect(center=r.center))

    mute = btns["mute"]
    s = pygame.Surface((mute.width, mute.height), pygame.SRCALPHA)
    pygame.draw.circle(s, (255, 255, 255, 140), (mute.width // 2, mute.height // 2), mute.width // 2)
    pygame.draw.circle(s, (40, 30, 20, 220), (mute.width // 2, mute.height // 2), mute.width // 2, width=2)
    surf.blit(s, mute.topleft)
    icon = font_small.render("♪" if music_enabled else "X", True, (40, 30, 20))
    surf.blit(icon, icon.get_rect(center=mute.center))


def draw_tap_to_continue_button(surf, label, y):
    """Botão de toque genérico (usado em 'começar', 'próxima pista' e
    'voltar ao menu') — sempre no mesmo estilo, centralizado."""
    lbl = font_med.render(label, True, (255, 255, 255))
    pad_x, pad_y = 34, 16
    rect = pygame.Rect(0, 0, lbl.get_width() + pad_x * 2, lbl.get_height() + pad_y * 2)
    rect.center = (WIDTH // 2, y)
    s = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(s, (90, 170, 90, 235), s.get_rect(), border_radius=14)
    pygame.draw.rect(s, (255, 255, 255, 230), s.get_rect(), width=3, border_radius=14)
    surf.blit(s, rect.topleft)
    surf.blit(lbl, lbl.get_rect(center=rect.center))
    return rect

def draw_equalizer(surf, song_time, x, y, enabled, synced=True):
    w = N_BARS * (BAR_PIX * 2)
    h = 12 * BAR_PIX
    panel = pygame.Rect(x - 8, y - 8, w + 16, h + 16)
    pygame.draw.rect(surf, (20, 14, 10), panel, border_radius=6)
    pygame.draw.rect(surf, (235, 205, 90), panel, width=2, border_radius=6)

    bar_pos = (song_time % BAR_DUR) / BEAT_DUR

    for i in range(N_BARS):
        phase = song_time * (2.2 + i * 0.35) + i * 0.7
        base = 0.35 + 0.30 * abs(math.sin(phase))
        punch = 0.0
        if synced:
            # sincronizado com o ritmo conhecido da trilha chiptune gerada
            kick_hit = min(abs((bar_pos - kb + 2) % 4) for kb in KICK_BEATS)
            snare_hit = min(abs((bar_pos - sb + 2) % 4) for sb in SNARE_BEATS)
            if i < 4:
                punch = max(0.0, 0.9 - kick_hit * 6.0)
            elif i >= N_BARS - 4:
                punch = max(0.0, 0.8 - snare_hit * 5.0)
        else:
            # música personalizada (não sabemos o tempo dela): animação
            # genérica, só pra decorar, sem tentar "acertar" a batida
            punch = 0.25 * abs(math.sin(phase * 1.7 + i))
        level = min(1.0, base + punch)
        if not enabled:
            level *= 0.15
        n_blocks = max(1, int(level * 12))
        bx = x + i * (BAR_PIX * 2)
        for b in range(n_blocks):
            by = y + h - (b + 1) * BAR_PIX
            col = (90, 220, 140) if b < 7 else ((250, 210, 60) if b < 10 else (235, 70, 60))
            pygame.draw.rect(surf, col, (bx, by + 1, BAR_PIX * 2 - 2, BAR_PIX - 2))


# --------------------------------------------------------------------------
# TELA DE TÍTULO
# --------------------------------------------------------------------------
def draw_title_screen(surf, t, selected_color_idx, difficulty, track_theme):
    for y in range(HEIGHT):
        tt = y / HEIGHT
        color = tuple(int(SKY_TOP[i] + (SKY_BOTTOM[i] - SKY_TOP[i]) * tt) for i in range(3))
        pygame.draw.line(surf, color, (0, y), (WIDTH, y))
    pygame.draw.rect(surf, (94, 168, 96), (0, HEIGHT - 66, WIDTH, 66))

    bob = math.sin(t * 3) * 5
    title1 = font_title.render("SUPER JUMP", True, (255, 230, 60))
    title2 = font_title.render("RACER", True, (255, 120, 90))
    surf.blit(title1, title1.get_rect(center=(WIDTH // 2, 62 + bob)))
    surf.blit(title2, title2.get_rect(center=(WIDTH // 2, 122 + bob)))

    sub = font_small.render("escolha seu robô, a pista e a dificuldade", True, (60, 50, 40))
    surf.blit(sub, sub.get_rect(center=(WIDTH // 2, 168)))

    # ---- seleção de cor ----
    color_rects = []
    n = len(RACER_COLORS)
    spacing = 132
    start_x = WIDTH // 2 - spacing * (n - 1) / 2
    cy_color = 240
    for i, c in enumerate(RACER_COLORS):
        cx = int(start_x + i * spacing)
        rect = pygame.Rect(cx - 48, cy_color - 48, 96, 96)
        color_rects.append(rect)
        selected = (i == selected_color_idx)
        bg = (255, 250, 220) if selected else (255, 255, 255)
        pygame.draw.rect(surf, bg, rect, border_radius=12)
        pygame.draw.rect(surf, (60, 45, 30), rect, width=4 if selected else 2, border_radius=12)
        icon = ROBOT_ICON[c]
        bob_i = math.sin(t * 3 + i) * (3 if selected else 0)
        surf.blit(icon, (cx - icon.get_width() // 2, cy_color - icon.get_height() // 2 + int(bob_i)))
        lbl = font_small.render(COLOR_LABELS[c], True, (60, 45, 30))
        surf.blit(lbl, lbl.get_rect(center=(cx, cy_color + 60)))

    # ---- seleção de pista (carrossel, já que são 12 opções) ----
    idx = next(i for i, tr in enumerate(TRACKS) if tr["key"] == track_theme)
    cy_track = 372
    card_w, card_h = 168, 84

    def draw_track_card(cx, cfg, big):
        w, h = (card_w, card_h) if big else (card_w - 30, card_h - 20)
        rect = pygame.Rect(cx - w // 2, cy_track - h // 2, w, h)
        bg = cfg["side_color"]
        luminance = 0.299 * bg[0] + 0.587 * bg[1] + 0.114 * bg[2]
        text_col = (255, 255, 255) if luminance < 140 else (40, 30, 20)
        border_col = (245, 245, 235) if luminance < 140 else (60, 45, 30)
        pygame.draw.rect(surf, bg, rect, border_radius=12)
        pygame.draw.rect(surf, border_col, rect, width=4 if big else 2, border_radius=12)
        icon_rect = pygame.Rect(rect.x + 6, rect.y + 6, 34 if big else 26, h - 12)
        pygame.draw.rect(surf, cfg["track_color"], icon_rect, border_radius=6)
        ob_img = OBSTACLE_IMG.get(cfg["obstacle_sprite"])
        if ob_img:
            small = pygame.transform.smoothscale(ob_img, (20, 20) if big else (16, 16))
            surf.blit(small, (icon_rect.centerx - small.get_width() // 2,
                               icon_rect.centery - small.get_height() // 2))
        f = font_track_label if big else font_small
        lbl = f.render(cfg["label"], True, text_col)
        label_area = pygame.Rect(icon_rect.right + 6, rect.y, rect.right - icon_rect.right - 10, rect.height)
        lbl_rect = lbl.get_rect(center=label_area.center)
        if lbl_rect.width > label_area.width:
            lbl = font_small.render(cfg["label"], True, text_col)
            lbl_rect = lbl.get_rect(center=label_area.center)
        surf.blit(lbl, lbl_rect)
        return rect

    prev_cfg = TRACKS[(idx - 1) % len(TRACKS)]
    next_cfg = TRACKS[(idx + 1) % len(TRACKS)]
    draw_track_card(WIDTH // 2 - 230, prev_cfg, big=False)
    track_rect = draw_track_card(WIDTH // 2, TRACKS[idx], big=True)
    draw_track_card(WIDTH // 2 + 230, next_cfg, big=False)

    arrow_l = font_med.render("<", True, (60, 45, 30))
    arrow_r = font_med.render(">", True, (60, 45, 30))
    surf.blit(arrow_l, arrow_l.get_rect(center=(WIDTH // 2 - 320, cy_track)))
    surf.blit(arrow_r, arrow_r.get_rect(center=(WIDTH // 2 + 320, cy_track)))

    dots_y = cy_track + 58
    dot_spacing = 14
    dots_start = WIDTH // 2 - dot_spacing * (len(TRACKS) - 1) / 2
    for i in range(len(TRACKS)):
        col = (60, 45, 30) if i == idx else (255, 255, 255)
        pygame.draw.circle(surf, col, (int(dots_start + i * dot_spacing), dots_y), 4)
        pygame.draw.circle(surf, (60, 45, 30), (int(dots_start + i * dot_spacing), dots_y), 4, width=1)

    track_rects = {"prev_arrow": pygame.Rect(WIDTH // 2 - 360, cy_track - 30, 80, 60),
                   "next_arrow": pygame.Rect(WIDTH // 2 + 280, cy_track - 30, 80, 60),
                   "card": track_rect}

    # ---- seleção de dificuldade ----
    diff_rects = {}
    diff_labels = [("facil", "FÁCIL", "adversários no seu ritmo"),
                   ("dificil", "DIFÍCIL", "adversários mais rápidos")]
    dw, dh = 210, 70
    dspacing = 230
    dstart_x = WIDTH // 2 - dspacing / 2
    cy_diff = 470
    for i, (key, label, desc) in enumerate(diff_labels):
        dx = int(dstart_x + i * dspacing - dw / 2)
        rect = pygame.Rect(dx, cy_diff - dh // 2, dw, dh)
        diff_rects[key] = rect
        selected = (difficulty == key)
        col_map = {"facil": (110, 200, 120), "dificil": (225, 90, 80)}
        bg = col_map[key] if selected else (255, 255, 255)
        pygame.draw.rect(surf, bg, rect, border_radius=12)
        pygame.draw.rect(surf, (60, 45, 30), rect, width=4 if selected else 2, border_radius=12)
        txt_col = (255, 255, 255) if selected else (60, 45, 30)
        lbl = font_med.render(label, True, txt_col)
        surf.blit(lbl, lbl.get_rect(center=(rect.centerx, rect.centery - 13)))
        dsc = font_small.render(desc, True, txt_col)
        surf.blit(dsc, dsc.get_rect(center=(rect.centerx, rect.centery + 16)))

    if IS_ANDROID:
        start_rect = draw_tap_to_continue_button(surf, "COMEÇAR!", HEIGHT - 33)
    else:
        hint = font_med.render("Pressione ENTER para começar!", True, (60, 45, 30))
        surf.blit(hint, hint.get_rect(center=(WIDTH // 2, HEIGHT - 33)))
        start_rect = None

    return color_rects, track_rects, diff_rects, start_rect


# --------------------------------------------------------------------------
# LOOP PRINCIPAL
# --------------------------------------------------------------------------
def new_race(player_color, difficulty, track_key):
    track_cfg = TRACKS_BY_KEY[track_key]
    obstacles, stars = generate_track(obstacle_prob=track_obstacle_prob(track_cfg))
    other_colors = [c for c in RACER_COLORS if c != player_color]
    lo, hi = DIFFICULTY_SKILL[difficulty]
    bonus = track_skill_bonus(track_cfg)
    lo, hi = lo + bonus, hi + bonus

    player = Racer(player_color, "Você", pos=1, is_player=True, skill=1.0)
    ai_positions = [p for p in range(POSITIONS) if p != 1]
    ais = [
        Racer(other_colors[i], f"Robô {COLOR_LABELS[other_colors[i]]}",
              pos=ai_positions[i % len(ai_positions)], skill=random.uniform(lo, hi))
        for i in range(3)
    ]
    return [player] + ais, obstacles, stars


def main():
    global music_on

    STATE_TITLE = "title"
    STATE_COUNTDOWN = "countdown"
    STATE_RACING = "racing"
    STATE_FINISHED = "finished"            # resultado de corrida avulsa (não-campanha)
    STATE_TRACK_RESULT = "track_result"    # resultado de UMA pista dentro da campanha
    STATE_CAMPAIGN_FINISHED = "campaign_finished"  # resultado final das 12 pistas

    state = STATE_TITLE
    selected_color_idx = 0
    difficulty = "facil"
    track_theme = "cidade"

    # ---- campanha (obrigatória quando o jogador começa pela pista 1) ----
    POINTS_TABLE = {1: 5, 2: 4, 3: 3, 4: 2}
    campaign_mode = False
    campaign_idx = 0
    campaign_points = {}
    campaign_player_color = None
    campaign_difficulty = "facil"

    racers, obstacles, stars = None, None, None
    player = None
    race_theme = "cidade"
    countdown_timer = 3.0  # segundos
    t = 0.0
    song_time = 0.0
    results = []
    color_rects, track_rects, diff_rects = [], {}, {}
    start_rect = None
    next_track_rect = None
    menu_rect = None
    touch_moving = False  # controle por toque: segurando o botão "ANDAR"?
    touch_move_finger_id = None  # qual dedo específico está segurando o "ANDAR"

    def start_race(track_key, p_color, diff):
        """(Re)inicia uma corrida numa pista específica, trocando a
        música e resetando o estado da corrida."""
        nonlocal racers, obstacles, stars, player, race_theme, countdown_timer, results, state
        racers, obstacles, stars = new_race(p_color, diff, track_key)
        player = racers[0]
        race_theme = track_key
        track_music_path = find_track_music(TRACKS_BY_KEY[track_key]["n"]) or MUSIC_PATH
        switch_music(track_music_path)
        set_music_volume(0.55 if music_on else 0.0)
        state = STATE_COUNTDOWN
        countdown_timer = 3.0
        results = []

    def begin_race_from_title():
        nonlocal campaign_mode, campaign_idx, campaign_points, campaign_player_color, campaign_difficulty
        player_color = RACER_COLORS[selected_color_idx]
        if track_theme == TRACKS[0]["key"]:
            # começar pela primeira pista obriga a campanha completa,
            # em sequência, até a pista 12
            campaign_mode = True
            campaign_idx = 0
            campaign_points = {c: 0 for c in RACER_COLORS}
            campaign_player_color = player_color
            campaign_difficulty = difficulty
        else:
            campaign_mode = False
        start_race(track_theme, player_color, difficulty)

    running = True
    while running:
        raw_dt = clock.tick(FPS) / 1000.0
        dt = min(raw_dt, MAX_DT)  # trava saltos grandes (engasgos reais)
        t += dt
        song_time += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_m:
                    music_on = not music_on
                    set_music_volume(0.55 if music_on else 0.0)

                if state == STATE_TITLE:
                    if event.key in (pygame.K_LEFT, pygame.K_a):
                        selected_color_idx = (selected_color_idx - 1) % len(RACER_COLORS)
                    elif event.key in (pygame.K_RIGHT, pygame.K_d):
                        selected_color_idx = (selected_color_idx + 1) % len(RACER_COLORS)
                    elif event.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_w, pygame.K_s):
                        difficulty = "dificil" if difficulty == "facil" else "facil"
                    elif event.key == pygame.K_t:
                        idx = next(i for i, tr in enumerate(TRACKS) if tr["key"] == track_theme)
                        mods = pygame.key.get_mods()
                        step = -1 if (mods & pygame.KMOD_SHIFT) else 1
                        track_theme = TRACKS[(idx + step) % len(TRACKS)]["key"]
                        preview_path = find_track_music(TRACKS_BY_KEY[track_theme]["n"]) or MUSIC_PATH
                        switch_music(preview_path)
                        set_music_volume(0.55 if music_on else 0.0)
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                        begin_race_from_title()

                elif state == STATE_RACING:
                    if event.key in (pygame.K_UP, pygame.K_w):
                        player.set_pos(player.target_pos - 1)
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        player.set_pos(player.target_pos + 1)

                elif state == STATE_FINISHED:
                    if event.key == pygame.K_r:
                        state = STATE_TITLE
                        switch_music(MUSIC_PATH)
                        set_music_volume(0.55 if music_on else 0.0)

                elif state == STATE_TRACK_RESULT:
                    if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                        campaign_idx += 1
                        next_track = TRACKS[campaign_idx]["key"]
                        start_race(next_track, campaign_player_color, campaign_difficulty)

                elif state == STATE_CAMPAIGN_FINISHED:
                    if event.key == pygame.K_r:
                        campaign_mode = False
                        state = STATE_TITLE
                        switch_music(MUSIC_PATH)
                        set_music_volume(0.55 if music_on else 0.0)

            elif event.type == pygame.MOUSEBUTTONDOWN and state == STATE_TITLE:
                mx, my = event.pos
                for i, rect in enumerate(color_rects):
                    if rect.collidepoint(mx, my):
                        selected_color_idx = i
                if track_rects:
                    idx = next(i for i, tr in enumerate(TRACKS) if tr["key"] == track_theme)
                    new_idx = None
                    if track_rects["prev_arrow"].collidepoint(mx, my):
                        new_idx = (idx - 1) % len(TRACKS)
                    elif track_rects["next_arrow"].collidepoint(mx, my):
                        new_idx = (idx + 1) % len(TRACKS)
                    if new_idx is not None:
                        track_theme = TRACKS[new_idx]["key"]
                        preview_path = find_track_music(TRACKS[new_idx]["n"]) or MUSIC_PATH
                        switch_music(preview_path)
                        set_music_volume(0.55 if music_on else 0.0)
                for key, rect in diff_rects.items():
                    if rect.collidepoint(mx, my):
                        difficulty = key
                if start_rect and start_rect.collidepoint(mx, my):
                    begin_race_from_title()

            elif event.type == pygame.MOUSEBUTTONDOWN and state == STATE_RACING:
                btns = race_touch_buttons()
                if btns["move"].collidepoint(event.pos):
                    touch_moving = not touch_moving
                elif btns["up"].collidepoint(event.pos):
                    player.set_pos(player.target_pos - 1)
                elif btns["down"].collidepoint(event.pos):
                    player.set_pos(player.target_pos + 1)
                elif btns["mute"].collidepoint(event.pos):
                    music_on = not music_on
                    set_music_volume(0.55 if music_on else 0.0)

            elif event.type == pygame.MOUSEBUTTONDOWN and state == STATE_TRACK_RESULT:
                if next_track_rect and next_track_rect.collidepoint(event.pos):
                    campaign_idx += 1
                    next_track = TRACKS[campaign_idx]["key"]
                    start_race(next_track, campaign_player_color, campaign_difficulty)

            elif event.type == pygame.MOUSEBUTTONDOWN and state in (STATE_FINISHED, STATE_CAMPAIGN_FINISHED):
                if menu_rect and menu_rect.collidepoint(event.pos):
                    campaign_mode = False
                    state = STATE_TITLE
                    switch_music(MUSIC_PATH)
                    set_music_volume(0.55 if music_on else 0.0)

        keys = pygame.key.get_pressed()
        moving_right = keys[pygame.K_RIGHT] or keys[pygame.K_d] or touch_moving

        if state == STATE_COUNTDOWN:
            countdown_timer -= dt
            for r in racers:
                r.bounce_phase += 0.03 * (dt * 60.0)
            if countdown_timer <= 0:
                state = STATE_RACING

        elif state == STATE_RACING:
            leader_x = max(r.world_x for r in racers)
            for r in racers:
                r.update(obstacles, stars, leader_x, dt, moving=moving_right if r.is_player else True)

            just_finished = [r for r in racers if r.finished and r.finish_rank is None]
            just_finished.sort(key=lambda r: -r.world_x)
            for r in just_finished:
                r.finish_rank = len(results) + 1
                results.append(r)

            if player.finished:
                remaining = [r for r in racers if r not in results]
                remaining.sort(key=lambda r: -r.world_x)
                for r in remaining:
                    r.finish_rank = len(results) + 1
                    results.append(r)

                if campaign_mode:
                    for r in racers:
                        campaign_points[r.color] = campaign_points.get(r.color, 0) + \
                            POINTS_TABLE.get(r.finish_rank, 0)
                    if campaign_idx < len(TRACKS) - 1:
                        state = STATE_TRACK_RESULT
                    else:
                        state = STATE_CAMPAIGN_FINISHED
                else:
                    state = STATE_FINISHED

        # ---------------- DESENHO ----------------
        if state == STATE_TITLE:
            color_rects, track_rects, diff_rects, start_rect = draw_title_screen(
                screen, t, selected_color_idx, difficulty, track_theme)
        else:
            cam_x = player.world_x
            draw_background(screen, cam_x, race_theme)
            draw_obstacles_and_stars(screen, cam_x, obstacles, stars, t, race_theme)
            for r in sorted(racers, key=lambda rr: rr.pos_visual):
                r.draw(screen, cam_x)
            draw_minimap(screen, racers)
            draw_equalizer(screen, song_time, WIDTH - 216, HEIGHT - 96, MUSIC_OK and music_on,
                           synced=not USING_CUSTOM_MUSIC)

            live_rank = sorted(racers, key=lambda r: -r.world_x).index(player) + 1
            rank_txt = font_med.render(f"{live_rank}º lugar", True, (255, 255, 255))
            rank_shadow = font_med.render(f"{live_rank}º lugar", True, (0, 0, 0))
            screen.blit(rank_shadow, (18, 62))
            screen.blit(rank_txt, (16, 60))

            dist_txt = font_small.render(f"{int(player.world_x)} / {int(TRACK_LENGTH)} m", True, (255, 255, 255))
            screen.blit(dist_txt, (16, 96))

            if state == STATE_RACING:
                if player.just_boosted:
                    flash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                    flash.fill((90, 255, 140, 60))
                    screen.blit(flash, (0, 0))
                if player.just_stunned:
                    flash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                    flash.fill((255, 70, 60, 70))
                    screen.blit(flash, (0, 0))
                if not moving_right:
                    hint = font_small.render("segure -> pra andar!", True, (255, 235, 120))
                    screen.blit(hint, (16, 122))
                if IS_ANDROID:
                    draw_race_touch_buttons(screen, moving_right, music_on)

            if state == STATE_COUNTDOWN:
                secs = int(countdown_timer) + 1
                label = "VAI!" if countdown_timer <= 0 else str(secs)
                cd_surf = font_big.render(label, True, (255, 240, 60))
                screen.blit(cd_surf, cd_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2)))

            if state == STATE_FINISHED:
                overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 150))
                screen.blit(overlay, (0, 0))
                titles = {1: "VOCÊ VENCEU!", 2: "2º LUGAR!", 3: "3º LUGAR!", 4: "4º LUGAR"}
                title = font_big.render(titles.get(player.finish_rank, "CORRIDA FINALIZADA"), True, (255, 220, 80))
                screen.blit(title, title.get_rect(center=(WIDTH // 2, 150)))
                for i, r in enumerate(results):
                    line = f"{r.finish_rank}º  {r.name}"
                    col = (255, 240, 150) if r.is_player else (255, 255, 255)
                    surf_line = font_med.render(line, True, col)
                    screen.blit(surf_line, surf_line.get_rect(center=(WIDTH // 2, 230 + i * 42)))
                hint = font_small.render("Pressione R para voltar ao menu  |  ESC para sair", True, (230, 230, 230))
                screen.blit(hint, hint.get_rect(center=(WIDTH // 2, HEIGHT - 90 if IS_ANDROID else HEIGHT - 60)))
                menu_rect = draw_tap_to_continue_button(screen, "VOLTAR AO MENU", HEIGHT - 45) if IS_ANDROID else None

            if state == STATE_TRACK_RESULT:
                overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 150))
                screen.blit(overlay, (0, 0))

                cur_track = TRACKS[campaign_idx]
                title = font_big.render(f"PISTA {cur_track['n']} CONCLUÍDA!", True, (255, 220, 80))
                screen.blit(title, title.get_rect(center=(WIDTH // 2, 110)))

                titles = {1: "1º lugar", 2: "2º lugar", 3: "3º lugar", 4: "4º lugar"}
                pts_earned = POINTS_TABLE.get(player.finish_rank, 0)
                place_txt = font_med.render(
                    f"Você: {titles.get(player.finish_rank, '?')}  (+{pts_earned} pontos)", True, (255, 240, 150))
                screen.blit(place_txt, place_txt.get_rect(center=(WIDTH // 2, 172)))

                # placar acumulado até agora, ordenado do maior pro menor
                standings = sorted(racers, key=lambda r: -campaign_points.get(r.color, 0))
                for i, r in enumerate(standings):
                    line = f"{i + 1}º  {r.name} — {campaign_points.get(r.color, 0)} pts"
                    col = (255, 240, 150) if r.is_player else (255, 255, 255)
                    surf_line = font_small.render(line, True, col)
                    screen.blit(surf_line, surf_line.get_rect(center=(WIDTH // 2, 220 + i * 32)))

                next_track = TRACKS[campaign_idx + 1]
                if IS_ANDROID:
                    hint = font_small.render(f"Próxima pista: {next_track['label']}", True, (230, 230, 230))
                    screen.blit(hint, hint.get_rect(center=(WIDTH // 2, HEIGHT - 90)))
                    next_track_rect = draw_tap_to_continue_button(screen, "PRÓXIMA PISTA!", HEIGHT - 45)
                else:
                    hint = font_med.render(f"ENTER para a próxima pista: {next_track['label']}", True, (230, 230, 230))
                    screen.blit(hint, hint.get_rect(center=(WIDTH // 2, HEIGHT - 60)))
                    next_track_rect = None

            if state == STATE_CAMPAIGN_FINISHED:
                overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 170))
                screen.blit(overlay, (0, 0))

                standings = sorted(racers, key=lambda r: -campaign_points.get(r.color, 0))
                player_place = standings.index(player) + 1
                titles = {1: "CAMPEÃO DAS 12 PISTAS!", 2: "2º LUGAR NA CAMPANHA!",
                          3: "3º LUGAR NA CAMPANHA!", 4: "4º LUGAR NA CAMPANHA"}
                title = font_big.render(titles.get(player_place, "CAMPANHA CONCLUÍDA"), True, (255, 220, 80))
                screen.blit(title, title.get_rect(center=(WIDTH // 2, 120)))

                sub = font_small.render("Classificação final (pontos acumulados nas 12 pistas)", True, (230, 230, 230))
                screen.blit(sub, sub.get_rect(center=(WIDTH // 2, 168)))

                for i, r in enumerate(standings):
                    line = f"{i + 1}º  {r.name} — {campaign_points.get(r.color, 0)} pontos"
                    col = (255, 240, 150) if r.is_player else (255, 255, 255)
                    surf_line = font_med.render(line, True, col)
                    screen.blit(surf_line, surf_line.get_rect(center=(WIDTH // 2, 220 + i * 42)))

                hint = font_small.render("Pressione R para voltar ao menu  |  ESC para sair", True, (230, 230, 230))
                screen.blit(hint, hint.get_rect(center=(WIDTH // 2, HEIGHT - 90 if IS_ANDROID else HEIGHT - 60)))
                menu_rect = draw_tap_to_continue_button(screen, "VOLTAR AO MENU", HEIGHT - 45) if IS_ANDROID else None

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
