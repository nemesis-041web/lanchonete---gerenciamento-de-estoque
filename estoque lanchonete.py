from datetime import datetime
import os
import sqlite3
import sys
import tkinter as tk
from tkinter import messagebox, ttk

# Utilitário para localizar recursos tanto no Python normal quanto dentro do .exe empacotado
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- CONFIGURAÇÃO DE BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect("lanchonete_boa_pedida.db")
    cursor = conn.cursor()

    # Cardápio / Vitrine
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            preco REAL NOT NULL,
            estoque INTEGER NOT NULL,
            categoria TEXT NOT NULL
        )
    """
    )

    # Histórico de Modificações de Preço/Estoque Manual
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER,
            nome TEXT,
            preco_antigo REAL,
            preco_novo REAL,
            estoque_antigo INTEGER,
            estoque_novo INTEGER,
            data_modificacao TEXT
        )
    """
    )

    # Registro de Vendas Finalizadas
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS vendas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            total REAL NOT NULL,
            data_venda TEXT NOT NULL
        )
    """
    )

    # Itens pertencentes a cada venda
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS itens_venda (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            venda_id INTEGER NOT NULL,
            produto_id INTEGER NOT NULL,
            nome_produto TEXT NOT NULL,
            quantidade INTEGER NOT NULL,
            subtotal REAL NOT NULL,
            FOREIGN KEY (venda_id) REFERENCES vendas (id)
        )
    """
    )

    conn.commit()
    conn.close()


