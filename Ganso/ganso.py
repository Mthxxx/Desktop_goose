import pygame
import os
import random
import time
import win32gui, win32con, win32api
import keyboard
import threading
import sys

pygame.init()

# === Função de monitoramento do ESC global ===
def monitorar_esc():
    keyboard.wait('esc')
    os._exit(0)

threading.Thread(target=monitorar_esc, daemon=True).start()

# TAMANHO DO SPRITE
SPRITE_LARGURA = 256
SPRITE_ALTURA = 256

# Offset da boca do ganso nos sprites (ajustados manualmente)
BOCA_OFFSET_D = (61, 140)
BOCA_OFFSET_E = (195, 140)

# Define a resolução da tela antes de criar a janela
screen_width = win32api.GetSystemMetrics(0)
screen_height = win32api.GetSystemMetrics(1)

# Cria uma janela sem bordas e transparente, cobrindo a tela inteira
screen = pygame.display.set_mode((screen_width, screen_height), pygame.NOFRAME)
pygame.display.set_caption("Ganso Desktop")
hwnd = pygame.display.get_wm_info()["window"]

# Define a janela como transparente, sempre no topo e oculta da barra de tarefas
win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE,
    win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    | win32con.WS_EX_LAYERED
    | win32con.WS_EX_TRANSPARENT
    | win32con.WS_EX_TOPMOST
    | win32con.WS_EX_TOOLWINDOW
)
win32gui.SetLayeredWindowAttributes(hwnd, win32api.RGB(120, 120, 120), 0, win32con.LWA_COLORKEY)

# Diretórios dos sprites
base_dir = os.path.dirname(__file__)
sprites_dir = os.path.join(base_dir, "Sprites")
sprites_direita = os.path.join(sprites_dir, "Direita")
sprites_esquerda = os.path.join(sprites_dir, "Esquerda")

def load_sprites(path, nomes):
    return [pygame.image.load(os.path.join(path, nome)).convert_alpha() for nome in nomes]

sprites = {
    "andar_d": load_sprites(sprites_direita, ["ganso_andando1D.png", "ganso_andando2D.png"]),
    "andar_e": load_sprites(sprites_esquerda, ["ganso_andando1E.png", "ganso_andando2E.png"]),
    "parado_d": load_sprites(sprites_direita, ["ganso_parado1D.png", "ganso_parado2D.png"]),
    "parado_e": load_sprites(sprites_esquerda, ["ganso_parado1E.png", "ganso_parado2E.png"]),
    "dormindo_d": load_sprites(sprites_direita, ["ganso_dormindo1D.png", "ganso_dormindo2D.png", "ganso_dormindo3D.png"]),
    "dormindo_e": load_sprites(sprites_esquerda, ["ganso_dormindo1E.png", "ganso_dormindo2E.png", "ganso_dormindo3E.png"]),
    "correndo_d": load_sprites(sprites_direita, ["ganso_correndo1D.png", "ganso_correndo2D.png", "ganso_correndo3D.png"]),
    "correndo_e": load_sprites(sprites_esquerda, ["ganso_correndo1E.png", "ganso_correndo2E.png", "ganso_correndo3E.png"]),
    "puxando_d": load_sprites(sprites_direita, ["ganso_puxando1D.png", "ganso_puxando2D.png"]),
    "puxando_e": load_sprites(sprites_esquerda, ["ganso_puxando1E.png", "ganso_puxando2E.png"])
}

# Sprites das folhas (explosão: 5 frames por direção)
sprites_folhas = {
    "d": load_sprites(sprites_direita, [f"folha{i}D.png" for i in range(1, 6)]),
    "e": load_sprites(sprites_esquerda, [f"folha{i}E.png" for i in range(1, 6)])
}

# Posição inicial do ganso (posição absoluta na tela)
x = screen_width // 2
y = screen_height // 2

frame_index = 0
estado = "parado"  # pode ser "andar", "parado", "dormindo", "correndo", "puxando", etc.
direcao = "d"
ultima_direcao_horizontal = "d"
tempo_proximo_estado = time.time() + random.uniform(2, 4)

ultimo_input = time.time()
ultima_pos_mouse = win32api.GetCursorPos()
tempo_ataque = time.time() + random.uniform(45, 100)
clock = pygame.time.Clock()

movimentos_possiveis = ["d", "e", "c", "b", "cd", "ce", "bd", "be"]

atacando = False
fase_puxando = False
ponto_destino = (0, 0)

