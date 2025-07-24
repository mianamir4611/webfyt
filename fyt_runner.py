
import argparse
import requests
import time
from datetime import datetime

def run_fyt_tool(post_id, hater_name, speed, token_file, comment_file, user_id, server_id):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting Post Convo Tool for user {user_id}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Post ID: {post_id}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Speed: {speed} seconds")
    
    # Read tokens and comments
    try:
        with open(token_file, 'r') as f:
            tokens = [line.strip() for line in f.readlines() if line.strip()]
        
        with open(comment_file, 'r') as f:
            comments = [line.strip() for line in f.readlines() if line.strip()]
            
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Loaded {len(tokens)} tokens and {len(comments)} comments")
        
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Error reading files: {e}")
        return
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'referer': 'https://www.facebook.com'
    }
    
    comment_url = f'https://graph.facebook.com/v15.0/{post_id}/comments'
    comment_count = 0
    
    try:
        while True:
            for comment_index, comment in enumerate(comments):
                token_index = comment_index % len(tokens)
                access_token = tokens[token_index]
                
                full_comment = f"{hater_name} {comment}" if hater_name else comment
                
                parameters = {
                    'access_token': access_token,
                    'message': full_comment
                }
                
                try:
                    response = requests.post(comment_url, json=parameters, headers=headers, timeout=30)
                    comment_count += 1
                    
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    if response.ok:
                        print(f"[{timestamp}] ✅ Comment #{comment_count} posted successfully")
                    else:
                        print(f"[{timestamp}] ❌ Comment #{comment_count} failed: {response.text[:100]}")
                        
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
    parser.add_argument('--post_id', required=True)
    parser.add_argument('--hater_name', default='')
    parser.add_argument('--speed', type=int, required=True)
    parser.add_argument('--token_file', required=True)
    parser.add_argument('--comment_file', required=True)
    parser.add_argument('--user_id', required=True)
    parser.add_argument('--server_id', required=True)
    
    args = parser.parse_args()
    
    run_fyt_tool(
        args.post_id,
        args.hater_name,
        args.speed,
        args.token_file,
        args.comment_file,
        args.user_id,
        args.server_id
    )
