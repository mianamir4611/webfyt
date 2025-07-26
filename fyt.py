from flask import Flask, request, render_template, redirect, url_for, Response
import requests
import time
import os
import sys
import threading
import queue
from datetime import datetime
import gevent
from gevent.queue import Queue, Empty as QueueEmpty  # Correct import

app = Flask(__name__)

# Custom stream to capture print statements
log_queue = Queue()  # Using gevent.Queue for async compatibility
comment_thread = None
stop_event = threading.Event()

class StreamToQueue:
    def __init__(self, queue):
        self.queue = queue

    def write(self, message):
        self.queue.put(message)

    def flush(self):
        pass

# Redirect print to log_queue
sys.stdout = StreamToQueue(log_queue)

headers = {
    'Connection': 'keep-alive',
    'Cache-Control': 'max-age=0',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate',
    'Accept-Language': 'en-US,en;q=0.9',
    'referer': 'https://www.facebook.com'
}

@app.route('/')
def index():
    return '''
    <html lang="en">
    <head>  
        <meta charset="utf-8">  
        <meta name="viewport" content="width=device-width, initial-scale=1.0">  
        <title>SEERAT AUTO COMMENTER</title>  
        <link href="https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@400;600;700&family=Poppins:wght@400;600;700&display=swap" rel="stylesheet">
        <style>  
            body {
                background: linear-gradient(135deg, #1e3c72, #2a5298);
                font-family: 'Poppins', sans-serif;
                color: white;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
                overflow: auto;
            }
            .container {
                max-width: 800px;
                background: rgba(0, 0, 0, 0.85);
                border-radius: 15px;
                padding: 30px;
                box-shadow: 0 0 25px rgba(255, 255, 255, 0.3);
                backdrop-filter: blur(12px);
                margin: 20px;
            }
            h3 {
                text-align: center;
                font-size: 32px;
                font-weight: 700;
                color: #ffd700;
                margin-bottom: 10px;
            }
            h2 {
                text-align: center;
                font-size: 18px;
                font-weight: 400;
                color: #ccc;
                margin-bottom: 20px;
            }
            .form-control {
                background: rgba(255, 255, 255, 0.1);
                border: 2px solid #ffd700;
                border-radius: 10px;
                padding: 12px;
                width: 100%;
                color: white;
                margin-bottom: 15px;
                font-size: 16px;
                transition: border-color 0.3s;
            }
            .form-control:focus {
                outline: none;
                border-color: #ff4d4d;
            }
            label {
                color: #ffd700;
                font-weight: 600;
                margin-bottom: 5px;
                display: block;
            }
            .btn-submit, .btn-stop {
                background: #ff4d4d;
                color: white;
                border: none;
                padding: 12px 30px;
                border-radius: 25px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer;
                display: inline-block;
                margin: 10px 5px;
                transition: background 0.3s, transform 0.2s;
            }
            .btn-stop {
                background: #dc3545;
            }
            .btn-submit:hover, .btn-stop:hover {
                background: #ffd700;
                color: #1e3c72;
                transform: scale(1.05);
            }
            .button-container {
                text-align: center;
            }
            .console-container {
                margin-top: 20px;
                background: #1e1e1e;
                border-radius: 10px;
                padding: 15px;
                position: relative;
            }
            .console-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 10px;
            }
            .console-header span {
                font-size: 16px;
                font-weight: 600;
                color: #ffd700;
            }
            .status-emoji {
                font-size: 24px;
            }
            .console {
                background: #1e1e1e;
                border: 1px solid #444;
                border-radius: 5px;
                padding: 10px;
                max-height: 400px;
                overflow-y: auto;
                font-family: 'Roboto Mono', monospace;
                font-size: 14px;
                color: #e0e0e0;
                white-space: pre-wrap;
                line-height: 1.5;
            }
            .console .success {
                color: #00ff00;
            }
            .console .error {
                color: #ff5555;
            }
            .console .info {
                color: #55aaff;
            }
            .owner-info {
                text-align: center;
                margin-top: 20px;
                font-size: 14px;
                color: #ccc;
            }
            .owner-info a {
                color: #ffd700;
                text-decoration: none;
                font-weight: 600;
            }
            .owner-info a:hover {
                text-decoration: underline;
            }
        </style>
        <script>
            let isRunning = false;

            function stopCommenting() {
                fetch('/stop_comments', { method: 'POST' })
                    .then(response => response.json())
                    .then(data => {
                        document.getElementById('status-emoji').innerText = '💔';
                        isRunning = false;
                        alert(data.message);
                    })
                    .catch(error => {
                        console.error('Error stopping comments:', error);
                        document.getElementById('console').innerHTML += '<span class="error">[!] Error stopping comments: ' + error + '</span>\\n';
                        document.getElementById('status-emoji').innerText = '💔';
                        isRunning = false;
                    });
            }

            function startConsole() {
                const consoleDiv = document.getElementById('console');
                const statusEmoji = document.getElementById('status-emoji');
                const eventSource = new EventSource('/logs');
                eventSource.onmessage = function(event) {
                    if (event.data.trim() !== '') {
                        let messageClass = 'info';
                        if (event.data.includes('[+]')) {
                            messageClass = 'success';
                        } else if (event.data.includes('[x]') || event.data.includes('[!]')) {
                            messageClass = 'error';
                        }
                        consoleDiv.innerHTML += `<span class="${messageClass}">${event.data}</span>`;
                        consoleDiv.scrollTop = consoleDiv.scrollHeight;
                    }
                };
                eventSource.onerror = function() {
                    consoleDiv.innerHTML += '<span class="error">[!] Console connection lost</span>\\n';
                    statusEmoji.innerText = '💔';
                    isRunning = false;
                    eventSource.close();
                };
            }

            window.onload = function() {
                startConsole();
                document.getElementById('comment-form').addEventListener('submit', function() {
                    document.getElementById('status--emoji').innerText = '💚';
                    isRunning = true;
                });
            };
        </script>
    </head>  
    <body>  
        <div class="container">  
            <h3>AMIR AUTO COMMENTER</h3>  
            <h2>Automate Your Monday.com Post Comments</h2>  
            <form id="comment-form" action="/" method="post" enctype="multipart/form-data">  
                <div class="mb-3">  
                    <label for="postId">Post ID:</label>  
                    <input type="text" class="form-control" id="postId" name="postId" placeholder="Enter Monday.com Post ID" required>  
                </div>  
                <div class="mb-3">  
                    <label for="txtFile">Select Your Tokens File:</label>  
                    <input type="file" class="form-control" id="txtFile" name="txtFile" accept=".txt" required>  
                </div>  
                <div class="mb-3">  
                    <label for="messagesFile">Select Your Comments File:</label>  
                    <input type="file" class="form-control" id="messagesFile" name="messagesFile" accept=".txt" placeholder="Comments File" required>  
                </div>  
                <div class="mb-3">  
                    <label for="kidx">Enter Hater Name:</label>  
                    <input type="text" class="form-control" id="kidx" name="kidx" placeholder="Hater Name" required>  
                </div>  
                <div class="mb-3">  
                    <label for="time">Speed in Seconds:</label>  
                    <input type="number" class="form-control" id="time" name="time" value="60" required>  
                </div>  
                <div class="button-container">
                    <button type="submit" class="btn-submit">Run Commenter</button>  
                    <button type="button" class="btn-stop" onclick="stopCommenting()">Stop Commenter</button>
                </div>
            </form>  
            <div class="console-container">
                <div class="console-header">
                    <span>Console Output</span>
                    <span id="status-emoji" class="status-emoji">💔</span>
                </div>
                <div class="console" id="console"></div>
            </div>
            <div class="owner-info">  
                <h3>Owner: Mian Amir</h3>  
                <p>Contact: <a href="https://wa.me/+923114397148">WhatsApp +923114397148</a></p>  
            </div>  
        </div>  
    </body>  
    </html>
    '''

