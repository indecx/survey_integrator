import streamlit as st
import pandas as pd
import requests
import json
import time
from datetime import datetime
import io
import asyncio
import aiohttp
from asyncio import Semaphore
import math
import ssl
import logging
from asyncio import Queue
from collections import deque
from time import time

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Variáveis globais para armazenar resultados e estado
all_results = []
processing_state = None

st.set_page_config(page_title="Integrador Indecx", page_icon="📊", layout="wide")

# Configuração de estilo
st.markdown("""
<style>
    .main {
        padding: 1rem;
    }
    .success {
        color: green;
    }
    .error {
        color: red;
    }
    .warning {
        color: orange;
    }
    .mapping-container {
        background-color: #f7f7f9;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 15px;
    }
    .stSelectbox div[data-baseweb="select"] {
        width: 100%;
    }
    .json-preview {
        background-color: #f0f0f0;
        padding: 15px;
        border-radius: 5px;
        font-family: monospace;
        white-space: pre;
        overflow-x: auto;
    }
</style>
""", unsafe_allow_html=True)

# Título da aplicação
st.title("Integrador de Dados Excel para API Indecx")
st.markdown("Importe seus dados de arquivos Excel e envie para a API Indecx.")

# Sidebar para configurações
with st.sidebar:
    st.header("Configurações")
    company_key = st.text_input("Company Key (Token)", type="password")
    control_id = st.text_input("Control ID")
    
    st.header("Sobre")
    st.info("Esta aplicação permite importar dados de arquivos Excel e enviá-los para a API Indecx.")

# Upload de arquivo
uploaded_file = st.file_uploader("Selecione um arquivo Excel (.xlsx, .xls)", type=["xlsx", "xls"])