# Classe para o monte de folhas
class MontinhoFolhas:
    def __init__(self):
        self.spawnar()

    def spawnar(self):
        self.x = random.randint(0, screen_width - SPRITE_LARGURA)
        self.y = random.randint(0, screen_height - SPRITE_ALTURA)
        self.estado = "parado"
        self.frame = 0
        self.direcao = "d"  # direção inicial da explosão; "d" ou "e"
        self.tempo_criacao = time.time()
        self.tempo_explosao = None
        self.tempo_sumir = None

    def atualizar(self):
        if self.estado == "explodindo":
            if time.time() - self.tempo_explosao > (self.frame + 1) / 8:
                self.frame += 1
                if self.frame >= 5:  # a animação tem 5 frames
                    self.estado = "espalhado"
                    self.tempo_sumir = time.time() + 4
        if self.estado == "espalhado" and time.time() > self.tempo_sumir:
            return False  # indica que o monte deve sumir
        return True

    def desenhar(self, screen):
        # Desenha as folhas na posição absoluta
        if self.estado in ["parado", "explodindo", "espalhado"]:
            img = sprites_folhas[self.direcao][min(self.frame, 4)]
            screen.blit(img, (self.x, self.y))

    def iniciar_explosao(self, direcao):
        self.estado = "explodindo"
        self.frame = 1
        self.direcao = direcao
        self.tempo_explosao = time.time()

montinho = None
tempo_proximo_montinho = time.time() + random.uniform(60, 90)

def proximo_estado():
    global estado, direcao, tempo_proximo_estado
    estado = random.choice(["andar", "parado"])
    direcao = random.choice(movimentos_possiveis)
    tempo_proximo_estado = time.time() + random.uniform(2, 4)

def calcular_direcao_alvo(origem, alvo):
    dx = alvo[0] - origem[0]
    dy = alvo[1] - origem[1]
    dist = max((dx ** 2 + dy ** 2) ** 0.5, 1)
    return dx / dist, dy / dist

def mover_mouse_para_boca(gx, gy, direcao):
    offset_x, offset_y = BOCA_OFFSET_E if direcao == "e" else BOCA_OFFSET_D
    win32api.SetCursorPos((int(gx + offset_x), int(gy + offset_y)))

