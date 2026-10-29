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
    - SETA CIMA / W / ESPAÇO -> segure para avançar (câmera atrás do robô)
    - SETA ESQUERDA / A      -> faixa à esquerda
    - SETA DIREITA  / D      -> faixa à direita
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

RACER_COLORS = ["yellow", "blue", "red", "green", "orange", "brown", "black", "purple", "white"]
COLOR_LABELS = {
    "yellow": "Amarelo", "blue": "Azul", "red": "Vermelho", "green": "Verde",
    "orange": "Laranja", "brown": "Marrom", "black": "Preto", "purple": "Roxo",
    "white": "Branco",
}

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

    {"key": "tabuleiro",  "n": 13, "label": "13. Jogos de Tabuleiro",
     "sky_top": (250, 235, 210), "sky_bottom": (255, 248, 232),
     "side_color": (120, 78, 48), "track_color": (238, 222, 190), "track_edge": (170, 140, 100),
     "lane_line": (200, 60, 55), "obstacle_sprite": "tabuleiro", "decor": "tabuleiro"},

    {"key": "laboratorio", "n": 14, "label": "14. Laboratório",
     "sky_top": (205, 225, 235), "sky_bottom": (235, 245, 248),
     "side_color": (150, 160, 168), "track_color": (222, 230, 233), "track_edge": (170, 180, 186),
     "lane_line": (90, 200, 150), "obstacle_sprite": "laboratorio", "decor": "laboratorio"},
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
               "obstacle_comida.png", "obstacle_assombrada.png",
               "obstacle_tabuleiro.png", "obstacle_laboratorio.png"]
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
        "orange": ((255, 140, 30, 255), (255, 185, 110, 255)),
        "brown":  ((140, 95, 55, 255),  (185, 140, 95, 255)),
        "black":  ((55, 55, 60, 255),   (95, 95, 102, 255)),
        "purple": ((150, 80, 200, 255), (195, 140, 230, 255)),
        "white":  ((225, 228, 232, 255), (250, 251, 253, 255)),
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

    # ---- dado (obstáculo da pista Jogos de Tabuleiro) ----
    DICE_PAL = {
        '.': (0, 0, 0, 0), 'D': (40, 30, 25, 255),
        'W': (250, 248, 245, 255), 'w': (225, 222, 218, 255),
        'K': (35, 35, 40, 255), 'R': (215, 55, 50, 255),
    }
    dice_rows = [
        "DDDDDDDDDDDDD.", "DWWWWWWWWWWWD.", "DWK.W.W.WKWWD.",
        "DWWWWWWWWWWWD.", "DWWKWWWWWKWWD.", "DWWWWWWWWWWWD.",
        "DWK.W.W.WKWWD.", "DWWWWWWWWWWWD.", "DWWWWWWWWWWWD.",
        "DWWWKWWWKWWWD.", "DWWWWWWWWWWWD.", "DwwwwwwwwwwwD",
        "DDDDDDDDDDDDD",
    ]
    save_sprite(dice_rows, os.path.join(ASSET_DIR, "obstacle_tabuleiro.png"), DICE_PAL, scale=6)

    # ---- frasco borbulhante (obstáculo da pista Laboratório) ----
    FLASK_PAL = {
        '.': (0, 0, 0, 0), 'D': (35, 40, 45, 255),
        'G': (150, 230, 100, 255), 'g': (200, 250, 150, 255),
        'S': (210, 230, 235, 255), 's': (240, 250, 252, 255),
        'B': (255, 255, 255, 200),
    }
    flask_rows = [
        "....DSSD.......", "....DSSD.......", "....DSSD.......",
        "...DSssSD......", "...DSssSD......", "..DSGggGSD.....",
        ".DSGGgGgGSD....", ".DGGgGGGgGGD...", "DGGgGGBGGgGGD..",
        "DGGGgGGGgGGGD..", "DGgGGGgGGGgGD..", "DGGGgGGGGgGGD..",
        ".DGGGGgGGGGD...", "..DDDDDDDDD....",
    ]
    save_sprite(flask_rows, os.path.join(ASSET_DIR, "obstacle_laboratorio.png"), FLASK_PAL, scale=7)

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


ROBOT_IMG = {c: load(f"robot_{c}.png", (92, 92)) for c in RACER_COLORS}
ROBOT_SQUASH_IMG = {c: load(f"robot_{c}_squash.png", (104, 57)) for c in RACER_COLORS}
ROBOT_ICON = {c: load(f"robot_{c}.png", (56, 56)) for c in RACER_COLORS}
star_img = load("star.png", (32, 32))
spike_img = load("spike.png", (40, 40))
cactus_img = load("cactus.png", (46, 46))
neve_img = load("obstacle_neve.png", (40, 40))
vulcao_img = load("obstacle_vulcao.png", (44, 40))
floresta_img = load("obstacle_floresta.png", (42, 40))
comida_img = load("obstacle_comida.png", (36, 40))
assombrada_img = load("obstacle_assombrada.png", (40, 40))
tabuleiro_img = load("obstacle_tabuleiro.png", (38, 38))
laboratorio_img = load("obstacle_laboratorio.png", (36, 40))
sun_img = load("sun.png", (72, 72))
OBSTACLE_IMG = {
    "spike": spike_img, "cactus": cactus_img, "neve": neve_img,
    "vulcao": vulcao_img, "floresta": floresta_img, "comida": comida_img,
    "assombrada": assombrada_img, "tabuleiro": tabuleiro_img, "laboratorio": laboratorio_img,
}
spring_img = load("spring_tile.png", (48, 30))
flag_img = load("finish_flag.png", (32, 24))

# --------------------------------------------------------------------------
# VISUAL DO MODO HISTÓRIA (zumbis e o VILÃO) — composto por cima dos
# sprites de robô já existentes, usando só desenho do pygame (sem PIL),
# pra não depender de nenhum arquivo de imagem novo em assets/.
# --------------------------------------------------------------------------
def _tint_zombie(img):
    """Aplica um tom verde-pálido no sprite, pra parecer um robô-zumbi."""
    tinted = img.copy()
    tinted.fill((150, 255, 170, 255), special_flags=pygame.BLEND_RGBA_MULT)
    return tinted


def _load_zombie(c, squash):
    """Zumbi 3D (assets/zombie_<cor>.png); se não existir, tinge o robô."""
    name = f"zombie_{c}_squash.png" if squash else f"zombie_{c}.png"
    try:
        return load(name, (104, 57) if squash else (92, 92))
    except (FileNotFoundError, pygame.error):
        return _tint_zombie(ROBOT_SQUASH_IMG[c] if squash else ROBOT_IMG[c])


ZOMBIE_IMG = {c: _load_zombie(c, False) for c in RACER_COLORS}
ZOMBIE_SQUASH_IMG = {c: _load_zombie(c, True) for c in RACER_COLORS}


