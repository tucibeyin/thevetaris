import os
from dotenv import load_dotenv
from src.database import create_user, get_db_connection, init_db
import psycopg2

load_dotenv()

def seed_admin():
    # Ensure DB is up to date (creates tables/columns if missing)
    init_db()

    email = os.getenv("ADMIN_EMAIL")
    password = os.getenv("ADMIN_PASS")

    if not email or not password:
        print("❌ ADMIN_EMAIL / ADMIN_PASS .env dosyasinda tanimli degil")
        return

    conn = get_db_connection()
    if not conn:
        print("❌ DB Connection failed")
        return

    try:
        cur = conn.cursor()
        # Check if admin exists
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        existing = cur.fetchone()
        
        if existing:
            print(f"⚠️ Admin user {email} already exists.")
            # Ensure is_admin is true
            cur.execute("UPDATE users SET is_admin = TRUE WHERE id = %s", (existing[0],))
            conn.commit()
            print("✅ ensured is_admin = TRUE")
        else:
            # Create user logic is complex in database.py (hashing etc), so let's use the function
            # But we need to manually set is_admin=True afterwards because create_user doesn't support it yet
            pass
        
        cur.close()
        conn.close()

        if not existing:
            try:
                user = create_user(email, password)
                if user:
                    conn = get_db_connection()
                    cur = conn.cursor()
                    cur.execute("UPDATE users SET is_admin = TRUE WHERE id = %s", (user[0],))
                    conn.commit()
                    cur.close()
                    conn.close()
                    print(f"✅ Created Admin User: {email}")
            except ValueError:
                print("User already exists (caught in creation)")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    seed_admin()
