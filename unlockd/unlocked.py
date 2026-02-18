import os
import time
import json
import threading
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from flask import Flask, jsonify, send_from_directory, render_template_string, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'super_secret_key_123'
app.config['SESSION_TYPE'] = 'filesystem'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=60, ping_interval=25)

VIDEO_FOLDER = "videos"
IMAGES_FOLDER = "images"
MESSAGES_FILE = "messages.json"
USERS_FILE = "users.json"
DELETED_FOLDER = "deleted"

for folder in [VIDEO_FOLDER, IMAGES_FOLDER, DELETED_FOLDER]:
    os.makedirs(folder, exist_ok=True)

ALLOWED_VIDEOS = {'mp4', 'webm', 'mov', 'avi', 'mkv', 'gif'}
ALLOWED_IMAGES = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'}

active_calls = {}

def init_users():
    if not os.path.exists(USERS_FILE):
        users = {
            "Пример": {
                "password": "Пароль",
                "avatar": "👤",
                "color": "#00a884",
                "theme": "dark"
            }
        }
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False, indent=2)

init_users()

def load_users():
    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def update_user_theme(username, theme):
    users = load_users()
    if username in users:
        users[username]['theme'] = theme
        save_users(users)
        return True
    return False

def load_messages():
    if os.path.exists(MESSAGES_FILE):
        with open(MESSAGES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_message(message):
    messages = load_messages()
    messages.append(message)
    if len(messages) > 500:
        messages = messages[-500:]
    with open(MESSAGES_FILE, 'w', encoding='utf-8') as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)
    return messages

def delete_message(message_id):
    messages = load_messages()
    updated_messages = []
    deleted_info = None
    
    for msg in messages:
        if msg.get('id') == message_id:
            deleted_info = msg
            if msg.get('type') in ['video', 'image']:
                folder = VIDEO_FOLDER if msg['type'] == 'video' else IMAGES_FOLDER
                filepath = os.path.join(folder, msg['filename'])
                if os.path.exists(filepath):
                    shutil.move(filepath, os.path.join(DELETED_FOLDER, msg['filename']))
        else:
            updated_messages.append(msg)
    
    with open(MESSAGES_FILE, 'w', encoding='utf-8') as f:
        json.dump(updated_messages, f, ensure_ascii=False, indent=2)
    
    return deleted_info

