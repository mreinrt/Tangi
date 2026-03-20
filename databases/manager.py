"""
Database manager for chat history and sessions
"""

import sqlite3
import os
import time
import random
import logging
from datetime import datetime

from PyQt6.QtCore import QMutexLocker

from Tangi.utils.helpers import format_timestamp

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages SQLite database operations for sessions and messages"""
    
    def __init__(self, db_path):
        self.db_path = db_path
        self.db = None
        
    def init_database(self):
        """Initialize database with required tables"""
        try:
            self.db = sqlite3.connect(self.db_path, timeout=30)
            c = self.db.cursor()
            
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA synchronous=NORMAL")
            c.execute("PRAGMA foreign_keys=ON")
            
            c.execute("""CREATE TABLE IF NOT EXISTS sessions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                model TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
            c.execute("""CREATE TABLE IF NOT EXISTS messages(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER REFERENCES sessions(id) ON DELETE CASCADE,
                role TEXT,
                text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
            c.execute("CREATE INDEX IF NOT EXISTS idx_text ON messages(text)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_session_id ON messages(session_id)")
            
            self.db.commit()
            logger.info(f"Database initialized at {self.db_path}")
            return True, "Database initialized successfully"
            
        except Exception as e:
            error_msg = f"Database initialization failed: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def create_session(self, name, model_path=None):
        """Create a new session"""
        try:
            c = self.db.cursor()
            c.execute("INSERT INTO sessions(name, model) VALUES (?, ?)", 
                     (name.strip(), str(model_path) if model_path else ""))
            session_id = c.lastrowid
            self.db.commit()
            logger.info(f"Created new session {session_id}: {name}")
            return session_id
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            raise
    
    def get_sessions(self, limit=50):
        """Get list of sessions with message counts"""
        c = self.db.cursor()
        c.execute("""
            SELECT id, name, model, created_at,
                (SELECT COUNT(*) FROM messages WHERE session_id = sessions.id) as msg_count
            FROM sessions 
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        return c.fetchall()
    
    def get_session_info(self, session_id):
        """Get session information"""
        c = self.db.cursor()
        c.execute("SELECT name, model, created_at FROM sessions WHERE id = ?", (session_id,))
        return c.fetchone()
    
    def get_session_messages(self, session_id):
        """Get all messages for a session"""
        c = self.db.cursor()
        c.execute("""
            SELECT role, text, created_at
            FROM messages 
            WHERE session_id = ? 
            ORDER BY created_at ASC
        """, (session_id,))
        return c.fetchall()
    
    def add_message(self, session_id, role, text):
        """Add a message to a session"""
        try:
            c = self.db.cursor()
            c.execute("BEGIN TRANSACTION")
            c.execute(
                "INSERT INTO messages (session_id, role, text) VALUES (?, ?, ?)",
                (session_id, role, text)
            )
            self.db.commit()
            
            # Occasionally log message count for large sessions
            if random.random() < 0.01:
                c.execute("SELECT COUNT(*) FROM messages WHERE session_id = ?", (session_id,))
                count = c.fetchone()[0]
                if count > 1000:
                    logger.info(f"Session {session_id} has {count} messages")
                    
        except Exception as e:
            try:
                self.db.rollback()
                logger.error(f"Database error saving message: {e}")
            except Exception as rollback_error:
                logger.error(f"Rollback failed: {rollback_error}")
            raise
    
    def rename_session(self, session_id, new_name):
        """Rename a session"""
        c = self.db.cursor()
        c.execute("UPDATE sessions SET name = ? WHERE id = ?", (new_name.strip(), session_id))
        self.db.commit()
    
    def update_session_model(self, session_id, model_path):
        """Update the model associated with a session"""
        c = self.db.cursor()
        c.execute("UPDATE sessions SET model = ? WHERE id = ?", 
                 (str(model_path), session_id))
        self.db.commit()
    
    def delete_session(self, session_id):
        """Delete a session and all its messages (cascade)"""
        c = self.db.cursor()
        c.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        self.db.commit()
    
    def delete_sessions(self, session_ids):
        """Delete multiple sessions"""
        c = self.db.cursor()
        placeholders = ','.join(['?' for _ in session_ids])
        c.execute(f"DELETE FROM sessions WHERE id IN ({placeholders})", session_ids)
        self.db.commit()
    
    def get_message_count(self, session_id):
        """Get message count for a session"""
        c = self.db.cursor()
        c.execute("SELECT COUNT(*) FROM messages WHERE session_id = ?", (session_id,))
        return c.fetchone()[0]
    
    def close(self):
        """Close database connection"""
        if self.db:
            try:
                self.db.close()
            except:
                pass
    
    def __del__(self):
        self.close()


__all__ = ['DatabaseManager']