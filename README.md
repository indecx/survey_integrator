# Integrador Indecx

Aplicação web desenvolvida em Python com Streamlit para importar dados de arquivos Excel e enviá-los para a API Indecx. A aplicação permite mapear colunas do Excel para os campos da API e processar múltiplos registros simultaneamente.

## Funcionalidades

- ✨ Interface web amigável com Streamlit
- 📊 Upload e visualização de arquivos Excel
- 🔄 Mapeamento flexível de colunas
- 🚀 Processamento assíncrono de dados
- 📝 Log em tempo real do processamento
- 📥 Exportação de registros com erro para CSV
- 🔒 Configuração segura de credenciais

## Tipos de Campos Suportados

- Campos básicos (nome, email, telefone, etc.)
- Avaliações numéricas (REVIEWS, LIKERT, CSAT)
- Like/Dislike
- Emoções
- Múltipla escolha
- Campos de texto
- Indicadores personalizados

## Requisitos

- Python 3.8 ou superior
- pip (gerenciador de pacotes Python)

## Instalação

1. Clone este repositório:
```bash
git clone https://github.com/seu-usuario/integrador-indecx.git
cd integrador-indecx
```

2. Crie um ambiente virtual:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# OU
venv\Scripts\activate     # Windows
```

3. Instale as dependências:
```bash
pip install -r requirements.txt
```

## Uso

1. Inicie a aplicação:
```bash
streamlit run app.py
```

2. Acesse no navegador:
```
http://localhost:8501
```

3. Configure:
   - Insira sua Company Key (Token)
   - Informe o Control ID
   - Faça upload do arquivo Excel
   - Configure o mapeamento das colunas

4. Clique em "Processar e Enviar Dados"

## Estrutura do Projeto

```
integrador-indecx/
├── app.py              # Aplicação principal
├── requirements.txt    # Dependências
├── examples/          # Arquivos de exemplo
└── README.md          # Documentação
```

## Configuração do Excel

O arquivo Excel deve conter as colunas que serão mapeadas para os seguintes campos da API:

### Campos Básicos
- Name
- email
- phone
- review
- createdAt
- feedback

### Campos Adicionais
- REVIEWS (1-5)
- LIKE/DISLIKE (sim/não)
- LIKERT (1-5)
- CSAT (1-10)
- EMOTION (texto)
- MULTIPLE (valores separados por vírgula)
- INPUT (texto livre)

### Indicadores
- Campos personalizados para métricas

## Performance

- Processamento assíncrono
- Suporte a até 5 requisições simultâneas
- Processamento em lotes de 10 registros
- Log em tempo real do progresso

## Tratamento de Erros

- Validação de campos obrigatórios
- Log detalhado de erros
- Exportação de registros com erro para CSV
- Continuação do processamento mesmo com erros

## Contribuindo

1. Faça um Fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## Licença

Este projeto está sob a licença MIT. Veja o arquivo `LICENSE` para mais detalhes.

## Suporte

Para suporte, abra uma issue no GitHub ou entre em contato com a equipe de desenvolvimento. 