HTML_CHAT = """
<!DOCTYPE html>
<html>
<head>
    <title>Unlocked</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🔓</text></svg>">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&display=swap" rel="stylesheet">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <script src="https://cdn.socket.io/4.5.0/socket.io.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        :root {
            --bg-primary: #0b141a;
            --bg-secondary: #202c33;
            --bg-tertiary: #2a3942;
            --text-primary: #e9edef;
            --text-secondary: #8696a0;
            --accent-color: #00a884;
            --message-mine: #005c4b;
            --message-other: #202c33;
            --border-color: #2a3942;
            --hover-color: #3b4a54;
        }
        
        .theme-light {
            --bg-primary: #f0f2f5;
            --bg-secondary: #ffffff;
            --bg-tertiary: #e9edef;
            --text-primary: #111b21;
            --text-secondary: #667781;
            --accent-color: #008069;
            --message-mine: #d9fdd3;
            --message-other: #ffffff;
            --border-color: #e9edef;
            --hover-color: #f5f6f6;
        }
        
        .theme-blue {
            --bg-primary: #1e2a3a;
            --bg-secondary: #2c3e50;
            --bg-tertiary: #34495e;
            --text-primary: #ecf0f1;
            --text-secondary: #bdc3c7;
            --accent-color: #3498db;
            --message-mine: #2980b9;
            --message-other: #34495e;
            --border-color: #3d566e;
            --hover-color: #405b77;
        }
        
        .theme-green {
            --bg-primary: #1a3b2e;
            --bg-secondary: #2d5a45;
            --bg-tertiary: #3a6b55;
            --text-primary: #e8f5e9;
            --text-secondary: #a5d6a7;
            --accent-color: #4caf50;
            --message-mine: #2e7d32;
            --message-other: #3a6b55;
            --border-color: #4e8d6b;
            --hover-color: #4e8d6b;
        }
        
        .theme-purple {
            --bg-primary: #2a1e3a;
            --bg-secondary: #3d2b52;
            --bg-tertiary: #4e3869;
            --text-primary: #f3e5f5;
            --text-secondary: #ce93d8;
            --accent-color: #9c27b0;
            --message-mine: #6a1b9a;
            --message-other: #4e3869;
            --border-color: #62407f;
            --hover-color: #62407f;
        }
        .theme-red {
            --bg-primary: #2d1a1a;
            --bg-secondary: #3d2a2a;
            --bg-tertiary: #4d3a3a;
            --text-primary: #ffe6e6;
            --text-secondary: #ffb3b3;
            --accent-color: #ff4444;
            --message-mine: #cc3333;
            --message-other: #4d3a3a;
            --border-color: #663333;
            --hover-color: #5a4040;
        }
        
        body { 
            font-family: 'Montserrat', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-primary); 
            color: var(--text-primary);
            height: 100vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            transition: background-color 0.3s, color 0.3s;
        }

        .current-user, .dropdown-item, .theme-option, .call-btn, .message, 
        .message-input, .send-btn, .auth-input, .auth-btn, .modal button,
        .attach-option, .mic-permission-btn, .call-control-btn {
            font-family: 'Montserrat', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }

        .message-header, .sender, .time, .message-content, .media-info,
        .download-btn, .notification, .call-status, .call-timer, .status {
            font-family: 'Montserrat', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }

        h2, h3, .dropdown-item span, .theme-option span {
            font-family: 'Montserrat', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            font-weight: 600;
        }

        .message-input::placeholder {
            font-family: 'Montserrat', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }
        
        .header {
            background: var(--bg-secondary);
            padding: 10px 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid var(--border-color);
            flex-shrink: 0;
        }
        
        .header-left {
            display: flex;
            align-items: center;
            gap: 15px;
        }
        
        .current-user {
            display: flex;
            align-items: center;
            gap: 8px;
            background: var(--bg-tertiary);
            padding: 5px 12px;
            border-radius: 20px;
            cursor: pointer;
            transition: background 0.2s;
        }
        
        .current-user:hover {
            background: var(--hover-color);
        }
        
        .user-avatar {
            font-size: 1.2rem;
        }
        
        .user-name {
            font-weight: 500;
        }
        
        .user-dropdown {
            position: absolute;
            top: 60px;
            left: 20px;
            background: var(--bg-secondary);
            border-radius: 8px;
            padding: 8px 0;
            box-shadow: 0 4px 12px rgba(0,0,0,0.5);
            display: none;
            z-index: 1000;
            min-width: 200px;
        }
        
        .user-dropdown.show {
            display: block;
        }
        
        .dropdown-item {
            padding: 12px 20px;
            cursor: pointer;
            transition: background 0.2s;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .dropdown-item:hover {
            background: var(--hover-color);
        }
        
        .status {
            font-size: 0.8rem;
        }
        .status.online { color: var(--accent-color); }
        
        .call-buttons {
            display: flex;
            gap: 10px;
        }
        
        .call-btn {
            background: var(--bg-tertiary);
            border: none;
            color: var(--text-primary);
            width: 40px;
            height: 40px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 1.2rem;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s;
        }
        
        .call-btn:hover {
            background: var(--accent-color);
            transform: scale(1.05);
        }
        
        .call-btn.active {
            background: var(--accent-color);
            animation: pulse 1.5s infinite;
        }
        
        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.1); }
            100% { transform: scale(1); }
        }
        
        .call-panel {
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: var(--bg-secondary);
            border-radius: 16px;
            padding: 30px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.5);
            z-index: 2000;
            text-align: center;
            min-width: 300px;
            display: none;
        }
        
        .call-panel.active {
            display: block;
        }
        
        .call-avatar {
            font-size: 4rem;
            margin-bottom: 20px;
        }
        
        .call-status {
            margin: 20px 0;
            color: var(--text-secondary);
        }
        
        .call-timer {
            font-size: 1.5rem;
            margin: 20px 0;
            font-family: monospace;
        }
        
        .call-controls {
            display: flex;
            gap: 15px;
            justify-content: center;
        }
        
        .call-control-btn {
            width: 50px;
            height: 50px;
            border-radius: 50%;
            border: none;
            cursor: pointer;
            font-size: 1.2rem;
            transition: all 0.2s;
        }
        
        .call-control-btn.answer {
            background: var(--accent-color);
            color: white;
        }
        
        .call-control-btn.hangup {
            background: #ff5252;
            color: white;
        }
        
        .call-control-btn.mute {
            background: var(--bg-tertiary);
            color: var(--text-primary);
        }
        
        .call-control-btn.mute.active {
            background: #ff5252;
        }
        
        .call-control-btn:hover {
            transform: scale(1.1);
        }
        
        .theme-dropdown {
            position: absolute;
            top: 60px;
            right: 20px;
            background: var(--bg-secondary);
            border-radius: 8px;
            padding: 8px 0;
            box-shadow: 0 4px 12px rgba(0,0,0,0.5);
            display: none;
            z-index: 1000;
            min-width: 150px;
        }
        
        .theme-dropdown.show {
            display: block;
        }
        
        .theme-option {
            padding: 10px 20px;
            cursor: pointer;
            transition: background 0.2s;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .theme-option:hover {
            background: var(--hover-color);
        }
        
        .messages-container {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            background: var(--bg-primary);
            scroll-behavior: smooth;
        }
        
        .messages {
            display: flex;
            flex-direction: column;
            gap: 8px;
            min-height: min-content;
        }
        
        .message {
            max-width: 65%;
            padding: 8px 12px;
            border-radius: 7px;
            position: relative;
            word-wrap: break-word;
            animation: fadeIn 0.2s ease;
            transition: opacity 0.3s;
        }
        
        .message.deleted-message {
            opacity: 0.5;
            background: var(--bg-tertiary) !important;
            font-style: italic;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(5px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .message.my-message {
            align-self: flex-end;
            background: var(--message-mine);
        }
        .message.other-message {
            align-self: flex-start;
            background: var(--message-other);
        }
        
        .message-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 4px;
            font-size: 0.7rem;
            position: relative;
        }
        
        .sender-info {
            display: flex;
            align-items: center;
            gap: 4px;
        }
        
        .sender-avatar {
            font-size: 0.9rem;
        }
        
        .sender {
            font-weight: 600;
        }
        
        .message-actions {
            position: relative;
        }
        
        .actions-btn {
            background: none;
            border: none;
            color: var(--text-secondary);
            cursor: pointer;
            padding: 2px 5px;
            font-size: 1rem;
            opacity: 0.7;
            transition: opacity 0.2s;
        }
        
        .actions-btn:hover {
            opacity: 1;
            color: var(--text-primary);
        }
        
        .actions-dropdown {
            position: absolute;
            right: 0;
            top: 20px;
            background: var(--bg-tertiary);
            border-radius: 4px;
            padding: 4px 0;
            display: none;
            z-index: 100;
            min-width: 120px;
        }
        
        .message-actions:hover .actions-dropdown {
            display: block;
        }
        
        .action-item {
            padding: 8px 12px;
            cursor: pointer;
            font-size: 0.8rem;
            transition: background 0.2s;
            white-space: nowrap;
        }
        
        .action-item:hover {
            background: var(--hover-color);
        }
        
        .action-item.delete {
            color: #ff5252;
        }
        
        .time {
            color: var(--text-secondary);
        }
        
        .message-content {
            font-size: 0.95rem;
            line-height: 1.4;
        }
        
        .media-message {
            margin-top: 5px;
            border-radius: 7px;
            overflow: hidden;
            background: #111;
            max-width: 100%;
        }
        
        .media-message img {
            max-width: 100%;
            max-height: 300px;
            display: block;
            cursor: pointer;
            transition: opacity 0.2s;
        }
        
        .media-message img:hover {
            opacity: 0.9;
        }
        
        .media-message video {
            max-width: 100%;
            max-height: 300px;
            display: block;
        }
        
        .media-info {
            padding: 8px;
            background: var(--bg-tertiary);
            font-size: 0.8rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-top: 1px solid var(--border-color);
        }
        
        .download-btn {
            color: var(--accent-color);
            text-decoration: none;
            padding: 4px 8px;
            border: 1px solid var(--accent-color);
            border-radius: 4px;
            font-size: 0.7rem;
            transition: all 0.2s;
        }
        
        .download-btn:hover {
            background: var(--accent-color);
            color: var(--bg-primary);
        }
        
        .gallery-modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.95);
            z-index: 3000;
            justify-content: center;
            align-items: center;
            cursor: pointer;
        }
        
        .gallery-modal.active {
            display: flex;
        }
        
        .gallery-modal img {
            max-width: 90%;
            max-height: 90%;
            object-fit: contain;
        }
        
        .gallery-close {
            position: absolute;
            top: 20px;
            right: 20px;
            color: white;
            font-size: 2rem;
            cursor: pointer;
            width: 40px;
            height: 40px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: rgba(0,0,0,0.5);
            border-radius: 50%;
        }
        
        .mic-permission-modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.9);
            z-index: 5000;
            justify-content: center;
            align-items: center;
        }
        
        .mic-permission-modal.active {
            display: flex;
        }
        
        .mic-permission-content {
            background: var(--bg-secondary);
            padding: 40px;
            border-radius: 16px;
            max-width: 450px;
            width: 90%;
            text-align: center;
        }
        
        .mic-permission-content h3 {
            margin-bottom: 20px;
            font-size: 1.5rem;
        }
        
        .mic-permission-content p {
            margin: 20px 0;
            color: var(--text-secondary);
            line-height: 1.5;
        }
        
        .mic-icon {
            font-size: 4rem;
            margin: 20px 0;
            animation: pulse 1.5s infinite;
        }
        
        .browser-warning {
            background: rgba(255, 193, 7, 0.2);
            border-left: 4px solid #ffc107;
            padding: 12px;
            margin: 20px 0;
            text-align: left;
            font-size: 0.9rem;
            color: var(--text-secondary);
            border-radius: 4px;
        }
        
        .mic-permission-buttons {
            display: flex;
            gap: 15px;
            justify-content: center;
            margin-top: 30px;
        }
        
        .mic-permission-btn {
            padding: 12px 30px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 1rem;
            transition: all 0.2s;
        }
        
        .mic-permission-btn.allow {
            background: var(--accent-color);
            color: white;
        }
        
        .mic-permission-btn.allow:hover {
            filter: brightness(0.9);
        }
        
        .mic-permission-btn.deny {
            background: var(--bg-tertiary);
            color: var(--text-primary);
        }
        
        .mic-permission-btn.deny:hover {
            background: #ff5252;
        }
        
        .auth-modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.9);
            z-index: 4000;
            justify-content: center;
            align-items: center;
        }
        
        .auth-modal.active {
            display: flex;
        }
        
        .auth-content {
            background: var(--bg-secondary);
            padding: 40px;
            border-radius: 12px;
            max-width: 400px;
            width: 90%;
        }
        
        .auth-content h2 {
            margin-bottom: 30px;
            text-align: center;
        }
        
        .auth-input {
            width: 100%;
            padding: 15px;
            margin: 10px 0;
            background: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            color: var(--text-primary);
            font-size: 1rem;
        }
        
        .auth-input:focus {
            outline: 2px solid var(--accent-color);
        }
        
        .auth-error {
            color: #ff5252;
            margin: 10px 0;
            font-size: 0.9rem;
        }
        
        .auth-buttons {
            display: flex;
            gap: 10px;
            margin-top: 20px;
        }
        
        .auth-btn {
            flex: 1;
            padding: 12px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 1rem;
            transition: background 0.2s;
        }
        
        .auth-btn.primary {
            background: var(--accent-color);
            color: white;
        }
        
        .auth-btn.primary:hover {
            background: var(--accent-color);
            filter: brightness(0.9);
        }
        
        .auth-btn.secondary {
            background: var(--bg-tertiary);
            color: var(--text-primary);
        }
        
        .auth-btn.secondary:hover {
            background: var(--hover-color);
        }
        
        .notification {
            position: fixed;
            top: 20px;
            right: 20px;
            background: var(--accent-color);
            color: white;
            padding: 12px 20px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            z-index: 1000;
            animation: slideIn 0.3s ease;
        }
        
        .notification.delete {
            background: #ff5252;
        }
        
        .notification.call {
            background: var(--accent-color);
        }
        
        @keyframes slideIn {
            from { transform: translateX(100%); }
            to { transform: translateX(0); }
        }
        
        .input-area {
            background: var(--bg-secondary);
            padding: 15px 20px;
            display: flex;
            gap: 8px;
            align-items: center;
            flex-shrink: 0;
            border-top: 1px solid var(--border-color);
        }
        
        .attach-menu {
            position: relative;
        }
        
        .attach-btn {
            background: none;
            border: none;
            color: var(--text-secondary);
            font-size: 1.5rem;
            cursor: pointer;
            padding: 8px;
            transition: color 0.2s;
            width: 45px;
            height: 45px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .attach-btn:hover {
            color: var(--accent-color);
        }
        
        .attach-btn.active {
            color: var(--accent-color);
        }
        
        .attach-dropdown {
            position: absolute;
            bottom: 100%;
            left: 0;
            background: var(--bg-secondary);
            border-radius: 8px;
            padding: 8px 0;
            margin-bottom: 10px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.5);
            z-index: 100;
            display: none;
            min-width: 180px;
        }
        
        .attach-dropdown.show {
            display: block;
        }
        
        .attach-option {
            padding: 12px 25px;
            cursor: pointer;
            white-space: nowrap;
            transition: background 0.2s;
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 1rem;
        }
        
        .attach-option:hover {
            background: var(--hover-color);
        }
        
        .attach-option span:first-child {
            font-size: 1.2rem;
        }
        
        .message-input {
            flex: 1;
            background: var(--bg-tertiary);
            border: none;
            border-radius: 8px;
            padding: 12px 15px;
            color: var(--text-primary);
            font-size: 0.95rem;
        }
        
        .message-input::placeholder {
            color: var(--text-secondary);
        }
        
        .message-input:focus {
            outline: 2px solid var(--accent-color);
        }
        
        .send-btn {
            background: var(--accent-color);
            border: none;
            color: white;
            border-radius: 50%;
            width: 45px;
            height: 45px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.2rem;
            cursor: pointer;
            transition: background 0.2s;
        }
        
        .send-btn:hover {
            background: var(--accent-color);
            filter: brightness(0.9);
        }
        
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.8);
            z-index: 2000;
            justify-content: center;
            align-items: center;
        }
        
        .modal.active {
            display: flex;
        }
        
        .modal-content {
            background: var(--bg-secondary);
            padding: 30px;
            border-radius: 12px;
            max-width: 500px;
            width: 90%;
        }
        
        .modal h3 {
            margin-bottom: 20px;
        }
        
        .modal input[type=file] {
            margin: 20px 0;
            color: var(--text-primary);
            width: 100%;
        }
        
        .modal-buttons {
            display: flex;
            gap: 10px;
            justify-content: flex-end;
        }
        
        .modal button {
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
        }
        
        .modal .cancel {
            background: var(--bg-tertiary);
            color: var(--text-primary);
        }
        
        .modal .send {
            background: var(--accent-color);
            color: white;
        }
    </style>
</head>
<body class="theme-dark">
    <div class="header">
        <div class="header-left">
            <div class="current-user" onclick="toggleUserDropdown()">
                <span class="user-avatar" id="currentAvatar">👤</span>
                <span class="user-name" id="currentUsername">Загрузка...</span>
                <span style="margin-left:5px;">▼</span>
            </div>
            <div class="status online" id="status">● В сети</div>
        </div>
        
        <div class="call-buttons">
            <button class="call-btn" onclick="toggleThemeMenu()" title="Сменить тему">🎨</button>
            <button class="call-btn" onclick="checkMicSupport()" title="Позвонить">📞</button>
        </div>
        
        <div class="user-dropdown" id="userDropdown">
            <div class="dropdown-item" onclick="switchAccount()">
                <span>🔄</span> Сменить аккаунт
            </div>
            <div class="dropdown-item" onclick="logout()">
                <span>🚪</span> Выйти
            </div>
        </div>
        
        <div class="theme-dropdown" id="themeDropdown">
            <div class="theme-option" onclick="changeTheme('dark')">
                <span>🌙</span> Темная
            </div>
            <div class="theme-option" onclick="changeTheme('light')">
                <span>☀️</span> Светлая
            </div>
            <div class="theme-option" onclick="changeTheme('blue')">
                <span>🔵</span> Синяя
            </div>
            <div class="theme-option" onclick="changeTheme('green')">
                <span>🟢</span> Зеленая
            </div>
            <div class="theme-option" onclick="changeTheme('purple')">
                <span>🟣</span> Фиолетовая
            </div>
            <div class="theme-option" onclick="changeTheme('red')">
                <span>🔴</span> Красная
            </div>
        </div>
    </div>
    
    <div class="call-panel" id="callPanel">
        <div class="call-avatar" id="callAvatar">👥</div>
        <h2 id="callWith">Звонок с другом</h2>
        <div class="call-status" id="callStatus">Ожидание...</div>
        <div class="call-timer" id="callTimer">00:00</div>
        <div class="call-controls">
            <button class="call-control-btn mute" id="muteBtn" onclick="toggleMute()" title="Отключить микрофон">🎤</button>
            <button class="call-control-btn hangup" onclick="endCall()" title="Завершить">📞</button>
        </div>
    </div>
    
    <div class="call-panel" id="incomingCallPanel">
        <div class="call-avatar">📞</div>
        <h2 id="incomingCaller">Входящий звонок</h2>
        <div class="call-status">Кто-то звонит...</div>
        <div class="call-controls">
            <button class="call-control-btn answer" onclick="answerCall()">📞 Ответить</button>
            <button class="call-control-btn hangup" onclick="rejectCall()">❌ Отклонить</button>
        </div>
    </div>
    
    <div class="mic-permission-modal" id="micPermissionModal">
        <div class="mic-permission-content">
            <div class="mic-icon">🎤</div>
            <h3>Разрешите доступ к микрофону</h3>
            <p>Для звонков нужен доступ к вашему микрофону. Браузер попросит разрешение.</p>
            
            <div class="browser-warning" id="browserWarning" style="display: none;">
                <strong>⚠️ Внимание!</strong><br>
                <span id="warningText"></span>
            </div>
            
            <div class="mic-permission-buttons">
                <button class="mic-permission-btn allow" onclick="requestMicPermission()">Разрешить</button>
                <button class="mic-permission-btn deny" onclick="closeMicPermissionModal()">Отмена</button>
            </div>
        </div>
    </div>
    
    <div class="messages-container" id="messagesContainer">
        <div class="messages" id="messages"></div>
    </div>
    
    <div class="input-area">
        <div class="attach-menu">
            <button class="attach-btn" id="attachBtn" onclick="toggleAttachMenu()">📎</button>
            <div class="attach-dropdown" id="attachDropdown">
                <div class="attach-option" onclick="showUploadModal('image')">
                    <span>🖼️</span> Отправить картинку
                </div>
                <div class="attach-option" onclick="showUploadModal('video')">
                    <span>🎬</span> Отправить видео
                </div>
            </div>
        </div>
        
        <input type="text" class="message-input" id="messageInput" 
               placeholder="Сообщение..." onkeypress="if(event.key==='Enter') sendMessage()">
        <button class="send-btn" onclick="sendMessage()">➤</button>
    </div>
    
    <div class="modal" id="uploadModal">
        <div class="modal-content">
            <h3 id="modalTitle">📹 Отправить видео</h3>
            <input type="file" id="uploadFile" accept="">
            <div class="modal-buttons">
                <button class="cancel" onclick="hideUploadModal()">Отмена</button>
                <button class="send" onclick="uploadMedia()">Отправить</button>
            </div>
        </div>
    </div>
    
    <div class="auth-modal" id="authModal">
        <div class="auth-content">
            <h2>🔐 Вход в Unlocked</h2>
            <input type="text" class="auth-input" id="loginInput" placeholder="Логин" autocomplete="off">
            <input type="password" class="auth-input" id="passwordInput" placeholder="Пароль">
            <div class="auth-error" id="authError"></div>
            <div class="auth-buttons">
                <button class="auth-btn primary" onclick="doLogin()">Войти</button>
                <button class="auth-btn secondary" onclick="cancelLogin()">Отмена</button>
            </div>
        </div>
    </div>
    
    <div class="gallery-modal" id="galleryModal" onclick="closeGallery()">
        <span class="gallery-close">&times;</span>
        <img id="galleryImage" src="">
    </div>
    
    <div id="notificationContainer"></div>

    <script>
        const socket = io();
        let currentUser = null;
        let users = null;
        let currentUploadType = 'video';
        let peerConnection = null;
        let localStream = null;
        let remoteStream = null;
        let callActive = false;
        let callTimer = null;
        let callSeconds = 0;
        let isMuted = false;
        let currentCallId = null;
        let micPermissionGranted = false;
        
        const configuration = {
            iceServers: [
                { urls: 'stun:stun.l.google.com:19302' },
                { urls: 'stun:stun1.l.google.com:19302' }
            ]
        };
        
        if (!navigator.mediaDevices) {
            navigator.mediaDevices = {};
        }
        
        if (!navigator.mediaDevices.getUserMedia) {
            navigator.mediaDevices.getUserMedia = function(constraints) {
                if (navigator.mediaDevices.webkitGetUserMedia) {
                    return navigator.mediaDevices.webkitGetUserMedia(constraints);
                }
                
                var getUserMedia = navigator.webkitGetUserMedia || navigator.mozGetUserMedia || navigator.msGetUserMedia;
                
                if (!getUserMedia) {
                    return Promise.reject(new Error('getUserMedia не поддерживается этим браузером'));
                }
                
                return new Promise(function(resolve, reject) {
                    getUserMedia.call(navigator, constraints, resolve, reject);
                });
            };
        }
        
        async function detectBrave() {
            if (navigator.brave && typeof navigator.brave.isBrave === 'function') {
                try {
                    return await navigator.brave.isBrave();
                } catch (e) {
                    return false;
                }
            }
            return false;
        }
        
        async function loadUsers() {
            const response = await fetch('/api/users');
            users = await response.json();
        }
        
        function toggleUserDropdown() {
            document.getElementById('userDropdown').classList.toggle('show');
        }
        
        function toggleThemeMenu() {
            document.getElementById('themeDropdown').classList.toggle('show');
        }
        
        async function changeTheme(theme) {
            document.body.className = `theme-${theme}`;
            document.getElementById('themeDropdown').classList.remove('show');
            
            if (currentUser) {
                await fetch('/api/theme', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        username: currentUser.username,
                        theme: theme
                    })
                });
            }
        }
        
        function toggleAttachMenu() {
            document.getElementById('attachDropdown').classList.toggle('show');
            document.getElementById('attachBtn').classList.toggle('active');
        }
        
        window.onclick = function(event) {
            if (!event.target.closest('.current-user')) {
                document.getElementById('userDropdown').classList.remove('show');
            }
            if (!event.target.closest('.call-btn')) {
                document.getElementById('themeDropdown').classList.remove('show');
            }
            if (!event.target.closest('.attach-menu')) {
                document.getElementById('attachDropdown').classList.remove('show');
                document.getElementById('attachBtn').classList.remove('active');
            }
        };
        
        async function checkMicSupport() {
            if (!currentUser) {
                showAuthModal();
                return;
            }
            
            const isBrave = await detectBrave();
            const isChrome = /Chrome/.test(navigator.userAgent) && /Google Inc/.test(navigator.vendor) && !isBrave;
            const isFirefox = navigator.userAgent.toLowerCase().indexOf('firefox') > -1;
            const isEdge = navigator.userAgent.indexOf("Edg") > -1;
            
            let browserName = 'Unknown';
            if (isBrave) browserName = 'Brave';
            else if (isChrome) browserName = 'Chrome';
            else if (isFirefox) browserName = 'Firefox';
            else if (isEdge) browserName = 'Edge';
            
            console.log('Браузер:', browserName);
            console.log('mediaDevices:', navigator.mediaDevices);
            console.log('getUserMedia:', navigator.mediaDevices ? navigator.mediaDevices.getUserMedia : 'undefined');
            
            const warningDiv = document.getElementById('browserWarning');
            const warningText = document.getElementById('warningText');
            
            if (location.protocol !== 'https:' && location.hostname !== 'localhost' && !location.hostname.match(/^192\\.168\\.|^10\\.|^172\\.(1[6-9]|2[0-9]|3[0-1])\\./)) {
                warningDiv.style.display = 'block';
                warningText.innerHTML = 'Сайт открыт по HTTP. Микрофон может не работать. Используйте Firefox или включите HTTPS.';
            } else {
                warningDiv.style.display = 'none';
            }
            
            if (!navigator.mediaDevices) {
                showNotification('❌ Ошибка', 
                    'navigator.mediaDevices не найден. Попробуйте Firefox или включите WebRTC в настройках браузера');
                return;
            }
            
            if (typeof navigator.mediaDevices.getUserMedia !== 'function') {
                showNotification('❌ Ошибка', 
                    'getUserMedia не поддерживается. Обновите браузер или попробуйте Firefox');
                return;
            }
            
            showMicPermissionModal();
        }
        
        function showMicPermissionModal() {
            document.getElementById('micPermissionModal').classList.add('active');
        }
        
        function closeMicPermissionModal() {
            document.getElementById('micPermissionModal').classList.remove('active');
        }
        
        async function requestMicPermission() {
            closeMicPermissionModal();
            
            try {
                showNotification('🎤 Запрашиваем доступ...', 'Разрешите использование микрофона');
                
                if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                    throw new Error('getUserMedia не поддерживается');
                }
                
                const stream = await navigator.mediaDevices.getUserMedia({ 
                    audio: {
                        echoCancellation: true,
                        noiseSuppression: true,
                        autoGainControl: true,
                        channelCount: 1,
                        sampleRate: 48000,
                        sampleSize: 16
                    } 
                });
                
                micPermissionGranted = true;
                localStream = stream;
                
                showNotification('✅ Микрофон доступен', 'Начинаем звонок');
                
                startCallWithStream();
                
            } catch (err) {
                console.error('Ошибка доступа к микрофону:', err);
                micPermissionGranted = false;
                
                let errorMessage = 'Неизвестная ошибка';
                let errorTitle = '❌ Ошибка микрофона';
                
                if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
                    errorTitle = '❌ Доступ запрещен';
                    errorMessage = 'Разрешите доступ в настройках браузера';
                } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
                    errorTitle = '❌ Микрофон не найден';
                    errorMessage = 'Подключите микрофон';
                } else if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
                    errorTitle = '❌ Микрофон занят';
                    errorMessage = 'Закройте другие программы, использующие микрофон';
                } else if (err.name === 'OverconstrainedError') {
                    errorTitle = '❌ Неподдерживаемые параметры';
                    errorMessage = 'Микрофон не поддерживает требуемые настройки';
                } else if (err.name === 'TypeError') {
                    errorTitle = '❌ Ошибка браузера';
                    errorMessage = 'Сайт должен открываться через HTTPS или localhost';
                } else if (err.message) {
                    errorMessage = err.message;
                }
                
                showNotification(errorTitle, errorMessage);
            }
        }
        
        async function startCallWithStream() {
            try {
                peerConnection = new RTCPeerConnection(configuration);
                
                localStream.getTracks().forEach(track => {
                    peerConnection.addTrack(track, localStream);
                });
                
                peerConnection.ontrack = (event) => {
                    remoteStream = event.streams[0];
                };
                
                peerConnection.onicecandidate = (event) => {
                    if (event.candidate) {
                        socket.emit('call_ice_candidate', {
                            callId: currentCallId,
                            candidate: event.candidate
                        });
                    }
                };
                
                peerConnection.oniceconnectionstatechange = () => {
                    console.log('ICE состояние:', peerConnection.iceConnectionState);
                };
                
                const offer = await peerConnection.createOffer();
                await peerConnection.setLocalDescription(offer);
                
                currentCallId = Date.now().toString();
                
                socket.emit('call_offer', {
                    callId: currentCallId,
                    offer: offer,
                    from: currentUser.username,
                    to: currentUser.username === 'ты' ? 'друг' : 'ты'
                });
                
                showCallPanel('исходящий');
                startCallTimer();
                callActive = true;
                
            } catch (err) {
                console.error('Ошибка звонка:', err);
                showNotification('❌ Ошибка', 'Не удалось начать звонок: ' + err.message);
            }
        }
        
        async function answerCall() {
            document.getElementById('incomingCallPanel').classList.remove('active');
            
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ 
                    audio: {
                        echoCancellation: true,
                        noiseSuppression: true,
                        autoGainControl: true
                    } 
                });
                localStream = stream;
                
                peerConnection = new RTCPeerConnection(configuration);
                
                localStream.getTracks().forEach(track => {
                    peerConnection.addTrack(track, localStream);
                });
                
                peerConnection.ontrack = (event) => {
                    remoteStream = event.streams[0];
                };
                
                peerConnection.onicecandidate = (event) => {
                    if (event.candidate) {
                        socket.emit('call_ice_candidate', {
                            callId: currentCallId,
                            candidate: event.candidate
                        });
                    }
                };
                
                await peerConnection.setRemoteDescription(new RTCSessionDescription(window.pendingOffer));
                
                const answer = await peerConnection.createAnswer();
                await peerConnection.setLocalDescription(answer);
                
                socket.emit('call_answer', {
                    callId: currentCallId,
                    answer: answer
                });
                
                showCallPanel('активный');
                startCallTimer();
                callActive = true;
                
            } catch (err) {
                console.error('Ошибка ответа:', err);
                showNotification('❌ Ошибка', 'Не удалось ответить на звонок: ' + err.message);
            }
        }
        
        function rejectCall() {
            document.getElementById('incomingCallPanel').classList.remove('active');
            socket.emit('call_reject', { callId: currentCallId });
            showNotification('📞 Звонок отклонен', '', 'call');
        }
        
        function endCall() {
            if (peerConnection) {
                peerConnection.close();
                peerConnection = null;
            }
            
            if (localStream) {
                localStream.getTracks().forEach(track => track.stop());
                localStream = null;
            }
            
            if (callTimer) {
                clearInterval(callTimer);
                callTimer = null;
            }
            
            callActive = false;
            callSeconds = 0;
            micPermissionGranted = false;
            
            document.getElementById('callPanel').classList.remove('active');
            
            if (currentCallId) {
                socket.emit('call_end', { callId: currentCallId });
                currentCallId = null;
            }
        }
        
        function toggleMute() {
            if (localStream) {
                isMuted = !isMuted;
                localStream.getAudioTracks().forEach(track => {
                    track.enabled = !isMuted;
                });
                document.getElementById('muteBtn').classList.toggle('active', isMuted);
                document.getElementById('muteBtn').textContent = isMuted ? '🔇' : '🎤';
            }
        }
        
        function showCallPanel(type) {
            const panel = document.getElementById('callPanel');
            const callWith = document.getElementById('callWith');
            const status = document.getElementById('callStatus');
            
            if (type === 'исходящий') {
                callWith.textContent = `Звонок ${currentUser.username === 'ты' ? 'другу' : 'тебе'}`;
                status.textContent = 'Вызов...';
            } else if (type === 'активный') {
                callWith.textContent = `Разговор с ${currentUser.username === 'ты' ? 'другом' : 'тобой'}`;
                status.textContent = 'Разговор';
            }
            
            panel.classList.add('active');
        }
        
        function startCallTimer() {
            callSeconds = 0;
            updateCallTimer();
            callTimer = setInterval(updateCallTimer, 1000);
        }
        
        function updateCallTimer() {
            const minutes = Math.floor(callSeconds / 60);
            const seconds = callSeconds % 60;
            document.getElementById('callTimer').textContent = 
                `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
            callSeconds++;
        }
        
        function showNotification(title, message, type = 'info') {
            const container = document.getElementById('notificationContainer');
            const notif = document.createElement('div');
            notif.className = `notification ${type}`;
            notif.innerHTML = `<strong>${title}</strong><br>${message}`;
            container.appendChild(notif);
            
            setTimeout(() => {
                notif.remove();
            }, 3000);
        }
        
        function switchAccount() {
            document.getElementById('userDropdown').classList.remove('show');
            localStorage.removeItem('username');
            localStorage.removeItem('password');
            showAuthModal();
        }
        
        function logout() {
            document.getElementById('userDropdown').classList.remove('show');
            localStorage.removeItem('username');
            localStorage.removeItem('password');
            window.location.reload();
        }
        
        function showAuthModal() {
            document.getElementById('authModal').classList.add('active');
            document.getElementById('loginInput').focus();
        }
        
        function hideAuthModal() {
            document.getElementById('authModal').classList.remove('active');
        }
        
        function cancelLogin() {
            hideAuthModal();
            if (!currentUser) {
                const lastUser = localStorage.getItem('lastUser');
                if (lastUser) {
                    attemptLogin(lastUser, localStorage.getItem('lastPass') || '');
                }
            }
        }
        
        async function attemptLogin(username, password) {
            const response = await fetch('/api/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username, password})
            });
            
            const result = await response.json();
            
            if (result.success) {
                currentUser = {
                    username: username,
                    avatar: result.avatar,
                    color: result.color
                };
                
                localStorage.setItem('username', username);
                localStorage.setItem('password', password);
                localStorage.setItem('lastUser', username);
                localStorage.setItem('lastPass', password);
                
                document.getElementById('currentUsername').textContent = username;
                document.getElementById('currentAvatar').textContent = result.avatar;
                
                if (result.theme) {
                    changeTheme(result.theme);
                }
                
                hideAuthModal();
                loadMessages();
                
                socket.emit('user_online', username);
            } else {
                document.getElementById('authError').textContent = 'Неверный логин или пароль';
            }
        }
        
        function doLogin() {
            const username = document.getElementById('loginInput').value.trim();
            const password = document.getElementById('passwordInput').value.trim();
            
            if (username && password) {
                attemptLogin(username, password);
            }
        }
        
        function scrollToBottom(force = false) {
            const container = document.getElementById('messagesContainer');
            const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 100;
            
            if (force || isNearBottom) {
                setTimeout(() => {
                    container.scrollTop = container.scrollHeight;
                }, 50);
            }
        }
        
        async function loadMessages() {
            const response = await fetch('/api/messages');
            const messages = await response.json();
            displayMessages(messages);
        }
        
        function displayMessages(messages) {
            const container = document.getElementById('messages');
            container.innerHTML = '';
            
            messages.forEach(msg => {
                if (msg.deleted && msg.sender !== currentUser?.username) {
                    return;
                }
                
                const messageDiv = document.createElement('div');
                const isMyMessage = msg.sender === currentUser?.username;
                messageDiv.className = `message ${isMyMessage ? 'my-message' : 'other-message'}`;
                
                if (msg.deleted) {
                    messageDiv.classList.add('deleted-message');
                }
                
                const time = new Date(msg.timestamp).toLocaleTimeString('ru-RU', {
                    hour: '2-digit', 
                    minute: '2-digit'
                });
                
                let content = '';
                
                if (msg.deleted) {
                    content = '<div class="message-content"><em>Сообщение удалено</em></div>';
                } else if (msg.type === 'text') {
                    content = `<div class="message-content">${msg.content}</div>`;
                } else if (msg.type === 'video') {
                    content = `
                        <div class="media-message">
                            <video controls>
                                <source src="/media/videos/${msg.filename}" type="video/mp4">
                            </video>
                            <div class="media-info">
                                <span>📹 ${msg.filename}</span>
                                <a href="/media/videos/${msg.filename}" download class="download-btn">⬇ Скачать</a>
                            </div>
                        </div>
                    `;
                } else if (msg.type === 'image') {
                    content = `
                        <div class="media-message">
                            <img src="/media/images/${msg.filename}" 
                                 onclick="openGallery('${msg.filename}')"
                                 alt="${msg.filename}">
                            <div class="media-info">
                                <span>🖼️ ${msg.filename}</span>
                                <a href="/media/images/${msg.filename}" download class="download-btn">⬇ Скачать</a>
                            </div>
                        </div>
                    `;
                }
                
                const userAvatar = users?.[msg.sender]?.avatar || '👤';
                const senderDisplay = msg.sender === currentUser?.username ? 'Вы' : msg.sender;
                
                messageDiv.innerHTML = `
                    <div class="message-header">
                        <div class="sender-info">
                            <span class="sender-avatar">${userAvatar}</span>
                            <span class="sender">${senderDisplay}</span>
                        </div>
                        <div class="message-actions">
                            <span class="time">${time}</span>
                            ${isMyMessage && !msg.deleted ? `
                                <span class="actions-btn">⋯</span>
                                <div class="actions-dropdown">
                                    <div class="action-item delete" onclick="deleteMessage('${msg.id}')">
                                        🗑️ Удалить
                                    </div>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                    ${content}
                `;
                
                container.appendChild(messageDiv);
            });
            
            scrollToBottom(true);
        }
        
        async function deleteMessage(messageId) {
            if (!confirm('Удалить сообщение?')) return;
            
            const response = await fetch('/api/delete-message', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    message_id: messageId,
                    username: currentUser?.username
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                socket.emit('message_deleted', {
                    message_id: messageId,
                    sender: currentUser?.username
                });
                
                showNotification('✅ Сообщение удалено', '', 'delete');
            }
        }
        
        function sendMessage() {
            if (!currentUser) {
                showAuthModal();
                return;
            }
            
            const input = document.getElementById('messageInput');
            const content = input.value.trim();
            
            if (content) {
                socket.emit('send_message', {
                    id: Date.now().toString(),
                    sender: currentUser.username,
                    content: content,
                    type: 'text',
                    timestamp: new Date().toISOString()
                });
                input.value = '';
            }
        }
        
        function showUploadModal(type) {
            document.getElementById('attachDropdown').classList.remove('show');
            document.getElementById('attachBtn').classList.remove('active');
            
            if (!currentUser) {
                showAuthModal();
                return;
            }
            
            currentUploadType = type;
            const modal = document.getElementById('uploadModal');
            const title = document.getElementById('modalTitle');
            const input = document.getElementById('uploadFile');
            
            if (type === 'video') {
                title.innerHTML = '🎬 Отправить видео';
                input.accept = 'video/mp4,video/webm,video/mov,video/avi,video/mkv';
            } else {
                title.innerHTML = '🖼️ Отправить изображение';
                input.accept = 'image/jpeg,image/png,image/gif,image/bmp,image/webp';
            }
            
            modal.classList.add('active');
        }
        
        function hideUploadModal() {
            document.getElementById('uploadModal').classList.remove('active');
            document.getElementById('uploadFile').value = '';
        }
        
        async function uploadMedia() {
            const file = document.getElementById('uploadFile').files[0];
            if (!file) return;
            
            const formData = new FormData();
            formData.append('media', file);
            formData.append('sender', currentUser.username);
            formData.append('type', currentUploadType);
            
            const response = await fetch('/api/upload-media', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (result.success) {
                socket.emit('send_message', {
                    id: Date.now().toString(),
                    sender: currentUser.username,
                    type: currentUploadType,
                    filename: result.filename,
                    timestamp: new Date().toISOString()
                });
                
                hideUploadModal();
                showNotification(
                    currentUploadType === 'video' ? 'Видео отправлено!' : 'Изображение отправлено!', 
                    file.name,
                    currentUploadType
                );
            }
        }
        
        function openGallery(filename) {
            const modal = document.getElementById('galleryModal');
            const img = document.getElementById('galleryImage');
            img.src = '/media/images/' + filename;
            modal.classList.add('active');
        }
        
        function closeGallery() {
            document.getElementById('galleryModal').classList.remove('active');
        }
        
        socket.on('new_message', (data) => {
            loadMessages();
        });
        
        socket.on('message_deleted', (data) => {
            loadMessages();
            if (data.sender !== currentUser?.username) {
                showNotification('🗑️ Сообщение удалено', `Пользователем ${data.sender}`, 'delete');
            }
        });
        
        socket.on('connect', () => {
            document.getElementById('status').textContent = '● В сети';
            if (currentUser) {
                socket.emit('user_online', currentUser.username);
            }
        });
        
        socket.on('disconnect', () => {
            document.getElementById('status').textContent = '○ Не в сети';
        });
        
        socket.on('call_offer', async (data) => {
            if (data.to === currentUser?.username) {
                currentCallId = data.callId;
                window.pendingOffer = data.offer;
                
                document.getElementById('incomingCaller').textContent = 
                    `Звонок от ${data.from === 'ты' ? 'тебя' : 'друга'}`;
                document.getElementById('incomingCallPanel').classList.add('active');
                
                showNotification('📞 Входящий звонок!', '', 'call');
            }
        });
        
        socket.on('call_answer', async (data) => {
            if (data.callId === currentCallId) {
                await peerConnection.setRemoteDescription(new RTCSessionDescription(data.answer));
                document.getElementById('callStatus').textContent = 'Разговор';
            }
        });
        
        socket.on('call_ice_candidate', async (data) => {
            if (data.callId === currentCallId && peerConnection) {
                await peerConnection.addIceCandidate(new RTCIceCandidate(data.candidate));
            }
        });
        
        socket.on('call_end', (data) => {
            if (data.callId === currentCallId) {
                endCall();
                showNotification('📞 Звонок завершен', '', 'call');
            }
        });
        
        socket.on('call_reject', (data) => {
            if (data.callId === currentCallId) {
                endCall();
                showNotification('📞 Звонок отклонен', '', 'call');
            }
        });
        
        window.onload = async () => {
            await loadUsers();
            
            if (!navigator.mediaDevices) {
                navigator.mediaDevices = {};
            }
            
            const savedUser = localStorage.getItem('username');
            const savedPass = localStorage.getItem('password');
            
            if (savedUser && savedPass) {
                await attemptLogin(savedUser, savedPass);
            } else {
                showAuthModal();
            }
        };
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_CHAT)

@app.route('/api/users')
def get_users():
    return jsonify(load_users())

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    users = load_users()
    
    if username in users and users[username]['password'] == password:
        return jsonify({
            "success": True,
            "avatar": users[username]['avatar'],
            "color": users[username]['color'],
            "theme": users[username].get('theme', 'dark')
        })
    
    return jsonify({"success": False})

@app.route('/api/theme', methods=['POST'])
def update_theme():
    data = request.json
    username = data.get('username')
    theme = data.get('theme')
    
    if update_user_theme(username, theme):
        return jsonify({"success": True})
    return jsonify({"success": False})

@app.route('/api/messages')
def get_messages():
    return jsonify(load_messages())

@app.route('/api/upload-media', methods=['POST'])
def upload_media():
    if 'media' not in request.files:
        return jsonify({"success": False, "error": "Нет файла"})
    
    file = request.files['media']
    sender = request.form.get('sender', 'unknown')
    media_type = request.form.get('type', 'video')
    
    if file.filename == '':
        return jsonify({"success": False, "error": "Пустое имя файла"})
    
    folder = VIDEO_FOLDER if media_type == 'video' else IMAGES_FOLDER
    
    timestamp = int(time.time())
    safe_filename = secure_filename(file.filename)
    filename = f"{timestamp}_{safe_filename}"
    filepath = os.path.join(folder, filename)
    file.save(filepath)
    
    return jsonify({
        "success": True,
        "filename": filename,
        "sender": sender,
        "type": media_type
    })

@app.route('/api/delete-message', methods=['POST'])
def delete_message_route():
    data = request.json
    message_id = data.get('message_id')
    username = data.get('username')
    
    if not message_id or not username:
        return jsonify({"success": False, "error": "Не хватает данных"})
    
    deleted = delete_message(message_id)
    
    if deleted:
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "error": "Сообщение не найдено"})

@app.route('/media/<path:subpath>/<filename>')
def serve_media(subpath, filename):
    if subpath == 'videos':
        return send_from_directory(VIDEO_FOLDER, filename)
    elif subpath == 'images':
        return send_from_directory(IMAGES_FOLDER, filename)
    return "Not found", 404

@socketio.on('send_message')
def handle_message(data):
    if 'timestamp' not in data:
        data['timestamp'] = datetime.now().isoformat()
    
    save_message(data)
    emit('new_message', data, broadcast=True)

@socketio.on('message_deleted')
def handle_message_deleted(data):
    emit('message_deleted', data, broadcast=True)

@socketio.on('user_online')
def handle_online(username):
    emit('user_status', {'username': username, 'status': 'online'}, broadcast=True)

@socketio.on('call_offer')
def handle_call_offer(data):
    emit('call_offer', data, broadcast=True)

@socketio.on('call_answer')
def handle_call_answer(data):
    emit('call_answer', data, broadcast=True)

@socketio.on('call_ice_candidate')
def handle_ice_candidate(data):
    emit('call_ice_candidate', data, broadcast=True)

@socketio.on('call_end')
def handle_call_end(data):
    emit('call_end', data, broadcast=True)

@socketio.on('call_reject')
def handle_call_reject(data):
    emit('call_reject', data, broadcast=True)
if __name__ == '__main__':
    print("="*70)
    print("Unlocked - Мессенджер который не заблокируют")
    print("="*70)
    print("📱 Адрес: https://ТВОЙ_IP_ИЗ_Radmin_VPN:5000")
    print()
    print("👤 Учетные записи:")
    print("   Нужно настроить в файле")
    print()
    print("✅ Функции:")
    print("   1.Логин")
    print("   2.Отправка сообщений, видео, изображений")
    print("   3.Смена аккаунта")
    print("   4.Смена темы оформления")
    print("   5.Звонок (в разработке)")
    print()
    print("⚠️ Браузер будет ругаться на самоподписанный сертификат")
    print("   Просто нажми 'Продолжить' или 'Дополнительно'")
    print("="*70)
    
    # Выбери один из вариантов:
    
    # ВАРИАНТ 1: Самый простой - adhoc (автоматический сертификат) сразу используется потому что самый легкий
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, ssl_context='adhoc')
    
    # ВАРИАНТ 2: Самоподписанный сертификат (нужно сгенерировать файлы)
    #socketio.run(app, host='0.0.0.0', port=5000, debug=True, 
    #            ssl_context=('cert.pem', 'key.pem'))