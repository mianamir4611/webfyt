
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, Response
import subprocess
import threading
import uuid
import os
import time
import signal
import psutil
from datetime import datetime
import requests
import json
import queue
import logging
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your-secure-secret-key-change-this-in-production'

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Persistent storage directory
STORAGE_DIR = "persistent_servers"
os.makedirs(STORAGE_DIR, exist_ok=True)

# Store running processes and their info
user_processes = {}
process_locks = {}
user_logs = {}

# Allowed file extensions
ALLOWED_EXTENSIONS = {'txt'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_user_id():
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    return session['user_id']

def log_message(user_id, server_id, message):
    """Add log message to user's server logs"""
    if user_id not in user_logs:
        user_logs[user_id] = {}
    if server_id not in user_logs[user_id]:
        user_logs[user_id][server_id] = []
    
    timestamp = datetime.now().strftime('%H:%M:%S')
    formatted_message = f"[{timestamp}] {message}"
    user_logs[user_id][server_id].append(formatted_message)
    
    # Keep only last 500 messages
    if len(user_logs[user_id][server_id]) > 500:
        user_logs[user_id][server_id] = user_logs[user_id][server_id][-500:]

def save_server_data(user_id, server_id, server_info, server_type):
    """Save server data to persistent storage"""
    user_dir = os.path.join(STORAGE_DIR, user_id)
    os.makedirs(user_dir, exist_ok=True)
    
    server_data = {
        'server_id': server_id,
        'user_id': user_id,
        'type': server_type,
        'started': server_info['started'].isoformat(),
        'status': server_info.get('status', 'running')
    }
    
    # Add type-specific data
    if server_type == 'convo':
        server_data.update({
            'thread_id': server_info.get('thread_id', ''),
            'hater_name': server_info.get('hater_name', ''),
            'speed': server_info.get('speed', 60)
        })
    elif server_type == 'fyt':
        server_data.update({
            'post_id': server_info.get('post_id', ''),
            'hater_name': server_info.get('hater_name', ''),
            'speed': server_info.get('speed', 60)
        })
    
    with open(os.path.join(user_dir, f"{server_id}.json"), 'w') as f:
        json.dump(server_data, f)

def load_server_data(user_id, server_id):
    """Load server data from persistent storage"""
    try:
        server_file = os.path.join(STORAGE_DIR, user_id, f"{server_id}.json")
        if os.path.exists(server_file):
            with open(server_file, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading server data: {e}")
    return None

def load_all_user_servers():
    """Load all user servers from persistent storage on startup"""
    global user_processes, process_locks, user_logs
    
    if not os.path.exists(STORAGE_DIR):
        return
    
    for user_id in os.listdir(STORAGE_DIR):
        user_dir = os.path.join(STORAGE_DIR, user_id)
        if not os.path.isdir(user_dir):
            continue
            
        user_processes[user_id] = {}
        process_locks[user_id] = {}
        user_logs[user_id] = {}
        
        for server_file in os.listdir(user_dir):
            if server_file.endswith('.json'):
                server_id = server_file[:-5]  # Remove .json extension
                data = load_server_data(user_id, server_id)
                
                if data:
                    # Check if server files still exist
                    user_data_dir = f"user_data/{user_id}"
                    server_files_exist = False
                    
                    if data['type'] == 'convo':
                        token_file = os.path.join(user_data_dir, f'tokens_{server_id}.txt')
                        message_file = os.path.join(user_data_dir, f'messages_{server_id}.txt')
                        server_files_exist = os.path.exists(token_file) and os.path.exists(message_file)
                    elif data['type'] == 'fyt':
                        token_file = os.path.join(user_data_dir, f'tokens_{server_id}.txt')
                        comment_file = os.path.join(user_data_dir, f'comments_{server_id}.txt')
                        server_files_exist = os.path.exists(token_file) and os.path.exists(comment_file)
                    
                    if server_files_exist:
                        # Recreate server info object
                        server_info = {
                            'process': None,  # Will be None until restarted
                            'type': data['type'],
                            'started': datetime.fromisoformat(data['started']),
                            'status': 'stopped'  # All servers start as stopped after restart
                        }
                        
                        # Add type-specific info
                        if data['type'] == 'convo':
                            server_info.update({
                                'thread_id': data.get('thread_id', ''),
                                'hater_name': data.get('hater_name', ''),
                                'speed': data.get('speed', 60)
                            })
                        elif data['type'] == 'fyt':
                            server_info.update({
                                'post_id': data.get('post_id', ''),
                                'hater_name': data.get('hater_name', ''),
                                'speed': data.get('speed', 60)
                            })
                        
                        user_processes[user_id][server_id] = server_info
                        process_locks[user_id][server_id] = threading.Lock()
                        user_logs[user_id][server_id] = []
                        
                        log_message(user_id, server_id, "Server restored from persistent storage")

def delete_server_data(user_id, server_id):
    """Delete server data from persistent storage"""
    try:
        server_file = os.path.join(STORAGE_DIR, user_id, f"{server_id}.json")
        if os.path.exists(server_file):
            os.remove(server_file)
        
        # Clean up empty user directory
        user_dir = os.path.join(STORAGE_DIR, user_id)
        if os.path.exists(user_dir) and not os.listdir(user_dir):
            os.rmdir(user_dir)
    except Exception as e:
        logger.error(f"Error deleting server data: {e}")

# Load existing servers on startup
load_all_user_servers()

def kill_process_tree(pid):
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            child.kill()
        parent.kill()
    except psutil.NoSuchProcess:
        pass

@app.route('/')
def index():
    user_id = get_user_id()
    return render_template('index.html', user_id=user_id)

@app.route('/convo')
def convo_page():
    user_id = get_user_id()
    user_servers = user_processes.get(user_id, {})
    convo_servers = {k: v for k, v in user_servers.items() if v.get('type') == 'convo'}
    return render_template('convo.html', user_id=user_id, servers=convo_servers)

@app.route('/fyt')
def fyt_page():
    user_id = get_user_id()
    user_servers = user_processes.get(user_id, {})
    fyt_servers = {k: v for k, v in user_servers.items() if v.get('type') == 'fyt'}
    return render_template('fyt.html', user_id=user_id, servers=fyt_servers)

@app.route('/token')
def token_page():
    user_id = get_user_id()
    return render_template('token.html', user_id=user_id)

@app.route('/token_validate')
def token_validate_page():
    user_id = get_user_id()
    return render_template('token_validate.html', user_id=user_id)

@app.route('/validate_token', methods=['POST'])
def validate_token():
    try:
        token = request.json.get('token', '').strip()
        
        if not token:
            return jsonify({'success': False, 'error': 'Token is required'})
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Try to get user info using the token
        me_url = f'https://graph.facebook.com/v15.0/me'
        params = {
            'access_token': token,
            'fields': 'id,name'
        }
        
        response = requests.get(me_url, params=params, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if 'error' in data:
                error_msg = data['error'].get('message', 'Token is expired or invalid')
                return jsonify({'success': False, 'error': error_msg})
            
            user_name = data.get('name', 'Unknown')
            user_id = data.get('id', 'Unknown')
            
            return jsonify({
                'success': True,
                'name': user_name,
                'uid': user_id
            })
        
        elif response.status_code == 400:
            return jsonify({'success': False, 'error': 'Token is expired or invalid'})
        elif response.status_code == 401:
            return jsonify({'success': False, 'error': 'Token is expired or invalid'})
        else:
            return jsonify({'success': False, 'error': 'Unable to validate token. Please try again.'})
            
    except requests.exceptions.Timeout:
        return jsonify({'success': False, 'error': 'Request timeout. Please try again.'})
    except requests.exceptions.RequestException:
        return jsonify({'success': False, 'error': 'Network error occurred. Please try again.'})
    except Exception as e:
        logger.error(f"Token validation error: {str(e)}")
        return jsonify({'success': False, 'error': 'An error occurred while validating the token.'})

@app.route('/start_convo', methods=['POST'])
def start_convo():
    try:
        user_id = get_user_id()
        
        # Get form data
        thread_id = request.form.get('threadId', '').strip()
        hater_name = request.form.get('haterName', '').strip()
        speed = int(request.form.get('speed', 60))
        
        # Validate inputs
        if not thread_id or not hater_name or speed < 1:
            return jsonify({'success': False, 'error': 'All fields are required and speed must be positive'})
        
        # Get files
        token_file = request.files.get('tokenFile')
        message_file = request.files.get('messageFile')
        
        if not token_file or not message_file:
            return jsonify({'success': False, 'error': 'Both token and message files are required'})
        
        if not allowed_file(token_file.filename) or not allowed_file(message_file.filename):
            return jsonify({'success': False, 'error': 'Only .txt files are allowed'})
        
        # Create user directory
        user_dir = f"user_data/{user_id}"
        os.makedirs(user_dir, exist_ok=True)
        
        # Generate unique server ID
        server_id = str(uuid.uuid4())
        
        # Save files with server ID
        token_path = os.path.join(user_dir, f'tokens_{server_id}.txt')
        message_path = os.path.join(user_dir, f'messages_{server_id}.txt')
        
        token_file.save(token_path)
        message_file.save(message_path)
        
        # Start convo process
        cmd = [
            'python', 'convo_runner.py',
            '--thread_id', thread_id,
            '--hater_name', hater_name,
            '--speed', str(speed),
            '--token_file', token_path,
            '--message_file', message_path,
            '--user_id', user_id,
            '--server_id', server_id
        ]
        
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                 text=True, bufsize=1, universal_newlines=True)
        
        # Store process info
        if user_id not in user_processes:
            user_processes[user_id] = {}
            process_locks[user_id] = {}
        
        server_info = {
            'process': process,
            'type': 'convo',
            'started': datetime.now(),
            'thread_id': thread_id,
            'hater_name': hater_name,
            'speed': speed,
            'status': 'running'
        }
        
        user_processes[user_id][server_id] = server_info
        process_locks[user_id][server_id] = threading.Lock()
        
        # Save to persistent storage
        save_server_data(user_id, server_id, server_info, 'convo')
        
        # Start log monitoring thread
        threading.Thread(target=monitor_process_logs, args=(user_id, server_id, process), daemon=True).start()
        
        log_message(user_id, server_id, f"Convo server started - Thread: {thread_id}, Speed: {speed}s")
        
        return jsonify({'success': True, 'server_id': server_id, 'message': 'Convo server started successfully'})
        
    except Exception as e:
        logger.error(f"Error starting convo server: {str(e)}")
        return jsonify({'success': False, 'error': f'Server error: {str(e)}'})

@app.route('/start_fyt', methods=['POST'])
def start_fyt():
    try:
        user_id = get_user_id()
        
        # Get form data
        post_id = request.form.get('postId', '').strip()
        hater_name = request.form.get('haterName', '').strip()
        speed = int(request.form.get('speed', 60))
        
        # Validate inputs
        if not post_id or not hater_name or speed < 1:
            return jsonify({'success': False, 'error': 'All fields are required and speed must be positive'})
        
        # Get files
        token_file = request.files.get('tokenFile')
        comment_file = request.files.get('commentFile')
        
        if not token_file or not comment_file:
            return jsonify({'success': False, 'error': 'Both token and comment files are required'})
        
        if not allowed_file(token_file.filename) or not allowed_file(comment_file.filename):
            return jsonify({'success': False, 'error': 'Only .txt files are allowed'})
        
        # Create user directory
        user_dir = f"user_data/{user_id}"
        os.makedirs(user_dir, exist_ok=True)
        
        # Generate unique server ID
        server_id = str(uuid.uuid4())
        
        # Save files with server ID
        token_path = os.path.join(user_dir, f'tokens_{server_id}.txt')
        comment_path = os.path.join(user_dir, f'comments_{server_id}.txt')
        
        token_file.save(token_path)
        comment_file.save(comment_path)
        
        # Start fyt process
        cmd = [
            'python', 'fyt_runner.py',
            '--post_id', post_id,
            '--hater_name', hater_name,
            '--speed', str(speed),
            '--token_file', token_path,
            '--comment_file', comment_path,
            '--user_id', user_id,
            '--server_id', server_id
        ]
        
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                 text=True, bufsize=1, universal_newlines=True)
        
        # Store process info
        if user_id not in user_processes:
            user_processes[user_id] = {}
            process_locks[user_id] = {}
        
        server_info = {
            'process': process,
            'type': 'fyt',
            'started': datetime.now(),
            'post_id': post_id,
            'hater_name': hater_name,
            'speed': speed,
            'status': 'running'
        }
        
        user_processes[user_id][server_id] = server_info
        process_locks[user_id][server_id] = threading.Lock()
        
        # Save to persistent storage
        save_server_data(user_id, server_id, server_info, 'fyt')
        
        # Start log monitoring thread
        threading.Thread(target=monitor_process_logs, args=(user_id, server_id, process), daemon=True).start()
        
        log_message(user_id, server_id, f"Post Convo server started - Post: {post_id}, Speed: {speed}s")
        
        return jsonify({'success': True, 'server_id': server_id, 'message': 'Post Convo server started successfully'})
        
    except Exception as e:
        logger.error(f"Error starting fyt server: {str(e)}")
        return jsonify({'success': False, 'error': f'Server error: {str(e)}'})

@app.route('/restart_server', methods=['POST'])
def restart_server():
    try:
        user_id = get_user_id()
        server_id = request.json.get('server_id')
        
        if user_id in user_processes and server_id in user_processes[user_id]:
            server_info = user_processes[user_id][server_id]
            
            # Check if process is already running
            if server_info['process'] and server_info['process'].poll() is None:
                return jsonify({'success': False, 'error': 'Server is already running'})
            
            # Restart the server
            user_data_dir = f"user_data/{user_id}"
            
            if server_info['type'] == 'convo':
                token_path = os.path.join(user_data_dir, f'tokens_{server_id}.txt')
                message_path = os.path.join(user_data_dir, f'messages_{server_id}.txt')
                
                cmd = [
                    'python', 'convo_runner.py',
                    '--thread_id', server_info['thread_id'],
                    '--hater_name', server_info['hater_name'],
                    '--speed', str(server_info['speed']),
                    '--token_file', token_path,
                    '--message_file', message_path,
                    '--user_id', user_id,
                    '--server_id', server_id
                ]
            elif server_info['type'] == 'fyt':
                token_path = os.path.join(user_data_dir, f'tokens_{server_id}.txt')
                comment_path = os.path.join(user_data_dir, f'comments_{server_id}.txt')
                
                cmd = [
                    'python', 'fyt_runner.py',
                    '--post_id', server_info['post_id'],
                    '--hater_name', server_info['hater_name'],
                    '--speed', str(server_info['speed']),
                    '--token_file', token_path,
                    '--comment_file', comment_path,
                    '--user_id', user_id,
                    '--server_id', server_id
                ]
            else:
                return jsonify({'success': False, 'error': 'Unknown server type'})
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                     text=True, bufsize=1, universal_newlines=True)
            
            server_info['process'] = process
            server_info['status'] = 'running'
            
            # Save to persistent storage
            save_server_data(user_id, server_id, server_info, server_info['type'])
            
            # Start log monitoring thread
            threading.Thread(target=monitor_process_logs, args=(user_id, server_id, process), daemon=True).start()
            
            log_message(user_id, server_id, "Server restarted by user")
            
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Server not found'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def monitor_process_logs(user_id, server_id, process):
    """Monitor process output and log messages"""
    try:
        while process.poll() is None:
            line = process.stdout.readline()
            if line:
                log_message(user_id, server_id, line.strip())
            time.sleep(0.1)
        
        # Process finished
        if user_id in user_processes and server_id in user_processes[user_id]:
            user_processes[user_id][server_id]['status'] = 'stopped'
            log_message(user_id, server_id, "Server process finished")
            
    except Exception as e:
        log_message(user_id, server_id, f"Log monitoring error: {str(e)}")

