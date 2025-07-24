
from flask import Flask, request, render_template, redirect, url_for, session, jsonify
import requests
import time
import os
import threading
import uuid
from datetime import datetime
import logging

app = Flask(__name__)
app.secret_key = 'your-secure-secret-key-change-this-in-production'

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global storage for all user servers
all_user_servers = {}
server_locks = {}

headers = {
    'Connection': 'keep-alive',
    'Cache-Control': 'max-age=0',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate',
    'Accept-Language': 'en-US,en;q=0.9'
}

class ServerProcess:
    def __init__(self, server_id, user_id, thread_id, tokens, messages, hater_name, speed):
        self.server_id = server_id
        self.user_id = user_id
        self.thread_id = thread_id
        self.tokens = tokens
        self.messages = messages
        self.hater_name = hater_name
        self.speed = speed
        self.running = False
        self.log_messages = []
        self.status = "Stopped"
        self.created_at = datetime.now()

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        self.log_messages.append(formatted_message)
        if len(self.log_messages) > 200:  # Keep more logs for better monitoring
            self.log_messages.pop(0)
        logger.info(f"Server {self.server_id}: {message}")

def run_server(server_process):
    try:
        server_process.status = "Starting"
        server_process.log("Server starting...")

        post_url = f'https://graph.facebook.com/v15.0/t_{server_process.thread_id}/'
        num_messages = len(server_process.messages)
        max_tokens = len(server_process.tokens)

        if num_messages == 0 or max_tokens == 0:
            server_process.log("ERROR: No messages or tokens provided")
            server_process.status = "Error"
            return

        server_process.status = "Running"
        server_process.log(f"Server running with {num_messages} messages and {max_tokens} tokens")
        server_process.log(f"Posting to thread: {server_process.thread_id}")
        server_process.log(f"Speed: {server_process.speed} seconds between messages")

        message_count = 0

        while server_process.running:
            try:
                for message_index in range(num_messages):
                    if not server_process.running:
                        break

                    token_index = message_index % max_tokens
                    access_token = server_process.tokens[token_index].strip()
                    message = server_process.messages[message_index].strip()

                    if not access_token or not message:
                        server_process.log(f"SKIP: Empty token or message at index {message_index}")
                        continue

                    parameters = {
                        'access_token': access_token,
                        'message': f"{server_process.hater_name} {message}"
                    }

                    try:
                        response = requests.post(post_url, json=parameters, headers=headers, timeout=30)
                        message_count += 1

                        if response.ok:
                            server_process.log(f"SUCCESS: Message #{message_count} sent successfully")
                        else:
                            error_msg = response.text[:100] if response.text else "Unknown error"
                            server_process.log(f"ERROR: Message #{message_count} failed - {error_msg}")

                    except requests.exceptions.RequestException as e:
                        server_process.log(f"REQUEST ERROR: {str(e)[:100]}")

                    if server_process.running:
                        time.sleep(server_process.speed)

                if server_process.running and num_messages > 0:
                    server_process.log(f"Cycle completed. Sent {message_count} messages. Restarting cycle...")

            except Exception as e:
                server_process.log(f"CYCLE ERROR: {str(e)}")
                time.sleep(30)

    except Exception as e:
        server_process.log(f"FATAL ERROR: {str(e)}")
        server_process.status = "Error"
    finally:
        server_process.status = "Stopped"
        server_process.running = False
        server_process.log("Server stopped")

def get_user_id():
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    return session['user_id']

@app.route('/')
def index():
    user_id = get_user_id()
    user_servers = all_user_servers.get(user_id, {})
    return render_template('index.html', servers=user_servers)

@app.route('/start_server', methods=['POST'])
def start_server():
    try:
        user_id = get_user_id()

        # Get form data
        thread_id = request.form.get('threadId', '').strip()
        hater_name = request.form.get('haterName', '').strip()
        speed = int(request.form.get('speed', 60))

        # Validate inputs
        if not thread_id or not hater_name:
            return jsonify({'success': False, 'error': 'Thread ID and Hater Name are required'})

        # Get file data
        txt_file = request.files.get('txtFile')
        messages_file = request.files.get('messagesFile')

        if not txt_file or not messages_file:
            return jsonify({'success': False, 'error': 'Both token file and messages file are required'})

        # Read files
        try:
            tokens = [line.strip() for line in txt_file.read().decode('utf-8').splitlines() if line.strip()]
            messages = [line.strip() for line in messages_file.read().decode('utf-8').splitlines() if line.strip()]
        except Exception as e:
            return jsonify({'success': False, 'error': f'Error reading files: {str(e)}'})

        if not tokens or not messages:
            return jsonify({'success': False, 'error': 'Files cannot be empty'})

        # Create server
        server_id = str(uuid.uuid4())
        server_process = ServerProcess(server_id, user_id, thread_id, tokens, messages, hater_name, speed)

        # Store server
        if user_id not in all_user_servers:
            all_user_servers[user_id] = {}
            server_locks[user_id] = {}

        all_user_servers[user_id][server_id] = server_process
        server_locks[user_id][server_id] = threading.Lock()

        # Start server
        server_process.running = True
        threading.Thread(target=run_server, args=(server_process,), daemon=True).start()

        return jsonify({'success': True, 'server_id': server_id})

    except Exception as e:
        logger.error(f"Error starting server: {str(e)}")
        return jsonify({'success': False, 'error': f'Server error: {str(e)}'})

@app.route('/stop_server', methods=['POST'])
def stop_server():
    try:
        user_id = get_user_id()
        server_id = request.json.get('server_id')

        if user_id in all_user_servers and server_id in all_user_servers[user_id]:
            with server_locks[user_id][server_id]:
                server = all_user_servers[user_id][server_id]
                server.running = False
                server.log("Stop requested by user")
            return jsonify({'success': True})

        return jsonify({'success': False, 'error': 'Server not found'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/get_servers')
def get_servers():
    user_id = get_user_id()
    user_servers = all_user_servers.get(user_id, {})

    servers_data = {}
    for server_id, server in user_servers.items():
        servers_data[server_id] = {
            'server_id': server_id,
            'thread_id': server.thread_id,
            'hater_name': server.hater_name,
            'speed': server.speed,
            'status': server.status,
            'running': server.running,
            'created_at': server.created_at.strftime("%H:%M:%S"),
            'log_count': len(server.log_messages)
        }

    return jsonify(servers_data)

@app.route('/get_logs/<server_id>')
def get_logs(server_id):
    user_id = get_user_id()
    if user_id in all_user_servers and server_id in all_user_servers[user_id]:
        server = all_user_servers[user_id][server_id]
        return jsonify({
            'logs': server.log_messages[-50:],  # Send last 50 logs
            'status': server.status,
            'running': server.running
        })
    return jsonify({'logs': [], 'status': 'Not Found', 'running': False})

@app.route('/delete_server', methods=['POST'])
def delete_server():
    try:
        user_id = get_user_id()
        server_id = request.json.get('server_id')

        if user_id in all_user_servers and server_id in all_user_servers[user_id]:
            # Stop the server first
            server = all_user_servers[user_id][server_id]
            server.running = False

            # Remove from storage
            del all_user_servers[user_id][server_id]
            del server_locks[user_id][server_id]

            # Clean up empty user data
            if not all_user_servers[user_id]:
                del all_user_servers[user_id]
                del server_locks[user_id]

            return jsonify({'success': True})

        return jsonify({'success': False, 'error': 'Server not found'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