running = True
while running:
    # A janela agora cobre toda a tela, então preenchemos com a cor de fundo
    screen.fill((120, 120, 120))
    
    nova_pos_mouse = win32api.GetCursorPos()
    if nova_pos_mouse != ultima_pos_mouse:
        ultimo_input = time.time()
    ultima_pos_mouse = nova_pos_mouse

    tempo_inativo = time.time() - ultimo_input
    dormindo = tempo_inativo > 40
    tempo_atual = time.time()

    if not atacando and not dormindo and tempo_atual > tempo_ataque:
        atacando = True
        fase_puxando = False
        tempo_ataque = time.time() + random.uniform(45, 100)

    if not montinho and not atacando and not dormindo and tempo_atual > tempo_proximo_montinho:
        montinho = MontinhoFolhas()

    if montinho:
        if not montinho.atualizar():
            montinho = None
            tempo_proximo_montinho = time.time() + random.uniform(60, 90)

    velocidade_andar = 3
    velocidade_correr = 8
    velocidade_puxar = 2

    sprite = None
    frame_rate = 1

    # Comportamento com o monte de folhas (ainda que não esteja puxando ou dormindo)
    indo_para_folha = False
    if montinho and not atacando and not dormindo and montinho.estado == "parado":
        # Calcula a distância entre o centro do ganso e o centro do monte de folhas
        cx_ganso = x + SPRITE_LARGURA // 2
        cy_ganso = y + SPRITE_ALTURA // 2
        cx_folha = montinho.x + SPRITE_LARGURA // 2
        cy_folha = montinho.y + SPRITE_ALTURA // 2
        dist = ((cx_ganso - cx_folha) ** 2 + (cy_ganso - cy_folha) ** 2) ** 0.5
        if dist > 5:
            indo_para_folha = True
            dx, dy = calcular_direcao_alvo((x, y), (montinho.x, montinho.y))
            x += dx * velocidade_correr
            y += dy * velocidade_correr
            ultima_direcao_horizontal = "d" if dx >= 0 else "e"
            sprite_direcao = ultima_direcao_horizontal
            sprite = sprites[f"correndo_{sprite_direcao}"][frame_index % 3]
            frame_rate = 10
        else:
            montinho.iniciar_explosao(ultima_direcao_horizontal)

    if not sprite:
        if atacando:
            if not fase_puxando:
                origem_ganso = (x + SPRITE_LARGURA // 2, y + SPRITE_ALTURA // 2)
                dx, dy = calcular_direcao_alvo(origem_ganso, nova_pos_mouse)
                x += dx * velocidade_correr
                y += dy * velocidade_correr
                x = max(0, min(screen_width - SPRITE_LARGURA, x))
                y = max(0, min(screen_height - SPRITE_ALTURA, y))
                origem_ganso = (x + SPRITE_LARGURA // 2, y + SPRITE_ALTURA // 2)
                dist_centro = ((origem_ganso[0] - nova_pos_mouse[0])**2 + (origem_ganso[1] - nova_pos_mouse[1])**2)**0.5
                if dist_centro < 40:
                    fase_puxando = True
                    ponto_destino = (
                        random.randint(0, screen_width - SPRITE_LARGURA),
                        random.randint(0, screen_height - SPRITE_ALTURA)
                    )
            else:
                dx, dy = calcular_direcao_alvo((x, y), ponto_destino)
                x += dx * velocidade_puxar
                y += dy * velocidade_puxar
                x = max(0, min(screen_width - SPRITE_LARGURA, x))
                y = max(0, min(screen_height - SPRITE_ALTURA, y))
                mover_mouse_para_boca(x, y, ultima_direcao_horizontal)
                if abs(x - ponto_destino[0]) < 10 and abs(y - ponto_destino[1]) < 10:
                    atacando = False

            ultima_direcao_horizontal = "d" if dx >= 0 else "e"
            sprite_direcao = ultima_direcao_horizontal
            if fase_puxando:
                sprite = sprites[f"puxando_{sprite_direcao}"][frame_index % 2]
                frame_rate = 3
            else:
                sprite = sprites[f"correndo_{sprite_direcao}"][frame_index % 3]
                frame_rate = 12

        elif dormindo:
            sprite_direcao = ultima_direcao_horizontal
            sprite = sprites[f"dormindo_{sprite_direcao}"][frame_index % 3]
            frame_rate = 1

        else:
            if tempo_atual > tempo_proximo_estado:
                proximo_estado()
            moveu = False
            novo_x, novo_y = x, y
            if "d" in direcao:
                novo_x += velocidade_andar
            if "e" in direcao:
                novo_x -= velocidade_andar
            if "c" in direcao:
                novo_y -= velocidade_andar
            if "b" in direcao:
                novo_y += velocidade_andar
            limite_x = 0 <= novo_x <= screen_width - SPRITE_LARGURA
            limite_y = 0 <= novo_y <= screen_height - SPRITE_ALTURA
            if not limite_x:
                if "d" in direcao:
                    direcao = direcao.replace("d", "e")
                elif "e" in direcao:
                    direcao = direcao.replace("e", "d")
            if not limite_y:
                if "b" in direcao:
                    direcao = direcao.replace("b", "c")
                elif "c" in direcao:
                    direcao = direcao.replace("c", "b")
            novo_x, novo_y = x, y
            if "d" in direcao:
                novo_x += velocidade_andar
            if "e" in direcao:
                novo_x -= velocidade_andar
            if "c" in direcao:
                novo_y -= velocidade_andar
            if "b" in direcao:
                novo_y += velocidade_andar
            moveu = (novo_x != x or novo_y != y)
            if "d" in direcao:
                ultima_direcao_horizontal = "d"
            elif "e" in direcao:
                ultima_direcao_horizontal = "e"
            sprite_direcao = ultima_direcao_horizontal
            if estado == "andar" and moveu:
                sprite = sprites[f"andar_{sprite_direcao}"][frame_index % 2]
                frame_rate = 6
                x, y = novo_x, novo_y
                x = max(0, min(screen_width - SPRITE_LARGURA, x))
                y = max(0, min(screen_height - SPRITE_ALTURA, y))
            else:
                sprite = sprites[f"parado_{sprite_direcao}"][frame_index % 2]
                frame_rate = 1

    # Desenha o ganso na posição (x, y) dentro da janela fixa
    screen.blit(sprite, (x, y))
    # Desenha o monte de folhas, se houver
    if montinho:
        montinho.desenhar(screen)

    pygame.display.update()
    
    # Atualiza o frame do sprite conforme a taxa definida
    if pygame.time.get_ticks() % (1000 // frame_rate) < 30:
        frame_index += 1

    # Mantém a janela fixa no topo e na posição (0,0) com tamanho total da tela
    win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, screen_width, screen_height, win32con.SWP_NOACTIVATE)

    clock.tick(30)

pygame.quit()