@app.route('/fetch_groups', methods=['POST'])
def fetch_groups():
    try:
        access_token = request.form.get('access_token', '').strip()
        
        if not access_token:
            return jsonify({'success': False, 'error': 'Access token is required'})
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Fetch conversations/groups
        groups_url = f'https://graph.facebook.com/v15.0/me/conversations'
        params = {
            'access_token': access_token,
            'fields': 'id,name,participants.summary(true),updated_time,can_reply,message_count',
            'limit': 100
        }
        
        response = requests.get(groups_url, params=params, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            
            if 'error' in data:
                return jsonify({'success': False, 'error': data['error'].get('message', 'Unknown error')})
            
            conversations = data.get('data', [])
            
            # Filter groups (more than 2 participants or has custom name)
            groups = []
            for conv in conversations:
                participants_count = 0
                if 'participants' in conv and 'summary' in conv['participants']:
                    participants_count = conv['participants']['summary'].get('total_count', 0)
                
                if participants_count > 2 or (conv.get('name') and not conv.get('name', '').startswith('Unnamed')):
                    groups.append({
                        'id': conv.get('id', ''),
                        'name': conv.get('name', 'Unnamed Group'),
                        'participants': participants_count,
                        'updated_time': conv.get('updated_time', '')
                    })
            
            return jsonify({'success': True, 'groups': groups, 'total': len(groups)})
        
        else:
            return jsonify({'success': False, 'error': f'API returned status code {response.status_code}'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/stop_server', methods=['POST'])
def stop_server():
    try:
        user_id = get_user_id()
        server_id = request.json.get('server_id')
        
        if user_id in user_processes and server_id in user_processes[user_id]:
            process_info = user_processes[user_id][server_id]
            process = process_info['process']
            
            if process and process.poll() is None:  # Process is still running
                kill_process_tree(process.pid)
                process.wait()
            
            process_info['status'] = 'stopped'
            
            # Update persistent storage
            save_server_data(user_id, server_id, process_info, process_info['type'])
            
            log_message(user_id, server_id, "Server stopped by user")
            
            return jsonify({'success': True, 'message': 'Server stopped successfully'})
        else:
            return jsonify({'success': False, 'error': 'Server not found'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/delete_server', methods=['POST'])
def delete_server():
    try:
        user_id = get_user_id()
        server_id = request.json.get('server_id')
        
        if user_id in user_processes and server_id in user_processes[user_id]:
            # Stop the process first
            process_info = user_processes[user_id][server_id]
            process = process_info['process']
            
            if process and process.poll() is None:
                kill_process_tree(process.pid)
                process.wait()
            
            # Clean up files
            user_dir = f"user_data/{user_id}"
            for filename in [f'tokens_{server_id}.txt', f'messages_{server_id}.txt', f'comments_{server_id}.txt']:
                filepath = os.path.join(user_dir, filename)
                if os.path.exists(filepath):
                    os.remove(filepath)
            
            # Remove from storage
            del user_processes[user_id][server_id]
            del process_locks[user_id][server_id]
            
            if user_id in user_logs and server_id in user_logs[user_id]:
                del user_logs[user_id][server_id]
            
            # Remove from persistent storage
            delete_server_data(user_id, server_id)
            
            # Clean up empty user data
            if not user_processes[user_id]:
                del user_processes[user_id]
                del process_locks[user_id]
            
            return jsonify({'success': True, 'message': 'Server deleted successfully'})
        else:
            return jsonify({'success': False, 'error': 'Server not found'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/server_status/<server_id>')
def server_status(server_id):
    user_id = get_user_id()
    
    if user_id in user_processes and server_id in user_processes[user_id]:
        process_info = user_processes[user_id][server_id]
        process = process_info['process']
        
        is_running = process and process.poll() is None
        
        return jsonify({
            'running': is_running,
            'started': process_info['started'].strftime('%H:%M:%S'),
            'type': process_info['type'],
            'status': process_info.get('status', 'unknown')
        })
    
    return jsonify({'running': False, 'status': 'not_found'})

@app.route('/server_logs/<server_id>')
def server_logs(server_id):
    user_id = get_user_id()
    
    if user_id in user_logs and server_id in user_logs[user_id]:
        logs = user_logs[user_id][server_id][-100:]  # Last 100 logs
        return jsonify({'logs': logs})
    
    return jsonify({'logs': []})

@app.route('/get_user_servers')
def get_user_servers():
    user_id = get_user_id()
    
    if user_id not in user_processes:
        return jsonify({'servers': {}})
    
    servers_data = {}
    for server_id, server_info in user_processes[user_id].items():
        process = server_info['process']
        is_running = process and process.poll() is None
        
        servers_data[server_id] = {
            'server_id': server_id,
            'type': server_info['type'],
            'started': server_info['started'].strftime('%H:%M:%S'),
            'running': is_running,
            'status': server_info.get('status', 'unknown')
        }
        
        # Add type-specific info
        if server_info['type'] == 'convo':
            servers_data[server_id].update({
                'thread_id': server_info.get('thread_id', ''),
                'hater_name': server_info.get('hater_name', ''),
                'speed': server_info.get('speed', 0)
            })
        elif server_info['type'] == 'fyt':
            servers_data[server_id].update({
                'post_id': server_info.get('post_id', ''),
                'hater_name': server_info.get('hater_name', ''),
                'speed': server_info.get('speed', 0)
            })
    
    return jsonify({'servers': servers_data})

if __name__ == '__main__':
    # Create user_data directory
    os.makedirs('user_data', exist_ok=True)
    
    # Production configuration
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
