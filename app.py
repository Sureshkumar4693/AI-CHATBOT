from flask import Flask, request, jsonify, render_template, send_from_directory, redirect, url_for, session
from flask_cors import CORS
# Use google-generativeai package (more stable and widely supported)
try:
    import google.generativeai as genai
    from google.generativeai import types
    GENAI_PACKAGE = "generativeai"
except ImportError:
    try:
        from google import genai
        from google.genai import types
        GENAI_PACKAGE = "genai"
    except ImportError:
        print("❌ Error: No Google AI package found. Please install with: pip install google-generativeai")
        exit(1)
try:
    import pymysql
    import pymysql.cursors
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False
    print("⚠️  PyMySQL not installed. Using SQLite. Install with: pip install pymysql")
import sqlite3
import json
from contextlib import contextmanager
import re
import os
import time
import hashlib
import secrets
from datetime import datetime, timedelta
import logging

app = Flask(__name__)
CORS(app, supports_credentials=True)  # Enable CORS for frontend-backend communication
# Configure Flask session
app.secret_key = secrets.token_hex(32)  # Generate a secure secret key
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
API_KEY = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"  # Replace with your actual API key
MAX_MESSAGE_LENGTH = 4000
RATE_LIMIT_DELAY = 1  # Minimum seconds between requests
DATABASE_PATH = "askcodzz.db"

# MySQL Configuration (set these in environment variables or update here)
USE_MYSQL = os.getenv('USE_MYSQL', 'false').lower() == 'true'
MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
MYSQL_PORT = int(os.getenv('MYSQL_PORT', 3306))
MYSQL_USER = os.getenv('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', '')
MYSQL_DATABASE = os.getenv('MYSQL_DATABASE', 'askcodzz')

# In-memory storage (use proper database in production)
users_db = {}  # {email: {password_hash, name, created_at, last_login}}
conversation_history = {}  # {user_id: [conversations]}
user_sessions = {}  # {session_token: {user_email, created_at, expires_at}}
user_conversations = {}  # {user_id: {conversation_id: {title, messages, created_at, updated_at}}}

# Database helper functions
@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    if USE_MYSQL and MYSQL_AVAILABLE:
        conn = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE,
            cursorclass=pymysql.cursors.DictCursor,
            charset='utf8mb4'
        )
        try:
            yield conn
        finally:
            conn.close()
    else:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

