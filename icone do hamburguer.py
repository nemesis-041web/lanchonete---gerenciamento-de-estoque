import struct

def criar_icone_hamburguer(nome_arquivo="hamburguer.ico"):
    largura = 32
    altura = 32

    # Paleta de cores (RGBA)
    TRANSP = (0, 0, 0, 0)
    PAO_CIMA = (225, 130, 40, 255)       # Laranja/dourado pão
    GERGELIM = (255, 235, 180, 255)      # Sementes
    ALFACE = (76, 175, 80, 255)          # Verde alface
    QUEIJO = (255, 214, 0, 255)          # Amarelo queijo
    CARNE = (93, 46, 21, 255)            # Marrom hambúrguer
    PAO_BAIXO = (210, 115, 30, 255)      # Base do pão
    BORDA = (45, 25, 10, 255)            # Contorno suave

    matriz = [[TRANSP for _ in range(largura)] for _ in range(altura)]

    # Desenho pixel art do hambúrguer (linhas de 0 no topo a 31 na base)
    for y in range(altura):
        for x in range(largura):
            # Pão Superior (Arco: linhas 5 a 13)
            if 5 <= y <= 13:
                dx = abs(x - 15.5)
                dy = 14 - y
                if (dx**2) / (12**2) + (dy**2) / (9**2) <= 1.0:
                    matriz[y][x] = PAO_CIMA
                    # Sementes de gergelim
                    if (x, y) in [(11, 8), (16, 7), (20, 9), (13, 11), (18, 11)]:
                        matriz[y][x] = GERGELIM

            # Folha de Alface Ondulada (linhas 14 a 15)
            elif 14 <= y <= 15 and 3 <= x <= 28:
                if (x % 4 in [0, 1] and y == 14) or (x % 4 in [2, 3] and y == 15):
                    matriz[y][x] = ALFACE

            # Queijo Derretido (linhas 16 a 17)
            elif 16 <= y <= 17 and 4 <= x <= 27:
                matriz[y][x] = QUEIJO
                # Gotas de queijo escorrendo
                if y == 17 and x in [7, 8, 19, 20]:
                    matriz[y][x] = QUEIJO

            # Carne / Hambúrguer Artesanal (linhas 18 a 21)
            elif 18 <= y <= 21 and 4 <= x <= 27:
                matriz[y][x] = CARNE

            # Pão da Base (linhas 22 a 25)
            elif 22 <= y <= 25 and 5 <= x <= 26:
                matriz[y][x] = PAO_BAIXO

    # Montagem binária do formato Windows ICO (DIB 32-bit RGBA)
    tamanho_pixels = largura * altura * 4
    tamanho_mask = ((largura + 31) // 32 * 4) * altura
    tamanho_imagem = 40 + tamanho_pixels + tamanho_mask

    cabecalho_ico = struct.pack("<HHH", 0, 1, 1)
    entrada_dir = struct.pack(
        "<BBBBHHII",
        largura, altura, 0, 0, 1, 32, tamanho_imagem, 6 + 16
    )

    # Cabeçalho BITMAPINFOHEADER (altura é dobrada no formato ICO: imagem + máscara)
    dib_header = struct.pack(
        "<IIIHHIIIIII",
        40, largura, altura * 2, 1, 32, 0,
        tamanho_pixels + tamanho_mask, 0, 0, 0, 0
    )

    # Gravação dos pixels de baixo para cima (padrão BMP) em BGRA
    pixels_bin = bytearray()
    for y in reversed(range(altura)):
        for x in range(largura):
            r, g, b, a = matriz[y][x]
            pixels_bin.extend([b, g, r, a])

    mask_bin = bytes(tamanho_mask)  # Máscara 1-bit nula pois o canal Alpha de 32-bit já resolve

    with open(nome_arquivo, "wb") as f:
        f.write(cabecalho_ico)
        f.write(entrada_dir)
        f.write(dib_header)
        f.write(pixels_bin)
        f.write(mask_bin)

    print(f"Sucesso! Arquivo '{nome_arquivo}' criado.")

if __name__ == "__main__":
    criar_icone_hamburguer()