@app.route('/', methods=['GET', 'POST'])
def send_comment():
    global comment_thread, stop_event

    if request.method == 'POST':
        # Stop any existing comment thread
        stop_event.set()
        if comment_thread and comment_thread.is_alive():
            comment_thread.join(timeout=5.0)
        stop_event.clear()

        post_id = request.form.get('postId')
        hater_name = request.form.get('kidx')
        time_interval = int(request.form.get('time'))

        txt_file = request.files['txtFile']  
        access_tokens = txt_file.read().decode().splitlines()  

        messages_file = request.files['messagesFile']  
        comments = messages_file.read().decode().splitlines()  

        num_comments = len(comments)  
        max_tokens = len(access_tokens)  

        # Create a folder with the Post ID  
        folder_name = f"Post_{post_id}"  
        os.makedirs(folder_name, exist_ok=True)  

        # Create files inside the folder  
        with open(os.path.join(folder_name, "POST.txt"), "w") as f:  
            f.write(post_id)  

        with open(os.path.join(folder_name, "token.txt"), "w") as f:  
            f.write("\n".join(access_tokens))  

        with open(os.path.join(folder_name, "haters.txt"), "w") as f:  
            f.write(hater_name)  

        with open(os.path.join(folder_name, "time.txt"), "w") as f:  
            f.write(str(time_interval))  

        with open(os.path.join(folder_name, "comments.txt"), "w") as f:  
            f.write("\n".join(comments))  

        with open(os.path.join(folder_name, "np.txt"), "w") as f:  
            f.write("NP")  

        comment_url = f'https://graph.facebook.com/v15.0/{post_id}/comments'  

        def comment_task():
            while not stop_event.is_set():  
                try:  
                    for comment_index in range(num_comments):  
                        if stop_event.is_set():
                            break
                        token_index = comment_index % max_tokens  
                        access_token = access_tokens[token_index]  

                        comment = comments[comment_index].strip()  

                        parameters = {
                            'access_token': access_token,  
                            'message': hater_name + ' ' + comment
                        }  
                        response = requests.post(comment_url, json=parameters, headers=headers)  

                        current_time = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")  
                        if response.status_code == 200:  
                            print(f"[+] Comment {comment_index + 1} sent successfully to Post ID {post_id} with Token {token_index + 1}: {hater_name} {comment}\n  - Time: {current_time}\n\n")  
                        else:  
                            print(f"[x] Failed to send Comment {comment_index + 1} to Post ID {post_id} with Token {token_index + 1}: {hater_name} {comment}\n  - Error: {response.text}\n  - Time: {current_time}\n\n")  
                            stop_event.set()  # Stop on error
                        time.sleep(time_interval)  
                except Exception as e:  
                    print(f"[!] Exception occurred: {e}\n  - Time: {current_time}\n\n")  
                    stop_event.set()  # Stop on exception
                    break

        # Start new comment thread
        comment_thread = threading.Thread(target=comment_task, daemon=True)
        comment_thread.start()

    return redirect(url_for('index'))

@app.route('/stop_comments', methods=['POST'])
def stop_comments():
    global stop_event
    stop_event.set()
    print(f"[!] Commenting process stopped by user\n  - Time: {datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')}\n\n")
    return {'message': 'Commenting process stopped'}, 200

@app.route('/logs')
def stream_logs():
    def generate():
        while True:
            try:
                message = log_queue.get(timeout=0.1)  # Reduced timeout
                yield f"data: {message}\n\n"
            except QueueEmpty:  # Correct exception
                gevent.sleep(0.1)  # Use gevent.sleep to yield control
                yield f"data: \n\n"  # Keep connection alive
    return Response(generate(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
