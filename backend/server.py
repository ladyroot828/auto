import os
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

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    
    # Member scraping logs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS member_logs (
            id TEXT PRIMARY KEY,
            log_id TEXT,
            member_id TEXT,
            username TEXT,
            action TEXT,
            success BOOLEAN,
            error_message TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (log_id) REFERENCES automation_logs (id)
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
    max_members: int = 100

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
        # Here you would integrate with Telethon to request verification code
        # For now, this is a placeholder that simulates the process
        
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
        
        # TODO: Implement actual Telethon code request
        # from telethon import TelegramClient
        # client = TelegramClient(session_name, api_id, api_hash)
        # await client.send_code_request(phone_number)
        
        logger.info(f"Código de verificação solicitado para {account.phone_number}")
        
        return {
            "success": True,
            "message": "Código de verificação enviado",
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
        
        # TODO: Implement actual Telethon verification
        # client = TelegramClient(session_name, api_id, api_hash)
        # await client.sign_in(phone_number, code)
        
        # For now, simulate successful verification
        cursor.execute('''
            UPDATE accounts 
            SET status = 'authenticated', is_active = TRUE, last_used = CURRENT_TIMESTAMP
            WHERE phone_number = ?
        ''', (verification.phone_number,))
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Conta não encontrada")
        
        conn.commit()
        conn.close()
        
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
    """Activate/deactivate account"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Deactivate all accounts first
        cursor.execute("UPDATE accounts SET is_active = FALSE")
        
        # Activate selected account
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
            request.max_members
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
                            target_group: str, delay_min: int, delay_max: int, max_members: int):
    """Background task for automation - PLACEHOLDER for your script"""
    try:
        logger.info(f"Iniciando automação {log_id}")
        
        # TODO: Replace this with your actual automation script
        # This is a placeholder that simulates the automation process
        
        import random
        import time
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        total_added = 0
        total_errors = 0
        
        for i in range(min(max_members, 20)):  # Simulate adding up to 20 members
            if log_id in automation_tasks and automation_tasks[log_id]["status"] == "stopped":
                logger.info(f"Automação {log_id} foi parada pelo usuário")
                break
                
            # Simulate member addition with random success/failure
            success = random.choice([True, True, True, False])  # 75% success rate
            
            if success:
                total_added += 1
                # Log successful addition
                cursor.execute('''
                    INSERT INTO member_logs (id, log_id, member_id, username, action, success)
                    VALUES (?, ?, ?, ?, 'add_member', TRUE)
                ''', (str(uuid.uuid4()), log_id, f"user_{i}", f"@username_{i}"))
            else:
                total_errors += 1
                # Log error
                cursor.execute('''
                    INSERT INTO member_logs (id, log_id, member_id, action, success, error_message)
                    VALUES (?, ?, ?, 'add_member', FALSE, 'Simulated error')
                ''', (str(uuid.uuid4()), log_id, f"user_{i}"))
            
            # Update progress
            cursor.execute('''
                UPDATE automation_logs 
                SET members_added = ?, errors = ?
                WHERE id = ?
            ''', (total_added, total_errors, log_id))
            
            conn.commit()
            
            # Simulate delay
            delay = random.randint(delay_min, delay_max)
            await asyncio.sleep(delay)
        
        # Mark as completed
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)