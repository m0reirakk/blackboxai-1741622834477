from flask import Flask, request, redirect, send_from_directory, url_for, jsonify, render_template
import os
import sqlite3
from werkzeug.utils import secure_filename
from datetime import datetime

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    # Tabela de produtos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS produtos (
            codigo TEXT PRIMARY KEY,
            genero TEXT NOT NULL,
            nome TEXT NOT NULL,
            marca TEXT NOT NULL,
            preco REAL NOT NULL,
            foto_path TEXT,
            estoque INTEGER DEFAULT 0
        )
    ''')
    
    # Tabela de vendas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vendas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_codigo TEXT NOT NULL,
            quantidade INTEGER NOT NULL,
            valor_total REAL NOT NULL,
            data_venda DATETIME NOT NULL,
            FOREIGN KEY (produto_codigo) REFERENCES produtos (codigo)
        )
    ''')
    
    # Dados demo
    produtos_demo = [
        ('001', 'Alimentos', 'Arroz Integral', 'Tio João', 8.99, 'arroz.jpg', 150),
        ('002', 'Bebidas', 'Refrigerante Cola', 'Coca-Cola', 6.50, 'refrigerante.jpg', 200),
        ('003', 'Higiene Pessoal', 'Sabonete', 'Dove', 3.75, 'sabonete.jpg', 300),
        ('004', 'Limpeza', 'Detergente', 'Ypê', 2.99, 'detergente.jpg', 250),
        ('005', 'Alimentos', 'Feijão Carioca', 'Camil', 7.50, 'feijao.jpg', 180),
        ('006', 'Bebidas', 'Suco de Laranja', 'Del Valle', 4.99, 'suco.jpg', 120)
    ]
    
    # Inserir produtos demo apenas se não existirem
    cursor.execute('SELECT COUNT(*) FROM produtos')
    if cursor.fetchone()[0] == 0:
        cursor.executemany('INSERT INTO produtos VALUES (?, ?, ?, ?, ?, ?, ?)', produtos_demo)
        
        # Inserir vendas demo para os últimos 6 meses
        vendas_demo = []
        for mes in range(6):
            for produto in produtos_demo:
                # Quantidade aleatória entre 5 e 20
                quantidade = __import__('random').randint(5, 20)
                # Data do mês atual menos 'mes' meses
                data_venda = (datetime.now() - __import__('dateutil').relativedelta.relativedelta(months=mes)).strftime('%Y-%m-%d %H:%M:%S')
                
                vendas_demo.append((
                    produto[0],  # código do produto
                    quantidade,  # quantidade aleatória
                    produto[4] * quantidade,  # valor total (preço * quantidade)
                    data_venda  # data do mês
                ))
        cursor.executemany('INSERT INTO vendas (produto_codigo, quantidade, valor_total, data_venda) VALUES (?, ?, ?, ?)', vendas_demo)
    
    conn.commit()
    conn.close()

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

init_db()

def get_all_products():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM produtos ORDER BY genero, nome')
    produtos = cursor.fetchall()
    conn.close()
    return produtos

def get_dashboard_stats():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    # Total de produtos
    cursor.execute('SELECT COUNT(*) FROM produtos')
    total_produtos = cursor.fetchone()[0]
    
    # Valor total do estoque
    cursor.execute('SELECT SUM(preco * estoque) FROM produtos')
    valor_total = cursor.fetchone()[0] or 0
    
    # Produtos com estoque baixo (menos de 50 unidades)
    cursor.execute('SELECT COUNT(*) FROM produtos WHERE estoque < 50')
    estoque_baixo = cursor.fetchone()[0]
    
    # Faturamento por categoria (soma dos preços dos produtos)
    cursor.execute('''
        SELECT p.genero, SUM(p.preco) as total
        FROM produtos p
        GROUP BY p.genero
    ''')
    faturamento_categoria = cursor.fetchall()
    
    # Faturamento mensal (soma dos preços dos produtos por mês)
    cursor.execute('''
        SELECT strftime('%Y-%m', v.data_venda) as mes, SUM(p.preco) as total
        FROM vendas v
        JOIN produtos p ON v.produto_codigo = p.codigo
        GROUP BY strftime('%Y-%m', v.data_venda)
        ORDER BY mes ASC
        LIMIT 6
    ''')
    faturamento_mensal = cursor.fetchall()
    
    # Processar os dados do faturamento mensal para o formato adequado
    dados_faturamento = []
    if faturamento_mensal:
        for mes, total in faturamento_mensal:
            # Converter o formato do mês para exibição (YYYY-MM para MM/YYYY)
            mes_formatado = f"{mes[5:]}/{mes[:4]}"
            dados_faturamento.append({
                'mes': mes_formatado,
                'total': float(total)
            })
    
    conn.close()
    return {
        'total_produtos': total_produtos,
        'valor_total': valor_total,
        'estoque_baixo': estoque_baixo,
        'faturamento_categoria': dict(faturamento_categoria),
        'faturamento_mensal': dados_faturamento
    }