def _bico_vector(surf, cx, by, s, t, mood, facing, press, remote):
    """Desenho vetorial do Bicoliso (chamado por draw_bicoliso, que o
    "pixeliza"). Unidades: 1.0 de escala ≈ 210 px de altura."""
    f = facing
    lw = lambda v: max(1, int(v * s))

    def P(dx, dy):
        return (int(cx + f * dx * s), int(by - dy * s))

    pink, pink_d = (240, 140, 150), (200, 95, 115)
    brown, brown_d = (88, 60, 52), (52, 34, 32)
    coat, coat_d = (226, 233, 240), (130, 145, 165)
    yellow, yellow_d = (244, 196, 44), (176, 128, 24)
    laugh = (mood == "laugh")
    tilt = math.sin(t * 14) * 4 if laugh else math.sin(t * 3) * 2

    # penas escuras da cauda (atrás do corpo)
    pygame.draw.polygon(surf, brown_d, [P(-22, 96), P(-62, 84), P(-48, 70), P(-66, 56),
                                         P(-44, 50), P(-58, 36), P(-24, 46)])
    pygame.draw.polygon(surf, brown, [P(-22, 92), P(-54, 82), P(-42, 68), P(-56, 56), P(-26, 54)])
    # pernas finas
    for off in (-14, 16):
        pygame.draw.line(surf, pink, P(off * 0.7, 56), P(off, 20), lw(6))
    # botas grandes com fivela
    for off in (-14, 16):
        boot = [P(off - 13, 20), P(off + 5, 20), P(off + 20, 12), P(off + 28, 6),
                P(off + 26, 0), P(off - 13, 0)]
        pygame.draw.polygon(surf, (112, 72, 46), boot)
        pygame.draw.polygon(surf, brown_d, boot, lw(2))
        pygame.draw.line(surf, (190, 150, 90), P(off - 12, 14), P(off + 6, 14), lw(3))
        pygame.draw.rect(surf, (210, 190, 120), pygame.Rect(P(off - 2, 17)[0] - lw(2), P(off - 2, 17)[1],
                                                           lw(4), lw(6)))
    # peito emplumado marrom
    chest = pygame.Rect(0, 0, lw(58), lw(66))
    chest.center = P(2, 80)
    pygame.draw.ellipse(surf, brown, chest)
    pygame.draw.ellipse(surf, brown_d, chest, lw(2))
    # jaleco rasgado (duas abas, abertas no meio)
    left = [P(-36, 104), P(-4, 104), P(-8, 34), P(-18, 42), P(-26, 28), P(-32, 44), P(-40, 36)]
    right = [P(10, 104), P(38, 100), P(42, 44), P(34, 30), P(26, 46), P(18, 32), P(12, 42)]
    for flap in (left, right):
        pygame.draw.polygon(surf, coat, flap)
        pygame.draw.polygon(surf, coat_d, flap, lw(2))
    pygame.draw.rect(surf, coat_d, pygame.Rect(*P(-30, 78), lw(12), lw(9)), lw(1))  # bolso
    # pescoço fino e curvo
    neck = [P(6, 104), P(18, 128), P(8, 152), P(18 + tilt, 174)]
    for a, b in zip(neck[:-1], neck[1:]):
        pygame.draw.line(surf, pink, a, b, lw(10))
    for p in neck:
        pygame.draw.circle(surf, pink, p, max(2, int(5 * s)))
    # cabeça
    head = P(22 + tilt, 188)
    pygame.draw.circle(surf, pink, head, lw(21))
    pygame.draw.circle(surf, pink_d, head, lw(21), lw(2))
    # bico grande, amarelo, curvado pra baixo
    op = 9 if (laugh and math.sin(t * 14) > -0.2) else 0
    top = [P(34 + tilt, 192 + op), P(66 + tilt, 190 + op), P(86 + tilt, 170 + op),
           P(90 + tilt, 148 + op), P(78 + tilt, 158 + op), P(58 + tilt, 170 + op), P(34 + tilt, 172 + op)]
    if op:
        pygame.draw.polygon(surf, (140, 40, 55), [P(34 + tilt, 172), P(70 + tilt, 166), P(34 + tilt, 160)])
        low = [P(34 + tilt, 166), P(62 + tilt, 158), P(78 + tilt, 140), P(66 + tilt, 148), P(34 + tilt, 156)]
        pygame.draw.polygon(surf, yellow_d, low)
    pygame.draw.polygon(surf, yellow, top)
    pygame.draw.polygon(surf, yellow_d, top, lw(2))
    pygame.draw.line(surf, yellow_d, P(36 + tilt, 182 + op), P(78 + tilt, 166 + op), lw(2))
    # olho
    eye = P(32 + tilt, 190)
    pygame.draw.circle(surf, (255, 255, 255), eye, max(2, int(5 * s)))
    pygame.draw.circle(surf, (30, 20, 30), (eye[0] + int(f * s), eye[1]), max(1, int(2.5 * s)))
    # óculos steampunk na testa (lentes com luzinhas verde/vermelha)
    pygame.draw.line(surf, (50, 55, 62), P(-2 + tilt, 200), P(44 + tilt, 205), lw(8))
    for (gx, gy, r, col) in ((8, 201, 7, (230, 70, 60)), (24, 204, 11, (70, 235, 100)),
                              (40, 205, 6, (255, 210, 70))):
        c = P(gx + tilt, gy)
        pygame.draw.circle(surf, (72, 78, 88), c, max(3, int(r * 1.3 * s)))
        pygame.draw.circle(surf, col, c, max(2, int(r * s)))
    # bravo: sobrancelha + fumaça
    if mood == "angry":
        pygame.draw.line(surf, (190, 35, 35), P(14 + tilt, 196), P(42 + tilt, 188), lw(4))
        for k in range(3):
            puff = P(-6 + k * 14, 222 + (t * 45 + k * 22) % 40)
            pygame.draw.circle(surf, (235, 235, 240), puff, max(2, int((5 + k) * s)))

    rp = None
    if remote:
        # braço rosa saindo da manga do jaleco
        pygame.draw.line(surf, coat, P(26, 100), P(48, 108), lw(11))
        pygame.draw.line(surf, pink, P(48, 108), P(62, 112), lw(6))
        box = [P(56, 102), P(76, 104), P(75, 126), P(55, 124)]
        pygame.draw.polygon(surf, (60, 66, 82), box)
        pygame.draw.polygon(surf, (150, 160, 175), box, lw(2))
        for (dx, dy, col) in ((60, 118, (230, 70, 60)), (66, 118, (250, 210, 70)), (72, 118, (80, 160, 240))):
            pygame.draw.circle(surf, col, P(dx, dy), max(1, int(2.2 * s)))
        rp = P(65, 108)
        pygame.draw.circle(surf, (235, 45, 45), rp, max(2, int(5 * s)))
        pygame.draw.line(surf, (60, 66, 82), P(66, 126), P(70, 138), lw(2))
        pygame.draw.circle(surf, (110, 255, 130), P(70, 139), max(2, int(3 * s)))
        if press:
            pygame.draw.circle(surf, (255, 240, 120), rp, max(3, int(12 * s)), lw(3))
            for k in range(6):
                a = k * math.pi / 3 + t * 6
                pygame.draw.line(surf, (255, 240, 120), rp,
                                 (int(rp[0] + math.cos(a) * 20 * s), int(rp[1] + math.sin(a) * 20 * s)), lw(2))
    return rp


def _draw_bicoliso_vector(surf, cx, by, s=1.0, t=0.0, mood="normal", facing=1,
                  press=False, remote=True):
    """Desenha o PROFESSOR BICOLISO — flamingo cientista maluco (jaleco
    rasgado, óculos steampunk, botas enormes e um controle remoto) — só
    com formas do pygame, "pixelizado" pra combinar com o resto do jogo.
    (cx, by) = centro dos pés. s = escala (1.0 ≈ 210 px de altura).
    facing: +1 olha pra direita, -1 pra esquerda.
    mood: "normal", "angry" (bravo, soltando fumaça) ou "laugh" (gargalhando).
    Devolve a posição do botão do controle remoto (ou None)."""
    k = 3 if s >= 0.6 else (2 if s >= 0.4 else 1)
    tw = int(310 * s / k) + 4
    th = int(255 * s / k) + 4
    tmp = pygame.Surface((tw, th), pygame.SRCALPHA)
    rp = _bico_vector(tmp, tw / 2.0, th - 2, s / k, t, mood, facing, press, remote)
    big = pygame.transform.scale(tmp, (tw * k, th * k)) if k > 1 else tmp
    ox = int(cx - tw * k / 2.0)
    oy = int(by - (th - 2) * k)
    surf.blit(big, (ox, oy))
    if rp is None:
        return None
    return (ox + rp[0] * k, oy + rp[1] * k)


# Arte oficial do Professor Bicoliso (assets/bicoliso.png, com fundo
# transparente). Se o arquivo não estiver na pasta assets/, o jogo usa o
# desenho feito por código (mais simples), então nunca quebra.
try:
    BICO_PHOTO = load("bicoliso.png")
except (FileNotFoundError, pygame.error):
    BICO_PHOTO = None
_BICO_CACHE = {}
_BICO_HAND = (0.45, 0.45)   # onde fica o controle na imagem (fração de largura/altura)


def _bico_scaled(h, flip, red):
    key = (h, flip, red)
    if key not in _BICO_CACHE:
        w = max(1, int(BICO_PHOTO.get_width() * h / BICO_PHOTO.get_height()))
        img = pygame.transform.smoothscale(BICO_PHOTO, (w, h))
        if flip:
            img = pygame.transform.flip(img, True, False)
        if red:
            img = img.copy()
            img.fill((70, 0, 0, 0), special_flags=pygame.BLEND_RGB_ADD)
        _BICO_CACHE[key] = img
    return _BICO_CACHE[key]


def _draw_bicoliso_photo(surf, cx, by, s, t, mood, facing, press, remote):
    h = max(8, int(250 * s))
    flip = (facing == 1)           # a arte original olha pra ESQUERDA
    img = _bico_scaled(h, flip, mood == "angry")
    laugh = (mood == "laugh")
    bounce = -abs(math.sin(t * 14)) * 7 * s if laugh else 0
    angle = math.sin(t * 14) * 5 if laugh else math.sin(t * 3) * 1.2
    rot = pygame.transform.rotate(img, angle) if abs(angle) > 0.2 else img
    rect = rot.get_rect(midbottom=(int(cx), int(by + bounce)))
    surf.blit(rot, rect)
    if mood == "angry":
        for k in range(3):
            puff = (int(cx + (k - 1) * 18 * s), int(by - h - 6 * s - (t * 45 + k * 22) % 40))
            pygame.draw.circle(surf, (235, 235, 240), puff, max(2, int((5 + k) * s)))
    if not remote:
        return None
    nx = (1 - _BICO_HAND[0]) if flip else _BICO_HAND[0]
    rp = (int(rect.left + nx * rect.width), int(rect.top + _BICO_HAND[1] * rect.height))
    if press:
        pygame.draw.circle(surf, (255, 240, 120), rp, max(4, int(14 * s)), 3)
        for k in range(6):
            a = k * math.pi / 3 + t * 6
            pygame.draw.line(surf, (255, 240, 120), rp,
                             (int(rp[0] + math.cos(a) * 24 * s), int(rp[1] + math.sin(a) * 24 * s)), 3)
    return rp


def draw_bicoliso(surf, cx, by, s=1.0, t=0.0, mood="normal", facing=1,
                  press=False, remote=True):
    """Professor Bicoliso (arte oficial se existir, senão o desenho de código).
    (cx, by) = centro dos pés; facing +1 olha pra direita, -1 pra esquerda;
    mood: "normal", "angry" ou "laugh". Devolve a posição do controle."""
    if BICO_PHOTO is not None:
        return _draw_bicoliso_photo(surf, cx, by, s, t, mood, facing, press, remote)
    return _draw_bicoliso_vector(surf, cx, by, s, t, mood, facing, press, remote)


def _build_bicoliso_sprite():
    if BICO_PHOTO is not None:
        return pygame.transform.flip(pygame.transform.smoothscale(BICO_PHOTO, (46, 82)), True, False)
    img = pygame.Surface((74, 74), pygame.SRCALPHA)
    draw_bicoliso(img, 32, 73, s=0.33, facing=1, remote=False)
    return img


