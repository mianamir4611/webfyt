
from flask import Flask, request, render_template
import requests

app = Flask(__name__)

headers = {
    'Connection': 'keep-alive',
    'Cache-Control': 'max-age=0',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate',
    'Accept-Language': 'en-US,en;q=0.9',
    'referer': 'www.google.com'
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/fetch_groups', methods=['POST'])
def fetch_groups():
    access_token = request.form.get('access_token')
    if not access_token:
        return render_template('index.html', error="Please provide a valid access token.")

    try:
        # Fetch conversations/groups with detailed information including names and participant counts
        groups_url = f'https://graph.facebook.com/v15.0/me/conversations'
        params = {
            'access_token': access_token,
            'fields': 'id,name,participants.summary(true),updated_time,can_reply,message_count',
            'limit': 100  # Increase limit to get more groups
        }

        response = requests.get(groups_url, params=params, headers=headers)

        if response.status_code == 200:
            data = response.json()

            if 'error' in data:
                error_msg = data['error'].get('message', 'Unknown error occurred')
                return render_template('index.html', error=f"Facebook API Error: {error_msg}")

            conversations = data.get('data', [])

            # Filter out individual conversations and keep only group conversations
            groups = []
            for conv in conversations:
                # A group conversation typically has more than 2 participants or has a name
                participants_count = 0
                if 'participants' in conv and 'summary' in conv['participants']:
                    participants_count = conv['participants']['summary'].get('total_count', 0)

                # Consider it a group if it has more than 2 participants or has a custom name
                if participants_count > 2 or (conv.get('name') and not conv.get('name', '').startswith('Unnamed')):
                    groups.append(conv)

            success_msg = f"Successfully fetched {len(groups)} groups from your Facebook account."
            return render_template('index.html', 
                                 groups=groups, 
                                 access_token=access_token,
                                 success_message=success_msg)

        elif response.status_code == 400:
            return render_template('index.html', 
                                 error="Invalid access token. Please check your token and try again.")
        elif response.status_code == 403:
            return render_template('index.html', 
                                 error="Access denied. Your token may not have the required permissions.")
        else:
            return render_template('index.html', 
                                 error=f"Facebook API returned status code {response.status_code}. Please try again.")

    except requests.exceptions.RequestException as e:
        return render_template('index.html', 
                             error=f"Network error occurred: {str(e)}")
    except Exception as e:
        return render_template('index.html', 
                             error=f"An unexpected error occurred: {str(e)}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
