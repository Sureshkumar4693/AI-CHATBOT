# MySQL Database Setup Guide for AskCodzz

This guide will walk you through setting up MySQL database connection for your AskCodzz project.

## Prerequisites

1. **MySQL Server installed and running**
   - Download from: https://dev.mysql.com/downloads/mysql/
   - Or use XAMPP/WAMP which includes MySQL
   - Make sure MySQL service is running

2. **Python Package**
   ```bash
   pip install pymysql
   ```

## Step-by-Step Instructions

### Step 1: Create MySQL Database

**Option A: Using MySQL Command Line**
```bash
mysql -u root -p
```

Then run:
```sql
CREATE DATABASE askcodzz CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
exit;
```

**Option B: Using MySQL Workbench or phpMyAdmin**
1. Open MySQL Workbench or phpMyAdmin
2. Create a new database named `askcodzz`
3. Set character set to `utf8mb4` and collation to `utf8mb4_unicode_ci`

### Step 2: Create MySQL User (Optional but Recommended)

For better security, create a dedicated user:

```sql
CREATE USER 'askcodzz_user'@'localhost' IDENTIFIED BY 'your_secure_password';
GRANT ALL PRIVILEGES ON askcodzz.* TO 'askcodzz_user'@'localhost';
FLUSH PRIVILEGES;
```

### Step 3: Configure Environment Variables

**For Windows (PowerShell):**
```powershell
$env:USE_MYSQL="true"
$env:MYSQL_HOST="localhost"
$env:MYSQL_PORT="3306"
$env:MYSQL_USER="root"  # or 'askcodzz_user' if you created one
$env:MYSQL_PASSWORD="Suresh@2006"
$env:MYSQL_DATABASE="askcodzz"
```

**For Windows (Command Prompt):**
```cmd
set USE_MYSQL=true
set MYSQL_HOST=localhost
set MYSQL_PORT=3306
set MYSQL_USER=root
set MYSQL_PASSWORD=your_password
set MYSQL_DATABASE=askcodzz
```

**For Linux/Mac:**
```bash
export USE_MYSQL=true
export MYSQL_HOST=localhost
export MYSQL_PORT=3306
export MYSQL_USER=root
export MYSQL_PASSWORD=your_password
export MYSQL_DATABASE=askcodzz
```

### Step 4: Create a Configuration File (Alternative Method)

Create a file named `.env` in your project root:

```
USE_MYSQL=true
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=askcodzz
```

Then install python-dotenv:
```bash
pip install python-dotenv
```

And update `app.py` to load from .env:
```python
from dotenv import load_dotenv
load_dotenv()
```

### Step 5: Run the Application

```bash
python app.py
```

The application will:
- Automatically create the database if it doesn't exist
- Create all necessary tables (users, conversations, messages, sessions, language_usage)
- Initialize the demo user

### Step 6: Verify Database Connection

Check the console output. You should see:
```
Database initialized successfully
🚀 Starting AskCodzz Chatbot Server with Authentication...
```

### Step 7: Verify Tables Were Created

Connect to MySQL and check:
```sql
USE askcodzz;
SHOW TABLES;
```

You should see:
- users
- conversations
- messages
- sessions
- language_usage

To view table structure:
```sql
DESCRIBE users;
DESCRIBE conversations;
DESCRIBE messages;
DESCRIBE sessions;
DESCRIBE language_usage;
```

## Database Schema

### Users Table
- `id`: Primary key (AUTO_INCREMENT)
- `email`: Unique user email
- `password_hash`: Encrypted password
- `name`: User's full name
- `created_at`: Account creation timestamp
- `last_login`: Last login timestamp

### Conversations Table
- `id`: Primary key (conversation ID)
- `user_email`: Foreign key to users
- `title`: Conversation title
- `created_at`: Creation timestamp
- `updated_at`: Last update timestamp

### Messages Table
- `id`: Primary key (AUTO_INCREMENT)
- `conversation_id`: Foreign key to conversations
- `content`: Message content
- `is_user`: Boolean (true for user, false for bot)
- `timestamp`: Message timestamp

### Sessions Table
- `token`: Primary key (session token)
- `user_email`: Foreign key to users
- `created_at`: Session creation time
- `expires_at`: Session expiration time

### Language Usage Table
- `id`: Primary key (AUTO_INCREMENT)
- `user_email`: Foreign key to users
- `language`: Programming language name
- `query_text`: Original query text
- `timestamp`: Query timestamp

## Troubleshooting

### Connection Error
- Check MySQL service is running
- Verify username and password
- Check firewall settings
- Ensure MySQL port 3306 is open

### Table Creation Error
- Verify database exists
- Check user has CREATE privileges
- Check character set is utf8mb4

### Import Data from SQLite
If you have existing SQLite data:
1. Export from SQLite
2. Convert to MySQL format
3. Import using MySQL Workbench or command line

## Switching Back to SQLite

If you want to use SQLite instead:
```bash
set USE_MYSQL=false
```
or simply don't set the USE_MYSQL variable.

## Quick Test Connection

Before running the main app, test your MySQL connection:

```bash
python test_mysql_connection.py
```

This script will:
- Check if PyMySQL is installed
- Test database connection
- Create database if it doesn't exist
- Verify tables (if any exist)
- Show you what's configured

## Conversation History Feature

The app now includes ChatGPT-like conversation history:

### Auto-Generated Titles
- When you start a new conversation and send your first message, the title is automatically generated from that first message
- Titles are truncated to 50 characters with smart word-boundary breaks
- Example: "How do I create a Python function?" → Title: "How do I create a Python function?"

### Sidebar Conversation List
- All your past conversations appear in the left sidebar
- Click any conversation to load its full history
- Conversations are sorted by most recently updated
- Each conversation shows:
  - Auto-generated or custom title
  - Edit button to rename
  - Delete button to remove

### Features
1. **Persistent Storage**: All conversations are stored in the database
2. **Auto-Titles**: First message automatically becomes the conversation title
3. **Easy Navigation**: Click any conversation in sidebar to switch
4. **Rename**: Edit button lets you customize conversation titles
5. **Delete**: Remove conversations you no longer need

## Production Recommendations

1. **Use strong passwords** for MySQL root user
2. **Create dedicated user** with limited privileges
3. **Enable SSL** for remote connections
4. **Regular backups**:
   ```bash
   mysqldump -u root -p askcodzz > backup.sql
   ```
5. **Monitor performance** using MySQL monitoring tools
6. **Set up connection pooling** for high-traffic applications

