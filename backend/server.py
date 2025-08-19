import sqlite3
import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager
import logging
from dotenv import load_dotenv
import os
import random
import time
from colorama import init, Fore, Style
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError, UserAlreadyParticipantError, UserPrivacyRestrictedError, UserNotParticipantError
from telethon.tl.functions.channels import InviteToChannelRequest, GetParticipantRequest
from telethon.tl.types import MessageService, ChannelParticipantsAdmins
import sys

init(autoreset=True)
load_dotenv()

# Carregar credenciais do .env
API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')

if not API_ID or not API_HASH:
    raise ValueError("API_ID e API_HASH devem ser definidos no arquivo .env")

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(_name_)

# Database setup
DATABASE_PATH = "telegram_automation.db"

def init_database():
    """Initialize SQLite database with required tables"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Accounts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id TEXT PRIMARY KEY,
            phone_number TEXT UNIQUE NOT NULL,
            session_name TEXT NOT NULL,
            is_active BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used TIMESTAMP,
            status TEXT DEFAULT 'pending'
        )
    ''')
    
    # Automation logs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS automation_logs (
            id TEXT PRIMARY KEY,
            account_id TEXT,
            action_type TEXT,
            source_group TEXT,
            target_group TEXT,
            members_added INTEGER DEFAULT 0,
            errors INTEGER DEFAULT 0,
            status TEXT,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            finished_at TIMESTAMP,
            details TEXT,
            FOREIGN KEY (account_id) REFERENCES accounts (id)
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("Database initialized successfully")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup"""
    init_database()
    yield

# FastAPI app
app = FastAPI(
    title="Telegram Automation Panel",
    description="Painel para automação de grupos Telegram",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class AccountCreate(BaseModel):
    phone_number: str

class VerificationCode(BaseModel):
    phone_number: str
    code: str

class AutomationRequest(BaseModel):
    account_id: str
    source_groups: List[str]
    target_group: str
    delay_min: int = 6
    delay_max: int = 15
    max_members: Optional[int] = None  # Agora opcional, sem limite fixo

class Account(BaseModel):
    id: str
    phone_number: str
    session_name: str
    is_active: bool
    status: str
    created_at: str
    last_used: Optional[str] = None

class AutomationLog(BaseModel):
    id: str
    account_id: str
    action_type: str
    source_group: str
    target_group: str
    members_added: int
    errors: int
    status: str
    started_at: str
    finished_at: Optional[str] = None

# Global variables for automation control
automation_tasks = {}
active_sessions = {}

# Database helper functions
def get_db_connection():
    return sqlite3.connect(DATABASE_PATH)

def dict_factory(cursor, row):
    """Convert sqlite rows to dictionaries"""
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

# API Routes

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/api/accounts/request-code")
async def request_verification_code(account: AccountCreate):
    """Request verification code for Telegram account"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        account_id = str(uuid.uuid4())
        session_name = f"session_{account.phone_number.replace('+', '')}"
        
        # Check if account already exists
        cursor.execute("SELECT id FROM accounts WHERE phone_number = ?", (account.phone_number,))
        existing = cursor.fetchone()
        
        if existing:
            # Update existing account
            cursor.execute('''
                UPDATE accounts 
                SET session_name = ?, status = 'code_requested', last_used = CURRENT_TIMESTAMP
                WHERE phone_number = ?
            ''', (session_name, account.phone_number))
            account_id = existing[0]
        else:
            # Create new account
            cursor.execute('''
                INSERT INTO accounts (id, phone_number, session_name, status)
                VALUES (?, ?, ?, 'code_requested')
            ''', (account_id, account.phone_number, session_name))
        
        conn.commit()
        conn.close()
        
        # Actual Telethon code request
        client = TelegramClient(session_name, API_ID, API_HASH)
        await client.connect()
        await client.send_code_request(account.phone_number)
        active_sessions[account.phone_number] = client  # Salvar client para verify
        
        logger.info(f"Código de verificação solicitado para {account.phone_number}")
        
        return {
            "success": True,
            "message": "Código de verificação enviado via Telegram",
            "account_id": account_id
        }
        
    except Exception as e:
        logger.error(f"Erro ao solicitar código: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao solicitar código: {str(e)}")

@app.post("/api/accounts/verify-code")
async def verify_code(verification: VerificationCode):
    """Verify code and authenticate account"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get client from active_sessions
        client = active_sessions.get(verification.phone_number)
        if not client:
            raise HTTPException(status_code=400, detail="Sessão não encontrada, solicite código novamente")
        
        await client.sign_in(verification.phone_number, verification.code)
        
        cursor.execute('''
            UPDATE accounts 
            SET status = 'authenticated', is_active = TRUE, last_used = CURRENT_TIMESTAMP
            WHERE phone_number = ?
        ''', (verification.phone_number,))
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Conta não encontrada")
        
        conn.commit()
        conn.close()
        
        del active_sessions[verification.phone_number]  # Limpar após sign_in
        
        logger.info(f"Conta autenticada com sucesso: {verification.phone_number}")
        
        return {
            "success": True,
            "message": "Conta autenticada com sucesso"
        }
        
    except Exception as e:
        logger.error(f"Erro na verificação: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro na verificação: {str(e)}")

@app.get("/api/accounts", response_model=List[Account])
async def get_accounts():
    """Get all Telegram accounts"""
    try:
        conn = get_db_connection()
        conn.row_factory = dict_factory
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, phone_number, session_name, is_active, status, 
                   created_at, last_used
            FROM accounts
            ORDER BY created_at DESC
        ''')
        
        accounts = cursor.fetchall()
        conn.close()
        
        return accounts
        
    except Exception as e:
        logger.error(f"Erro ao buscar contas: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao buscar contas: {str(e)}")

@app.post("/api/accounts/{account_id}/activate")
async def activate_account(account_id: str):
    """Activate account (sem desativar outras para permitir múltiplas)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Ativa a conta selecionada (sem desativar outras)
        cursor.execute('''
            UPDATE accounts 
            SET is_active = TRUE, last_used = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (account_id,))
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Conta não encontrada")
        
        conn.commit()
        conn.close()
        
        return {"success": True, "message": "Conta ativada"}
        
    except Exception as e:
        logger.error(f"Erro ao ativar conta: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao ativar conta: {str(e)}")