# --- INTERFACE PRINCIPAL ---
class BoaPedidaApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Lanchonete Boa Pedida")
        self.root.geometry("1080x720")
        self.root.configure(bg="#E3F2FD")

        # Configura o ícone de hambúrguer na barra de título
        caminho_ico = resource_path("hamburguer.ico")
        if os.path.exists(caminho_ico):
            try:
                self.root.iconbitmap(caminho_ico)
            except Exception:
                pass

        # Paleta de Cores
        self.cor_azul_claro = "#E3F2FD"
        self.cor_azul_medio = "#90CAF9"
        self.cor_laranja = "#FF9800"
        self.cor_laranja_escuro = "#F57C00"
        self.cor_texto = "#263238"

        # Comanda atual (em memória durante o atendimento)
        self.carrinho_atual = []

        self.setup_styles()
        self.setup_ui()
        self.listar_produtos()
        self.listar_historico()
        self.carregar_catalogo_pdv()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("TNotebook", background=self.cor_azul_claro)
        style.configure(
            "TNotebook.Tab",
            background=self.cor_azul_medio,
            foreground=self.cor_texto,
            padding=[16, 7],
            font=("Helvetica", 10, "bold"),
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", self.cor_laranja)],
            foreground=[("selected", "#FFFFFF")],
        )

        style.configure(
            "Treeview",
            background="#FFFFFF",
            foreground=self.cor_texto,
            fieldbackground="#FFFFFF",
            rowheight=26,
            font=("Helvetica", 9),
        )
        style.configure(
            "Treeview.Heading",
            background=self.cor_azul_medio,
            foreground=self.cor_texto,
            font=("Helvetica", 9, "bold"),
        )
        style.map(
            "Treeview",
            background=[("selected", self.cor_laranja)],
            foreground=[("selected", "#FFFFFF")],
        )

    def setup_ui(self):
        header = tk.Frame(self.root, bg=self.cor_laranja, height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        titulo = tk.Label(
            header,
            text="LANCHONETE BOA PEDIDA",
            font=("Helvetica", 18, "bold"),
            fg="#FFFFFF",
            bg=self.cor_laranja,
        )
        titulo.pack(pady=12)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        self.tab_pdv = tk.Frame(self.notebook, bg=self.cor_azul_claro)
        self.tab_produtos = tk.Frame(self.notebook, bg=self.cor_azul_claro)
        self.tab_historico = tk.Frame(self.notebook, bg=self.cor_azul_claro)

        self.notebook.add(self.tab_pdv, text="Frente de Caixa")
        self.notebook.add(self.tab_produtos, text="Gestão do Cardápio / Vitrine")
        self.notebook.add(self.tab_historico, text="Histórico de Preços")

        self.montar_aba_pdv()
        self.montar_aba_produtos()
        self.montar_aba_historico()

    # --- ABA: FRENTE DE CAIXA (PDV) ---
    def montar_aba_pdv(self):
        frame_esq = tk.LabelFrame(
            self.tab_pdv,
            text=" Itens Disponíveis na Vitrine ",
            bg=self.cor_azul_claro,
            fg=self.cor_texto,
            font=("Helvetica", 10, "bold"),
            padx=10,
            pady=10,
        )
        frame_esq.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 5), pady=10)

        frame_pesq = tk.Frame(frame_esq, bg=self.cor_azul_claro)
        frame_pesq.pack(fill=tk.X, pady=(0, 8))

        tk.Label(frame_pesq, text="Pesquisar:", bg=self.cor_azul_claro, fg=self.cor_texto).pack(side=tk.LEFT)
        self.txt_busca_pdv = tk.Entry(frame_pesq)
        self.txt_busca_pdv.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.txt_busca_pdv.bind("<KeyRelease>", lambda e: self.carregar_catalogo_pdv(self.txt_busca_pdv.get()))

        cols = ("id", "nome", "preco", "estoque")
        self.tree_catalogo_pdv = ttk.Treeview(frame_esq, columns=cols, show="headings", selectmode="browse")
        self.tree_catalogo_pdv.heading("id", text="ID")
        self.tree_catalogo_pdv.heading("nome", text="Item")
        self.tree_catalogo_pdv.heading("preco", text="Preço (R$)")
        self.tree_catalogo_pdv.heading("estoque", text="Disponível")

        self.tree_catalogo_pdv.column("id", width=40, anchor="center")
        self.tree_catalogo_pdv.column("nome", width=180)
        self.tree_catalogo_pdv.column("preco", width=80, anchor="e")
        self.tree_catalogo_pdv.column("estoque", width=80, anchor="center")
        self.tree_catalogo_pdv.pack(fill=tk.BOTH, expand=True)

        frame_add = tk.Frame(frame_esq, bg=self.cor_azul_claro)
        frame_add.pack(fill=tk.X, pady=10)

        tk.Label(frame_add, text="Qtd:", bg=self.cor_azul_claro, fg=self.cor_texto).pack(side=tk.LEFT)
        self.spin_qtd_venda = tk.Spinbox(frame_add, from_=1, to=100, width=5)
        self.spin_qtd_venda.pack(side=tk.LEFT, padx=6)

        btn_add = tk.Button(
            frame_add,
            text="+ Adicionar à Comanda",
            bg=self.cor_laranja,
            fg="#FFFFFF",
            font=("Helvetica", 9, "bold"),
            command=self.adicionar_item_comanda,
            relief=tk.FLAT,
            cursor="hand2",
            padx=10,
        )
        btn_add.pack(side=tk.RIGHT)

        frame_dir = tk.LabelFrame(
            self.tab_pdv,
            text=" Comanda Aberta ",
            bg=self.cor_azul_claro,
            fg=self.cor_texto,
            font=("Helvetica", 10, "bold"),
            padx=10,
            pady=10,
        )
        frame_dir.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 10), pady=10)

        cols_comanda = ("nome", "qtd", "subtotal")
        self.tree_comanda = ttk.Treeview(frame_dir, columns=cols_comanda, show="headings")
        self.tree_comanda.heading("nome", text="Item")
        self.tree_comanda.heading("qtd", text="Qtd")
        self.tree_comanda.heading("subtotal", text="Subtotal (R$)")

        self.tree_comanda.column("nome", width=180)
        self.tree_comanda.column("qtd", width=50, anchor="center")
        self.tree_comanda.column("subtotal", width=90, anchor="e")
        self.tree_comanda.pack(fill=tk.BOTH, expand=True)

        frame_acoes_comanda = tk.Frame(frame_dir, bg=self.cor_azul_claro)
        frame_acoes_comanda.pack(fill=tk.X, pady=5)

        btn_remover_comanda = tk.Button(
            frame_acoes_comanda,
            text="Remover Item",
            bg="#E57373",
            fg="#FFFFFF",
            font=("Helvetica", 8, "bold"),
            command=self.remover_item_comanda,
            relief=tk.FLAT,
        )
        btn_remover_comanda.pack(side=tk.LEFT)

        self.lbl_total_comanda = tk.Label(
            frame_dir,
            text="TOTAL: R$ 0.00",
            font=("Helvetica", 16, "bold"),
            bg=self.cor_azul_medio,
            fg=self.cor_texto,
            pady=8,
        )
        self.lbl_total_comanda.pack(fill=tk.X, pady=10)

        btn_fechar = tk.Button(
            frame_dir,
            text="FINALIZAR PEDIDO",
            bg=self.cor_laranja,
            fg="#FFFFFF",
            font=("Helvetica", 11, "bold"),
            command=self.finalizar_pedido,
            relief=tk.FLAT,
            cursor="hand2",
            pady=8,
        )
        btn_fechar.pack(fill=tk.X)

    # --- LÓGICA DE PDV ---
    def carregar_catalogo_pdv(self, filtro=""):
        for row in self.tree_catalogo_pdv.get_children():
            self.tree_catalogo_pdv.delete(row)

        conn = sqlite3.connect("lanchonete_boa_pedida.db")
        cursor = conn.cursor()
        if filtro:
            cursor.execute(
                "SELECT id, nome, preco, estoque FROM produtos WHERE nome LIKE ? AND estoque > 0",
                (f"%{filtro}%",),
            )
        else:
            cursor.execute("SELECT id, nome, preco, estoque FROM produtos WHERE estoque > 0")

        for item in cursor.fetchall():
            self.tree_catalogo_pdv.insert(
                "", tk.END, values=(item[0], item[1], f"{item[2]:.2f}", f"{item[3]} un")
            )
        conn.close()

    def adicionar_item_comanda(self):
        sel = self.tree_catalogo_pdv.selection()
        if not sel:
            messagebox.showwarning("Aviso", "Selecione um produto da vitrine.")
            return

        try:
            qtd_pedida = int(self.spin_qtd_venda.get())
            if qtd_pedida <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Erro", "Quantidade inválida.")
            return

        item_selecionado = self.tree_catalogo_pdv.item(sel[0])["values"]
        prod_id = item_selecionado[0]
        nome = item_selecionado[1]
        preco = float(item_selecionado[2])
        estoque_disponivel = int(str(item_selecionado[3]).replace(" un", ""))

        qtd_ja_no_carrinho = sum(i["qtd"] for i in self.carrinho_atual if i["id"] == prod_id)

        if qtd_pedida + qtd_ja_no_carrinho > estoque_disponivel:
            messagebox.showerror(
                "Estoque Insuficiente",
                f"Apenas {estoque_disponivel} unidades disponíveis na vitrine!",
            )
            return

        for item in self.carrinho_atual:
            if item["id"] == prod_id:
                item["qtd"] += qtd_pedida
                item["subtotal"] = item["qtd"] * item["preco"]
                break
        else:
            self.carrinho_atual.append(
                {
                    "id": prod_id,
                    "nome": nome,
                    "preco": preco,
                    "qtd": qtd_pedida,
                    "subtotal": preco * qtd_pedida,
                }
            )

        self.atualizar_tabela_comanda()

    def remover_item_comanda(self):
        sel = self.tree_comanda.selection()
        if not sel:
            return
        idx = self.tree_comanda.index(sel[0])
        del self.carrinho_atual[idx]
        self.atualizar_tabela_comanda()

    def atualizar_tabela_comanda(self):
        for row in self.tree_comanda.get_children():
            self.tree_comanda.delete(row)

        total = 0.0
        for item in self.carrinho_atual:
            self.tree_comanda.insert(
                "", tk.END, values=(item["nome"], item["qtd"], f"{item['subtotal']:.2f}")
            )
            total += item["subtotal"]

        self.lbl_total_comanda.config(text=f"TOTAL: R$ {total:.2f}")

    def finalizar_pedido(self):
        if not self.carrinho_atual:
            messagebox.showwarning("Aviso", "A comanda está vazia.")
            return

        total_pedido = sum(i["subtotal"] for i in self.carrinho_atual)
        data_atual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        conn = sqlite3.connect("lanchonete_boa_pedida.db")
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT INTO vendas (total, data_venda) VALUES (?, ?)",
                (total_pedido, data_atual),
            )
            venda_id = cursor.lastrowid

            for item in self.carrinho_atual:
                cursor.execute(
                    """
                    INSERT INTO itens_venda (venda_id, produto_id, nome_produto, quantidade, subtotal)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (venda_id, item["id"], item["nome"], item["qtd"], item["subtotal"]),
                )

                cursor.execute(
                    "UPDATE produtos SET estoque = estoque - ? WHERE id = ?",
                    (item["qtd"], item["id"]),
                )

            conn.commit()

            messagebox.showinfo(
                "Pedido Finalizado",
                f"Pedido #{venda_id} concluído com sucesso!\nTotal: R$ {total_pedido:.2f}\nEstoque atualizado!",
            )

            self.carrinho_atual.clear()
            self.atualizar_tabela_comanda()
            self.carregar_catalogo_pdv()
            self.listar_produtos()

        except Exception as e:
            conn.rollback()
            messagebox.showerror("Erro de Transação", f"Falha ao concluir venda: {str(e)}")
        finally:
            conn.close()

    # --- ABA: GESTÃO DO CARDÁPIO & VITRINE ---
    def montar_aba_produtos(self):
        frame_form = tk.LabelFrame(
            self.tab_produtos,
            text=" Dados do Item ",
            bg=self.cor_azul_claro,
            fg=self.cor_texto,
            font=("Helvetica", 11, "bold"),
            padx=12,
            pady=12,
        )
        frame_form.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 5), pady=10)

        tk.Label(frame_form, text="ID:", bg=self.cor_azul_claro, fg=self.cor_texto).grid(row=0, column=0, sticky="w")
        self.txt_id = tk.Entry(frame_form, state="readonly", width=10, bg="#ECEFF1")
        self.txt_id.grid(row=0, column=1, pady=4, sticky="w")

        tk.Label(frame_form, text="Nome:", bg=self.cor_azul_claro, fg=self.cor_texto).grid(row=1, column=0, sticky="w")
        self.txt_nome = tk.Entry(frame_form, width=22)
        self.txt_nome.grid(row=1, column=1, pady=4, sticky="w")

        tk.Label(frame_form, text="Preço (R$):", bg=self.cor_azul_claro, fg=self.cor_texto).grid(
            row=2, column=0, sticky="w"
        )
        self.txt_preco = tk.Entry(frame_form, width=22)
        self.txt_preco.grid(row=2, column=1, pady=4, sticky="w")

        tk.Label(frame_form, text="Qtd. Vitrine:", bg=self.cor_azul_claro, fg=self.cor_texto).grid(
            row=3, column=0, sticky="w"
        )
        self.txt_estoque = tk.Entry(frame_form, width=22)
        self.txt_estoque.grid(row=3, column=1, pady=4, sticky="w")

        tk.Label(frame_form, text="Categoria:", bg=self.cor_azul_claro, fg=self.cor_texto).grid(
            row=4, column=0, sticky="w"
        )
        self.combo_cat = ttk.Combobox(
            frame_form,
            values=["Bolo/Sobremesa", "Salgado", "Bebida", "Lanche"],
            state="readonly",
            width=20,
        )
        self.combo_cat.set("Bolo/Sobremesa")
        self.combo_cat.grid(row=4, column=1, pady=4, sticky="w")

        btn_frame = tk.Frame(frame_form, bg=self.cor_azul_claro)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=15)

        self.criar_botao(btn_frame, "Adicionar", self.salvar_produto, self.cor_laranja).grid(
            row=0, column=0, padx=2, pady=2, sticky="ew"
        )
        self.criar_botao(btn_frame, "Salvar Edição", self.atualizar_produto, self.cor_azul_medio).grid(
            row=0, column=1, padx=2, pady=2, sticky="ew"
        )
        self.criar_botao(btn_frame, "Excluir Item", self.excluir_produto, "#E57373").grid(
            row=1, column=0, padx=2, pady=2, sticky="ew"
        )
        self.criar_botao(btn_frame, "Limpar", self.limpar_campos, "#CFD8DC").grid(
            row=1, column=1, padx=2, pady=2, sticky="ew"
        )

        frame_tabela = tk.Frame(self.tab_produtos, bg=self.cor_azul_claro)
        frame_tabela.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 10), pady=10)

        frame_busca = tk.Frame(frame_tabela, bg=self.cor_azul_claro)
        frame_busca.pack(fill=tk.X, pady=(0, 10))

        tk.Label(frame_busca, text="Buscar Item:", font=("Helvetica", 10, "bold"), bg=self.cor_azul_claro).pack(
            side=tk.LEFT
        )
        self.txt_busca = tk.Entry(frame_busca)
        self.txt_busca.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        self.txt_busca.bind("<KeyRelease>", self.filtrar_produtos)

        cols = ("id", "nome", "preco", "estoque", "categoria")
        self.tabela_prod = ttk.Treeview(frame_tabela, columns=cols, show="headings", selectmode="browse")
        self.tabela_prod.heading("id", text="ID")
        self.tabela_prod.heading("nome", text="Nome do Item")
        self.tabela_prod.heading("preco", text="Preço (R$)")
        self.tabela_prod.heading("estoque", text="Disponível (Vitrine)")
        self.tabela_prod.heading("categoria", text="Categoria")

        self.tabela_prod.column("id", width=45, anchor="center")
        self.tabela_prod.column("nome", width=200)
        self.tabela_prod.column("preco", width=80, anchor="e")
        self.tabela_prod.column("estoque", width=120, anchor="center")
        self.tabela_prod.column("categoria", width=110, anchor="center")

        self.tabela_prod.pack(fill=tk.BOTH, expand=True)
        self.tabela_prod.bind("<<TreeviewSelect>>", self.carregar_dados_selecionados)

    # --- ABA: HISTÓRICO ---
    def montar_aba_historico(self):
        frame_hist = tk.Frame(self.tab_historico, bg=self.cor_azul_claro)
        frame_hist.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        cols = ("id", "prod_id", "nome", "p_antigo", "p_novo", "e_antigo", "e_novo", "data")
        self.tabela_hist = ttk.Treeview(frame_hist, columns=cols, show="headings")

        self.tabela_hist.heading("id", text="Log ID")
        self.tabela_hist.heading("prod_id", text="Item ID")
        self.tabela_hist.heading("nome", text="Produto")
        self.tabela_hist.heading("p_antigo", text="Preço Antigo")
        self.tabela_hist.heading("p_novo", text="Preço Novo")
        self.tabela_hist.heading("e_antigo", text="Vitrine Ant.")
        self.tabela_hist.heading("e_novo", text="Vitrine Nova")
        self.tabela_hist.heading("data", text="Data / Horário")

        for col in cols:
            self.tabela_hist.column(col, anchor="center")
        self.tabela_hist.column("nome", anchor="w", width=150)
        self.tabela_hist.column("data", width=140)

        self.tabela_hist.pack(fill=tk.BOTH, expand=True)

    def criar_botao(self, container, texto, comando, cor_bg):
        return tk.Button(
            container,
            text=texto,
            command=comando,
            bg=cor_bg,
            fg="#263238" if cor_bg in [self.cor_azul_medio, "#CFD8DC"] else "#FFFFFF",
            font=("Helvetica", 9, "bold"),
            relief=tk.FLAT,
            padx=8,
            pady=4,
            cursor="hand2",
        )

    def salvar_produto(self):
        nome = self.txt_nome.get().strip()
        preco = self.txt_preco.get().strip().replace(",", ".")
        estoque = self.txt_estoque.get().strip()
        cat = self.combo_cat.get()

        if not nome or not preco or not estoque:
            messagebox.showwarning("Aviso", "Preencha todos os campos obrigatórios!")
            return

        try:
            preco = float(preco)
            estoque = int(estoque)
        except ValueError:
            messagebox.showerror("Erro", "Preço deve ser numérico e Vitrine em unidades inteiras.")
            return

        conn = sqlite3.connect("lanchonete_boa_pedida.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO produtos (nome, preco, estoque, categoria) VALUES (?, ?, ?, ?)",
            (nome, preco, estoque, cat),
        )
        conn.commit()
        conn.close()

        self.limpar_campos()
        self.listar_produtos()
        self.carregar_catalogo_pdv()
        messagebox.showinfo("Sucesso", "Item cadastrado com sucesso!")

    def atualizar_produto(self):
        prod_id = self.txt_id.get().strip()
        if not prod_id:
            messagebox.showwarning("Aviso", "Selecione um item da tabela para editar.")
            return

        nome = self.txt_nome.get().strip()
        preco = float(self.txt_preco.get().strip().replace(",", "."))
        estoque = int(self.txt_estoque.get().strip())
        cat = self.combo_cat.get()

        conn = sqlite3.connect("lanchonete_boa_pedida.db")
        cursor = conn.cursor()
        cursor.execute("SELECT preco, estoque FROM produtos WHERE id = ?", (prod_id,))
        p_antigo, e_antigo = cursor.fetchone()

        if p_antigo != preco or e_antigo != estoque:
            data_atual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            cursor.execute(
                """
                INSERT INTO historico (produto_id, nome, preco_antigo, preco_novo, estoque_antigo, estoque_novo, data_modificacao)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (prod_id, nome, p_antigo, preco, e_antigo, estoque, data_atual),
            )

        cursor.execute(
            """
            UPDATE produtos 
            SET nome = ?, preco = ?, estoque = ?, categoria = ? 
            WHERE id = ?
        """,
            (nome, preco, estoque, cat, prod_id),
        )

        conn.commit()
        conn.close()

        self.limpar_campos()
        self.listar_produtos()
        self.listar_historico()
        self.carregar_catalogo_pdv()
        messagebox.showinfo("Sucesso", "Item alterado e histórico atualizado!")

    def excluir_produto(self):
        prod_id = self.txt_id.get().strip()
        if not prod_id:
            messagebox.showwarning("Aviso", "Selecione um item para excluir.")
            return

        if messagebox.askyesno("Confirmação", "Deseja remover este item do cardápio?"):
            conn = sqlite3.connect("lanchonete_boa_pedida.db")
            cursor = conn.cursor()
            cursor.execute("DELETE FROM produtos WHERE id = ?", (prod_id,))
            conn.commit()
            conn.close()

            self.limpar_campos()
            self.listar_produtos()
            self.carregar_catalogo_pdv()

    def listar_produtos(self, filtro=""):
        for row in self.tabela_prod.get_children():
            self.tabela_prod.delete(row)

        conn = sqlite3.connect("lanchonete_boa_pedida.db")
        cursor = conn.cursor()
        if filtro:
            cursor.execute(
                "SELECT id, nome, preco, estoque, categoria FROM produtos WHERE nome LIKE ?",
                (f"%{filtro}%",),
            )
        else:
            cursor.execute("SELECT id, nome, preco, estoque, categoria FROM produtos")

        for item in cursor.fetchall():
            self.tabela_prod.insert(
                "", tk.END, values=(item[0], item[1], f"{item[2]:.2f}", f"{item[3]} unid.", item[4])
            )
        conn.close()

    def listar_historico(self):
        for row in self.tabela_hist.get_children():
            self.tabela_hist.delete(row)

        conn = sqlite3.connect("lanchonete_boa_pedida.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM historico ORDER BY id DESC")

        for h in cursor.fetchall():
            self.tabela_hist.insert(
                "",
                tk.END,
                values=(
                    h[0],
                    h[1],
                    h[2],
                    f"R$ {h[3]:.2f}",
                    f"R$ {h[4]:.2f}",
                    f"{h[5]} un",
                    f"{h[6]} un",
                    h[7],
                ),
            )
        conn.close()

    def filtrar_produtos(self, event=None):
        self.listar_produtos(self.txt_busca.get().strip())

    def carregar_dados_selecionados(self, event=None):
        selecao = self.tabela_prod.selection()
        if not selecao:
            return

        item = self.tabela_prod.item(selecao[0])["values"]
        self.txt_id.config(state="normal")
        self.txt_id.delete(0, tk.END)
        self.txt_id.insert(0, str(item[0]))
        self.txt_id.config(state="readonly")

        self.txt_nome.delete(0, tk.END)
        self.txt_nome.insert(0, str(item[1]))

        self.txt_preco.delete(0, tk.END)
        self.txt_preco.insert(0, str(item[2]))

        self.txt_estoque.delete(0, tk.END)
        self.txt_estoque.insert(0, str(item[3]).replace(" unid.", ""))
        self.combo_cat.set(str(item[4]))

    def limpar_campos(self):
        self.txt_id.config(state="normal")
        self.txt_id.delete(0, tk.END)
        self.txt_id.config(state="readonly")
        self.txt_nome.delete(0, tk.END)
        self.txt_preco.delete(0, tk.END)
        self.txt_estoque.delete(0, tk.END)
        self.combo_cat.set("Bolo/Sobremesa")
        if self.tabela_prod.selection():
            self.tabela_prod.selection_remove(self.tabela_prod.selection()[0])


if __name__ == "__main__":
    init_db()
    root = tk.Tk()
    app = BoaPedidaApp(root)
    root.mainloop()