"""
MySQL Connection Test Script for AskCodzz
Run this script to test your MySQL connection before starting the main application.
"""

import os
import sys

try:
    import pymysql
    import pymysql.cursors
    print("✅ PyMySQL is installed")
except ImportError:
    print("❌ PyMySQL is not installed. Install it with: pip install pymysql")
    sys.exit(1)

# Get configuration from environment variables or use defaults
MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
MYSQL_PORT = int(os.getenv('MYSQL_PORT', 3306))
MYSQL_USER = os.getenv('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', '')
MYSQL_DATABASE = os.getenv('MYSQL_DATABASE', 'askcodzz')

print("\n🔍 Testing MySQL Connection...")
print(f"   Host: {MYSQL_HOST}")
print(f"   Port: {MYSQL_PORT}")
print(f"   User: {MYSQL_USER}")
print(f"   Database: {MYSQL_DATABASE}")

try:
    # Test basic connection
    print("\n📡 Step 1: Testing basic connection...")
    conn = pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        cursorclass=pymysql.cursors.DictCursor
    )
    print("   ✅ Connection successful!")
    
    # Test database creation
    print("\n📦 Step 2: Checking/Creating database...")
    with conn.cursor() as cursor:
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {MYSQL_DATABASE} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        conn.commit()
    print(f"   ✅ Database '{MYSQL_DATABASE}' is ready!")
    
    # Test connecting to the database
    print("\n🗄️  Step 3: Connecting to database...")
    conn.select_db(MYSQL_DATABASE)
    print("   ✅ Database connection successful!")
    
    # Check existing tables
    print("\n📋 Step 4: Checking tables...")
    with conn.cursor() as cursor:
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        if tables:
            print(f"   ✅ Found {len(tables)} existing table(s):")
            for table in tables:
                print(f"      - {list(table.values())[0]}")
        else:
            print("   ℹ️  No tables found. They will be created when you run app.py")
    
    conn.close()
    
    print("\n" + "="*50)
    print("🎉 All tests passed! Your MySQL setup is ready.")
    print("="*50)
    print("\n💡 Next steps:")
    print("   1. Set environment variables:")
    print("      set USE_MYSQL=true")
    print("      set MYSQL_HOST=localhost")
    print("      set MYSQL_USER=root")
    print("      set MYSQL_PASSWORD=your_password")
    print("      set MYSQL_DATABASE=askcodzz")
    print("\n   2. Run your application:")
    print("      python app.py")
    print("\n✅ Your app will automatically create all necessary tables!")
    
except pymysql.Error as e:
    print(f"\n❌ MySQL Error: {e}")
    print("\n🔧 Troubleshooting:")
    print("   1. Check MySQL service is running")
    print("   2. Verify username and password")
    print("   3. Check MySQL port (default: 3306)")
    print("   4. Ensure MySQL user has CREATE DATABASE privileges")
    sys.exit(1)
except Exception as e:
    print(f"\n❌ Error: {e}")
    sys.exit(1)