@app.delete("/api/accounts/{account_id}")
async def delete_account(account_id: str):
    """Delete account"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Conta não encontrada")
        
        conn.commit()
        conn.close()
        
        return {"success": True, "message": "Conta removida"}
        
    except Exception as e:
        logger.error(f"Erro ao remover conta: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao remover conta: {str(e)}")

@app.post("/api/automation/start")
async def start_automation(request: AutomationRequest, background_tasks: BackgroundTasks):
    """Start automation process"""
    try:
        # Create automation log
        conn = get_db_connection()
        cursor = conn.cursor()
        
        log_id = str(uuid.uuid4())
        cursor.execute('''
            INSERT INTO automation_logs 
            (id, account_id, action_type, source_group, target_group, status)
            VALUES (?, ?, 'member_scraping', ?, ?, 'running')
        ''', (log_id, request.account_id, ', '.join(request.source_groups), request.target_group))
        
        conn.commit()
        conn.close()
        
        # Add background task
        background_tasks.add_task(
            run_automation_task, 
            log_id, 
            request.account_id,
            request.source_groups,
            request.target_group,
            request.delay_min,
            request.delay_max,
            request.max_members  # Passa None se não definido
        )
        
        automation_tasks[log_id] = {
            "status": "running",
            "started_at": datetime.now().isoformat()
        }
        
        return {
            "success": True,
            "message": "Automação iniciada",
            "log_id": log_id
        }
        
    except Exception as e:
        logger.error(f"Erro ao iniciar automação: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao iniciar automação: {str(e)}")

@app.post("/api/automation/{log_id}/stop")
async def stop_automation(log_id: str):
    """Stop automation process"""
    try:
        if log_id in automation_tasks:
            automation_tasks[log_id]["status"] = "stopped"
            
            # Update database
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE automation_logs 
                SET status = 'stopped', finished_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (log_id,))
            conn.commit()
            conn.close()
            
            return {"success": True, "message": "Automação parada"}
        else:
            raise HTTPException(status_code=404, detail="Automação não encontrada")
            
    except Exception as e:
        logger.error(f"Erro ao parar automação: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao parar automação: {str(e)}")

@app.get("/api/automation/logs", response_model=List[AutomationLog])
async def get_automation_logs():
    """Get automation logs"""
    try:
        conn = get_db_connection()
        conn.row_factory = dict_factory
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT al.*, a.phone_number
            FROM automation_logs al
            LEFT JOIN accounts a ON al.account_id = a.id
            ORDER BY al.started_at DESC
            LIMIT 50
        ''')
        
        logs = cursor.fetchall()
        conn.close()
        
        return logs
        
    except Exception as e:
        logger.error(f"Erro ao buscar logs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao buscar logs: {str(e)}")

@app.get("/api/automation/stats")
async def get_automation_stats():
    """Get automation statistics"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Today's stats
        cursor.execute('''
            SELECT 
                COUNT(*) as total_runs,
                SUM(members_added) as total_added,
                SUM(errors) as total_errors
            FROM automation_logs
            WHERE DATE(started_at) = DATE('now')
        ''')
        
        today_stats = cursor.fetchone()
        
        # Last 24 hours stats
        cursor.execute('''
            SELECT 
                COUNT(*) as runs_24h,
                SUM(members_added) as added_24h,
                ROUND(AVG(members_added), 2) as avg_per_hour
            FROM automation_logs
            WHERE started_at >= datetime('now', '-24 hours')
        ''')
        
        stats_24h = cursor.fetchone()
        
        conn.close()
        
        return {
            "today": {
                "total_runs": today_stats[0] or 0,
                "total_added": today_stats[1] or 0,
                "total_errors": today_stats[2] or 0
            },
            "last_24h": {
                "runs": stats_24h[0] or 0,
                "added": stats_24h[1] or 0,
                "avg_per_hour": stats_24h[2] or 0
            }
        }
        
    except Exception as e:
        logger.error(f"Erro ao buscar estatísticas: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao buscar estatísticas: {str(e)}")

