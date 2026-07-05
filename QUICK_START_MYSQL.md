# Quick Start: MySQL Setup for AskCodzz

## 📋 Prerequisites Checklist

- [ ] MySQL Server installed and running
- [ ] PyMySQL package installed: `pip install pymysql`
- [ ] You know your MySQL root password

## 🚀 Step-by-Step Setup

### Step 1: Install PyMySQL
```bash
pip install pymysql
```

### Step 2: Create MySQL Database (Choose one method)

**Method A: Using MySQL Command Line**
```bash
mysql -u root -p
```
Then type:
```sql
CREATE DATABASE askcodzz CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
exit;
```

**Method B: Using MySQL Workbench**
1. Open MySQL Workbench
2. Connect to your MySQL server
3. Create new schema named `askcodzz`
4. Set default character set to `utf8mb4`

### Step 3: Set Environment Variables

**Windows PowerShell:**
```powershell
$env:USE_MYSQL="true"
$env:MYSQL_HOST="localhost"
$env:MYSQL_PORT="3306"
$env:MYSQL_USER="root"
$env:MYSQL_PASSWORD="your_mysql_password"
$env:MYSQL_DATABASE="askcodzz"
```

**Windows Command Prompt:**
```cmd
set USE_MYSQL=true
set MYSQL_HOST=localhost
set MYSQL_PORT=3306
set MYSQL_USER=root
set MYSQL_PASSWORD=your_mysql_password
set MYSQL_DATABASE=askcodzz
```

**Linux/Mac:**
```bash
export USE_MYSQL=true
export MYSQL_HOST=localhost
export MYSQL_PORT=3306
export MYSQL_USER=root
export MYSQL_PASSWORD=your_mysql_password
export MYSQL_DATABASE=askcodzz
```

**⚠️ Replace `your_mysql_password` with your actual MySQL root password!**

### Step 4: Test Connection (Optional but Recommended)
```bash
python test_mysql_connection.py
```

You should see:
```
✅ Connection successful!
✅ Database 'askcodzz' is ready!
🎉 All tests passed!
```

### Step 5: Run Your Application
```bash
python app.py
```

The app will automatically:
- ✅ Create all necessary tables
- ✅ Create demo user (demo@askcodzz.com / demo123)
- ✅ Initialize database structure

## 📊 What Tables Will Be Created?

When you run `app.py`, these tables will be automatically created:

1. **users** - User accounts (email, password, name)
2. **conversations** - Chat conversations with auto-generated titles
3. **messages** - Individual messages in conversations
4. **sessions** - User login sessions
5. **language_usage** - Programming language tracking for dashboard

## 💬 Conversation History Feature

### How It Works:
1. **Start a new chat** - Click "New Chat" button
2. **Send your first message** - Example: "How do I create a Python function?"
3. **Auto-title generation** - The title becomes "How do I create a Python function?"
4. **View in sidebar** - Your conversation appears in the left sidebar
5. **Switch conversations** - Click any conversation in sidebar to load it
6. **Rename/Delete** - Use edit/delete buttons on each conversation

### Features:
- ✅ Automatic title generation from first message (like ChatGPT)
- ✅ All conversations stored in MySQL database
- ✅ Easy navigation through conversation history
- ✅ Rename conversations anytime
- ✅ Delete conversations you don't need

## 🔧 Troubleshooting

### "Can't connect to MySQL server"
- Check MySQL service is running
- Verify username and password
- Check firewall settings

### "Access denied"
- Verify MySQL root password
- Check user has CREATE privileges

### Tables not created
- Check database exists
- Verify user has CREATE TABLE privileges
- Check console for error messages

### Want to use SQLite instead?
Simply don't set `USE_MYSQL=true` or set it to `false`

## ✅ Verification

After running the app, verify in MySQL:
```sql
USE askcodzz;
SHOW TABLES;
```

You should see 5 tables:
- users
- conversations
- messages
- sessions
- language_usage

## 🎉 You're Ready!

1. Login with: `demo@askcodzz.com` / `demo123`
2. Start a new conversation
3. Send a message - it will auto-generate a title
4. See it appear in your sidebar!
5. Click conversations to switch between them

---

**Need more details?** See `MYSQL_SETUP_GUIDE.md` for comprehensive documentation.

