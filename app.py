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
import threading

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(page_title="Integrador Indecx", page_icon="📊", layout="wide")

# Configuração de estilo
st.markdown("""
<style>
    .main { padding: 1rem; }
    .success { color: green; }
    .error { color: red; }
    .warning { color: orange; }
    .mapping-container { background-color: #f7f7f9; padding: 15px; border-radius: 10px; margin-bottom: 15px; }
    .stSelectbox div[data-baseweb="select"] { width: 100%; }
    .json-preview { background-color: #f0f0f0; padding: 15px; border-radius: 5px; font-family: monospace; white-space: pre; overflow-x: auto; }
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

class ProcessingState:
    def __init__(self, total_records):
        self.success_count = 0
        self.failure_count = 0
        self.processed_count = 0
        self.last_errors = deque(maxlen=5)
        self.is_running = True
        self.start_time = time.time()
        self.total_records = total_records

class RateLimiter:
    def __init__(self, rate_limit, time_window=1.0):
        self.rate_limit = rate_limit
        self.time_window = time_window
        self.tokens = rate_limit
        self.last_refill = time.time()
        self.lock = asyncio.Lock()

    async def acquire(self):
        async with self.lock:
            now = time.time()
            time_passed = now - self.last_refill
            
            if time_passed > self.time_window:
                self.tokens = self.rate_limit
                self.last_refill = now

            if self.tokens > 0:
                self.tokens -= 1
                return
            else:
                sleep_time = self.time_window - time_passed
                await asyncio.sleep(sleep_time)
                self.tokens = self.rate_limit - 1
                self.last_refill = time.time()

# Upload de arquivo
uploaded_file = st.file_uploader("Selecione um arquivo Excel (.xlsx, .xls)", type=["xlsx", "xls"])

if uploaded_file is not None:
    try:
        df = pd.read_excel(uploaded_file)
        st.success(f"Arquivo carregado com sucesso! {len(df)} registros encontrados.")
        
        st.subheader("Visualização dos dados")
        st.dataframe(df.head())
        
        columns = df.columns.tolist()
        
        json_options = [
            "Name", "email", "phone", "review", "channel", "createdAt", "feedback", 
            "additionalQuestions.REVIEWS", "additionalQuestions.LIKE/DISLIKE",
            "additionalQuestions.LIKERT", "additionalQuestions.CSAT",
            "additionalQuestions.EMOTION", "additionalQuestions.MULTIPLE", 
            "additionalQuestions.INPUT", "additionalQuestions.NPS",
            "additionalQuestions.CES", "additionalQuestions.CES17",
            "additionalQuestions.CSAT-1-5", "indicators.column",
            "categories.category", "categories.subcategory"
        ]
        
        st.subheader("Mapeamento do arquivo excel")
        st.markdown("Associe cada coluna do seu arquivo Excel aos campos da API Indecx")
        
        st.markdown("""
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-weight: bold; margin-bottom: 10px;">
            <div>Colunas EXCEL</div>
            <div>Associação</div>
        </div>
        """, unsafe_allow_html=True)
        
        mappings = {}
        for col in columns:
            col1, col2 = st.columns(2)
            with col1:
                st.text(col)
            with col2:
                selected_json = st.selectbox(
                    label=f"Mapeamento para {col}", options=json_options,
                    key=f"json_{col}", label_visibility="collapsed",
                    index=json_options.index("indicators.column")
                )
                mappings[col] = selected_json
        
        def generate_payload(row_data, mappings):
            payload = {}
            basic_fields = {}
            additional_questions = {}
            indicators = {}
            categories_data = {"category": [], "subcategory": []}
            
            for excel_col, json_field in mappings.items():
                if json_field in ["Name", "email", "phone", "review", "channel", "createdAt", "feedback"]:
                    basic_fields[json_field.lower()] = excel_col
                elif json_field.startswith("additionalQuestions."):
                    q_type = json_field.split('.')[1]
                    if q_type not in additional_questions:
                        additional_questions[q_type] = []
                    additional_questions[q_type].append(excel_col)
                elif json_field.startswith("indicators."):
                    indicators[excel_col] = True
                elif json_field.startswith("categories."):
                    field_type = json_field.split('.')[1]
                    if pd.notna(row_data[excel_col]):
                        categories_data[field_type].append(excel_col)

            for json_field, excel_col in basic_fields.items():
                if pd.notna(row_data[excel_col]):
                    if json_field == "review":
                        try:
                            payload[json_field] = int(float(row_data[excel_col]))
                        except (ValueError, TypeError):
                            payload[json_field] = str(row_data[excel_col]) if isinstance(row_data[excel_col], str) else None
                    elif json_field == "createdat":
                        try:
                            payload["createdAt"] = pd.to_datetime(row_data[excel_col], dayfirst=True).strftime("%Y-%m-%d %H:%M:%S")
                        except:
                            payload["createdAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        payload[json_field] = str(row_data[excel_col])
            
            if "createdAt" not in payload:
                payload["createdAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            questions_list = []
            for q_type, excel_cols in additional_questions.items():
                for excel_col in excel_cols:
                    if pd.notna(row_data[excel_col]):
                        question = {"type": q_type, "text": excel_col}
                        if q_type in ["REVIEWS", "LIKERT", "CSAT"]:
                            try:
                                question["review"] = int(float(row_data[excel_col]))
                            except (ValueError, TypeError): continue
                        elif q_type == "LIKE/DISLIKE":
                            question["review"] = str(row_data[excel_col]).lower() in ["1", "true", "yes", "sim", "like", "gosto", "👍"]
                        elif q_type == "MULTIPLE":
                            question["review"] = [item.strip() for item in str(row_data[excel_col]).split(',') if item.strip()]
                        else:
                            question["review"] = str(row_data[excel_col])
                        questions_list.append(question)
            
            if questions_list:
                payload["additionalQuestions"] = questions_list

            indicators_list = []
            for excel_col in indicators:
                if pd.notna(row_data[excel_col]):
                    indicators_list.append({"column": excel_col, "value": str(row_data[excel_col])})
            if indicators_list:
                payload["indicators"] = indicators_list
            
            categories_list = []
            if categories_data["category"] or categories_data["subcategory"]:
                max_len = max(len(categories_data["category"]), len(categories_data["subcategory"]))
                for i in range(max_len):
                    cat_obj = {}
                    if i < len(categories_data["category"]) and pd.notna(row_data[categories_data['category'][i]]):
                        cat_obj["category"] = str(row_data[categories_data['category'][i]])
                    if i < len(categories_data["subcategory"]) and pd.notna(row_data[categories_data['subcategory'][i]]):
                        cat_obj["subcategory"] = str(row_data[categories_data['subcategory'][i]])
                    if cat_obj:
                        categories_list.append(cat_obj)
            if categories_list:
                payload["categories"] = categories_list
            
            return payload

        async def process_single_record_optimized(session, rate_limiter, index, row, payload, headers, url, result_queue, worker_id):
            max_retries = 3
            retry_delay = 1
            for attempt in range(max_retries):
                try:
                    await rate_limiter.acquire()
                    async with session.post(url, json=payload, headers=headers, timeout=60, ssl=False) as response:
                        if response.status in [200, 201]:
                            await result_queue.put(('success', 1, None, index))
                            return
                        else:
                            error_message = await response.text()
                            if attempt == max_retries - 1:
                                logger.error(f"Erro ao enviar registro {index} (Worker {worker_id}): Status {response.status} - {error_message}")
                            await asyncio.sleep(retry_delay * (2 ** attempt))
                except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                    error_message = f"Erro de conexão/timeout: {e}"
                    if attempt == max_retries - 1:
                        logger.error(f"Erro de Conexão/Timeout ao enviar registro {index} (Worker {worker_id}): {e}")
            await result_queue.put(('failure', 1, error_message, index))

        async def process_all(state):
            url = f"https://indecx.com/v2/create-answer/{control_id}"
            headers = {"Content-Type": "application/json", "company-key": company_key}
            num_workers = 10
            rate_limiter = RateLimiter(10, 1.0)
            
            work_queue = Queue()
            result_queue = Queue()

            async def result_processor():
                while state.is_running:
                    try:
                        result_tuple = await asyncio.wait_for(result_queue.get(), timeout=0.1)
                        if result_tuple is None: continue
                        
                        result_type, count, error_msg, index = result_tuple
                        if result_type == 'success':
                            state.success_count += count
                            logger.info(f"Registro {index} processado com sucesso.")
                        elif result_type == 'failure':
                            state.failure_count += count
                            if error_msg: state.last_errors.append(error_msg)
                        
                        state.processed_count = state.success_count + state.failure_count
                        result_queue.task_done()
                    except asyncio.TimeoutError:
                        if state.processed_count == state.total_records:
                            break
                        continue
            
            async def worker(worker_id):
                async with aiohttp.ClientSession() as session:
                    while True:
                        task = await work_queue.get()
                        if task is None:
                            work_queue.task_done()
                            break
                        index, row, payload = task
                        await process_single_record_optimized(session, rate_limiter, index, row, payload, headers, url, result_queue, worker_id)
                        work_queue.task_done()

            for index, row in df.iterrows():
                await work_queue.put((index, row, generate_payload(row, mappings)))
            
            for _ in range(num_workers):
                await work_queue.put(None)

            worker_tasks = [asyncio.create_task(worker(i)) for i in range(num_workers)]
            result_task = asyncio.create_task(result_processor())

            await work_queue.join()
            await asyncio.gather(*worker_tasks)
            await result_queue.join()
            
            state.is_running = False
            await result_task

        def run_async_processing(state):
            asyncio.run(process_all(state))

        if "processing_state" not in st.session_state:
            st.session_state.processing_state = None

        if st.button("Processar e Enviar Dados"):
            if not company_key or not control_id:
                st.warning("Por favor, insira a Company Key e o Control ID.")
            elif st.session_state.processing_state is None or not st.session_state.processing_state.is_running:
                st.session_state.processing_state = ProcessingState(total_records=len(df))
                thread = threading.Thread(
                    target=run_async_processing,
                    args=(st.session_state.processing_state,)
                )
                thread.start()
                st.rerun()
            else:
                st.warning("Um processamento já está em andamento.")

        if st.session_state.processing_state:
            state = st.session_state.processing_state
            
            st.subheader("Progresso do Envio")
            progress_bar = st.progress(0)
            stats_placeholder = st.empty()
            errors_placeholder = st.empty()
            
            elapsed_time = time.time() - state.start_time
            rate = state.processed_count / elapsed_time if elapsed_time > 0 else 0
            progress_value = state.processed_count / state.total_records if state.total_records > 0 else 0
            remaining_time = ((state.total_records - state.processed_count) / rate) if rate > 0 else 0

            progress_bar.progress(min(progress_value, 1.0))
            stats_placeholder.markdown(f"""
            - **Processados:** {state.processed_count}/{state.total_records}
            - **Sucessos:** <span class="success">{state.success_count}</span>
            - **Erros:** <span class="error">{state.failure_count}</span>
            - **Velocidade:** {rate:.2f} regs/s
            - **Tempo restante estimado:** {remaining_time:.0f}s
            """, unsafe_allow_html=True)

            if state.last_errors:
                errors_placeholder.error("Últimos erros:\\n" + "\\n".join(state.last_errors))

            if state.is_running:
                time.sleep(1)
                st.rerun()
            else:
                st.subheader("Processamento Concluído")
                if state.failure_count == 0:
                    st.success("Todos os registros foram processados com sucesso!")
                else:
                    st.warning(f"Processamento concluído com {state.success_count} sucessos e {state.failure_count} erros.")
                st.session_state.processing_state = None # Limpa o estado para permitir nova execução

    except Exception as e:
        st.error(f"Ocorreu um erro ao carregar ou processar o arquivo: {e}")
else:
    st.info("Por favor, faça o upload de um arquivo Excel para continuar.")

# Rodapé
st.markdown("---")
st.markdown("© 2023 - Integrador Indecx - Desenvolvido com Streamlit") 