@app.route('/')
def home():
    produtos = get_all_products()
    stats = get_dashboard_stats()
    categoria_cores = {
        'Alimentos': 'green',
        'Bebidas': 'blue',
        'Higiene Pessoal': 'purple',
        'Limpeza': 'yellow',
        'Outros': 'gray'
    }
    return render_template('index.html', 
                         produtos=produtos, 
                         stats=stats, 
                         categoria_cores=categoria_cores)

@app.route('/faturamento')
def faturamento():
    stats = get_dashboard_stats()
    # Obter vendas recentes
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT 
            v.data_venda,
            p.nome,
            p.genero,
            v.quantidade,
            v.valor_total
        FROM vendas v
        JOIN produtos p ON v.produto_codigo = p.codigo
        ORDER BY v.data_venda DESC
        LIMIT 10
    ''')
    vendas = [
        {
            'data': datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y'),
            'produto': row[1],
            'categoria': row[2],
            'quantidade': row[3],
            'valor_total': row[4]
        }
        for row in cursor.fetchall()
    ]
    conn.close()

    # Cores para as categorias
    categoria_cores = {
        'Alimentos': 'green',
        'Bebidas': 'blue',
        'Higiene Pessoal': 'purple',
        'Limpeza': 'yellow',
        'Outros': 'gray'
    }

    return render_template('faturamento.html', 
                         stats=stats,
                         vendas=vendas,
                         categoria_cores=categoria_cores)

@app.route('/fornecedores')
def fornecedores():
    return render_template('fornecedores.html')

@app.route('/relatorios')
def relatorios():
    return render_template('relatorios.html')

@app.route('/configuracoes')
def configuracoes():
    return render_template('configuracoes.html')

@app.route('/produto/<codigo>', methods=['GET'])
def get_produto(codigo):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM produtos WHERE codigo = ?', (codigo,))
    produto = cursor.fetchone()
    conn.close()
    
    if produto:
        return jsonify({
            'codigo': produto[0],
            'genero': produto[1],
            'nome': produto[2],
            'marca': produto[3],
            'preco': produto[4],
            'foto_path': produto[5],
            'estoque': produto[6]
        })
    return jsonify({'error': 'Produto não encontrado'}), 404

@app.route('/produto/<codigo>', methods=['PUT'])
def update_produto(codigo):
    data = request.json
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE produtos 
        SET genero = ?, nome = ?, marca = ?, preco = ?, estoque = ?
        WHERE codigo = ?
    ''', (data['genero'], data['nome'], data['marca'], data['preco'], data['estoque'], codigo))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Produto atualizado com sucesso'})

@app.route('/produto/<codigo>', methods=['DELETE'])
def delete_produto(codigo):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM produtos WHERE codigo = ?', (codigo,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Produto excluído com sucesso'})

@app.route('/submit', methods=['POST'])
def submit():
    codigo = request.form['codigo']
    genero = request.form['genero']
    nome = request.form['nome']
    marca = request.form['marca']
    preco = float(request.form['preco'])
    
    foto = request.files['foto']
    foto_path = None
    
    if foto and allowed_file(foto.filename):
        filename = secure_filename(foto.filename)
        foto_path = f"{codigo}_{filename}"
        foto.save(os.path.join(app.config['UPLOAD_FOLDER'], foto_path))
    
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO produtos (codigo, genero, nome, marca, preco, foto_path, estoque) VALUES (?, ?, ?, ?, ?, ?, ?)', 
                  (codigo, genero, nome, marca, preco, foto_path, 0))
    
    # Registrar uma venda demo para o novo produto
    valor_total = preco * 10  # 10 unidades vendidas
    cursor.execute('INSERT INTO vendas (produto_codigo, quantidade, valor_total, data_venda) VALUES (?, ?, ?, ?)',
                  (codigo, 10, valor_total, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    
    conn.commit()
    conn.close()
    
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True, port=8080)