VILLAIN_IMG = _build_bicoliso_sprite()
VILLAIN_SQUASH_IMG = pygame.transform.smoothscale(VILLAIN_IMG, (84, 46))

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
    def __init__(self, color, name, pos, is_player=False, skill=1.0,
                 is_zombie=False, is_villain=False):
        self.color = color
        self.name = name
        self.pos = pos
        self.target_pos = pos
        self.pos_visual = float(pos)
        self.is_player = is_player
        self.skill = skill
        self.is_zombie = is_zombie    # modo HISTÓRIA, Cenário 1: anda devagar e errático
        self.is_villain = is_villain  # modo HISTÓRIA, Cenário 2: o VILÃO perseguido
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
        elif self.is_zombie:
            # zumbis sempre mais lentos que o jogador, sem "elástico" com o
            # líder — é pra serem alcançados, não pra competir pela corrida.
            base = BASE_SPEED * 60.0 * self.skill * 0.72
            speed = base * self.current_speed_mult()
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
                self.ai_decision_cooldown = 12 if self.is_zombie else 20
                lookahead = 220
                danger = any(
                    ob["pos"] == self.target_pos and 0 < ob["x"] - self.world_x < lookahead
                    for ob in obstacles
                )
                # zumbis também trocam de posição "sem motivo" de vez em
                # quando, de forma errática — reforça o jeito "zumbi" de
                # andar, mesmo sem nenhum obstáculo por perto.
                shamble = self.is_zombie and random.random() < 0.4
                if danger or shamble:
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
            if self.is_villain:
                normal_img, squash_img = VILLAIN_IMG, VILLAIN_SQUASH_IMG
            elif self.is_zombie:
                normal_img, squash_img = ZOMBIE_IMG[self.color], ZOMBIE_SQUASH_IMG[self.color]
            else:
                normal_img, squash_img = ROBOT_IMG[self.color], ROBOT_SQUASH_IMG[self.color]
            if self.squash_timer > 0:
                img = squash_img
                surf.blit(img, (sx - img.get_width() // 2, sy - img.get_height() + 10))
            else:
                img = normal_img
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
    elif decor == "tabuleiro":
        # cartas de baralho e pecas de xadrez flutuando no "ceu" da mesa
        off = int(cam_x * 0.12) % 240
        card_colors = [(230, 60, 60), (40, 40, 45), (230, 60, 60), (40, 40, 45)]
        for i in range(-1, 5):
            dx = i * 240 - off + 60
            cy = 14 + (i % 2) * 20
            col = card_colors[i % len(card_colors)]
            pygame.draw.rect(surf, (250, 248, 240), (dx, cy, 26, 36), border_radius=3)
            pygame.draw.rect(surf, (60, 45, 30), (dx, cy, 26, 36), width=2, border_radius=3)
            pygame.draw.circle(surf, col, (dx + 13, cy + 18), 7)
        piece_off = int(cam_x * 0.18) % 300
        for i in range(-1, 3):
            dx = i * 300 - piece_off + 200
            pygame.draw.polygon(surf, (50, 45, 40), [(dx - 10, 58), (dx + 10, 58), (dx + 5, 20), (dx - 5, 20)])
            pygame.draw.circle(surf, (50, 45, 40), (dx, 16), 8)
    elif decor == "laboratorio":
        # bolhas subindo e uma helice de DNA estilizada ao fundo
        bub_off = int(cam_x * 0.3) % 40
        for i in range(20):
            sx = (i * 61 - bub_off) % (WIDTH + 30) - 15
            sy = 55 - ((i * 37 + int(cam_x * 0.5)) % 55)
            r = 2 + (i % 3)
            pygame.draw.circle(surf, (150, 220, 235), (int(sx), int(sy)), r, width=1)
        dna_off = int(cam_x * 0.1) % 200
        for i in range(-1, 5):
            dx = i * 200 - dna_off + 100
            for k in range(6):
                yk = 4 + k * 9
                spread = 14 * math.sin(k * 0.9)
                pygame.draw.line(surf, (120, 200, 160), (dx - spread, yk), (dx + spread, yk), 2)
                pygame.draw.circle(surf, (90, 170, 220), (int(dx - spread), yk), 2)
                pygame.draw.circle(surf, (230, 110, 130), (int(dx + spread), yk), 2)


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
            elif decor == "tabuleiro":
                img = pygame.transform.smoothscale(tabuleiro_img, (26, 26))
                surf.blit(img, (sx - 13, TRACK_TOP - 38))
                surf.blit(img, (sx - 13, TRACK_BOTTOM + 26))
            elif decor == "laboratorio":
                img = pygame.transform.smoothscale(laboratorio_img, (24, 26))
                surf.blit(img, (sx - 12, TRACK_TOP - 40))
                surf.blit(img, (sx - 12, TRACK_BOTTOM + 26))
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


# --------------------------------------------------------------------------
# CORRIDA EM PERSPECTIVA (câmera atrás do robô, pseudo-3D)
# A lógica do jogo (world_x, faixas, colisões) é a mesma de sempre; só o
# DESENHO muda: a pista foge pro horizonte e os corredores aparecem de costas.
# --------------------------------------------------------------------------
PERSPECTIVE = True
P_HOR = TRACK_TOP - 10        # linha do horizonte (y)
P_G = 300.0                   # "altura da câmera" em pixels
P_ZREF = 260.0                # distância (mundo) da câmera ao jogador (escala 1.0)
P_LANEW = 118.0               # largura de uma faixa (pixels) na escala 1.0
P_CX = WIDTH // 2
P_VIEW = 2100.0               # alcance da visão
P_STEP = 2                    # altura (px) de cada fatia do chão

def _load_back(name, fallback):
    try:
        return load(name)
    except (FileNotFoundError, pygame.error):
        return fallback

ROBOT_BACK = {c: _load_back(f"robotb_{c}.png", ROBOT_IMG[c]) for c in RACER_COLORS}
ZOMBIE_BACK = {c: _load_back(f"zombieb_{c}.png", ZOMBIE_IMG[c]) for c in RACER_COLORS}
VILLAIN_BACK = _load_back("bicoliso_back.png", VILLAIN_IMG)

_P_ROWS = [(y, (y - P_HOR) / P_G) for y in range(P_HOR + P_STEP, HEIGHT, P_STEP)]
_P_SKY_CACHE = {}
_P_COLOR_CACHE = {}
_P_SHADOW = None


def _mix(a, b, k):
    return (int(a[0] + (b[0] - a[0]) * k), int(a[1] + (b[1] - a[1]) * k), int(a[2] + (b[2] - a[2]) * k))


def _p_row_colors(theme, band):
    key = (theme, band)
    if key not in _P_COLOR_CACHE:
        cfg = TRACKS_BY_KEY[theme]
        fog = cfg["sky_bottom"]
        dark = 0.94 if band else 1.0
        rows = []
        for y, s in _P_ROWS:
            z = P_ZREF / s
            f = min(0.85, (z / P_VIEW) ** 1.3)
            ground = _mix(tuple(int(v * (0.96 if band else 1.0)) for v in cfg["side_color"]), fog, f)
            road = _mix(tuple(int(v * dark) for v in cfg["track_color"]), fog, f)
            edge = _mix(cfg["track_edge"], fog, f)
            line = _mix(cfg["lane_line"], fog, f)
            rows.append((ground, road, edge, line))
        _P_COLOR_CACHE[key] = rows
    return _P_COLOR_CACHE[key]


def _p_sky(surf, cam_x, theme):
    cfg = TRACKS_BY_KEY[theme]
    if theme not in _P_SKY_CACHE:
        g = pygame.Surface((WIDTH, P_HOR + 1))
        for y in range(P_HOR + 1):
            t = y / HEIGHT
            g.fill(tuple(int(cfg["sky_top"][i] + (cfg["sky_bottom"][i] - cfg["sky_top"][i]) * t) for i in range(3)),
                   (0, y, WIDTH, 1))
        _P_SKY_CACHE[theme] = g
    surf.blit(_P_SKY_CACHE[theme], (0, 0))
    old_clip = surf.get_clip()
    surf.set_clip(pygame.Rect(0, 0, WIDTH, P_HOR + 1))
    draw_sky_decor(surf, cam_x, cfg["decor"])
    pygame.draw.rect(surf, cfg["side_color"], (0, P_HOR - 56, WIDTH, 60))
    draw_ground_decor(surf, cam_x, cfg["decor"])
    surf.set_clip(old_clip)


def _p_lane_x(lane, s, cam_lane):
    return P_CX + (lane - cam_lane) * P_LANEW * s


def _p_ground(surf, cam_world, cam_lane, theme):
    band_len = 70.0
    for idx, (y, s) in enumerate(_P_ROWS):
        z = P_ZREF / s
        w = cam_world + z
        band = int(w // band_len) & 1
        ground, road, edge, line = _p_row_colors(theme, band)[idx]
        pygame.draw.rect(surf, ground, (0, y, WIDTH, P_STEP))
        xl = _p_lane_x(-0.5, s, cam_lane)
        xr = _p_lane_x(3.5, s, cam_lane)
        ew = max(2.0, 0.09 * P_LANEW * s)
        pygame.draw.rect(surf, edge, (xl - ew, y, xr - xl + 2 * ew, P_STEP))
        pygame.draw.rect(surf, road, (xl, y, xr - xl, P_STEP))
        if int(w // 36.0) & 1 == 0:
            lw = max(1.0, 0.045 * P_LANEW * s)
            for k in (0.5, 1.5, 2.5):
                lx = _p_lane_x(k, s, cam_lane)
                pygame.draw.rect(surf, line, (lx - lw, y, lw * 2, P_STEP))


def _p_blit(surf, img, x, y, h, fog=0.0, angle=0.0, squash=1.0):
    """Desenha img com altura h (px), pés em (x, y)."""
    h = int(h)
    if h < 3 or h > 1400:
        return
    w = max(1, int(img.get_width() * h / img.get_height() * (1.0 + (1.0 - squash) * 0.6)))
    hh = max(1, int(h * squash))
    sc = pygame.transform.smoothscale(img, (w, hh)) if h > 24 else pygame.transform.scale(img, (w, hh))
    if abs(angle) > 0.5:
        sc = pygame.transform.rotate(sc, angle)
    if fog > 0.02:
        sc.set_alpha(int(255 * (1 - fog)))
    surf.blit(sc, sc.get_rect(midbottom=(int(x), int(y))))


def _p_shadow(surf, x, y, wpx, hpx):
    global _P_SHADOW
    if _P_SHADOW is None:
        _P_SHADOW = pygame.Surface((64, 20), pygame.SRCALPHA)
        pygame.draw.ellipse(_P_SHADOW, (0, 0, 0, 90), (0, 0, 64, 20))
    wpx, hpx = int(wpx), int(hpx)
    if wpx > 2 and hpx > 1:
        sh = pygame.transform.scale(_P_SHADOW, (wpx, hpx))
        surf.blit(sh, sh.get_rect(center=(int(x), int(y))))


def draw_race_perspective(surf, player, racers, obstacles, stars, t, theme):
    cam_world = player.world_x - P_ZREF
    cam_lane = 1.5 + (player.pos_visual - 1.5) * 0.55
    cfg = TRACKS_BY_KEY[theme]
    _p_sky(surf, player.world_x, theme)
    _p_ground(surf, cam_world, cam_lane, theme)

    items = []   # (z, tipo, dado)
    zmin, zmax = 70.0, P_VIEW
    for ob in obstacles:
        z = ob["x"] - cam_world
        if zmin < z < zmax:
            items.append((z, "ob", ob))
    for st in stars:
        if not st["collected"]:
            z = st["x"] - cam_world
            if zmin < z < zmax:
                items.append((z, "st", st))
    for r in racers:
        z = r.world_x - cam_world
        if zmin < z < zmax:
            items.append((z, "rc", r))
    post = (int((cam_world + zmin) // 150) + 1) * 150
    while post - cam_world < zmax:
        items.append((post - cam_world, "post", None))
        post += 150
    zf = TRACK_LENGTH - cam_world
    if zmin < zf < zmax:
        items.append((zf, "fin", None))
    items.sort(key=lambda it: -it[0])

    ob_img = OBSTACLE_IMG[cfg["obstacle_sprite"]]
    for z, kind, d in items:
        s = P_ZREF / z
        gy = P_HOR + P_G * s
        if gy > HEIGHT + 260:
            continue
        fog = min(0.85, (z / P_VIEW) ** 1.3)
        if kind == "post":
            for lane in (-0.95, 3.95):
                x = _p_lane_x(lane, s, cam_lane)
                ph = 70 * s
                col = _mix(cfg["track_edge"], cfg["sky_bottom"], fog)
                pygame.draw.rect(surf, col, (x - 3 * s, gy - ph, max(2, 6 * s), ph))
                pygame.draw.circle(surf, _mix(cfg["lane_line"], cfg["sky_bottom"], fog),
                                   (int(x), int(gy - ph)), max(2, int(8 * s)))
        elif kind == "fin":
            x0, x1 = _p_lane_x(-0.5, s, cam_lane), _p_lane_x(3.5, s, cam_lane)
            s2 = P_ZREF / (z + 28)
            gy2 = P_HOR + P_G * s2
            n = 12
            for i in range(n):
                xa = x0 + (x1 - x0) * i / n
                xb = x0 + (x1 - x0) * (i + 1) / n
                xa2 = _p_lane_x(-0.5 + 4.0 * i / n, s2, cam_lane)
                xb2 = _p_lane_x(-0.5 + 4.0 * (i + 1) / n, s2, cam_lane)
                col = (250, 250, 250) if i % 2 == 0 else (20, 20, 20)
                pygame.draw.polygon(surf, col, [(xa, gy), (xb, gy), (xb2, gy2), (xa2, gy2)])
            ph = 190 * s
            for xx in (x0 - 8 * s, x1 + 8 * s):
                pygame.draw.rect(surf, (60, 45, 30), (xx - 5 * s, gy - ph, max(3, 10 * s), ph))
            bh = 34 * s
            cells = 14
            for i in range(cells):
                for j in range(2):
                    col = (250, 250, 250) if (i + j) % 2 == 0 else (20, 20, 20)
                    cw = (x1 - x0 + 16 * s) / cells
                    pygame.draw.rect(surf, col, (x0 - 8 * s + i * cw, gy - ph + j * bh / 2, cw + 1, bh / 2 + 1))
        elif kind == "ob":
            x = _p_lane_x(d["pos"], s, cam_lane)
            _p_shadow(surf, x, gy, 52 * s, 14 * s)
            _p_blit(surf, ob_img, x, gy + 4 * s, ob_img.get_height() * 2.3 * s, fog)
        elif kind == "st":
            x = _p_lane_x(d["pos"], s, cam_lane)
            _p_shadow(surf, x, gy, 40 * s, 10 * s)
            hov = (46 + math.sin(t * 4 + d["x"]) * 8) * s
            _p_blit(surf, star_img, x, gy - hov + 36 * s, 62 * s, fog)
        else:   # corredor
            r = d
            x = _p_lane_x(r.pos_visual, s, cam_lane)
            y = gy + r.bob_offset() * s * 1.4
            if r.is_villain:
                img, h = VILLAIN_BACK, 175 * s
            elif r.is_zombie:
                img, h = ZOMBIE_BACK[r.color], 120 * s
            else:
                img, h = ROBOT_BACK[r.color], 120 * s
            _p_shadow(surf, x, gy, 70 * s, 18 * s)
            lean = (r.target_pos - r.pos_visual) * -8.0
            if r.boost_timer > 0:
                for k in range(3):
                    fy = y + (6 + k * 7) * s
                    pygame.draw.polygon(surf, (255, 190 - k * 40, 40),
                                        [(x - 12 * s, fy - 6 * s), (x + 12 * s, fy - 6 * s), (x, fy + (14 + k * 5) * s)])
            _p_blit(surf, img, x, y, h, fog, angle=lean, squash=0.9 if r.squash_timer > 0 else 1.0)
            if r.stun_timer > 0:
                dizzy = font_small.render("*", True, (255, 230, 60))
                surf.blit(dizzy, (x + 18 * s, y - h - 8))
            if r.is_player:
                pygame.draw.polygon(surf, (255, 230, 60),
                                    [(x - 9, y - h - 22), (x + 9, y - h - 22), (x, y - h - 8)])
                pygame.draw.polygon(surf, (60, 40, 10),
                                    [(x - 9, y - h - 22), (x + 9, y - h - 22), (x, y - h - 8)], 2)


def draw_minimap(surf, racers):
    mx0, mx1 = 260, WIDTH - 40
    my = 30
    pygame.draw.rect(surf, (0, 0, 0), (mx0 - 10, my - 12, mx1 - mx0 + 20, 24), border_radius=10)
    pygame.draw.line(surf, (255, 255, 255), (mx0, my), (mx1, my), 4)
    dot_colors = {
        "yellow": (255, 205, 40), "blue": (70, 150, 240), "red": (235, 80, 70), "green": (80, 200, 120),
        "orange": (255, 140, 30), "brown": (140, 95, 55), "black": (55, 55, 60),
        "purple": (150, 80, 200), "white": (225, 228, 232),
        "villain": (250, 130, 170),
    }
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
        "up": pygame.Rect(18, HEIGHT - 110, 84, 84),
        "down": pygame.Rect(116, HEIGHT - 110, 84, 84),
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
        c = r.center
        if PERSPECTIVE:   # setas pra esquerda / direita
            d = -1 if key == "up" else 1
            pygame.draw.polygon(surf, (40, 30, 20), [(c[0] - 18 * d, c[1]), (c[0] + 14 * d, c[1] - 22), (c[0] + 14 * d, c[1] + 22)])
        else:
            lbl = font_med.render(arrow, True, (40, 30, 20))
            surf.blit(lbl, lbl.get_rect(center=c))

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

    bob = math.sin(t * 3) * 4
    title1 = font_title.render("SUPER JUMP", True, (255, 230, 60))
    title2 = font_title.render("RACER", True, (255, 120, 90))
    surf.blit(title1, title1.get_rect(center=(WIDTH // 2, 54 + bob)))
    surf.blit(title2, title2.get_rect(center=(WIDTH // 2, 104 + bob)))

    sub = font_small.render("escolha seu robô, a pista e a dificuldade", True, (60, 50, 40))
    surf.blit(sub, sub.get_rect(center=(WIDTH // 2, 134)))

    # ---- seleção de cor (duas fileiras, já que agora são 9 opções) ----
    color_rects = [None] * len(RACER_COLORS)
    box = 72
    spacing = 100
    rows = [RACER_COLORS[0:5], RACER_COLORS[5:9]]
    cy_rows = [193, 285]
    idx_base = 0
    for row, cy_color in zip(rows, cy_rows):
        n_row = len(row)
        start_x = WIDTH // 2 - spacing * (n_row - 1) / 2
        for j, c in enumerate(row):
            i = idx_base + j
            cx = int(start_x + j * spacing)
            rect = pygame.Rect(cx - box // 2, cy_color - box // 2, box, box)
            color_rects[i] = rect
            selected = (i == selected_color_idx)
            bg = (255, 250, 220) if selected else (255, 255, 255)
            pygame.draw.rect(surf, bg, rect, border_radius=10)
            pygame.draw.rect(surf, (60, 45, 30), rect, width=4 if selected else 2, border_radius=10)
            icon = pygame.transform.smoothscale(ROBOT_ICON[c], (48, 48))
            bob_i = math.sin(t * 3 + i) * (3 if selected else 0)
            surf.blit(icon, (cx - icon.get_width() // 2, cy_color - icon.get_height() // 2 + int(bob_i)))
            lbl = font_small.render(COLOR_LABELS[c], True, (60, 45, 30))
            surf.blit(lbl, lbl.get_rect(center=(cx, cy_color + box // 2 + 12)))
        idx_base += n_row

    # ---- seleção de pista (carrossel, já que são 14 opções) ----
    idx = next(i for i, tr in enumerate(TRACKS) if tr["key"] == track_theme)
    cy_track = 400
    card_w, card_h = 168, 70
    big_card_w = 260  # maior que o das laterais, pra caber nomes de pista compridos

    def draw_track_card(cx, cfg, big):
        w, h = (big_card_w, card_h) if big else (card_w - 30, card_h - 20)
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
        # nos cards laterais (menores), mostra só o número da pista pra
        # nunca vazar da tela, não importa quão comprido seja o nome —
        # o nome completo aparece no card grande (central)
        text_to_show = cfg["label"] if big else f"{cfg['n']}º"
        lbl = f.render(text_to_show, True, text_col)
        label_area = pygame.Rect(icon_rect.right + 6, rect.y, rect.right - icon_rect.right - 10, rect.height)
        lbl_rect = lbl.get_rect(center=label_area.center)
        if lbl_rect.width > label_area.width:
            lbl = font_small.render(text_to_show, True, text_col)
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

    dots_y = cy_track + 50
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
    dw, dh = 210, 60
    dspacing = 230
    dstart_x = WIDTH // 2 - dspacing / 2
    cy_diff = 500
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
# TELA INICIAL (HISTÓRIA / CORRIDA)
# --------------------------------------------------------------------------
def draw_splash_screen(surf, t):
    for y in range(HEIGHT):
        tt = y / HEIGHT
        color = tuple(int(SKY_TOP[i] + (SKY_BOTTOM[i] - SKY_TOP[i]) * tt) for i in range(3))
        pygame.draw.line(surf, color, (0, y), (WIDTH, y))
    pygame.draw.rect(surf, (94, 168, 96), (0, HEIGHT - 66, WIDTH, 66))

    bob = math.sin(t * 2.4) * 6
    title1 = font_title.render("SUPER JUMP", True, (255, 230, 60))
    title2 = font_title.render("RACER", True, (255, 120, 90))
    surf.blit(title1, title1.get_rect(center=(WIDTH // 2, 160 + bob)))
    surf.blit(title2, title2.get_rect(center=(WIDTH // 2, 220 + bob)))

    icon = ROBOT_IMG["yellow"]
    bobr = abs(math.sin(t * 3)) * 18
    surf.blit(icon, (WIDTH // 2 - icon.get_width() // 2, 300 - bobr))

    def draw_btn(cx, cy, label, bg):
        lbl = font_med.render(label, True, (255, 255, 255))
        w, h = 270, 76
        rect = pygame.Rect(cx - w // 2, cy - h // 2, w, h)
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(s, bg, s.get_rect(), border_radius=16)
        pygame.draw.rect(s, (255, 255, 255, 230), s.get_rect(), width=3, border_radius=16)
        surf.blit(s, rect.topleft)
        surf.blit(lbl, lbl.get_rect(center=rect.center))
        return rect

    historia_rect = draw_btn(WIDTH // 2, 420, "HISTÓRIA", (110, 90, 200, 235))
    corrida_rect = draw_btn(WIDTH // 2, 505, "CORRIDA", (90, 170, 90, 235))

    hint_txt = ("toque num botão para escolher" if IS_ANDROID else
                "clique num botão, ou ENTER = CORRIDA / H = HISTÓRIA")
    hint = font_small.render(hint_txt, True, (50, 40, 30))
    surf.blit(hint, hint.get_rect(center=(WIDTH // 2, 565)))
    return historia_rect, corrida_rect


# --------------------------------------------------------------------------
# TELA DE MODO: 2D ou 3D (aparece antes da tela HISTÓRIA / CORRIDA)
# --------------------------------------------------------------------------
try:
    MODE_COVER = load("modo_capa.png")
except (FileNotFoundError, pygame.error):
    MODE_COVER = None
_MODE_BG = None
# caixas "2D" e "3D" desenhadas na arte original (768 x 1364)
_COVER_BOX = {"2d": (197, 1283, 285, 1332), "3d": (443, 1283, 532, 1332)}


def draw_mode_screen(surf, t, sel):
    """Devolve {"2d": [retângulos clicáveis], "3d": [...]}."""
    global _MODE_BG
    if MODE_COVER is not None:
        if _MODE_BG is None:   # fundo: a mesma arte, esticada e borrada
            small = pygame.transform.smoothscale(MODE_COVER, (12, 20))
            bg = pygame.transform.smoothscale(small, (WIDTH, HEIGHT))
            bg.fill((120, 120, 120), special_flags=pygame.BLEND_RGB_MULT)
            _MODE_BG = bg
        surf.blit(_MODE_BG, (0, 0))
        k = HEIGHT / MODE_COVER.get_height()
        art = pygame.transform.smoothscale(MODE_COVER, (int(MODE_COVER.get_width() * k), HEIGHT))
        ax = (WIDTH - art.get_width()) // 2
        surf.blit(art, (ax, 0))
        kk = HEIGHT / 1364.0
        sx = art.get_width() / 768.0
    else:
        for y in range(HEIGHT):
            tt = y / HEIGHT
            surf.fill(tuple(int(SKY_TOP[i] + (SKY_BOTTOM[i] - SKY_TOP[i]) * tt) for i in range(3)), (0, y, WIDTH, 1))
        ax, kk, sx = 0, 1.0, 1.0
    rects = {"2d": [], "3d": []}
    # botões grandes nas laterais (bons pra tocar) ...
    cy = HEIGHT // 2 + 40
    for key, cx, label, col in (("2d", 150, "2D", (70, 150, 90)), ("3d", WIDTH - 150, "3D", (210, 120, 40))):
        w, h = 230, 120
        r = pygame.Rect(cx - w // 2, cy - h // 2, w, h)
        pulse = 1 + (0.04 * math.sin(t * 5) if sel == key else 0)
        rr = r.inflate(int(w * (pulse - 1)), int(h * (pulse - 1)))
        s2 = pygame.Surface(rr.size, pygame.SRCALPHA)
        pygame.draw.rect(s2, col + ((245,) if sel == key else (190,)), s2.get_rect(), border_radius=22)
        pygame.draw.rect(s2, (255, 255, 255, 255 if sel == key else 150), s2.get_rect(),
                         width=6 if sel == key else 3, border_radius=22)
        surf.blit(s2, rr.topleft)
        lbl = font_big.render(label, True, (255, 255, 255))
        surf.blit(lbl, lbl.get_rect(center=rr.center))
        rects[key].append(r)
    # ... e as caixas da própria arte também funcionam
    for key, (x0, y0, x1, y1) in _COVER_BOX.items():
        rc = pygame.Rect(int(ax + x0 * sx) - 24, int(y0 * kk) - 22, int((x1 - x0) * sx) + 48, int((y1 - y0) * kk) + 44)
        rects[key].append(rc)
        if sel == key:
            pygame.draw.rect(surf, (255, 255, 255), rc, width=3, border_radius=8)
    tip = font_small.render("2D = vista lateral clássica   |   3D = câmera atrás do robô", True, (255, 255, 255))
    surf.blit(font_small.render("2D = vista lateral clássica   |   3D = câmera atrás do robô", True, (0, 0, 0)),
              tip.get_rect(center=(WIDTH // 2 + 1, 26)))
    surf.blit(tip, tip.get_rect(center=(WIDTH // 2, 25)))
    if not IS_ANDROID:
        for cx, txt in ((150, "tecla 2"), (WIDTH - 150, "tecla 3")):
            h2 = font_small.render(txt, True, (255, 255, 255))
            surf.blit(h2, h2.get_rect(center=(cx, cy + 82)))
    return rects


# --------------------------------------------------------------------------
# MODO HISTÓRIA — seleção de robô
# --------------------------------------------------------------------------
def draw_story_color_screen(surf, t, selected_color_idx):
    for y in range(HEIGHT):
        tt = y / HEIGHT
        color = tuple(int(SKY_TOP[i] + (SKY_BOTTOM[i] - SKY_TOP[i]) * tt) for i in range(3))
        pygame.draw.line(surf, color, (0, y), (WIDTH, y))
    pygame.draw.rect(surf, (94, 168, 96), (0, HEIGHT - 66, WIDTH, 66))

    title = font_big.render("MODO HISTÓRIA", True, (255, 230, 60))
    surf.blit(title, title.get_rect(center=(WIDTH // 2, 68)))
    sub = font_small.render("escolha seu robô para a perseguição", True, (60, 50, 40))
    surf.blit(sub, sub.get_rect(center=(WIDTH // 2, 116)))

    color_rects = [None] * len(RACER_COLORS)
    box = 86
    spacing = 118
    rows = [RACER_COLORS[0:5], RACER_COLORS[5:9]]
    cy_rows = [228, 350]
    idx_base = 0
    for row, cy_color in zip(rows, cy_rows):
        n_row = len(row)
        start_x = WIDTH // 2 - spacing * (n_row - 1) / 2
        for j, c in enumerate(row):
            i = idx_base + j
            cx = int(start_x + j * spacing)
            rect = pygame.Rect(cx - box // 2, cy_color - box // 2, box, box)
            color_rects[i] = rect
            selected = (i == selected_color_idx)
            bg = (255, 250, 220) if selected else (255, 255, 255)
            pygame.draw.rect(surf, bg, rect, border_radius=12)
            pygame.draw.rect(surf, (60, 45, 30), rect, width=4 if selected else 2, border_radius=12)
            icon = pygame.transform.smoothscale(ROBOT_ICON[c], (58, 58))
            bob_i = math.sin(t * 3 + i) * (4 if selected else 0)
            surf.blit(icon, (cx - icon.get_width() // 2, cy_color - icon.get_height() // 2 + int(bob_i)))
            lbl = font_small.render(COLOR_LABELS[c], True, (60, 45, 30))
            surf.blit(lbl, lbl.get_rect(center=(cx, cy_color + box // 2 + 14)))
        idx_base += n_row

    if IS_ANDROID:
        confirm_rect = draw_tap_to_continue_button(surf, "COMEÇAR HISTÓRIA!", HEIGHT - 33)
    else:
        hint = font_med.render("Pressione ENTER para começar a história!", True, (60, 45, 30))
        surf.blit(hint, hint.get_rect(center=(WIDTH // 2, HEIGHT - 33)))
        confirm_rect = None

    return color_rects, confirm_rect


# --------------------------------------------------------------------------
# MODO HISTÓRIA — CENÁRIO 3: tela final ("novo logo" + "FIM")
# --------------------------------------------------------------------------
def draw_story_end_screen(surf, t):
    top = (255, 170, 110)
    bottom = (255, 225, 160)
    for y in range(HEIGHT):
        tt = y / HEIGHT
        color = tuple(int(top[i] + (bottom[i] - top[i]) * tt) for i in range(3))
        pygame.draw.line(surf, color, (0, y), (WIDTH, y))

    pygame.draw.circle(surf, (255, 225, 140), (WIDTH // 2, 300), 110)

    pygame.draw.rect(surf, (90, 160, 190), (0, 360, WIDTH, HEIGHT - 360))
    for i in range(10):
        wy = 375 + i * 20
        off = int(t * 40 + i * 37) % 60
        for wx in range(-60 + off, WIDTH, 60):
            pygame.draw.arc(surf, (210, 235, 245), (wx, wy, 44, 14), 3.4, 6.0, 2)

    pygame.draw.rect(surf, (235, 210, 160), (0, 520, WIDTH, HEIGHT - 520))

    cheer_colors = ["yellow", "blue", "red", "green"]
    cx0 = WIDTH // 2 - 150
    for i, c in enumerate(cheer_colors):
        bobr = abs(math.sin(t * 3 + i)) * 14
        icon = ROBOT_IMG[c]
        surf.blit(icon, (cx0 + i * 100 - icon.get_width() // 2, 470 - bobr))

    bob = math.sin(t * 2) * 5
    shadow1 = font_title.render("SUPER JUMP", True, (90, 50, 20))
    shadow2 = font_title.render("RACERS", True, (90, 50, 20))
    title1 = font_title.render("SUPER JUMP", True, (255, 255, 255))
    title2 = font_title.render("RACERS", True, (255, 240, 90))
    surf.blit(shadow1, shadow1.get_rect(center=(WIDTH // 2 + 3, 63 + bob)))
    surf.blit(title1, title1.get_rect(center=(WIDTH // 2, 60 + bob)))
    surf.blit(shadow2, shadow2.get_rect(center=(WIDTH // 2 + 3, 113 + bob)))
    surf.blit(title2, title2.get_rect(center=(WIDTH // 2, 110 + bob)))

    for i in range(14):
        sxp = (i * 83 + int(t * 20)) % (WIDTH + 40) - 20
        syp = 20 + (i * 29) % 40
        pygame.draw.circle(surf, (255, 255, 255), (sxp, syp), 2)

    fim_bob = math.sin(t * 2.5) * 6
    fim_shadow = font_big.render("FIM", True, (120, 60, 20))
    fim = font_big.render("FIM", True, (255, 255, 255))
    big_fim = pygame.transform.smoothscale(fim, (int(fim.get_width() * 1.8), int(fim.get_height() * 1.8)))
    big_fim_shadow = pygame.transform.smoothscale(
        fim_shadow, (int(fim_shadow.get_width() * 1.8), int(fim_shadow.get_height() * 1.8)))
    surf.blit(big_fim_shadow, big_fim_shadow.get_rect(center=(WIDTH // 2 + 4, 234 + fim_bob)))
    surf.blit(big_fim, big_fim.get_rect(center=(WIDTH // 2, 230 + fim_bob)))

    sub = font_small.render("Obrigado por jogar Super Jump Racer!", True, (70, 40, 20))
    surf.blit(sub, sub.get_rect(center=(WIDTH // 2, 300)))

    if IS_ANDROID:
        back_rect = draw_tap_to_continue_button(surf, "CONTINUAR", HEIGHT - 33)
    else:
        hint = font_med.render("Pressione ENTER para continuar", True, (70, 40, 20))
        surf.blit(hint, hint.get_rect(center=(WIDTH // 2, HEIGHT - 33)))
        back_rect = None
    return back_rect


# --------------------------------------------------------------------------
# MODO HISTÓRIA — CUTSCENES (pequenos "filmes" animados, 100% desenhados
# com formas do pygame e os sprites que já existem)
# --------------------------------------------------------------------------
CUTSCENE_DUR = {"intro": 14.5, "lab_arrival": 11.0, "victory": 13.0, "laugh": 12.5}
_CUT_ROBOT_CACHE = {}


def _ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def _seg(t, a, b):
    return max(0.0, min(1.0, (t - a) / (b - a)))


def _cut_robot(color, zombie, size=100):
    key = (color, zombie, size)
    if key not in _CUT_ROBOT_CACHE:
        base = ZOMBIE_IMG[color] if zombie else ROBOT_IMG[color]
        _CUT_ROBOT_CACHE[key] = pygame.transform.smoothscale(base, (size, size))
    return _CUT_ROBOT_CACHE[key]


def _wrap_text(text, font, max_w):
    words, lines, cur = text.split(" "), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if font.size(trial)[0] <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _draw_caption(surf, speaker, text, elapsed):
    box = pygame.Surface((WIDTH - 60, 112), pygame.SRCALPHA)
    pygame.draw.rect(box, (10, 8, 20, 205), box.get_rect(), border_radius=14)
    pygame.draw.rect(box, (255, 255, 255, 220), box.get_rect(), width=3, border_radius=14)
    surf.blit(box, (30, HEIGHT - 134))
    y = HEIGHT - 124
    if speaker:
        sp = font_small.render(speaker, True, (255, 220, 90))
        surf.blit(sp, (50, y))
        y += 26
    shown = text[: int(elapsed * 32)]
    # quebra o texto COMPLETO em linhas (pra não "pular" durante a digitação)
    full_lines = _wrap_text(text, font_med, WIDTH - 110)
    count = len(shown)
    for ln in full_lines:
        part = ln[:max(0, count)]
        count -= len(ln) + 1
        if part:
            surf.blit(font_med.render(part, True, (255, 255, 255)), (50, y))
        y += 32


def draw_cutscene(surf, cid, ct, pc):
    """Desenha o quadro da cutscene `cid` no instante `ct` (segundos).
    pc = cor do robô que o jogador escolheu."""
    bg = "cidade" if cid == "intro" else "laboratorio"
    draw_background(surf, 0, bg)
    others = [c for c in RACER_COLORS if c != pc][:3]
    pc_name = f"Robô {COLOR_LABELS[pc]}"
    layer = None
    caps = []
    flash = 0
    robots = []      # (y_base, color, zombie, x, run, wobble)
    bico = None      # dict de argumentos de draw_bicoliso
    extras = []      # funções de desenho extra (depois dos personagens)

    if cid == "intro":
        ys = [440, 410, 450, 425]
        zombie = ct >= 6.35
        run = _seg(ct, 9.5, 11.0)
        px = 150 + 100 * _ease(run)
        conv = _ease(_seg(ct, 9.5, 12.0))
        init = [330, 450, 570]
        final = [350, 410, 470]
        robots.append((ys[0], pc, False, px, 0 < run < 1, 0))
        for i, c in enumerate(others):
            x = init[i] + (final[i] - init[i]) * conv
            wob = math.sin(ct * 5 + i) * 4 if zombie else 0
            robots.append((ys[i + 1], c, zombie, x, False, wob))
        if ct >= 3.0:
            enter = _ease(_seg(ct, 3.0, 4.6))
            flee = _ease(_seg(ct, 9.5, 12.5))
            bx = 1100 + (790 - 1100) * enter + 560 * flee
            angry = 7.0 <= ct < 9.5
            press = (5.6 <= ct < 6.0) or (angry and (ct * 3) % 1 < 0.35)
            shake = math.sin(ct * 40) * 3 if angry else 0
            bico = dict(cx=bx + shake, by=470, s=0.78, t=ct, mood="angry" if angry else "normal",
                        facing=1 if ct >= 9.5 else -1, press=press)
        if 7.2 <= ct < 9.5:
            def q(surf=surf):
                qs = font_big.render("?", True, (255, 255, 255))
                surf.blit(qs, (int(150 - 10), 300))
            extras.append(q)
        if 5.9 <= ct < 6.6:
            flash = int(220 * (1 - (ct - 5.9) / 0.7))
        caps = [(0.0, 3.0, "", "Os robôs passeavam tranquilos pela cidade..."),
                (3.0, 5.6, "Professor Bicoliso", "Hahaha! Chegou a hora da minha invenção!"),
                (5.6, 7.0, "Professor Bicoliso", "Aperta... o botão!!"),
                (7.0, 9.5, "Professor Bicoliso", "O quê?! Por que ELE não virou zumbi?!"),
                (9.5, 11.5, "@P", "Bicoliso, volta aqui!"),
                (11.5, 14.5, "", "Mas os robôs zumbis bloqueiam o caminho!")]

    elif cid == "lab_arrival":
        run = _seg(ct, 0, 2.6)
        px = -80 + 380 * _ease(run)
        robots.append((440, pc, False, px, ct < 2.6, 0))
        if ct >= 3.0:
            bico = dict(cx=730, by=470, s=0.78 * (0.4 + 0.6 * _ease(_seg(ct, 3.0, 3.5))), t=ct,
                        mood="normal", facing=-1, press=False)
        if 2.9 <= ct < 4.2:
            def smoke(surf=surf, ct=ct):
                lay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                k = (ct - 2.9) / 1.3
                for i in range(7):
                    ox = math.cos(i * 0.9) * 70 * k
                    oy = math.sin(i * 1.7) * 50 * k
                    pygame.draw.circle(lay, (230, 230, 235, int(190 * (1 - k))),
                                       (int(730 + ox), int(400 + oy)), int(26 + 26 * k))
                surf.blit(lay, (0, 0))
            extras.append(smoke)
        caps = [(0.0, 3.0, "", "O robô chegou ao Laboratório do Professor Bicoliso..."),
                (3.0, 6.5, "Professor Bicoliso", "Você chegou longe, hein? Que tal uma corrida?"),
                (6.5, 9.0, "Professor Bicoliso", "Se me vencer, eu desfaço o feitiço dos seus amigos!"),
                (9.0, 11.0, "@P", "Aceito o desafio!")]

    elif cid == "victory":
        zombie = ct < 3.4
        charge = _ease(_seg(ct, 6.0, 9.0))
        init = [330, 420, 510]
        robots.append((440, pc, False, 200 + 330 * charge, 6.0 <= ct < 9.5, 0))
        for i, c in enumerate(others):
            x = init[i] + 330 * charge
            wob = math.sin(ct * 5 + i) * 4 if zombie else 0
            robots.append(([410, 450, 425][i], c, zombie, x, 6.0 <= ct < 9.5, wob))
        flee = _ease(_seg(ct, 7.0, 10.0))
        bico = dict(cx=790 + 520 * flee, by=470, s=0.78, t=ct,
                    mood="angry" if ct < 3.2 else "normal", facing=1 if ct >= 7.0 else -1, press=False)
        if 3.2 <= ct < 3.9:
            flash = int(220 * (1 - (ct - 3.2) / 0.7))
        if 3.4 <= ct < 5.2:
            def sparks(surf=surf, ct=ct):
                for i in range(3):
                    cx = 330 + i * 90 + int(math.sin(ct * 6 + i) * 6)
                    for k in range(4):
                        a = ct * 4 + k * math.pi / 2
                        pygame.draw.circle(surf, (255, 240, 120),
                                           (int(cx + math.cos(a) * 28), int(300 + math.sin(a) * 20)), 4)
            extras.append(sparks)
        caps = [(0.0, 3.0, "Professor Bicoliso", "Impossível! Eu perdi a corrida?!"),
                (3.0, 5.5, "", "O feitiço se quebrou! Os robôs voltaram ao normal!"),
                (5.5, 8.0, "Robôs", "Agora você vai ver só, Bicoliso!"),
                (8.0, 11.0, "Professor Bicoliso", "Aaah! Isso não vai ficar assim! Eu volto!"),
                (11.0, 13.0, "", "O Bicoliso fugiu!")]

    elif cid == "laugh":
        pass

    if cid != "laugh":
        for (yb, color, zomb, x, run, wob) in sorted(robots, key=lambda r: r[0]):
            img = _cut_robot(color, zomb)
            bob = abs(math.sin(ct * (9 if run else 3) + yb)) * (14 if run else 6)
            pygame.draw.ellipse(surf, (35, 35, 40), (int(x - 28 + wob), int(yb - 6), 56, 10), 0)
            surf.blit(img, (int(x - img.get_width() / 2 + wob), int(yb - img.get_height() - bob)))
        if bico:
            rp = draw_bicoliso(surf, **bico)
            if cid == "intro" and 5.9 <= ct < 7.0 and rp:
                lay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                pygame.draw.circle(lay, (90, 255, 130, 160), rp, int((ct - 5.9) * 800), 10)
                surf.blit(lay, (0, 0))
        for fn in extras:
            fn()
    else:
        dark = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dark.fill((10, 20, 15, 110))
        surf.blit(dark, (0, 0))
        if math.sin(ct * 9) > 0.85:
            lit = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            lit.fill((150, 255, 170, 45))
            surf.blit(lit, (0, 0))
        laughing = ct < 7.5
        dx = math.sin(ct * 30) * 4 if laughing else 0
        draw_bicoliso(surf, 480 + dx, 458, s=1.1, t=ct, mood="laugh" if laughing else "normal",
                      facing=-1 if int(ct * 1.2) % 2 else 1, remote=False)
        if laughing:
            for k in range(4):
                yy = 330 - ((ct * 70 + k * 55) % 200)
                has = font_med.render("HA!", True, (255, 240, 120))
                surf.blit(has, (170 + k * 190 + int(math.sin(ct * 8 + k) * 10), int(yy + 120)))
        caps = [(0.0, 3.8, "Professor Bicoliso", "Hahaha... vocês ganharam esta batalha..."),
                (3.8, 7.5, "Professor Bicoliso", "...mas a guerra está só começando! MUAHAHAHA!")]
        fade = _seg(ct, 7.5, 8.7)
        if fade > 0:
            blk = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            blk.fill((0, 0, 0, int(255 * fade)))
            surf.blit(blk, (0, 0))
        if ct >= 8.9:
            txt = font_big.render("CONTINUA...", True, (255, 255, 255))
            txt.set_alpha(int(255 * _seg(ct, 8.9, 10.2)))
            surf.blit(txt, txt.get_rect(center=(WIDTH // 2, HEIGHT // 2)))

    if flash > 0:
        fl = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        fl.fill((255, 255, 255, flash))
        surf.blit(fl, (0, 0))

    for (a, b, speaker, text) in caps:
        if a <= ct < b:
            _draw_caption(surf, pc_name if speaker == "@P" else speaker, text, ct - a)
            break

    hint = font_small.render("toque para pular" if IS_ANDROID else "ENTER: pular", True, (255, 255, 255))
    surf.blit(hint, (WIDTH - hint.get_width() - 16, 12))


# --------------------------------------------------------------------------
# LOOP PRINCIPAL
# --------------------------------------------------------------------------
def new_story_race_ch1(player_color, track_key):
    """Modo HISTÓRIA, CENÁRIO 1: o robô escolhido persegue 3 zumbis
    (sempre mais lentos e com movimento errático) pelas pistas 1-13."""
    track_cfg = TRACKS_BY_KEY[track_key]
    obstacles, stars = generate_track(obstacle_prob=track_obstacle_prob(track_cfg))
    other_colors = [c for c in RACER_COLORS if c != player_color][:3]
    player = Racer(player_color, "Você", pos=1, is_player=True, skill=1.0)
    ai_positions = [p for p in range(POSITIONS) if p != 1]
    zumbis = [
        Racer(other_colors[i], f"Zumbi {COLOR_LABELS[other_colors[i]]}",
              pos=ai_positions[i % len(ai_positions)], skill=random.uniform(0.85, 0.98),
              is_zombie=True)
        for i in range(3)
    ]
    return [player] + zumbis, obstacles, stars


def new_story_race_ch2(player_color, track_key):
    """Modo HISTÓRIA, CENÁRIO 2: só o robô escolhido e o VILÃO, na
    pista do Laboratório (14)."""
    track_cfg = TRACKS_BY_KEY[track_key]
    obstacles, stars = generate_track(obstacle_prob=track_obstacle_prob(track_cfg))
    player = Racer(player_color, "Você", pos=1, is_player=True, skill=1.0)
    vilao = Racer("villain", "Professor Bicoliso", pos=2, skill=random.uniform(0.98, 1.04),
                  is_villain=True)
    return [player, vilao], obstacles, stars


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
    global music_on, PERSPECTIVE

    STATE_MODE = "mode"                    # NOVA tela inicial: 2D ou 3D
    STATE_SPLASH = "splash"                # NOVA tela inicial: HISTÓRIA ou CORRIDA
    STATE_TITLE = "title"
    STATE_COUNTDOWN = "countdown"
    STATE_RACING = "racing"
    STATE_FINISHED = "finished"            # resultado de corrida avulsa (não-campanha)
    STATE_TRACK_RESULT = "track_result"    # resultado de UMA pista dentro da campanha
    STATE_CAMPAIGN_FINISHED = "campaign_finished"  # resultado final das 12 pistas

    # ---- modo HISTÓRIA ----
    STATE_STORY_COLOR_SELECT = "story_color_select"
    STATE_STORY_TRACK_RESULT = "story_track_result"      # fim de UMA pista no Cenário 1
    STATE_STORY_VILLAIN_RESULT = "story_villain_result"  # fim da pista do Cenário 2
    STATE_STORY_END = "story_end"                        # Cenário 3: "novo logo" + FIM
    STATE_CUTSCENE = "cutscene"                          # filminhos da história

    state = STATE_MODE
    mode_sel = "3d" if PERSPECTIVE else "2d"
    mode_rects = {"2d": [], "3d": []}
    mode_chip_rect = None
    selected_color_idx = 0
    difficulty = "facil"
    track_theme = "cidade"

    # ---- modo HISTÓRIA: estado da campanha narrativa ----
    story_mode = False
    story_chapter = 1          # 1 = perseguição aos zumbis (pistas 1-13), 2 = VILÃO (pista 14)
    story_track_idx = 0        # índice em TRACKS (0..12) durante o Cenário 1
    story_player_color = None
    historia_rect = None
    corrida_rect = None
    story_color_rects = []
    story_confirm_rect = None
    story_next_rect = None
    story_continue_rect = None
    story_back_rect = None
    cutscene_id = None
    cutscene_t = 0.0

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

    def start_story_race(chapter, track_key, p_color):
        """(Re)inicia uma corrida do modo HISTÓRIA (zumbis no Cenário 1,
        ou o VILÃO no Cenário 2), trocando a música da pista."""
        nonlocal racers, obstacles, stars, player, race_theme, countdown_timer, results, state
        if chapter == 1:
            racers, obstacles, stars = new_story_race_ch1(p_color, track_key)
        else:
            racers, obstacles, stars = new_story_race_ch2(p_color, track_key)
        player = racers[0]
        race_theme = track_key
        track_music_path = find_track_music(TRACKS_BY_KEY[track_key]["n"]) or MUSIC_PATH
        switch_music(track_music_path)
        set_music_volume(0.55 if music_on else 0.0)
        state = STATE_COUNTDOWN
        countdown_timer = 3.0
        results = []

    def begin_story():
        nonlocal story_mode, story_chapter, story_track_idx, story_player_color
        story_mode = True
        story_chapter = 1
        story_track_idx = 0
        story_player_color = RACER_COLORS[selected_color_idx]
        start_cutscene("intro")

    def start_cutscene(cid):
        nonlocal state, cutscene_id, cutscene_t
        state = STATE_CUTSCENE
        cutscene_id = cid
        cutscene_t = 0.0

    def end_cutscene():
        """Fim (ou pulo) de uma cutscene: segue pro que vem depois dela."""
        nonlocal state, story_chapter, story_mode
        if cutscene_id == "intro":
            start_story_race(1, TRACKS[0]["key"], story_player_color)
        elif cutscene_id == "lab_arrival":
            story_chapter = 2
            start_story_race(2, TRACKS[13]["key"], story_player_color)
        elif cutscene_id == "victory":
            state = STATE_STORY_END
        else:  # "laugh" -> volta pra tela inicial
            story_mode = False
            state = STATE_SPLASH
            switch_music(MUSIC_PATH)
            set_music_volume(0.55 if music_on else 0.0)

    def advance_story():
        """Chamado ao confirmar o resultado de uma pista do modo HISTÓRIA:
        segue pra próxima pista do Cenário 1, ou passa pro Cenário 2
        (VILÃO, pista 14) depois da 13ª pista."""
        nonlocal story_track_idx, story_chapter
        story_track_idx += 1
        if story_track_idx < 13:
            start_story_race(1, TRACKS[story_track_idx]["key"], story_player_color)
        else:
            start_cutscene("lab_arrival")

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

                if state == STATE_MODE:
                    if event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_2, pygame.K_KP2):
                        mode_sel = "2d"
                    elif event.key in (pygame.K_RIGHT, pygame.K_d, pygame.K_3, pygame.K_KP3):
                        mode_sel = "3d"
                    if event.key in (pygame.K_2, pygame.K_KP2, pygame.K_3, pygame.K_KP3,
                                     pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                        PERSPECTIVE = (mode_sel == "3d")
                        state = STATE_SPLASH

                elif state == STATE_SPLASH:
                    if event.key == pygame.K_TAB:
                        state = STATE_MODE
                    elif event.key == pygame.K_h:
                        state = STATE_STORY_COLOR_SELECT
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                        state = STATE_TITLE

                elif state == STATE_STORY_COLOR_SELECT:
                    if event.key in (pygame.K_LEFT, pygame.K_a):
                        selected_color_idx = (selected_color_idx - 1) % len(RACER_COLORS)
                    elif event.key in (pygame.K_RIGHT, pygame.K_d):
                        selected_color_idx = (selected_color_idx + 1) % len(RACER_COLORS)
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                        begin_story()

                elif state == STATE_STORY_TRACK_RESULT:
                    if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                        advance_story()

                elif state == STATE_STORY_VILLAIN_RESULT:
                    if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                        start_story_race(2, TRACKS[13]["key"], story_player_color)  # tenta de novo

                elif state == STATE_STORY_END:
                    if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                        start_cutscene("laugh")

                elif state == STATE_CUTSCENE:
                    if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER) and cutscene_t > 0.6:
                        end_cutscene()

                elif state == STATE_TITLE:
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
                    if PERSPECTIVE:
                        if event.key in (pygame.K_LEFT, pygame.K_a):
                            player.set_pos(player.target_pos - 1)
                        elif event.key in (pygame.K_RIGHT, pygame.K_d):
                            player.set_pos(player.target_pos + 1)
                    elif event.key in (pygame.K_UP, pygame.K_w):
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

            elif event.type == pygame.MOUSEBUTTONDOWN and state == STATE_MODE:
                for key in ("2d", "3d"):
                    if any(r.collidepoint(event.pos) for r in mode_rects[key]):
                        mode_sel = key
                        PERSPECTIVE = (key == "3d")
                        state = STATE_SPLASH

            elif event.type == pygame.MOUSEBUTTONDOWN and state == STATE_SPLASH:
                if mode_chip_rect and mode_chip_rect.collidepoint(event.pos):
                    state = STATE_MODE
                elif historia_rect and historia_rect.collidepoint(event.pos):
                    state = STATE_STORY_COLOR_SELECT
                elif corrida_rect and corrida_rect.collidepoint(event.pos):
                    state = STATE_TITLE

            elif event.type == pygame.MOUSEBUTTONDOWN and state == STATE_STORY_COLOR_SELECT:
                mx, my = event.pos
                for i, rect in enumerate(story_color_rects):
                    if rect and rect.collidepoint(mx, my):
                        selected_color_idx = i
                if story_confirm_rect and story_confirm_rect.collidepoint(mx, my):
                    begin_story()

            elif event.type == pygame.MOUSEBUTTONDOWN and state == STATE_STORY_TRACK_RESULT:
                if story_next_rect and story_next_rect.collidepoint(event.pos):
                    advance_story()

            elif event.type == pygame.MOUSEBUTTONDOWN and state == STATE_STORY_VILLAIN_RESULT:
                if story_continue_rect and story_continue_rect.collidepoint(event.pos):
                    start_story_race(2, TRACKS[13]["key"], story_player_color)  # tenta de novo

            elif event.type == pygame.MOUSEBUTTONDOWN and state == STATE_STORY_END:
                if story_back_rect and story_back_rect.collidepoint(event.pos):
                    start_cutscene("laugh")

            elif event.type == pygame.MOUSEBUTTONDOWN and state == STATE_CUTSCENE:
                if cutscene_t > 0.6:
                    end_cutscene()

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
        if PERSPECTIVE:
            moving_right = keys[pygame.K_UP] or keys[pygame.K_w] or keys[pygame.K_SPACE] or touch_moving
        else:
            moving_right = keys[pygame.K_RIGHT] or keys[pygame.K_d] or touch_moving

        if state == STATE_COUNTDOWN:
            countdown_timer -= dt
            for r in racers:
                r.bounce_phase += 0.03 * (dt * 60.0)
            if countdown_timer <= 0:
                state = STATE_RACING

        elif state == STATE_CUTSCENE:
            cutscene_t += dt
            if cutscene_t >= CUTSCENE_DUR[cutscene_id]:
                end_cutscene()

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

                if story_mode:
                    if story_chapter == 1:
                        state = STATE_STORY_TRACK_RESULT
                    elif player.finish_rank == 1:
                        start_cutscene("victory")      # ganhou do Bicoliso!
                    else:
                        state = STATE_STORY_VILLAIN_RESULT  # perdeu: tenta de novo
                elif campaign_mode:
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
        if state == STATE_MODE:
            mode_rects = draw_mode_screen(screen, t, mode_sel)
        elif state == STATE_SPLASH:
            historia_rect, corrida_rect = draw_splash_screen(screen, t)
            chip = font_small.render("MODO: 3D  (trocar)" if PERSPECTIVE else "MODO: 2D  (trocar)", True, (255, 255, 255))
            mode_chip_rect = chip.get_rect(topleft=(14, 12)).inflate(24, 14)
            cs = pygame.Surface(mode_chip_rect.size, pygame.SRCALPHA)
            pygame.draw.rect(cs, (30, 30, 40, 190), cs.get_rect(), border_radius=12)
            screen.blit(cs, mode_chip_rect.topleft)
            screen.blit(chip, chip.get_rect(center=mode_chip_rect.center))
        elif state == STATE_STORY_COLOR_SELECT:
            story_color_rects, story_confirm_rect = draw_story_color_screen(screen, t, selected_color_idx)
        elif state == STATE_STORY_END:
            story_back_rect = draw_story_end_screen(screen, t)
        elif state == STATE_CUTSCENE:
            draw_cutscene(screen, cutscene_id, cutscene_t, story_player_color)
        elif state == STATE_TITLE:
            color_rects, track_rects, diff_rects, start_rect = draw_title_screen(
                screen, t, selected_color_idx, difficulty, track_theme)
        else:
            cam_x = player.world_x
            if PERSPECTIVE:
                draw_race_perspective(screen, player, racers, obstacles, stars, t, race_theme)
            else:
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
                    hint = font_small.render("segure CIMA (ou W) pra andar!" if PERSPECTIVE else "segure -> pra andar!", True, (255, 235, 120))
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

            if state == STATE_STORY_TRACK_RESULT:
                overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 150))
                screen.blit(overlay, (0, 0))

                cur_track = TRACKS[story_track_idx]
                caught = (player.finish_rank == 1)
                title_txt = "VOCÊ DEIXOU OS ZUMBIS ATRÁS!" if caught else "ELES QUASE TE ALCANÇARAM!"
                title = font_big.render(title_txt, True, (255, 220, 80))
                screen.blit(title, title.get_rect(center=(WIDTH // 2, 120)))

                sub = font_med.render(f"Pista {cur_track['n']}: {cur_track['label']} concluída",
                                      True, (255, 240, 150))
                screen.blit(sub, sub.get_rect(center=(WIDTH // 2, 180)))

                is_last = (story_track_idx >= 12)
                next_txt = ("Próximo: o LABORATÓRIO do Professor Bicoliso!" if is_last
                            else f"Próxima pista: {TRACKS[story_track_idx + 1]['label']}")
                if IS_ANDROID:
                    hint = font_small.render(next_txt, True, (230, 230, 230))
                    screen.blit(hint, hint.get_rect(center=(WIDTH // 2, HEIGHT - 90)))
                    story_next_rect = draw_tap_to_continue_button(
                        screen, "CONTINUAR!" if is_last else "PRÓXIMA PISTA!", HEIGHT - 45)
                else:
                    hint = font_med.render(f"ENTER para continuar — {next_txt}", True, (230, 230, 230))
                    screen.blit(hint, hint.get_rect(center=(WIDTH // 2, HEIGHT - 60)))
                    story_next_rect = None

            if state == STATE_STORY_VILLAIN_RESULT:
                overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 170))
                screen.blit(overlay, (0, 0))

                title = font_big.render("O BICOLISO VENCEU!", True, (255, 220, 80))
                screen.blit(title, title.get_rect(center=(WIDTH // 2, 150)))

                sub = font_small.render("Tente de novo — a corrida do Laboratório recomeça!", True, (230, 230, 230))
                screen.blit(sub, sub.get_rect(center=(WIDTH // 2, 210)))

                if IS_ANDROID:
                    story_continue_rect = draw_tap_to_continue_button(screen, "TENTAR DE NOVO", HEIGHT - 45)
                else:
                    hint = font_med.render("Pressione ENTER para tentar de novo", True, (230, 230, 230))
                    screen.blit(hint, hint.get_rect(center=(WIDTH // 2, HEIGHT - 60)))
                    story_continue_rect = None

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
