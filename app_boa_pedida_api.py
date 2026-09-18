import http.server
import json
import socketserver
import threading
import tkinter as tk
from tkinter import messagebox, ttk
import urllib.error
import urllib.parse
import urllib.request

# =====================================================================
# 1. API FALSA (MOCK SERVER REST EM BACKGROUND)
# =====================================================================

PORT = 8000
API_URL = f"http://127.0.0.1:{PORT}"

# Banco de dados simulado em memória
mock_db = {
    "produtos": [
        {"id": 1, "nome": "Bolo de Cenoura c/ Chocolate", "preco": 8.50, "estoque": 12, "categoria": "Bolo/Sobremesa"},
        {"id": 2, "nome": "Torta Holandesa (Fatia)", "preco": 12.00, "estoque": 8, "categoria": "Bolo/Sobremesa"},
        {"id": 3, "nome": "Coxinha de Frango c/ Catupiry", "preco": 7.00, "estoque": 25, "categoria": "Salgado"},
        {"id": 4, "nome": "Pão de Queijo Mineiro", "preco": 4.50, "estoque": 30, "categoria": "Salgado"},
        {"id": 5, "nome": "Café Expresso", "preco": 5.00, "estoque": 50, "categoria": "Bebida"},
        {"id": 6, "nome": "Suco de Laranja Natural (400ml)", "preco": 9.00, "estoque": 15, "categoria": "Bebida"}
    ],
    "historico": [
        {
            "id": 1,
            "produto_id": 1,
            "nome": "Bolo de Cenoura c/ Chocolate",
            "preco_antigo": 7.50,
            "preco_novo": 8.50,
            "estoque_antigo": 10,
            "estoque_novo": 12,
            "data_modificacao": "18/09/2026 10:30:00"
        }
    ],
    "vendas": [],
    "next_prod_id": 7,
    "next_hist_id": 2,
    "next_venda_id": 1
}

class MockAPIHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Desativa os logs no console para não poluir o terminal
        pass

    def _set_headers(self, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/produtos":
            filtro = query.get("q", [""])[0].lower()
            apenas_disponiveis = query.get("apenas_estoque", ["false"])[0].lower() == "true"
            
            res = mock_db["produtos"]
            if filtro:
                res = [p for p in res if filtro in p["nome"].lower()]
            if apenas_disponiveis:
                res = [p for p in res if p["estoque"] > 0]
                
            self._set_headers(200)
            self.wfile.write(json.dumps(res).encode("utf-8"))

        elif path == "/historico":
            self._set_headers(200)
            # Retorna histórico invertido (mais recente primeiro)
            self.wfile.write(json.dumps(list(reversed(mock_db["historico"]))).encode("utf-8"))

        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": "Rota não encontrada"}).encode("utf-8"))

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}
        path = self.path

        if path == "/produtos":
            novo = {
                "id": mock_db["next_prod_id"],
                "nome": body["nome"],
                "preco": float(body["preco"]),
                "estoque": int(body["estoque"]),
                "categoria": body["categoria"]
            }
            mock_db["next_prod_id"] += 1
            mock_db["produtos"].append(novo)
            
            self._set_headers(201)
            self.wfile.write(json.dumps(novo).encode("utf-8"))

        elif path == "/pedidos/finalizar":
            # Realiza baixa em lote no estoque
            itens = body.get("itens", [])
            total = body.get("total", 0.0)
            data_hora = body.get("data", "")

            # Validação prévia de estoque
            for it in itens:
                p = next((x for x in mock_db["produtos"] if x["id"] == it["id"]), None)
                if not p or p["estoque"] < it["qtd"]:
                    self._set_headers(400)
                    self.wfile.write(json.dumps({"error": f"Estoque insuficiente para {it['nome']}"}).encode("utf-8"))
                    return

            # Efetua baixa
            for it in itens:
                p = next(x for x in mock_db["produtos"] if x["id"] == it["id"])
                p["estoque"] -= it["qtd"]

            venda_id = mock_db["next_venda_id"]
            mock_db["next_venda_id"] += 1
            mock_db["vendas"].append({
                "id": venda_id,
                "total": total,
                "data": data_hora,
                "itens": itens
            })

            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "sucesso", "venda_id": venda_id}).encode("utf-8"))

        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": "Rota não encontrada"}).encode("utf-8"))

    def do_PUT(self):
        # Ex: /produtos/1
        if self.path.startswith("/produtos/"):
            try:
                prod_id = int(self.path.split("/")[-1])
            except ValueError:
                self._set_headers(400)
                return

            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8"))

            p = next((x for x in mock_db["produtos"] if x["id"] == prod_id), None)
            if not p:
                self._set_headers(404)
                self.wfile.write(json.dumps({"error": "Produto não encontrado"}).encode("utf-8"))
                return

            # Registra alteração no histórico se preço ou estoque mudaram
            novo_preco = float(body["preco"])
            novo_estoque = int(body["estoque"])

            if p["preco"] != novo_preco or p["estoque"] != novo_estoque:
                log_entry = {
                    "id": mock_db["next_hist_id"],
                    "produto_id": p["id"],
                    "nome": body["nome"],
                    "preco_antigo": p["preco"],
                    "preco_novo": novo_preco,
                    "estoque_antigo": p["estoque"],
                    "estoque_novo": novo_estoque,
                    "data_modificacao": body.get("data_modificacao", "")
                }
                mock_db["next_hist_id"] += 1
                mock_db["historico"].append(log_entry)

            p["nome"] = body["nome"]
            p["preco"] = novo_preco
            p["estoque"] = novo_estoque
            p["categoria"] = body["categoria"]

            self._set_headers(200)
            self.wfile.write(json.dumps(p).encode("utf-8"))

    def do_DELETE(self):
        if self.path.startswith("/produtos/"):
            try:
                prod_id = int(self.path.split("/")[-1])
            except ValueError:
                self._set_headers(400)
                return

            mock_db["produtos"] = [x for x in mock_db["produtos"] if x["id"] != prod_id]
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "removido"}).encode("utf-8"))


