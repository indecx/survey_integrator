import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Definir o número de registros de exemplo
num_records = 10

# Criar dados fictícios
data = {
    'Nome': [f'Cliente {i}' for i in range(1, num_records + 1)],
    'Email': [f'cliente{i}@exemplo.com' for i in range(1, num_records + 1)],
    'Telefone': [f'(11) 9{i}{i}{i}{i}-{i}{i}{i}{i}' for i in range(1, num_records + 1)],
    'Avaliacao': [np.random.randint(1, 11) for _ in range(num_records)],
    'Data': [(datetime.now() - timedelta(days=np.random.randint(1, 30))).strftime('%Y-%m-%d %H:%M:%S') for _ in range(num_records)],
    'Comentario': [f'Comentário de feedback do cliente {i}' for i in range(1, num_records + 1)],
    'Produto_Comprado': [np.random.choice(['Produto A', 'Produto B', 'Produto C']) for _ in range(num_records)],
    'Atendimento': [np.random.randint(1, 6) for _ in range(num_records)],
    'Qualidade': [np.random.randint(1, 6) for _ in range(num_records)],
    'Recomendaria': [np.random.choice(['Sim', 'Não', 'Talvez']) for _ in range(num_records)],
    'Sugestao_Melhoria': [f'Sugestão de melhoria {i}' for i in range(1, num_records + 1)],
    'Canal_Compra': [np.random.choice(['Loja Física', 'Site', 'Aplicativo']) for _ in range(num_records)],
    'Valor_Compra': [round(np.random.uniform(50, 500), 2) for _ in range(num_records)]
}

# Criar DataFrame
df = pd.DataFrame(data)

# Salvar como Excel
df.to_excel('examples/dados_exemplo.xlsx', index=False)

print("Arquivo de exemplo criado com sucesso: examples/dados_exemplo.xlsx") 