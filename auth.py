
import hashlib
import json
import os
from datetime import datetime
from functools import wraps
from flask import session, redirect, url_for, request, flash

# Simple file-based user storage
USERS_FILE = 'users.json'

def load_users():
    """Load users from JSON file"""
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_users(users):
    """Save users to JSON file"""
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

def hash_password(password):
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, hashed):
    """Verify password against hash"""
    return hash_password(password) == hashed

def create_user(email, password):
    """Create a new user"""
    users = load_users()
    
    if email in users:
        return False, "User already exists"
    
    users[email] = {
        'password': hash_password(password),
        'created_at': str(datetime.now())
    }
    
    save_users(users)
    return True, "User created successfully"

def authenticate_user(email, password):
    """Authenticate user login"""
    users = load_users()
    
    if email not in users:
        return False, "User not found"
    
    if verify_password(password, users[email]['password']):
        return True, "Login successful"
    
    return False, "Invalid password"

def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def is_authenticated():
    """Check if user is authenticated"""
    return 'user_email' in session

def get_current_user():
    """Get current logged in user email"""
    return session.get('user_email')