def start_mock_api():
    # Permite reutilizar a porta imediatamente se fechar e abrir rápido
    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.TCPServer(("127.0.0.1", PORT), MockAPIHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()


# =====================================================================
# 2. CLIENTE API (FUNÇÕES AUXILIARES DE CONSUMO HTTP)
# =====================================================================

def api_get(endpoint, params=None):
    url = f"{API_URL}{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def api_post(endpoint, data):
    url = f"{API_URL}{endpoint}"
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def api_put(endpoint, data):
    url = f"{API_URL}{endpoint}"
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="PUT")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def api_delete(endpoint):
    url = f"{API_URL}{endpoint}"
    req = urllib.request.Request(url, method="DELETE")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


# =====================================================================
# 3. INTERFACE TKINTER (CLIENTE CONSUMINDO A API)
# =====================================================================

class BoaPedidaApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Lanchonete Boa Pedida - Conectado via API Mock")
        self.root.geometry("1080x720")
        self.root.configure(bg="#E3F2FD")

        # Paleta de Cores
        self.cor_azul_claro = "#E3F2FD"
        self.cor_azul_medio = "#90CAF9"
        self.cor_laranja = "#FF9800"
        self.cor_texto = "#263238"

        self.carrinho_atual = []

        self.setup_styles()
        self.setup_ui()
        self.atualizar_todas_as_telas()

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
        style.map("TNotebook.Tab", background=[("selected", self.cor_laranja)], foreground=[("selected", "#FFFFFF")])

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
        style.map("Treeview", background=[("selected", self.cor_laranja)], foreground=[("selected", "#FFFFFF")])

    def setup_ui(self):
        # Cabeçalho com indicador da API
        header = tk.Frame(self.root, bg=self.cor_laranja, height=65)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        titulo = tk.Label(
            header,
            text="LANCHONETE BOA PEDIDA",
            font=("Helvetica", 17, "bold"),
            fg="#FFFFFF",
            bg=self.cor_laranja,
        )
        titulo.pack(side=tk.LEFT, padx=20, pady=12)

        badge_api = tk.Label(
            header,
            text="● API Conectada (127.0.0.1:8000)",
            font=("Helvetica", 9, "bold"),
            fg="#E8F5E9",
            bg=self.cor_laranja,
        )
        badge_api.pack(side=tk.RIGHT, padx=20)

        # Abas
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        self.tab_pdv = tk.Frame(self.notebook, bg=self.cor_azul_claro)
        self.tab_produtos = tk.Frame(self.notebook, bg=self.cor_azul_claro)
        self.tab_historico = tk.Frame(self.notebook, bg=self.cor_azul_claro)

        self.notebook.add(self.tab_pdv, text="Frente de Caixa (PDV)")
        self.notebook.add(self.tab_produtos, text="Gestão de Cardápio e Vitrine")
        self.notebook.add(self.tab_historico, text="Histórico de Preços e Modificações")

        self.montar_aba_pdv()
        self.montar_aba_produtos()
        self.montar_aba_historico()

    # --- ABA: FRENTE DE CAIXA ---
    def montar_aba_pdv(self):
        frame_esq = tk.LabelFrame(
            self.tab_pdv, text=" Vitrine / Pronta Entrega ", bg=self.cor_azul_claro,
            fg=self.cor_texto, font=("Helvetica", 10, "bold"), padx=10, pady=10
        )
        frame_esq.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 5), pady=10)

        frame_pesq = tk.Frame(frame_esq, bg=self.cor_azul_claro)
        frame_pesq.pack(fill=tk.X, pady=(0, 8))

        tk.Label(frame_pesq, text="Pesquisar:", bg=self.cor_azul_claro, fg=self.cor_texto).pack(side=tk.LEFT)
        self.txt_busca_pdv = tk.Entry(frame_pesq)
        self.txt_busca_pdv.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.txt_busca_pdv.bind("<KeyRelease>", lambda e: self.listar_vitrine_pdv())

        cols = ("id", "nome", "preco", "estoque")
        self.tree_pdv = ttk.Treeview(frame_esq, columns=cols, show="headings", selectmode="browse")
        self.tree_pdv.heading("id", text="ID")
        self.tree_pdv.heading("nome", text="Item")
        self.tree_pdv.heading("preco", text="Preço")
        self.tree_pdv.heading("estoque", text="Na Vitrine")

        self.tree_pdv.column("id", width=40, anchor="center")
        self.tree_pdv.column("nome", width=180)
        self.tree_pdv.column("preco", width=80, anchor="e")
        self.tree_pdv.column("estoque", width=80, anchor="center")
        self.tree_pdv.pack(fill=tk.BOTH, expand=True)

        frame_add = tk.Frame(frame_esq, bg=self.cor_azul_claro)
        frame_add.pack(fill=tk.X, pady=10)

        tk.Label(frame_add, text="Qtd:", bg=self.cor_azul_claro, fg=self.cor_texto).pack(side=tk.LEFT)
        self.spin_qtd_pdv = tk.Spinbox(frame_add, from_=1, to=100, width=5)
        self.spin_qtd_pdv.pack(side=tk.LEFT, padx=6)

        btn_add = tk.Button(
            frame_add, text="+ Adicionar à Comanda", bg=self.cor_laranja, fg="#FFFFFF",
            font=("Helvetica", 9, "bold"), command=self.adicionar_item_comanda, relief=tk.FLAT, cursor="hand2"
        )
        btn_add.pack(side=tk.RIGHT)

        # Lado direito: Comanda
        frame_dir = tk.LabelFrame(
            self.tab_pdv, text=" Comanda Aberta ", bg=self.cor_azul_claro,
            fg=self.cor_texto, font=("Helvetica", 10, "bold"), padx=10, pady=10
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

        frame_acoes = tk.Frame(frame_dir, bg=self.cor_azul_claro)
        frame_acoes.pack(fill=tk.X, pady=5)

        tk.Button(
            frame_acoes, text="Remover Item", bg="#E57373", fg="#FFFFFF",
            font=("Helvetica", 8, "bold"), command=self.remover_item_comanda, relief=tk.FLAT
        ).pack(side=tk.LEFT)

        self.lbl_total = tk.Label(
            frame_dir, text="TOTAL: R$ 0.00", font=("Helvetica", 15, "bold"),
            bg=self.cor_azul_medio, fg=self.cor_texto, pady=8
        )
        self.lbl_total.pack(fill=tk.X, pady=8)

        tk.Button(
            frame_dir, text="FINALIZAR PEDIDO", bg=self.cor_laranja, fg="#FFFFFF",
            font=("Helvetica", 11, "bold"), command=self.finalizar_pedido_api, relief=tk.FLAT, cursor="hand2", pady=8
        ).pack(fill=tk.X)

    # --- ABA: GESTÃO DO CARDÁPIO ---
    def montar_aba_produtos(self):
        frame_form = tk.LabelFrame(
            self.tab_produtos, text=" Gerenciar Produto ", bg=self.cor_azul_claro,
            fg=self.cor_texto, font=("Helvetica", 10, "bold"), padx=12, pady=12
        )
        frame_form.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 5), pady=10)

        campos = [("ID:", "txt_id"), ("Nome:", "txt_nome"), ("Preço (R$):", "txt_preco"), ("Estoque Vitrine:", "txt_estoque")]
        for idx, (label_txt, var_name) in enumerate(campos):
            tk.Label(frame_form, text=label_txt, bg=self.cor_azul_claro, fg=self.cor_texto).grid(row=idx, column=0, sticky="w", pady=4)
            entry = tk.Entry(frame_form, width=22)
            if var_name == "txt_id":
                entry.config(state="readonly", bg="#ECEFF1")
            entry.grid(row=idx, column=1, pady=4, sticky="w")
            setattr(self, var_name, entry)

        tk.Label(frame_form, text="Categoria:", bg=self.cor_azul_claro, fg=self.cor_texto).grid(row=4, column=0, sticky="w", pady=4)
        self.combo_cat = ttk.Combobox(frame_form, values=["Bolo/Sobremesa", "Salgado", "Bebida", "Lanche"], state="readonly", width=20)
        self.combo_cat.set("Bolo/Sobremesa")
        self.combo_cat.grid(row=4, column=1, pady=4, sticky="w")

        btn_frame = tk.Frame(frame_form, bg=self.cor_azul_claro)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=15)

        self.criar_botao(btn_frame, "Novo / Salvar", self.salvar_produto_api, self.cor_laranja).grid(row=0, column=0, padx=2, pady=2, sticky="ew")
        self.criar_botao(btn_frame, "Atualizar", self.atualizar_produto_api, self.cor_azul_medio).grid(row=0, column=1, padx=2, pady=2, sticky="ew")
        self.criar_botao(btn_frame, "Excluir", self.excluir_produto_api, "#E57373").grid(row=1, column=0, padx=2, pady=2, sticky="ew")
        self.criar_botao(btn_frame, "Limpar", self.limpar_campos, "#CFD8DC").grid(row=1, column=1, padx=2, pady=2, sticky="ew")

        # Tabela
        frame_tab = tk.Frame(self.tab_produtos, bg=self.cor_azul_claro)
        frame_tab.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 10), pady=10)

        frame_busca = tk.Frame(frame_tab, bg=self.cor_azul_claro)
        frame_busca.pack(fill=tk.X, pady=(0, 8))

        tk.Label(frame_busca, text="Buscar Item:", font=("Helvetica", 9, "bold"), bg=self.cor_azul_claro).pack(side=tk.LEFT)
        self.txt_busca_geral = tk.Entry(frame_busca)
        self.txt_busca_geral.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        self.txt_busca_geral.bind("<KeyRelease>", lambda e: self.listar_catalogo_geral())

        cols = ("id", "nome", "preco", "estoque", "categoria")
        self.tree_catalogo = ttk.Treeview(frame_tab, columns=cols, show="headings", selectmode="browse")
        self.tree_catalogo.heading("id", text="ID")
        self.tree_catalogo.heading("nome", text="Nome")
        self.tree_catalogo.heading("preco", text="Preço (R$)")
        self.tree_catalogo.heading("estoque", text="Qtd Vitrine")
        self.tree_catalogo.heading("categoria", text="Categoria")

        self.tree_catalogo.column("id", width=45, anchor="center")
        self.tree_catalogo.column("nome", width=200)
        self.tree_catalogo.column("preco", width=80, anchor="e")
        self.tree_catalogo.column("estoque", width=100, anchor="center")
        self.tree_catalogo.column("categoria", width=110, anchor="center")
        self.tree_catalogo.pack(fill=tk.BOTH, expand=True)
        self.tree_catalogo.bind("<<TreeviewSelect>>", self.carregar_selecao_formulario)

    # --- ABA: HISTÓRICO ---
    def montar_aba_historico(self):
        frame_hist = tk.Frame(self.tab_historico, bg=self.cor_azul_claro)
        frame_hist.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        cols = ("id", "prod_id", "nome", "p_antigo", "p_novo", "e_antigo", "e_novo", "data")
        self.tree_hist = ttk.Treeview(frame_hist, columns=cols, show="headings")
        self.tree_hist.heading("id", text="Log ID")
        self.tree_hist.heading("prod_id", text="Item ID")
        self.tree_hist.heading("nome", text="Produto")
        self.tree_hist.heading("p_antigo", text="Preço Antigo")
        self.tree_hist.heading("p_novo", text="Preço Novo")
        self.tree_hist.heading("e_antigo", text="Vitrine Ant.")
        self.tree_hist.heading("e_novo", text="Vitrine Nova")
        self.tree_hist.heading("data", text="Data / Horário")

        for c in cols:
            self.tree_hist.column(c, anchor="center")
        self.tree_hist.column("nome", anchor="w", width=160)
        self.tree_hist.column("data", width=140)
        self.tree_hist.pack(fill=tk.BOTH, expand=True)

    def criar_botao(self, container, texto, comando, cor_bg):
        return tk.Button(
            container, text=texto, command=comando, bg=cor_bg,
            fg="#263238" if cor_bg in [self.cor_azul_medio, "#CFD8DC"] else "#FFFFFF",
            font=("Helvetica", 9, "bold"), relief=tk.FLAT, padx=8, pady=4, cursor="hand2"
        )

    # --- INTEGRAÇÃO COM A API ---
    def atualizar_todas_as_telas(self):
        self.listar_catalogo_geral()
        self.listar_vitrine_pdv()
        self.listar_historico()

    def listar_catalogo_geral(self):
        for r in self.tree_catalogo.get_children():
            self.tree_catalogo.delete(r)
        termo = self.txt_busca_geral.get().strip()
        try:
            dados = api_get("/produtos", params={"q": termo} if termo else None)
            for p in dados:
                self.tree_catalogo.insert("", tk.END, values=(p["id"], p["nome"], f"{p['preco']:.2f}", f"{p['estoque']} un", p["categoria"]))
        except Exception as e:
            messagebox.showerror("Erro API", f"Falha ao obter produtos: {e}")

    def listar_vitrine_pdv(self):
        for r in self.tree_pdv.get_children():
            self.tree_pdv.delete(r)
        termo = self.txt_busca_pdv.get().strip()
        params = {"apenas_estoque": "true"}
        if termo:
            params["q"] = termo
        try:
            dados = api_get("/produtos", params=params)
            for p in dados:
                self.tree_pdv.insert("", tk.END, values=(p["id"], p["nome"], f"{p['preco']:.2f}", f"{p['estoque']} un"))
        except Exception as e:
            messagebox.showerror("Erro API", f"Falha no PDV: {e}")

    def listar_historico(self):
        for r in self.tree_hist.get_children():
            self.tree_hist.delete(r)
        try:
            logs = api_get("/historico")
            for h in logs:
                self.tree_hist.insert("", tk.END, values=(
                    h["id"], h["produto_id"], h["nome"],
                    f"R$ {h['preco_antigo']:.2f}", f"R$ {h['preco_novo']:.2f}",
                    f"{h['estoque_antigo']} un", f"{h['estoque_novo']} un", h["data_modificacao"]
                ))
        except Exception as e:
            messagebox.showerror("Erro API", f"Falha no histórico: {e}")

    def salvar_produto_api(self):
        nome = self.txt_nome.get().strip()
        preco = self.txt_preco.get().strip().replace(",", ".")
        estoque = self.txt_estoque.get().strip()
        cat = self.combo_cat.get()

        if not nome or not preco or not estoque:
            messagebox.showwarning("Aviso", "Preencha todos os campos!")
            return

        try:
            payload = {"nome": nome, "preco": float(preco), "estoque": int(estoque), "categoria": cat}
            resp = api_post("/produtos", payload)
            messagebox.showinfo("Sucesso", f"Item #{resp['id']} criado via API!")
            self.limpar_campos()
            self.atualizar_todas_as_telas()
        except Exception as e:
            messagebox.showerror("Erro API", str(e))

    def atualizar_produto_api(self):
        prod_id = self.txt_id.get().strip()
        if not prod_id:
            messagebox.showwarning("Aviso", "Selecione um produto para atualizar.")
            return

        from datetime import datetime
        payload = {
            "nome": self.txt_nome.get().strip(),
            "preco": float(self.txt_preco.get().strip().replace(",", ".")),
            "estoque": int(self.txt_estoque.get().strip()),
            "categoria": self.combo_cat.get(),
            "data_modificacao": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        }

        try:
            api_put(f"/produtos/{prod_id}", payload)
            messagebox.showinfo("Sucesso", "Item atualizado na API!")
            self.limpar_campos()
            self.atualizar_todas_as_telas()
        except Exception as e:
            messagebox.showerror("Erro API", str(e))

    def excluir_produto_api(self):
        prod_id = self.txt_id.get().strip()
        if not prod_id:
            messagebox.showwarning("Aviso", "Selecione um produto.")
            return

        if messagebox.askyesno("Excluir", "Deseja remover este produto?"):
            try:
                api_delete(f"/produtos/{prod_id}")
                self.limpar_campos()
                self.atualizar_todas_as_telas()
            except Exception as e:
                messagebox.showerror("Erro API", str(e))

    # --- AÇÕES DO PDV ---
    def adicionar_item_comanda(self):
        sel = self.tree_pdv.selection()
        if not sel:
            messagebox.showwarning("Aviso", "Selecione um item da vitrine.")
            return

        try:
            qtd = int(self.spin_qtd_pdv.get())
            if qtd <= 0: raise ValueError
        except ValueError:
            messagebox.showerror("Erro", "Quantidade inválida.")
            return

        item = self.tree_pdv.item(sel[0])["values"]
        prod_id, nome, preco, estoque = item[0], item[1], float(item[2]), int(str(item[3]).replace(" un", ""))

        qtd_ja_no_carrinho = sum(x["qtd"] for x in self.carrinho_atual if x["id"] == prod_id)
        if qtd + qtd_ja_no_carrinho > estoque:
            messagebox.showerror("Estoque Insuficiente", f"A vitrine possui apenas {estoque} unidades.")
            return

        for x in self.carrinho_atual:
            if x["id"] == prod_id:
                x["qtd"] += qtd
                x["subtotal"] = x["qtd"] * x["preco"]
                break
        else:
            self.carrinho_atual.append({"id": prod_id, "nome": nome, "preco": preco, "qtd": qtd, "subtotal": preco * qtd})

        self.atualizar_grid_comanda()

    def remover_item_comanda(self):
        sel = self.tree_comanda.selection()
        if not sel: return
        idx = self.tree_comanda.index(sel[0])
        del self.carrinho_atual[idx]
        self.atualizar_grid_comanda()

    def atualizar_grid_comanda(self):
        for r in self.tree_comanda.get_children():
            self.tree_comanda.delete(r)
        total = 0.0
        for it in self.carrinho_atual:
            self.tree_comanda.insert("", tk.END, values=(it["nome"], it["qtd"], f"{it['subtotal']:.2f}"))
            total += it["subtotal"]
        self.lbl_total.config(text=f"TOTAL: R$ {total:.2f}")

    def finalizar_pedido_api(self):
        if not self.carrinho_atual:
            messagebox.showwarning("Aviso", "Comanda vazia!")
            return

        from datetime import datetime
        total = sum(x["subtotal"] for x in self.carrinho_atual)
        payload = {
            "itens": self.carrinho_atual,
            "total": total,
            "data": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        }

        try:
            resp = api_post("/pedidos/finalizar", payload)
            messagebox.showinfo("Sucesso!", f"Pedido #{resp['venda_id']} finalizado com sucesso via API!\nEstoque baixado na vitrine.")
            self.carrinho_atual.clear()
            self.atualizar_grid_comanda()
            self.atualizar_todas_as_telas()
        except urllib.error.HTTPError as e:
            err = json.loads(e.read().decode())
            messagebox.showerror("Erro de Venda", err.get("error", "Erro ao processar venda"))
        except Exception as e:
            messagebox.showerror("Erro Conexão", str(e))

    def carregar_selecao_formulario(self, event=None):
        sel = self.tree_catalogo.selection()
        if not sel: return
        it = self.tree_catalogo.item(sel[0])["values"]
        self.txt_id.config(state="normal")
        self.txt_id.delete(0, tk.END)
        self.txt_id.insert(0, str(it[0]))
        self.txt_id.config(state="readonly")
        self.txt_nome.delete(0, tk.END)
        self.txt_nome.insert(0, str(it[1]))
        self.txt_preco.delete(0, tk.END)
        self.txt_preco.insert(0, str(it[2]))
        self.txt_estoque.delete(0, tk.END)
        self.txt_estoque.insert(0, str(it[3]).replace(" un", ""))
        self.combo_cat.set(str(it[4]))

    def limpar_campos(self):
        self.txt_id.config(state="normal")
        self.txt_id.delete(0, tk.END)
        self.txt_id.config(state="readonly")
        self.txt_nome.delete(0, tk.END)
        self.txt_preco.delete(0, tk.END)
        self.txt_estoque.delete(0, tk.END)
        self.combo_cat.set("Bolo/Sobremesa")
        if self.tree_catalogo.selection():
            self.tree_catalogo.selection_remove(self.tree_catalogo.selection()[0])


if __name__ == "__main__":
    # Inicia a API REST falsa em uma thread separada
    start_mock_api()

    # Inicia a interface gráfica
    root = tk.Tk()
    app = BoaPedidaApp(root)
    root.mainloop()