def init_database():
    """Initialize the database with required tables"""
    if USE_MYSQL and MYSQL_AVAILABLE:
        # Create database if it doesn't exist
        try:
            conn = pymysql.connect(
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                cursorclass=pymysql.cursors.DictCursor
            )
            with conn.cursor() as cursor:
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS {MYSQL_DATABASE}")
            conn.close()
        except Exception as e:
            logger.error(f"Error creating MySQL database: {e}")
            return
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        if USE_MYSQL and MYSQL_AVAILABLE:
            # MySQL table definitions
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP NULL,
                    INDEX idx_email (email)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS conversations (
                    id VARCHAR(255) PRIMARY KEY,
                    user_email VARCHAR(255) NOT NULL,
                    title VARCHAR(500) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_user_email (user_email),
                    FOREIGN KEY (user_email) REFERENCES users (email) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    conversation_id VARCHAR(255) NOT NULL,
                    content TEXT NOT NULL,
                    is_user BOOLEAN NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_conversation_id (conversation_id),
                    FOREIGN KEY (conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    token VARCHAR(500) PRIMARY KEY,
                    user_email VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    INDEX idx_user_email (user_email),
                    FOREIGN KEY (user_email) REFERENCES users (email) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS language_usage (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_email VARCHAR(255) NOT NULL,
                    language VARCHAR(100) NOT NULL,
                    query_text TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_user_email (user_email),
                    INDEX idx_language (language),
                    INDEX idx_timestamp (timestamp),
                    FOREIGN KEY (user_email) REFERENCES users (email) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            ''')
        else:
            # SQLite table definitions
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    user_email TEXT NOT NULL,
                    title TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_email) REFERENCES users (email)
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    is_user BOOLEAN NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES conversations (id)
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    user_email TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    FOREIGN KEY (user_email) REFERENCES users (email)
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS language_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_email TEXT NOT NULL,
                    language TEXT NOT NULL,
                    query_text TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_email) REFERENCES users (email)
                )
            ''')
        
        conn.commit()
        logger.info("Database initialized successfully")

def save_user_to_db(email, password_hash, name):
    """Save user to database"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if USE_MYSQL and MYSQL_AVAILABLE:
            cursor.execute('''
                INSERT INTO users (email, password_hash, name, created_at, last_login)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE password_hash=%s, name=%s, created_at=%s
            ''', (email, password_hash, name, datetime.now().isoformat(), None, password_hash, name, datetime.now().isoformat()))
        else:
            cursor.execute('''
                INSERT OR REPLACE INTO users (email, password_hash, name, created_at, last_login)
                VALUES (?, ?, ?, ?, ?)
            ''', (email, password_hash, name, datetime.now().isoformat(), None))
        conn.commit()

def get_user_from_db(email):
    """Get user from database"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if USE_MYSQL and MYSQL_AVAILABLE:
            cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
        else:
            cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        row = cursor.fetchone()
        if row:
            return dict(row) if isinstance(row, dict) else dict(row)
        return None

def update_user_last_login(email):
    """Update user's last login time"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if USE_MYSQL and MYSQL_AVAILABLE:
            cursor.execute('''
                UPDATE users SET last_login = %s WHERE email = %s
            ''', (datetime.now().isoformat(), email))
        else:
            cursor.execute('''
                UPDATE users SET last_login = ? WHERE email = ?
            ''', (datetime.now().isoformat(), email))
        conn.commit()

def save_conversation_to_db(conversation_id, user_email, title):
    """Save conversation to database"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if USE_MYSQL and MYSQL_AVAILABLE:
            cursor.execute('''
                INSERT INTO conversations (id, user_email, title, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE title=%s, updated_at=%s
            ''', (conversation_id, user_email, title, datetime.now().isoformat(), datetime.now().isoformat(), title, datetime.now().isoformat()))
        else:
            cursor.execute('''
                INSERT OR REPLACE INTO conversations (id, user_email, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (conversation_id, user_email, title, datetime.now().isoformat(), datetime.now().isoformat()))
        conn.commit()

def save_message_to_db(conversation_id, content, is_user):
    """Save message to database"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if USE_MYSQL and MYSQL_AVAILABLE:
            cursor.execute('''
                INSERT INTO messages (conversation_id, content, is_user, timestamp)
                VALUES (%s, %s, %s, %s)
            ''', (conversation_id, content, is_user, datetime.now().isoformat()))
        else:
            cursor.execute('''
                INSERT INTO messages (conversation_id, content, is_user, timestamp)
                VALUES (?, ?, ?, ?)
            ''', (conversation_id, content, is_user, datetime.now().isoformat()))
        conn.commit()

def get_user_conversations_from_db(user_email):
    """Get all conversations for a user from database"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if USE_MYSQL and MYSQL_AVAILABLE:
            cursor.execute('''
                SELECT c.*, COUNT(m.id) as message_count
                FROM conversations c
                LEFT JOIN messages m ON c.id = m.conversation_id
                WHERE c.user_email = %s
                GROUP BY c.id
                ORDER BY c.updated_at DESC
            ''', (user_email,))
        else:
            cursor.execute('''
                SELECT c.*, COUNT(m.id) as message_count
                FROM conversations c
                LEFT JOIN messages m ON c.id = m.conversation_id
                WHERE c.user_email = ?
                GROUP BY c.id
                ORDER BY c.updated_at DESC
            ''', (user_email,))
        rows = cursor.fetchall()
        return [dict(row) if isinstance(row, dict) else dict(row) for row in rows]

def get_conversation_messages_from_db(conversation_id):
    """Get all messages for a conversation from database"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if USE_MYSQL and MYSQL_AVAILABLE:
            cursor.execute('''
                SELECT * FROM messages 
                WHERE conversation_id = %s 
                ORDER BY timestamp ASC
            ''', (conversation_id,))
        else:
            cursor.execute('''
                SELECT * FROM messages 
                WHERE conversation_id = ? 
                ORDER BY timestamp ASC
            ''', (conversation_id,))
        rows = cursor.fetchall()
        return [dict(row) if isinstance(row, dict) else dict(row) for row in rows]

def delete_conversation_from_db(conversation_id):
    """Delete conversation and all its messages from database"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if USE_MYSQL and MYSQL_AVAILABLE:
            cursor.execute('DELETE FROM messages WHERE conversation_id = %s', (conversation_id,))
            cursor.execute('DELETE FROM conversations WHERE id = %s', (conversation_id,))
        else:
            cursor.execute('DELETE FROM messages WHERE conversation_id = ?', (conversation_id,))
            cursor.execute('DELETE FROM conversations WHERE id = ?', (conversation_id,))
        conn.commit()

def rename_conversation_in_db(conversation_id, new_title):
    """Rename conversation in database"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if USE_MYSQL and MYSQL_AVAILABLE:
            cursor.execute('''
                UPDATE conversations 
                SET title = %s, updated_at = %s 
                WHERE id = %s
            ''', (new_title, datetime.now().isoformat(), conversation_id))
        else:
            cursor.execute('''
                UPDATE conversations 
                SET title = ?, updated_at = ? 
                WHERE id = ?
            ''', (new_title, datetime.now().isoformat(), conversation_id))
        conn.commit()

def save_session_to_db(token, user_email, expires_at):
    """Save session to database"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if USE_MYSQL and MYSQL_AVAILABLE:
            cursor.execute('''
                INSERT INTO sessions (token, user_email, created_at, expires_at)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE user_email=%s, expires_at=%s
            ''', (token, user_email, datetime.now().isoformat(), expires_at.isoformat(), user_email, expires_at.isoformat()))
        else:
            cursor.execute('''
                INSERT OR REPLACE INTO sessions (token, user_email, created_at, expires_at)
                VALUES (?, ?, ?, ?)
            ''', (token, user_email, datetime.now().isoformat(), expires_at.isoformat()))
        conn.commit()

def get_session_from_db(token):
    """Get session from database"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if USE_MYSQL and MYSQL_AVAILABLE:
            cursor.execute('SELECT * FROM sessions WHERE token = %s', (token,))
        else:
            cursor.execute('SELECT * FROM sessions WHERE token = ?', (token,))
        row = cursor.fetchone()
        if row:
            return dict(row) if isinstance(row, dict) else dict(row)
        return None

def delete_session_from_db(token):
    """Delete session from database"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if USE_MYSQL and MYSQL_AVAILABLE:
            cursor.execute('DELETE FROM sessions WHERE token = %s', (token,))
        else:
            cursor.execute('DELETE FROM sessions WHERE token = ?', (token,))
        conn.commit()

class ChatbotConfig:
    def __init__(self):
        # Use the latest available models
        self.model = "gemini-2.0-flash"  # Latest stable model
        self.max_tokens = 1000
        self.temperature = 0.7
        
    def get_system_prompt(self):
        return """You are AskCodzz AI Assistant, a helpful and knowledgeable AI powered by Google Gemini. 
        You are friendly, informative, and always try to provide accurate and helpful responses. 
        Keep your responses conversational and engaging. If you're not sure about something, 
        it's okay to say so."""

config = ChatbotConfig()

def hash_password(password):
    """Hash a password with salt"""
    salt = secrets.token_hex(32)
    password_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return f"{salt}:{password_hash.hex()}"

def verify_password(password, password_hash):
    """Verify a password against its hash"""
    try:
        salt, hash_hex = password_hash.split(':')
        password_check = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
        return password_check.hex() == hash_hex
    except:
        return False

def generate_token():
    """Generate a secure session token"""
    return secrets.token_urlsafe(32)

def generate_conversation_title(message_text):
    """Generate a conversation title from the first message (like ChatGPT)"""
    # Clean the message
    text = message_text.strip()
    
    # Remove system prompt if present
    if "User question:" in text:
        text = text.split("User question:")[-1].strip()
    
    # Limit length
    max_length = 50
    
    if len(text) <= max_length:
        return text
    
    # Try to find a good breaking point (sentence, word boundary)
    if '.' in text[:max_length]:
        # Break at last sentence
        last_period = text[:max_length].rfind('.')
        if last_period > 10:  # At least 10 characters
            return text[:last_period + 1]
    
    # Break at last space
    last_space = text[:max_length].rfind(' ')
    if last_space > 10:
        return text[:last_space] + '...'
    
    # Just truncate
    return text[:max_length - 3] + '...'

def extract_programming_languages(text):
    """Extract programming languages from user query"""
    languages = []
    # Common programming languages
    language_keywords = {
        'python': ['python', 'py', 'pytest', 'django', 'flask', 'numpy', 'pandas'],
        'javascript': ['javascript', 'js', 'node', 'nodejs', 'react', 'vue', 'angular', 'express'],
        'java': ['java', 'spring', 'hibernate', 'maven', 'gradle'],
        'cpp': ['c++', 'cpp', 'cplusplus'],
        'c': ['c programming', 'c language'],
        'csharp': ['c#', 'csharp', '.net', 'asp.net'],
        'php': ['php', 'laravel', 'symfony', 'codeigniter'],
        'ruby': ['ruby', 'rails', 'ruby on rails'],
        'go': ['golang', 'go language', 'go programming'],
        'rust': ['rust', 'rustlang'],
        'swift': ['swift', 'ios', 'swiftui'],
        'kotlin': ['kotlin', 'android kotlin'],
        'typescript': ['typescript', 'ts', 'tsx'],
        'r': ['r language', 'r programming', 'rstudio'],
        'matlab': ['matlab', 'matlab programming'],
        'scala': ['scala', 'apache spark'],
        'perl': ['perl', 'perl programming'],
        'sql': ['sql', 'mysql', 'postgresql', 'sqlite', 'database'],
        'html': ['html', 'html5', 'css', 'css3'],
        'bash': ['bash', 'shell script', 'shell scripting'],
        'powershell': ['powershell', 'ps1']
    }
    
    text_lower = text.lower()
    for lang, keywords in language_keywords.items():
        for keyword in keywords:
            if keyword in text_lower:
                languages.append(lang)
                break
    
    return list(set(languages))  # Remove duplicates

def save_language_usage(user_email, languages, query_text):
    """Save programming language usage to database"""
    if not languages:
        return
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        for language in languages:
            try:
                if USE_MYSQL and MYSQL_AVAILABLE:
                    cursor.execute('''
                        INSERT INTO language_usage (user_email, language, query_text, timestamp)
                        VALUES (%s, %s, %s, %s)
                    ''', (user_email, language, query_text[:500], datetime.now().isoformat()))
                else:
                    cursor.execute('''
                        INSERT INTO language_usage (user_email, language, query_text, timestamp)
                        VALUES (?, ?, ?, ?)
                    ''', (user_email, language, query_text[:500], datetime.now().isoformat()))
            except Exception as e:
                logger.error(f"Error saving language usage: {e}")
        conn.commit()

def get_language_statistics(user_email=None, days=30):
    """Get programming language statistics from database"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        date_limit = (datetime.now() - timedelta(days=days)).isoformat()
        
        if USE_MYSQL and MYSQL_AVAILABLE:
            if user_email:
                cursor.execute('''
                    SELECT language, COUNT(*) as count
                    FROM language_usage
                    WHERE user_email = %s AND timestamp >= %s
                    GROUP BY language
                    ORDER BY count DESC
                ''', (user_email, date_limit))
            else:
                cursor.execute('''
                    SELECT language, COUNT(*) as count
                    FROM language_usage
                    WHERE timestamp >= %s
                    GROUP BY language
                    ORDER BY count DESC
                ''', (date_limit,))
        else:
            if user_email:
                cursor.execute('''
                    SELECT language, COUNT(*) as count
                    FROM language_usage
                    WHERE user_email = ? AND timestamp >= ?
                    GROUP BY language
                    ORDER BY count DESC
                ''', (user_email, date_limit))
            else:
                cursor.execute('''
                    SELECT language, COUNT(*) as count
                    FROM language_usage
                    WHERE timestamp >= ?
                    GROUP BY language
                    ORDER BY count DESC
                ''', (date_limit,))
        
        rows = cursor.fetchall()
        total = sum(row['count'] if isinstance(row, dict) else row[1] for row in rows)
        
        stats = []
        for row in rows:
            count = row['count'] if isinstance(row, dict) else row[1]
            language = row['language'] if isinstance(row, dict) else row[0]
            percentage = (count / total * 100) if total > 0 else 0
            stats.append({
                'language': language,
                'count': count,
                'percentage': round(percentage, 2)
            })
        
        return stats

def validate_email(email):

    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def require_auth(f):
    """Decorator to require authentication"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check session token
        token = request.headers.get('Authorization')
        if not token:
            token = session.get('token')
        
        if not token:
            return jsonify({"error": "Authentication required"}), 401
        
        # Check session in database
        user_session = get_session_from_db(token)
        if not user_session:
            return jsonify({"error": "Invalid session"}), 401
        
        # Check if token is expired
        expires_at = user_session['expires_at']
        if isinstance(expires_at, str):
            # Handle string format (SQLite or MySQL string)
            try:
                expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            except:
                expires_at = datetime.fromisoformat(expires_at)
        elif hasattr(expires_at, 'isoformat'):
            # Already a datetime object
            expires_at = expires_at
        else:
            expires_at = datetime.now() + timedelta(days=1)  # Default to 1 day if parsing fails
        
        if datetime.now() > expires_at:
            delete_session_from_db(token)
            return jsonify({"error": "Session expired"}), 401
        
        # Add user info to request context
        request.user_email = user_session['user_email']
        request.user_token = token
        
        return f(*args, **kwargs)
    return decorated_function

def get_user_id():
    """Get current user ID from session"""
    return request.user_email if hasattr(request, 'user_email') else None

def clean_response(text):
    """Clean and format the response text"""
    if not text:
        return ""
    
    # Remove excessive markdown formatting
    text = re.sub(r'\*{3,}', '**', text)  # Replace *** with **
    text = re.sub(r'_{3,}', '__', text)   # Replace ___ with __
    
    # Clean up extra whitespace
    text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)  # Remove excessive line breaks
    text = text.strip()
    
    return text

def save_conversation(user_id, user_message, bot_response):
    """Save conversation to history"""
    if user_id not in conversation_history:
        conversation_history[user_id] = []
    
    conversation_history[user_id].append({
        "timestamp": datetime.now().isoformat(),
        "user_message": user_message,
        "bot_response": bot_response
    })
    
    # Keep only last 20 exchanges to prevent memory issues
    if len(conversation_history[user_id]) > 20:
        conversation_history[user_id] = conversation_history[user_id][-20:]

def create_conversation(user_id, title="New Chat"):
    """Create a new conversation for a user"""
    conversation_id = f"conv_{int(time.time() * 1000)}"
    
    # Save to database
    save_conversation_to_db(conversation_id, user_id, title)
    
    # Also maintain in-memory for backward compatibility
    if user_id not in user_conversations:
        user_conversations[user_id] = {}
    
    user_conversations[user_id][conversation_id] = {
        "title": title,
        "messages": [],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    
    return conversation_id

def add_message_to_conversation(user_id, conversation_id, message, is_user=True):
    """Add a message to a specific conversation"""
    # Save to database
    save_message_to_db(conversation_id, message, is_user)
    
    # Also maintain in-memory for backward compatibility
    if user_id not in user_conversations or conversation_id not in user_conversations[user_id]:
        return False
    
    user_conversations[user_id][conversation_id]["messages"].append({
        "content": message,
        "is_user": is_user,
        "timestamp": datetime.now().isoformat()
    })
    
    user_conversations[user_id][conversation_id]["updated_at"] = datetime.now().isoformat()
    
    # Auto-generate title from first user message if still "New Chat"
    if (user_conversations[user_id][conversation_id]["title"] == "New Chat" and 
        is_user and len(user_conversations[user_id][conversation_id]["messages"]) == 1):
        title = message[:50] + ("..." if len(message) > 50 else "")
        user_conversations[user_id][conversation_id]["title"] = title
    
    return True

def get_user_conversations(user_id):
    """Get all conversations for a user"""
    # Get from database
    db_conversations = get_user_conversations_from_db(user_id)
    
    # Convert to expected format
    conversations = []
    for conv in db_conversations:
        conversations.append({
            "id": conv["id"],
            "title": conv["title"],
            "created_at": conv["created_at"],
            "updated_at": conv["updated_at"],
            "message_count": conv["message_count"]
        })
    
    return conversations

def get_conversation_messages(user_id, conversation_id):
    """Get messages for a specific conversation"""
    # Get from database
    db_messages = get_conversation_messages_from_db(conversation_id)
    
    # Convert to expected format
    messages = []
    for msg in db_messages:
        messages.append({
            "content": msg["content"],
            "is_user": bool(msg["is_user"]),
            "timestamp": msg["timestamp"]
        })
    
    return messages

def delete_conversation(user_id, conversation_id):
    """Delete a conversation"""
    # Delete from database
    delete_conversation_from_db(conversation_id)
    
    # Also remove from in-memory
    if (user_id in user_conversations and 
        conversation_id in user_conversations[user_id]):
        del user_conversations[user_id][conversation_id]
    
    return True

def rename_conversation(user_id, conversation_id, new_title):
    """Rename a conversation"""
    # Update in database
    rename_conversation_in_db(conversation_id, new_title)
    
    # Also update in-memory
    if (user_id in user_conversations and 
        conversation_id in user_conversations[user_id]):
        user_conversations[user_id][conversation_id]["title"] = new_title
        user_conversations[user_id][conversation_id]["updated_at"] = datetime.now().isoformat()
    
    return True

def get_conversation_context_from_db(conversation_id, max_exchanges=10):
    """Get recent conversation context from database"""
    messages = get_conversation_messages_from_db(conversation_id)
    
    # Get the last max_exchanges pairs (user + bot messages)
    recent_messages = messages[-max_exchanges*2:] if len(messages) > max_exchanges*2 else messages
    
    context = []
    for msg in recent_messages:
        if GENAI_PACKAGE == "generativeai":
            # Use google-generativeai format
            role = "user" if msg["is_user"] else "model"
            context.append({"role": role, "parts": [msg["content"]]})
        else:
            # Use google-genai format
            role = "user" if msg["is_user"] else "assistant"
            context.append(types.Content(role=role, parts=[types.Part.from_text(text=msg["content"])]))
    
    return context

def get_conversation_context(user_id, max_exchanges=5):
    """Get recent conversation context (legacy function for backward compatibility)"""
    if user_id not in conversation_history:
        return []
    
    recent_history = conversation_history[user_id][-max_exchanges:]
    context = []
    
    for exchange in recent_history:
        if GENAI_PACKAGE == "generativeai":
            # Use google-generativeai format
            context.extend([
                {"role": "user", "parts": [exchange["user_message"]]},
                {"role": "model", "parts": [exchange["bot_response"]]}
            ])
        else:
            # Use google-genai format
            context.extend([
                types.Content(role="user", parts=[types.Part.from_text(text=exchange["user_message"])]),
                types.Content(role="assistant", parts=[types.Part.from_text(text=exchange["bot_response"])])
            ])
    
    return context

def validate_input(question):
    """Validate user input"""
    if not question or not question.strip():
        return False, "Please enter a message."
    
    if len(question) > MAX_MESSAGE_LENGTH:
        return False, f"Message too long. Please keep it under {MAX_MESSAGE_LENGTH} characters."
    
    # Check for potentially harmful content (basic check)
    harmful_patterns = [
        r'<script',
        r'javascript:',
        r'on\w+\s*=',
    ]
    
    for pattern in harmful_patterns:
        if re.search(pattern, question, re.IGNORECASE):
            return False, "Invalid input detected."
    
    return True, None

# Routes
@app.route("/")
def index():
    """Redirect to login or chat based on session"""
    token = session.get('token')
    if token and token in user_sessions:
        # Check if token is still valid
        user_session = user_sessions[token]
        if datetime.now() <= user_session['expires_at']:
            return redirect('/chat')
    
    return redirect('/login')

@app.route("/login")
def login_page():
    """Serve the login page"""
    return render_template("login.html")

@app.route("/chat")
def chat_page():
    """Serve the chat page (requires authentication)"""
    token = session.get('token')
    if not token:
        return redirect('/login')
    
    # Check session in database
    session_data = get_session_from_db(token)
    if not session_data:
        session.pop('token', None)
        return redirect('/login')
    
    # Check if token is expired
    expires_at = session_data['expires_at']
    if isinstance(expires_at, str):
        try:
            expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        except:
            expires_at = datetime.fromisoformat(expires_at)
    elif hasattr(expires_at, 'isoformat'):
        expires_at = expires_at
    else:
        expires_at = datetime.now() + timedelta(days=1)
    
    if datetime.now() > expires_at:
        delete_session_from_db(token)
        session.pop('token', None)
        return redirect('/login')
    
    return render_template("chat.html")

@app.route("/dashboard")
def dashboard_page():
    """Serve the dashboard page (requires authentication)"""
    token = session.get('token')
    if not token:
        return redirect('/login')
    
    # Check session in database
    session_data = get_session_from_db(token)
    if not session_data:
        session.pop('token', None)
        return redirect('/login')
    
    # Check if token is expired
    expires_at = session_data['expires_at']
    if isinstance(expires_at, str):
        try:
            expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        except:
            expires_at = datetime.fromisoformat(expires_at)
    elif hasattr(expires_at, 'isoformat'):
        expires_at = expires_at
    else:
        expires_at = datetime.now() + timedelta(days=1)
    
    if datetime.now() > expires_at:
        delete_session_from_db(token)
        session.pop('token', None)
        return redirect('/login')
    
    return render_template("dashboard.html")

@app.route("/api/dashboard/stats", methods=["GET"])
@require_auth
def get_dashboard_stats():
    """Get dashboard statistics"""
    try:
        user_email = request.user_email
        
        # Get days parameter from query string (default to 30)
        days = int(request.args.get('days', 30))
        
        # Get language statistics
        stats = get_language_statistics(user_email=user_email, days=days)
        
        return jsonify({
            "success": True,
            "language_stats": stats,
            "period": f"last {days} days"
        })
        
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {str(e)}")
        return jsonify({"error": "Failed to get dashboard statistics"}), 500

@app.route("/signup", methods=["POST"])
def signup():
    """Handle user registration"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        name = data.get("name", "").strip()
        email = data.get("email", "").strip().lower()
        password = data.get("password", "")
        
        # Validation
        if not name or not email or not password:
            return jsonify({"error": "All fields are required"}), 400
        
        if len(name) < 2:
            return jsonify({"error": "Name must be at least 2 characters long"}), 400
        
        if not validate_email(email):
            return jsonify({"error": "Please enter a valid email address"}), 400
        
        if len(password) < 6:
            return jsonify({"error": "Password must be at least 6 characters long"}), 400
        
        # Check if user already exists in database
        existing_user = get_user_from_db(email)
        if existing_user:
            return jsonify({"error": "An account with this email already exists"}), 400
        
        # Create new user in database
        password_hash = hash_password(password)
        save_user_to_db(email, password_hash, name)
        
        logger.info(f"New user registered: {email}")
        return jsonify({
            "message": "Account created successfully",
            "user": {"name": name, "email": email}
        })
        
    except Exception as e:
        logger.error(f"Signup error: {str(e)}")
        return jsonify({"error": "Registration failed. Please try again."}), 500

@app.route("/login", methods=["POST"])
def login():
    """Handle user login"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        email = data.get("email", "").strip().lower()
        password = data.get("password", "")
        
        # Validation
        if not email or not password:
            return jsonify({"error": "Email and password are required"}), 400
        
        # Check if user exists in database
        user = get_user_from_db(email)
        if not user:
            return jsonify({"error": "Invalid email or password"}), 401
        
        # Verify password
        if not verify_password(password, user["password_hash"]):
            return jsonify({"error": "Invalid email or password"}), 401
        
        # Create session
        token = generate_token()
        expires_at = datetime.now() + timedelta(days=7)
        
        # Save session to database
        save_session_to_db(token, email, expires_at)
        
        # Update last login
        update_user_last_login(email)
        
        # Set session cookie
        session['token'] = token
        session.permanent = True
        
        logger.info(f"User logged in: {email}")
        return jsonify({
            "message": "Login successful",
            "token": token,
            "user": {
                "name": user["name"],
                "email": email
            }
        })
        
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({"error": "Login failed. Please try again."}), 500

@app.route("/ask", methods=["POST"])
@require_auth
def ask():
    """Handle chat requests"""
    try:
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        question = data.get("question", "").strip()
        conversation_id = data.get("conversation_id")
        user_id = get_user_id()
        
        # Create new conversation if none provided
        if not conversation_id:
            conversation_id = create_conversation(user_id)
        
        # Validate input
        is_valid, error_message = validate_input(question)
        if not is_valid:
            return jsonify({"error": error_message}), 400
        
        logger.info(f"Processing request for {user_id}: {question[:50]}...")
        
        # Initialize Gemini client
        try:
            if GENAI_PACKAGE == "generativeai":
                # Use google-generativeai package
                genai.configure(api_key=API_KEY)
                client = genai
            else:
                # Use google-genai package
                client = genai.Client(api_key=API_KEY)
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {str(e)}")
            return jsonify({"error": "AI service temporarily unavailable"}), 500
        
        # Prepare conversation context
        # Get conversation context for better responses
        context_messages = get_conversation_context_from_db(conversation_id, max_exchanges=10)
        
        # Add system prompt and current user message
        if GENAI_PACKAGE == "generativeai":
            # Use google-generativeai format
            messages = [config.get_system_prompt() + "\n\n" + question]
            if context_messages:
                # Add conversation history
                history_text = ""
                for msg in context_messages:
                    role = "User" if msg["role"] == "user" else "Assistant"
                    history_text += f"{role}: {msg['parts'][0]}\n"
                messages[0] = history_text + "\n" + messages[0]
        else:
            # Use google-genai format
            messages = [
                types.Content(role="user", parts=[types.Part.from_text(text=config.get_system_prompt())])
            ]
            messages.extend(context_messages)
            messages.append(types.Content(role="user", parts=[types.Part.from_text(text=question)]))
        
        # Configure generation parameters
        if GENAI_PACKAGE == "generativeai":
            # Use google-generativeai format
            generation_config = {
                'max_output_tokens': config.max_tokens,
                'temperature': config.temperature,
            }
        else:
            # Use google-genai format
            generation_config = types.GenerateContentConfig(
                response_mime_type="text/plain",
                max_output_tokens=config.max_tokens,
                temperature=config.temperature
            )
        
        # Generate response
        response_text = ""
        try:
            if GENAI_PACKAGE == "generativeai":
                # Use google-generativeai package with correct model names
                model_names_to_try = [
                    "gemini-2.0-flash",
                    "gemini-2.0-flash-001", 
                    "gemini-flash-latest",
                    "gemini-2.5-flash",
                    "gemini-pro-latest"
                ]
                
                success = False
                for model_name in model_names_to_try:
                    try:
                        logger.info(f"Trying generativeai model: {model_name}")
                        model = client.GenerativeModel(model_name)
                        response = model.generate_content(
                            messages,
                            generation_config=generation_config
                        )
                        response_text = response.text if response.text else ""
                        success = True
                        logger.info(f"Successfully used generativeai model: {model_name}")
                        break
                    except Exception as model_error:
                        logger.warning(f"Failed with generativeai model {model_name}: {str(model_error)}")
                        continue
                
                if not success:
                    raise Exception("All generativeai model name formats failed")
                    
            else:
                # Use google-genai package
                model_names_to_try = [
                    f"models/{config.model}",
                    config.model,
                    "models/gemini-2.0-flash",
                    "gemini-2.0-flash",
                    "models/gemini-2.5-flash",
                    "gemini-2.5-flash"
                ]
                
                success = False
                for model_name in model_names_to_try:
                    try:
                        logger.info(f"Trying genai model: {model_name}")
                        for chunk in client.models.generate_content_stream(
                            model=model_name, 
                            contents=messages, 
                            config=generation_config
                        ):
                            if chunk.text:
                                response_text += chunk.text
                        success = True
                        logger.info(f"Successfully used genai model: {model_name}")
                        break
                    except Exception as model_error:
                        logger.warning(f"Failed with genai model {model_name}: {str(model_error)}")
                        continue
                
                if not success:
                    raise Exception("All genai model name formats failed")
        
        except Exception as e:
            logger.error(f"Gemini API error: {str(e)}")
            return jsonify({"error": "Failed to generate response. Please try again."}), 500
        
        # Clean and validate response
        response_text = clean_response(response_text)
        if not response_text:
            response_text = "I apologize, but I couldn't generate a proper response. Please try rephrasing your question."
        
        # Track programming languages from user query
        user_email = request.user_email
        languages = extract_programming_languages(question)
        if languages:
            save_language_usage(user_email, languages, question)
        
        # Check if this is the first message in the conversation (for auto-title generation)
        # Check BEFORE adding messages
        existing_messages = get_conversation_messages_from_db(conversation_id)
        is_first_message = len(existing_messages) == 0
        
        # Save conversation to both old and new systems
        save_conversation(user_id, question, response_text)
        
        # Add messages to conversation
        add_message_to_conversation(user_id, conversation_id, question, is_user=True)
        add_message_to_conversation(user_id, conversation_id, response_text, is_user=False)
        
        # Auto-generate title from first message (like ChatGPT)
        # Only generate title if conversation still has default title
        if is_first_message:
            # Check current title
            current_conversation = get_user_conversations_from_db(user_email)
            conv_info = next((c for c in current_conversation if c['id'] == conversation_id), None)
            
            if conv_info and (conv_info['title'] == 'New Chat' or conv_info['title'] == 'New Conversation'):
                auto_title = generate_conversation_title(question)
                rename_conversation_in_db(conversation_id, auto_title)
                logger.info(f"Auto-generated conversation title: {auto_title}")
        
        # Return response
        return jsonify({
            "reply": response_text,
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "conversation_id": conversation_id
        })
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({"error": "An unexpected error occurred. Please try again."}), 500

@app.route("/clear", methods=["POST"])
@require_auth
def clear_conversation():
    """Clear conversation history"""
    try:
        user_id = get_user_id()
        if user_id in conversation_history:
            del conversation_history[user_id]
        
        return jsonify({"message": "Conversation cleared successfully"})
    
    except Exception as e:
        logger.error(f"Error clearing conversation: {str(e)}")
        return jsonify({"error": "Failed to clear conversation"}), 500

@app.route("/logout", methods=["POST"])
@require_auth
def logout():
    """Logout endpoint"""
    try:
        token = request.user_token
        
        # Delete session from database
        delete_session_from_db(token)
        
        # Clear session cookie
        session.pop('token', None)
        
        logger.info(f"User logged out: {request.user_email}")
        return jsonify({"message": "Logout successful"})
        
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        return jsonify({"error": "Logout failed"}), 500

@app.route("/profile", methods=["GET"])
@require_auth
def get_profile():
    """Get user profile information"""
    try:
        user_email = get_user_id()
        
        # Get user from database
        user = get_user_from_db(user_email)
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Get conversation count from database
        conversations = get_user_conversations_from_db(user_email)
        conversation_count = len(conversations)
        
        # Calculate message count
        message_count = sum(conv['message_count'] for conv in conversations)
        
        return jsonify({
            "user": {
                "name": user["name"],
                "email": user_email,
                "created_at": user["created_at"],
                "last_login": user["last_login"],
                "message_count": message_count,
                "conversation_count": conversation_count
            }
        })
        
    except Exception as e:
        logger.error(f"Profile error: {str(e)}")
        return jsonify({"error": "Failed to get profile"}), 500

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
        "authenticated_users": len(user_sessions)
    })

@app.route("/stats", methods=["GET"])
def get_stats():
    """Get basic statistics"""
    total_users = len(users_db)
    active_sessions = len(user_sessions)
    total_conversations = len(conversation_history)
    total_messages = sum(len(history) for history in conversation_history.values())
    
    return jsonify({
        "total_users": total_users,
        "active_sessions": active_sessions,
        "total_conversations": total_conversations,
        "total_messages": total_messages
    })

@app.route("/conversations", methods=["GET"])
@require_auth
def get_conversations():
    """Get all conversations for the current user"""
    try:
        user_id = get_user_id()
        conversations = get_user_conversations(user_id)
        
        return jsonify({
            "conversations": conversations,
            "total": len(conversations)
        })
        
    except Exception as e:
        logger.error(f"Error getting conversations: {str(e)}")
        return jsonify({"error": "Failed to get conversations"}), 500

@app.route("/conversations", methods=["POST"])
@require_auth
def create_new_conversation():
    """Create a new conversation"""
    try:
        user_id = get_user_id()
        data = request.get_json()
        title = data.get("title", "New Chat") if data else "New Chat"
        
        conversation_id = create_conversation(user_id, title)
        
        return jsonify({
            "conversation_id": conversation_id,
            "title": title,
            "message": "Conversation created successfully"
        })
        
    except Exception as e:
        logger.error(f"Error creating conversation: {str(e)}")
        return jsonify({"error": "Failed to create conversation"}), 500

@app.route("/conversations/<conversation_id>", methods=["GET"])
@require_auth
def get_conversation(conversation_id):
    """Get messages for a specific conversation"""
    try:
        user_id = get_user_id()
        messages = get_conversation_messages(user_id, conversation_id)
        
        if messages is None:
            return jsonify({"error": "Conversation not found"}), 404
        
        return jsonify({
            "conversation_id": conversation_id,
            "messages": messages,
            "total": len(messages)
        })
        
    except Exception as e:
        logger.error(f"Error getting conversation: {str(e)}")
        return jsonify({"error": "Failed to get conversation"}), 500

@app.route("/conversations/<conversation_id>", methods=["DELETE"])
@require_auth
def delete_conversation_endpoint(conversation_id):
    """Delete a conversation"""
    try:
        user_id = get_user_id()
        success = delete_conversation(user_id, conversation_id)
        
        if not success:
            return jsonify({"error": "Conversation not found"}), 404
        
        return jsonify({
            "message": "Conversation deleted successfully",
            "conversation_id": conversation_id
        })
        
    except Exception as e:
        logger.error(f"Error deleting conversation: {str(e)}")
        return jsonify({"error": "Failed to delete conversation"}), 500

@app.route("/conversations/<conversation_id>/rename", methods=["POST"])
@require_auth
def rename_conversation_endpoint(conversation_id):
    """Rename a conversation"""
    try:
        user_id = get_user_id()
        data = request.get_json()
        
        if not data or "title" not in data:
            return jsonify({"error": "Title is required"}), 400
        
        new_title = data["title"].strip()
        if not new_title:
            return jsonify({"error": "Title cannot be empty"}), 400
        
        success = rename_conversation(user_id, conversation_id, new_title)
        
        if not success:
            return jsonify({"error": "Conversation not found"}), 404
        
        return jsonify({
            "message": "Conversation renamed successfully",
            "conversation_id": conversation_id,
            "new_title": new_title
        })
        
    except Exception as e:
        logger.error(f"Error renaming conversation: {str(e)}")
        return jsonify({"error": "Failed to rename conversation"}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

# Clean up expired sessions periodically
def cleanup_expired_sessions():
    """Remove expired sessions"""
    current_time = datetime.now()
    expired_tokens = [
        token for token, session_data in user_sessions.items()
        if current_time > session_data['expires_at']
    ]
    
    for token in expired_tokens:
        del user_sessions[token]
        logger.info(f"Cleaned up expired session: {token[:10]}...")

if __name__ == "__main__":
    # Initialize database
    init_database()
    
    # Create templates directory if it doesn't exist
    os.makedirs("templates", exist_ok=True)
    os.makedirs("static", exist_ok=True)
    
    # Check if API key is set
    if API_KEY == "AIzaSyAbNfGTfN-WGCbDzEFYnY3MVfvortl-J3s" or not API_KEY:
        print("⚠️  WARNING: Please set your Google Gemini API key in the API_KEY variable")
        print("🔗 Get your API key from: https://aistudio.google.com/app/apikey")
    
    # Create some demo users for testing (save to database)
    demo_users = [
        {"email": "demo@askcodzz.com", "password": "demo123", "name": "Demo User"},
        {"email": "test@example.com", "password": "test123", "name": "Test User"}
    ]
    
    for demo_user in demo_users:
        existing_user = get_user_from_db(demo_user["email"])
        if not existing_user:
            password_hash = hash_password(demo_user["password"])
            save_user_to_db(demo_user["email"], password_hash, demo_user["name"])
            logger.info(f"Created demo user: {demo_user['email']}")
    
    print("🚀 Starting AskCodzz Chatbot Server with Authentication...")
    print("📱 Open your browser and go to: http://localhost:5000")
    print("👤 Demo login: demo@askcodzz.com / demo123")
    
    app.run(
        debug=True,
        host="0.0.0.0",
        port=5000,
        threaded=True
    )