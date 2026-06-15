import http.server
import socketserver
import json
import os
import re
import mimetypes
from http import cookies
from urllib.parse import urlparse, parse_qs
import database  # Import our database module
from datetime import datetime, date

PORT = 8801
DIRECTORY = "public"

# Ensure common MIME types are registered on minimal Linux installs
mimetypes.add_type('image/jpeg', '.jpg')
mimetypes.add_type('image/jpeg', '.jpeg')
mimetypes.add_type('image/png', '.png')
mimetypes.add_type('image/webp', '.webp')
mimetypes.add_type('image/gif', '.gif')
mimetypes.add_type('image/svg+xml', '.svg')

# Initialize Database
database.init_db()

class ThreadingHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True

class VetarisHandler(http.server.SimpleHTTPRequestHandler):
    def parse_cookies(self):
        if 'Cookie' in self.headers:
            return cookies.SimpleCookie(self.headers['Cookie'])
        return cookies.SimpleCookie()

    def get_current_user(self):
        cookie = self.parse_cookies()
        if 'session_id' in cookie:
            session_id = cookie['session_id'].value
            return database.get_session(session_id)
        return None

    def send_json_response(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        # Helper to serialize datetime and decimal objects
        from decimal import Decimal
        def json_serial(obj):
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            if isinstance(obj, Decimal):
                return float(obj)
            raise TypeError ("Type %s not serializable" % type(obj))

        self.wfile.write(json.dumps(data, default=json_serial).encode('utf-8'))

    def check_admin(self):
        user_session = self.get_current_user()
        if user_session and user_session.get('is_admin'):
            return True
        return False

    def do_POST(self):
        parsed = urlparse(self.path)
        clean_path = parsed.path

        # Admin Upload Endpoint (Multipart) - Quick & Dirty handling
        if clean_path == '/api/upload':
            if not self.check_admin():
                self.send_json_response({"error": "Unauthorized"}, 403)
                return
            
            # This is a basic implementation. For production, use `cgi` or `multipart` parser
            # But simplehttp server doesn't parse multipart automatically.
            # We'll skip complex upload for now or assume a simpler base64 json mechanism if possible,
            # Or just save files to distinct path if we really want multipart.
            # Let's switch to JSON base64 for simplicity in this "no-framework" environment.
            pass 

        # Parse JSON content length
        try:
            content_length = int(self.headers.get('Content-Length', 0))
        except ValueError:
            content_length = 0
            
        post_data = self.rfile.read(content_length)
        
        try:
            if content_length > 0:
                data = json.loads(post_data.decode('utf-8'))
            else:
                data = {}
        except json.JSONDecodeError:
            self.send_json_response({"error": "Invalid JSON"}, 400)
            return

        # Auth Endpoints
        if clean_path == '/api/auth/register':
            email = data.get('email')
            password = data.get('password')

            if not email or not password:
                self.send_json_response({"error": "Email and password required"}, 400)
                return

            try:
                user = database.create_user(email, password)
                if user:
                    self.send_json_response({"message": "User created successfully", "user_id": user[0]})
                else:
                    self.send_json_response({"error": "Unknown error"}, 500)
            except ValueError as e:
                # User already exists
                self.send_json_response({"error": str(e)}, 409)
            except Exception as e:
                # Database error
                self.send_json_response({"error": str(e)}, 500)
            return

        elif clean_path == '/api/auth/login':
            email = data.get('email')
            password = data.get('password')

            user = database.get_user_by_email(email)
            if user and database.verify_password(user['password_hash'], password):
                session_id = database.create_session(user['id'])

                # Set Cookie
                self.send_response(200)
                self.send_header('Content-type', 'application/json')

                # HttpOnly cookie for security
                cookie = cookies.SimpleCookie()
                cookie['session_id'] = session_id
                cookie['session_id']['path'] = '/'
                cookie['session_id']['httponly'] = True
                self.send_header('Set-Cookie', cookie.output(header=''))

                self.end_headers()
                self.wfile.write(json.dumps({
                    "message": "Login successful",
                    "email": user['email'],
                    "is_admin": user.get('is_admin', False)
                }).encode('utf-8'))
            else:
                self.send_json_response({"error": "Invalid credentials"}, 401)
            return

        elif clean_path == '/api/orders':
            user_session = self.get_current_user()
            if not user_session:
                self.send_json_response({"error": "Unauthorized"}, 401)
                return

            items = data.get('items')
            total = data.get('total')

            if not items or not total:
                 self.send_json_response({"error": "Items and total required"}, 400)
                 return

            try:
                order_id = database.create_order(user_session['user_id'], items, total)
                self.send_json_response({"message": "Order created successfully", "order_id": order_id})
            except Exception as e:
                self.send_json_response({"error": str(e)}, 500)
            return

        elif clean_path == '/api/auth/logout':
            cookie = self.parse_cookies()
            if 'session_id' in cookie:
                database.delete_session(cookie['session_id'].value)

            # Clear cookie
            self.send_response(200)
            cookie = cookies.SimpleCookie()
            cookie['session_id'] = ''
            cookie['session_id']['path'] = '/'
            cookie['session_id']['expires'] = 0
            self.send_header('Set-Cookie', cookie.output(header=''))
            self.end_headers()
            self.wfile.write(json.dumps({"message": "Logged out"}).encode('utf-8'))
            return

        # --- Admin Endpoints ---

        elif clean_path == '/api/products': # Create Product
            if not self.check_admin():
                self.send_json_response({"error": "Unauthorized"}, 403)
                return
            try:
                product = database.create_product(data)
                self.send_json_response(product, 201)
            except Exception as e:
                self.send_json_response({"error": str(e)}, 500)
            return

        elif clean_path.startswith('/api/admin/orders/'):
            # e.g. /api/admin/orders/5/status
            if not self.check_admin():
                self.send_json_response({"error": "Unauthorized"}, 403)
                return

            parts = clean_path.split('/')
            if len(parts) >= 6 and parts[5] == 'status':
                order_id = parts[4]
                status = data.get('status')
                if database.update_order_status(order_id, status):
                    self.send_json_response({"success": True})
                else:
                     self.send_json_response({"error": "Update failed"}, 500)
            return

        elif clean_path == '/api/posts': # Create Blog Post
            if not self.check_admin():
                self.send_json_response({"error": "Unauthorized"}, 403)
                return
            try:
                post = database.create_post(data)
                self.send_json_response(post, 201)
            except Exception as e:
                self.send_json_response({"error": str(e)}, 500)
            return
            
        self.send_error(404, "Endpoint not found")

    def do_PUT(self):
        parsed = urlparse(self.path)
        clean_path = parsed.path

        # Parse content length
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 0:
                data = json.loads(self.rfile.read(content_length).decode('utf-8'))
            else:
                data = {}
        except:
             self.send_json_response({"error": "Invalid request"}, 400)
             return

        if clean_path.startswith('/api/products/'):
            if not self.check_admin():
                self.send_json_response({"error": "Unauthorized"}, 403)
                return

            product_id = clean_path.split('/')[-1]
            try:
                updated = database.update_product(product_id, data)
                if updated:
                    self.send_json_response(updated)
                else:
                    self.send_json_response({"error": "Product not found"}, 404)
            except Exception as e:
                 self.send_json_response({"error": str(e)}, 500)
            return

        elif clean_path.startswith('/api/posts/'):
            if not self.check_admin():
                self.send_json_response({"error": "Unauthorized"}, 403)
                return

            post_id = clean_path.split('/')[-1]
            try:
                updated = database.update_post(post_id, data)
                if updated:
                    self.send_json_response(updated)
                else:
                    self.send_json_response({"error": "Post not found"}, 404)
            except Exception as e:
                 self.send_json_response({"error": str(e)}, 500)
            return

    def do_DELETE(self):
        parsed = urlparse(self.path)
        clean_path = parsed.path

        if clean_path.startswith('/api/products/'):
            if not self.check_admin():
                self.send_json_response({"error": "Unauthorized"}, 403)
                return

            product_id = clean_path.split('/')[-1]
            try:
                database.delete_product(product_id)
                self.send_json_response({"success": True})
            except Exception as e:
                 self.send_json_response({"error": str(e)}, 500)
            return

        elif clean_path.startswith('/api/posts/'):
            if not self.check_admin():
                self.send_json_response({"error": "Unauthorized"}, 403)
                return

            post_id = clean_path.split('/')[-1]
            try:
                database.delete_post(post_id)
                self.send_json_response({"success": True})
            except Exception as e:
                 self.send_json_response({"error": str(e)}, 500)
            return

    def do_GET(self):
        parsed = urlparse(self.path)
        clean_path = parsed.path
        query_params = parse_qs(parsed.query)

        # API Endpoints
        if clean_path == '/api/products':
            try:
                products = database.get_all_products()
                self.send_json_response(products)
            except Exception as e:
                self.send_json_response({"error": str(e)}, 500)
            return

        elif clean_path.startswith('/api/products/'):
            product_id = clean_path.split('/')[-1]
            try:
                product = database.get_product(product_id)
                if product:
                    self.send_json_response(product)
                else:
                    self.send_json_response({"error": "Product not found"}, 404)
            except Exception as e:
                self.send_json_response({"error": str(e)}, 500)
            return

        elif clean_path == '/api/auth/me':
            user_session = self.get_current_user()
            if user_session:
                self.send_json_response({
                    "authenticated": True,
                    "email": user_session['email'],
                    "is_admin": user_session.get('is_admin', False)
                })
            else:
                self.send_json_response({"authenticated": False}, 401)
            return

        elif clean_path == '/api/orders':
            user_session = self.get_current_user()
            if not user_session:
                self.send_json_response({"error": "Unauthorized"}, 401)
                return

            orders = database.get_user_orders(user_session['user_id'])
            self.send_json_response(orders)
            return

        elif clean_path == '/api/admin/orders':
            if not self.check_admin():
                 self.send_json_response({"error": "Unauthorized"}, 403)
                 return
            orders = database.get_all_orders()
            self.send_json_response(orders)
            return

        # Blog Public Endpoints
        elif clean_path == '/api/posts':
            try:
                posts = database.get_all_posts(public_only=True)
                self.send_json_response(posts)
            except Exception as e:
                self.send_json_response({"error": str(e)}, 500)
            return

        elif clean_path.startswith('/api/posts/'):
            # Single Post by ID or Slug
            post_id = clean_path.split('/')[-1]
            try:
                post = database.get_post(post_id)
                if post:
                     self.send_json_response(post)
                else:
                     self.send_json_response({"error": "Post not found"}, 404)
            except Exception as e:
                self.send_json_response({"error": str(e)}, 500)
            return

        # Admin Blog List (All posts)
        elif clean_path == '/api/admin/posts':
            if not self.check_admin():
                 self.send_json_response({"error": "Unauthorized"}, 403)
                 return
            posts = database.get_all_posts(public_only=False)
            self.send_json_response(posts)
            return

        # Serve Static Files
        file_path_str = clean_path if clean_path != '/' else '/index.html'

        # Construct full path to the file in 'public' directory
        file_path = os.path.join(DIRECTORY, file_path_str.lstrip('/'))

        # Check if file exists
        if not (os.path.exists(file_path) and os.path.isfile(file_path)):
            self.send_error(404, "File not found")
            return

        mime_type, _ = mimetypes.guess_type(file_path)
        file_size = os.path.getsize(file_path)
        range_header = self.headers.get('Range')

        if range_header:
            # Mobil tarayıcılar video için Range Request gönderir (RFC 7233)
            match = re.match(r'bytes=(\d*)-(\d*)', range_header)
            if match:
                start = int(match.group(1)) if match.group(1) else 0
                end = int(match.group(2)) if match.group(2) else file_size - 1
                end = min(end, file_size - 1)
                length = end - start + 1

                self.send_response(206)
                if mime_type:
                    self.send_header('Content-Type', mime_type)
                self.send_header('Content-Range', f'bytes {start}-{end}/{file_size}')
                self.send_header('Content-Length', str(length))
                self.send_header('Accept-Ranges', 'bytes')
                self.end_headers()
                with open(file_path, 'rb') as f:
                    f.seek(start)
                    self.wfile.write(f.read(length))
            else:
                self.send_error(400, "Invalid Range header")
        else:
            self.send_response(200)
            if mime_type:
                self.send_header('Content-Type', mime_type)
            self.send_header('Content-Length', str(file_size))
            self.send_header('Accept-Ranges', 'bytes')
            self.end_headers()
            with open(file_path, 'rb') as f:
                self.wfile.write(f.read())

    def log_message(self, format, *args):
        # Override to log to console
        print(f"[{self.log_date_time_string()}] {format%args}")

if __name__ == "__main__":
    # Force unbuffered output for Docker/Systemd logs
    import sys
    sys.stdout.reconfigure(line_buffering=True)
    
    print(f"✅ SYSTEM: Vetaris Server baslatiliyor... Port: {PORT}")
    print(f"Statik dosya dizini: {DIRECTORY}")
    
    # Use ThreadingTCPServer for concurrent requests
    with ThreadingHTTPServer(("", PORT), VetarisHandler) as httpd:
        print("Sunucu calisiyor. Durdurmak icin CTRL+C basin.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nSunucu durduruluyor...")
            httpd.server_close()