async def run_automation_task(log_id: str, account_id: str, source_groups: List[str], 
                            target_group: str, delay_min: int, delay_max: int, max_members: Optional[int]):
    """Background task for automation - Integrated script"""
    try:
        logger.info(f"Iniciando automação {log_id}")
        
        # Buscar session_name do account_id
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT session_name FROM accounts WHERE id = ?", (account_id,))
        row = cursor.fetchone()
        if not row:
            raise Exception("Account not found")
        session_name = row[0]
        conn.close()
        
        # Criar client
        client = TelegramClient(session_name, API_ID, API_HASH)
        await client.start()
        
        # Configs adaptadas
        DESTINO_URL = target_group
        DELAY_MIN = delay_min
        DELAY_MAX = delay_max
        PAUSA_CADA = 10
        PAUSA_MIN = 10
        PAUSA_MAX = 20
        ARQ_ALVO = "usuarios_alvo.txt"
        CP_FILE = "checkpoint.txt"
        LEDGER = "adicionados_global.csv"
        LOG_CSV = "hydra_log.csv"
        
        # Funções auxiliares
        def _append(path, line, header=None):
            new = not os.path.exists(path)
            with open(path, "a", encoding="utf-8") as f:
                if header and new: f.write(header + "\n")
                f.write(line + ("\n" if not line.endswith("\n") else ""))

        def log(acao, alvo, detalhe=""):
            ts = datetime.now().isoformat(timespec="seconds")
            _append(LOG_CSV, f"{ts},{acao},{alvo},{detalhe}", header="timestamp,acao,alvo,detalhe")
            logger.info(f"[LOG] {ts} - {acao}: {alvo} {detalhe}")

        def load_set(path):
            if not os.path.exists(path): return set()
            with open(path, "r", encoding="utf-8") as f:
                return set(x.strip() for x in f if x.strip())

        def save_set(path, s):
            with open(path, "w", encoding="utf-8") as f:
                for x in sorted(s): f.write(x + "\n")

        def ledger_add(username, destino):
            ts = datetime.now().isoformat(timespec="seconds")
            _append(LEDGER, f"{username},{destino},{ts}", header="username,destino,timestamp")

        def ledger_seen(username):
            if not os.path.exists(LEDGER): return False
            with open(LEDGER, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("username,"): continue
                    if line.split(",", 1)[0] == username: return True
            return False

        async def retry_func(client, func, max_retries=10):
            for attempt in range(max_retries):
                try:
                    return await func()
                except FloodWaitError as e:
                    wait = min(e.seconds * (1.5 ** attempt), 3600) + random.randint(5, 15)
                    log("floodwait", "retry", f"{wait}s")
                    await asyncio.sleep(wait)
                except Exception as e:
                    log("retry_erro", "tentativa", str(e))
                    if attempt == max_retries - 1: raise
                    await asyncio.sleep(1.5 ** attempt + random.random() * 3)

        def setup_event_handlers(client, destino_entity):
            @client.on(events.ChatAction(chats=destino_entity.id))
            async def _del_service(event):
                try: await event.delete()
                except: pass

            @client.on(events.NewMessage(chats=destino_entity.id))
            async def _del_incoming(event):
                if isinstance(event.message, MessageService) or (event.message.from_id and event.message.text):
                    try: await event.delete()
                    except: pass

        async def scrape_groups(links, simulate=False):
            alvo = load_set(ARQ_ALVO)
            total_new = 0
            async def scrape_one(link):
                nonlocal total_new
                try:
                    chat = await retry_func(client, lambda: client.get_entity(link))
                    admin_ids = set(u.id async for u in client.iter_participants(chat, filter=ChannelParticipantsAdmins))
                    async for u in client.iter_participants(chat):
                        if u.bot or not u.username or u.deleted or u.id in admin_ids: continue
                        uname = u.username.strip()
                        if uname not in alvo:
                            alvo.add(uname)
                            total_new += 1
                    log("scrape", link, f"{total_new} novos")
                except Exception as e:
                    log("scrape_erro", link, str(e))

            tasks = [scrape_one(link) for link in links]
            await asyncio.gather(*tasks)

            if not simulate:
                save_set(ARQ_ALVO, alvo)
            log("scrape_ok", "total", str(len(alvo)))
            return total_new

        async def add_from_file(simulate=False):
            destino_entity = await retry_func(client, lambda: client.get_entity(DESTINO_URL))
            alvo = load_set(ARQ_ALVO)
            cp = load_set(CP_FILE)
            pend = [u for u in alvo if u not in cp]  # Sem limite fixo
            if max_members is not None:
                pend = pend[:max_members]  # Só se definido
            if not pend: return 0, 0

            total_ok = 0
            total_errors = 0
            batch_size = 1  # Sequencial

            for batch_start in range(0, len(pend), batch_size):
                if log_id in automation_tasks and automation_tasks[log_id]["status"] == "stopped":
                    break
                
                batch = pend[batch_start:batch_start + batch_size]
                results = await asyncio.gather(*[add_one(client, destino_entity, username, simulate, total_ok) for username in batch])
                for result in results:
                    if result == 1:
                        total_ok += 1
                    else:
                        total_errors += 1

                # Atualizar banco
                conn_temp = get_db_connection()
                cursor_temp = conn_temp.cursor()
                cursor_temp.execute('''
                    UPDATE automation_logs 
                    SET members_added = ?, errors = ?
                    WHERE id = ?
                ''', (total_ok, total_errors, log_id))
                conn_temp.commit()
                conn_temp.close()

                await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX) + random.random() * 2)
                
                if (batch_start // batch_size + 1) % PAUSA_CADA == 0:
                    pausa = random.randint(PAUSA_MIN, PAUSA_MAX)
                    logger.info(f"⏳ Pausa mínima {pausa}s...")
                    await asyncio.sleep(pausa)

            return total_ok, total_errors

        async def add_one(client, destino_entity, username, simulate, total_ok):
            if ledger_seen(username): 
                _append(CP_FILE, username)
                return 0

            try:
                user = await retry_func(client, lambda: client.get_entity(username))
                try:
                    await client(GetParticipantRequest(destino_entity, user))
                    log("ja_no_grupo", username, "")
                    _append(CP_FILE, username)
                    return 0
                except UserNotParticipantError:
                    pass
            except Exception as e:
                log("resolver_fail", username, str(e))
                return 0

            if simulate:
                logger.info(f"[SIM] Adicionado: @{username}")
                _append(CP_FILE, username)
                return 1

            try:
                await retry_func(client, lambda: client(InviteToChannelRequest(destino_entity, [user])))
                ledger_add(username, DESTINO_URL)
                log("adicionado", username, "")
                logger.info(f"✅ Adicionado: @{username} | OK: {total_ok + 1}")
                _append(CP_FILE, username)
                return 1
            except UserPrivacyRestrictedError:
                log("privacidade", username, "")
                _append(CP_FILE, username)
                return 0
            except Exception as e:
                log("erro", username, str(e))
                return 0

        # Setup handlers
        destino_entity = await client.get_entity(target_group)
        setup_event_handlers(client, destino_entity)

        # Rodar automação
        await scrape_groups(source_groups, simulate=False)
        total_added, total_errors = await add_from_file(simulate=False)

        # Mark as completed
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE automation_logs 
            SET status = 'completed', finished_at = CURRENT_TIMESTAMP,
                members_added = ?, errors = ?
            WHERE id = ?
        ''', (total_added, total_errors, log_id))
        conn.commit()
        conn.close()
        
        if log_id in automation_tasks:
            automation_tasks[log_id]["status"] = "completed"
        
        logger.info(f"Automação {log_id} concluída: {total_added} adicionados, {total_errors} erros")
        
        await client.disconnect()
        
    except Exception as e:
        logger.error(f"Erro na automação {log_id}: {str(e)}")
        
        # Mark as failed
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE automation_logs 
            SET status = 'failed', finished_at = CURRENT_TIMESTAMP, details = ?
            WHERE id = ?
        ''', (str(e), log_id))
        conn.commit()
        conn.close()
        
        if log_id in automation_tasks:
            automation_tasks[log_id]["status"] = "failed"

if _name_ == "_main_":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
