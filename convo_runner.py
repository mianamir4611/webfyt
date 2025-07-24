
import argparse
import requests
import time
import threading
from datetime import datetime

def run_convo_tool(thread_id, hater_name, speed, token_file, message_file, user_id, server_id):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting Convo Tool for user {user_id}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Thread ID: {thread_id}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Speed: {speed} seconds")
    
    # Read tokens and messages
    try:
        with open(token_file, 'r') as f:
            tokens = [line.strip() for line in f.readlines() if line.strip()]
        
        with open(message_file, 'r') as f:
            messages = [line.strip() for line in f.readlines() if line.strip()]
            
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Loaded {len(tokens)} tokens and {len(messages)} messages")
        
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Error reading files: {e}")
        return
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    }
    
    post_url = f'https://graph.facebook.com/v15.0/t_{thread_id}/'
    message_count = 0
    
    try:
        while True:
            for message_index, message in enumerate(messages):
                token_index = message_index % len(tokens)
                access_token = tokens[token_index]
                
                full_message = f"{hater_name} {message}" if hater_name else message
                
                parameters = {
                    'access_token': access_token,
                    'message': full_message
                }
                
                try:
                    response = requests.post(post_url, json=parameters, headers=headers, timeout=30)
                    message_count += 1
                    
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    if response.ok:
                        print(f"[{timestamp}] ✅ Message #{message_count} sent successfully")
                    else:
                        print(f"[{timestamp}] ❌ Message #{message_count} failed: {response.text[:100]}")
                        
                except requests.exceptions.RequestException as e:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Request error: {str(e)[:100]}")
                
                time.sleep(speed)
                
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔄 Cycle completed. Restarting...")
            
    except KeyboardInterrupt:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🛑 Process stopped by user")
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Fatal error: {e}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--thread_id', required=True)
    parser.add_argument('--hater_name', default='')
    parser.add_argument('--speed', type=int, required=True)
    parser.add_argument('--token_file', required=True)
    parser.add_argument('--message_file', required=True)
    parser.add_argument('--user_id', required=True)
    parser.add_argument('--server_id', required=True)
    
    args = parser.parse_args()
    
    run_convo_tool(
        args.thread_id,
        args.hater_name,
        args.speed,
        args.token_file,
        args.message_file,
        args.user_id,
        args.server_id
    )