if uploaded_file is not None:
    # Leitura do arquivo Excel
    try:
        df = pd.read_excel(uploaded_file)
        st.success(f"Arquivo carregado com sucesso! {len(df)} registros encontrados.")
        
        # Exibir primeiras linhas do dataframe
        st.subheader("Visualização dos dados")
        st.dataframe(df.head())
        
        # Obter nomes das colunas
        columns = df.columns.tolist()
        
        # Definir opções de mapeamento para o JSON
        json_options = [
            "Name", 
            "email", 
            "phone", 
            "review",
            "channel",
            "createdAt", 
            "feedback", 
            "additionalQuestions.REVIEWS", 
            "additionalQuestions.LIKE/DISLIKE",
            "additionalQuestions.LIKERT",
            "additionalQuestions.CSAT",
            "additionalQuestions.EMOTION",
            "additionalQuestions.MULTIPLE", 
            "additionalQuestions.INPUT", 
            "indicators.column",
            "categories.category",
            "categories.subcategory"
        ]
        
        # Mapeamento de colunas
        st.subheader("Mapeamento do arquivo excel")
        st.markdown("Associe cada coluna do seu arquivo Excel aos campos da API Indecx")
        
        # Criar uma tabela estilo Excel para mapeamento
        st.markdown("""
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-weight: bold; margin-bottom: 10px;">
            <div>Colunas EXCEL</div>
            <div>Associação</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Inicializar o dicionário de mapeamentos
        mappings = {}
        
        # Para cada coluna do Excel, criar uma linha de mapeamento
        for col in columns:
            col1, col2 = st.columns(2)
            with col1:
                st.text(col)
            with col2:
                # Dropdown para escolher o campo do JSON
                selected_json = st.selectbox(
                    label=f"Mapeamento para {col}",
                    options=json_options,
                    key=f"json_{col}",
                    label_visibility="collapsed",
                    index=json_options.index("indicators.column")  # Define o valor padrão
                )
                mappings[col] = selected_json
        
        # Função para gerar o payload JSON com base no mapeamento
        def generate_payload(row_data, mappings):
            # Agrupar mapeamentos por tipo de campo
            basic_fields = {}
            additional_questions = {}
            indicators = {}
            categories_data = {"category": [], "subcategory": []}
            
            for excel_col, json_field in mappings.items():
                if json_field in ["Name", "email", "phone", "review", "channel", "createdAt", "feedback"]:
                    basic_fields[json_field.lower()] = excel_col
                elif json_field.startswith("additionalQuestions."):
                    question_type = json_field.split('.')[1]
                    if question_type not in additional_questions:
                        additional_questions[question_type] = []
                    additional_questions[question_type].append(excel_col)
                elif json_field.startswith("indicators."):
                    indicators[excel_col] = True
                elif json_field.startswith("categories."):
                    field_type = json_field.split('.')[1]
                    if pd.notna(row_data[excel_col]):
                        categories_data[field_type].append(excel_col)
            
            # Construir o payload JSON
            payload = {}
            
            # Adicionar campos básicos
            for json_field, excel_col in basic_fields.items():
                if pd.notna(row_data[excel_col]):
                    if json_field == "review":
                        try:
                            payload[json_field] = int(float(row_data[excel_col]))
                        except (ValueError, TypeError):
                            if isinstance(row_data[excel_col], str):
                                payload[json_field] = row_data[excel_col]
                            else:
                                payload[json_field] = None
                    elif json_field == "createdat":
                        try:
                            if isinstance(row_data[excel_col], datetime):
                                payload["createdAt"] = row_data[excel_col].strftime("%Y-%m-%d %H:%M:%S")
                            else:
                                payload["createdAt"] = str(row_data[excel_col])
                        except:
                            payload["createdAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    elif json_field == "channel":
                        payload[json_field] = str(row_data[excel_col]).strip()
                    else:
                        payload[json_field] = str(row_data[excel_col])
            
            # Se createdAt não foi definido, usar data atual
            if "createdAt" not in payload:
                payload["createdAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Adicionar perguntas adicionais
            questions_list = []
            
            # Processar todos os tipos de additionalQuestions
            for question_type, excel_cols in additional_questions.items():
                for excel_col in excel_cols:
                    if pd.notna(row_data[excel_col]):
                        if question_type in ["REVIEWS", "LIKERT", "CSAT"]:
                            try:
                                review_value = int(float(row_data[excel_col]))
                                questions_list.append({
                                    "type": question_type,
                                    "text": excel_col,
                                    "review": review_value
                                })
                            except (ValueError, TypeError):
                                pass
                        elif question_type == "LIKE/DISLIKE":
                            value = str(row_data[excel_col]).lower()
                            is_like = value in ["1", "true", "yes", "sim", "like", "gosto", "👍"]
                            questions_list.append({
                                "type": "LIKE/DISLIKE",
                                "text": excel_col,
                                "review": is_like
                            })
                        elif question_type == "EMOTION":
                            questions_list.append({
                                "type": "EMOTION",
                                "text": excel_col,
                                "review": str(row_data[excel_col])
                            })
                        elif question_type == "INPUT":
                            questions_list.append({
                                "type": "INPUT",
                                "text": excel_col,
                                "review": str(row_data[excel_col])
                            })
                        elif question_type == "MULTIPLE":
                            value = str(row_data[excel_col])
                            options = [item.strip() for item in value.split(',') if item.strip()]
                            
                            questions_list.append({
                                "type": "MULTIPLE",
                                "text": excel_col,
                                "review": options
                            })
            
            if questions_list:
                payload["additionalQuestions"] = questions_list
            
            # Adicionar indicadores
            indicators_list = []
            for excel_col in indicators:
                if pd.notna(row_data[excel_col]):
                    indicators_list.append({
                        "column": excel_col,
                        "value": str(row_data[excel_col])
                    })
            
            if indicators_list:
                payload["indicators"] = indicators_list

            # Adicionar categorias
            categories_list = []
            for cat_col in categories_data["category"]:
                if pd.notna(row_data[cat_col]):
                    category_item = {
                        "category": str(row_data[cat_col]),
                        "subcategory": ""
                    }
                    # Procurar subcategoria correspondente
                    for subcat_col in categories_data["subcategory"]:
                        if pd.notna(row_data[subcat_col]):
                            category_item["subcategory"] = str(row_data[subcat_col])
                            break
                    categories_list.append(category_item)
            
            if categories_list:
                payload["categories"] = categories_list
                
            return payload
        
        class RateLimiter:
            def __init__(self, rate_limit, time_window=1.0):
                self.rate_limit = rate_limit
                self.time_window = time_window
                self.requests = deque()
                self.lock = asyncio.Lock()
                self._sleep_time = time_window / rate_limit
            
            async def acquire(self):
                async with self.lock:
                    now = time()
                    
                    # Remover timestamps antigos
                    while self.requests and self.requests[0] <= now - self.time_window:
                        self.requests.popleft()
                    
                    if self.requests:
                        # Calcular tempo exato para próxima requisição
                        elapsed = now - self.requests[-1]
                        if elapsed < self._sleep_time:
                            await asyncio.sleep(self._sleep_time - elapsed)
                    
                    # Adicionar novo timestamp
                    self.requests.append(time())

        async def process_all(state):
            global all_results
            all_results = []  # Reiniciar a lista de resultados
            
            try:
                # Configurar o contexto SSL
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                
                # Usar exatamente 4 conexões para 4 req/s
                connector = aiohttp.TCPConnector(
                    ssl=ssl_context,
                    limit=4,  # 4 conexões simultâneas
                    limit_per_host=4,  # 4 conexões por host
                    ttl_dns_cache=300,
                    force_close=False,  # Reutilizar conexões
                    enable_cleanup_closed=True
                )
                
                timeout = aiohttp.ClientTimeout(total=None, connect=30, sock_connect=30, sock_read=30)
                
                async with aiohttp.ClientSession(
                    connector=connector,
                    timeout=timeout,
                    raise_for_status=False
                ) as session:
                    rate_limiter = RateLimiter(rate_limit=4)
                    
                    # Criar placeholders para informações de progresso
                    progress_text = st.empty()
                    stats_text = st.empty()
                    rate_text = st.empty()
                    error_text = st.empty()
                    
                    # Variáveis para calcular taxa de processamento
                    start_time = time()
                    processed_count = 0
                    failed_tasks = []
                    
                    # Criar fila de trabalho
                    work_queue = Queue()
                    result_queue = Queue()
                    
                    # Adicionar todos os registros na fila de trabalho
                    for index, row in df.iterrows():
                        try:
                            payload = generate_payload(row, mappings)
                            await work_queue.put((index, row, payload))
                        except Exception as e:
                            logger.error(f"Erro ao preparar registro {index}: {str(e)}")
                            await result_queue.put({
                                "index": index,
                                "status": "error",
                                "response": f"Erro ao preparar payload: {str(e)}"
                            })
                    
                    # Sinalizar fim da fila de trabalho
                    for _ in range(4):  # 4 workers
                        await work_queue.put(None)
                    
                    async def worker(worker_id):
                        """Worker que processa registros sequencialmente respeitando rate limit"""
                        while True:
                            try:
                                work_item = await work_queue.get()
                                if work_item is None:
                                    break
                                
                                index, row, payload = work_item
                                
                                # Processar este registro
                                await process_single_record_optimized(
                                    session, rate_limiter, index, row, payload, 
                                    headers, url, result_queue, worker_id
                                )
                                
                            except Exception as e:
                                logger.error(f"Erro no worker {worker_id}: {str(e)}")
                            finally:
                                work_queue.task_done()
                    
                    async def result_processor():
                        """Processa resultados e atualiza interface"""
                        nonlocal processed_count, failed_tasks
                        while True:
                            try:
                                result = await result_queue.get()
                                if result is None:
                                    break
                                    
                                all_results.append(result)
                                processed_count += 1
                                
                                if result.get("status") in [200, 201]:
                                    state.success_count += 1
                                else:
                                    state.error_count += 1
                                    error_msg = f"Erro ao enviar registro {result['index'] + 1}: {result.get('response', 'Sem resposta')}"
                                    logger.error(error_msg)
                                    failed_tasks.append(error_msg)
                                
                                # Atualizar estatísticas a cada 4 registros ou no final
                                if processed_count % 4 == 0 or processed_count == total_records:
                                    progress = int((processed_count / total_records) * 100)
                                    progress_bar.progress(min(progress, 100))
                                    
                                    # Calcular taxa de processamento
                                    elapsed_time = time() - start_time
                                    rate = processed_count / elapsed_time if elapsed_time > 0 else 0
                                    
                                    stats_text.markdown(f"""
                                    **Progresso:**
                                    - Registros processados: {processed_count}/{total_records}
                                    - Sucessos: {state.success_count}
                                    - Erros: {state.error_count}
                                    - Taxa de sucesso: {(state.success_count/processed_count)*100:.1f}%
                                    """)
                                    
                                    rate_text.markdown(f"""
                                    **Performance:**
                                    - Taxa de processamento: {rate:.2f} registros/segundo
                                    - Tempo estimado restante: {((total_records - processed_count) / rate) / 60:.1f} minutos
                                    """)
                                    
                                    # Mostrar últimos 5 erros
                                    if failed_tasks:
                                        error_text.markdown("**Últimos erros:**\n" + "\n".join(failed_tasks[-5:]))
                            
                            except Exception as e:
                                logger.error(f"Erro no processamento de resultado: {str(e)}")
                            finally:
                                result_queue.task_done()
                    
                    # Iniciar workers e processor
                    workers = [asyncio.create_task(worker(i)) for i in range(4)]
                    result_task = asyncio.create_task(result_processor())
                    
                    progress_text.text(f"Iniciando processamento de {total_records} registros com 4 workers...")
                    
                    # Aguardar todos os workers terminarem
                    await asyncio.gather(*workers)
                    
                    # Sinalizar fim do processamento de resultados
                    await result_queue.put(None)
                    await result_task
                    
                    return all_results
                    
            except Exception as e:
                logger.error(f"Erro no processamento geral: {str(e)}")
                st.error(f"Erro ao processar os dados: {str(e)}")
                return []

        async def process_single_record_optimized(session, rate_limiter, index, row, payload, headers, url, result_queue, worker_id):
            max_retries = 3
            retry_delay = 1
            
            for attempt in range(max_retries):
                try:
                    logger.info(f"Worker {worker_id} processando registro {index}, tentativa {attempt + 1}")
                    payload["controlId"] = control_id
                    
                    # Aguardar rate limiter (isso garante 4 req/s no total)
                    await rate_limiter.acquire()
                    
                    async with session.post(url, json=payload, headers=headers) as response:
                        response_text = await response.text()
                        try:
                            result = json.loads(response_text)
                        except json.JSONDecodeError:
                            result = {"raw_response": response_text}
                        
                        await result_queue.put({
                            "index": index,
                            "status": response.status,
                            "response": result,
                            "worker_id": worker_id
                        })
                        
                        if response.status in [200, 201]:
                            logger.info(f"Worker {worker_id} - Registro {index} processado com sucesso")
                            return
                        elif response.status == 429:  # Rate limit
                            retry_delay = 2 ** attempt  # Exponential backoff
                            logger.warning(f"Worker {worker_id} - Rate limit atingido para registro {index}, aguardando {retry_delay}s")
                            await asyncio.sleep(retry_delay)
                            continue
                        else:
                            logger.error(f"Worker {worker_id} - Erro na API para registro {index}: Status {response.status}, Response: {result}")
                            if attempt == max_retries - 1:  # Última tentativa
                                return
                            await asyncio.sleep(retry_delay)
                            
                except Exception as e:
                    logger.error(f"Worker {worker_id} - Erro ao processar registro {index}, tentativa {attempt + 1}: {str(e)}")
                    if attempt == max_retries - 1:  # Última tentativa
                        await result_queue.put({
                            "index": index,
                            "status": "error",
                            "response": str(e),
                            "worker_id": worker_id
                        })
                    else:
                        await asyncio.sleep(retry_delay)

        # Botão para processar e enviar dados
        if st.button("Processar e Enviar Dados"):
            logger.info("Botão 'Processar e Enviar Dados' foi clicado")
            
            if not company_key or not control_id:
                st.error("Por favor, preencha a Company Key e o Control ID antes de continuar.")
                logger.error("Tentativa de processamento sem Company Key ou Control ID")
                st.stop()

            logger.info(f"Iniciando processamento com {len(df)} registros")
            
            # Configurações da API
            url = "https://indecx.com/v2/create-answer"
            if control_id:
                url = f"{url}/{control_id}"
                
            headers = {
                "Content-Type": "application/json",
                "company-key": company_key
            }

            logger.info(f"Usando endpoint: {url}")

            # Criar container para log em tempo real
            log_container = st.empty()
            progress_bar = st.progress(0)
            
            # Classe para armazenar o estado do processamento
            class ProcessingState:
                def __init__(self):
                    self.success_count = 0
                    self.error_count = 0
                    
            state = ProcessingState()
            total_records = len(df)
            
            # Executar o processamento assíncrono
            results = asyncio.run(process_all(state))
            
            # Atualizar barra de progresso para 100%
            progress_bar.progress(100)
            
            # Exibir resumo final
            st.subheader("Resumo do Processamento")
            st.markdown(f"""
            * **Registros processados:** {total_records}
            * **Sucessos:** {state.success_count}
            * **Erros:** {state.error_count}
            """)
            
            if state.error_count == 0:
                st.success("Todos os registros foram processados com sucesso!")
            elif state.success_count == 0:
                st.error("Ocorreram erros em todos os registros. Verifique as configurações e tente novamente.")
            else:
                st.warning(f"Processamento concluído com {state.success_count} sucessos e {state.error_count} erros.")
            
            # Se houver registros com erro, criar e disponibilizar o arquivo CSV
            if state.error_count > 0 and results:
                error_records = [r for r in results if r["status"] not in [200, 201]]
                error_df = pd.DataFrame(error_records)
                csv_buffer = io.StringIO()
                error_df.to_csv(csv_buffer, index=False, encoding='utf-8')
                
                st.download_button(
                    label="Baixar registros com erro (CSV)",
                    data=csv_buffer.getvalue(),
                    file_name="registros_com_erro.csv",
                    mime="text/csv"
                )

    except Exception as e:
        st.error(f"Erro ao processar o arquivo: {str(e)}")
else:
    st.info("Por favor, faça o upload de um arquivo Excel para continuar.")

# Rodapé
st.markdown("---")
st.markdown("© 2023 - Integrador Indecx - Desenvolvido com Streamlit") 