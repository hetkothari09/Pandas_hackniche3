# Het kothari

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import groq
import firebase_admin
from firebase_admin import credentials, db, auth
import requests
import difflib
import os
from dotenv import load_dotenv
import time
from PIL import Image
import cv2
import numpy as np
from gradio_client import Client
import re
import firebase_admin.auth

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend communication

# 🔹 Groq API Client
groq_client = groq.Groq(api_key=os.getenv('GROQ_API_KEY'))

# 🔹 HuggingFace API Token (Load from environment variable)
HUGGINGFACE_API_TOKEN = os.getenv('HUGGINGFACE_API_TOKEN')

# 🔹 Firebase setup
cred = credentials.Certificate("firebase_key.json")
try:
    # Check if Firebase app is already initialized
    firebase_admin.get_app()
except ValueError:
    # Initialize Firebase app if not already initialized
    firebase_admin.initialize_app(cred, {
        "databaseURL": "https://pandas-hackniche-default-rtdb.firebaseio.com/"  # Replace with your actual database URL
    })

# 🔹 Dictionary to store version history (Temporary; can be stored in DB)
versions = {}

# 🔷 1️⃣ Home Route (Login/Signup Page)
@app.route("/", methods=["GET"])
def home():
    return render_template('index.html')

# Add this route after the home route
@app.route("/dashboard")
def dashboard():
    return render_template('dashboard.html')

# API status endpoint
@app.route("/api/status", methods=["GET"])
def api_status():
    return jsonify({
        "message": "AI Copilot Backend Running",
        "auth_required": True,
        "endpoints": {
            "signup": "/signup",
            "login": "/login",
            "profile": "/user/profile"
        }
    }), 200

# 🔷 2️⃣ AI Content Generation (Groq LLM)
@app.route("/generate-content", methods=["POST"])
def generate_content():
    data = request.json
    prompt = data.get("prompt", "")
    content_type = data.get("type", "script")  # Options: script, article, marketing copy, dialogue

    ai_prompt = f"Generate a {content_type} based on: {prompt}"

    try:
        completion = groq_client.chat.completions.create(
            model="mixtral-8x7b-32768",  # Groq's Mixtral model
            messages=[{"role": "user", "content": ai_prompt}],
            temperature=0.7,
            max_tokens=32768
        )
        generated_content = completion.choices[0].message.content
        return jsonify({"content": generated_content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 🔷 3️⃣ AI Video Suggestions (Scene Description, Sound Effects, Visual Cues)
scene_cues = {
    "action": "Loud explosion sound, fast-paced background score",
    "romance": "Soft violin music, warm lighting",
    "mystery": "Dark ambiance, echoing footsteps",
}

@app.route("/suggest-scene", methods=["POST"])
def suggest_scene():
    data = request.json
    script = data.get("script", "").lower()

    suggestions = []
    for keyword, cue in scene_cues.items():
        if keyword in script:
            suggestions.append({keyword: cue})

    return jsonify({"suggestions": suggestions})

# 🔷 4️⃣ AI Video Generation (HuggingFace)
@app.route("/generate-video", methods=["POST"])
def generate_video():
    data = request.json
    prompt = data.get("script", "")
    
    if not HUGGINGFACE_API_TOKEN:
        return jsonify({"error": "HuggingFace API token not configured"}), 500

    try:
        print(f"Starting video generation for prompt: {prompt}")
        
        # Initialize Gradio client for Wan2.1
        client = Client("https://wan-ai-wan2-1.hf.space")
        
        # Generate video directly using t2v_generation_async
        print("Sending generation request...")
        result = client.predict(
            prompt=str(prompt),
            size="960*960",  # Using a more standard size
            watermark_wan=True,
            seed=-1,
            api_name="/t2v_generation_async"
        )
        print(f"Initial response: {result}")
        
        # Create videos directory if it doesn't exist
        if not os.path.exists('generated_videos'):
            os.makedirs('generated_videos')

        # Generate a unique filename
        timestamp = int(time.time())
        video_filename = f"generated_videos/video_{timestamp}.mp4"
        
        # Start polling for the video with longer timeout
        max_retries = 30  # 5 minutes total
        for attempt in range(max_retries):
            try:
                print(f"\nAttempt {attempt + 1}/{max_retries}")
                status = client.predict(api_name="/status_refresh_1")
                print(f"Status response: {status}")
                
                if status and isinstance(status, tuple) and len(status) > 0:
                    video_info = status[0]
                    if isinstance(video_info, dict) and 'video' in video_info:
                        video_path = video_info['video']
                        if video_path and os.path.exists(video_path):
                            print(f"Video found at: {video_path}")
                            import shutil
                            shutil.copy2(video_path, video_filename)
                            print(f"Video copied to: {video_filename}")
                            
                            return jsonify({
                                "status": "success",
                                "message": "Video generation completed",
                                "video_path": os.path.abspath(video_filename),
                                "prompt_used": prompt,
                                "settings": {
                                    "resolution": "960*960",
                                    "watermark": True,
                                    "attempts": attempt + 1,
                                    "generation_time": (attempt + 1) * 10
                                }
                            })
                
                print("Video not ready yet, waiting...")
                time.sleep(10)
                
            except Exception as poll_error:
                print(f"Polling error: {str(poll_error)}")
                time.sleep(10)
                continue
        
        raise ValueError("Video generation timed out after 5 minutes")

    except Exception as e:
        print(f"Error details: {str(e)}")
        return jsonify({
            "error": "Video generation failed",
            "details": str(e),
            "message": "An unexpected error occurred. Please try again."
        }), 500

# 🔷 5️⃣ Real-time Collaboration (Save Content in Firebase)
@app.route("/save-content", methods=["POST"])
def save_content():
    data = request.json
    user_id = data.get("user_id", "anonymous")
    content = data.get("content", "")

    ref = db.reference(f"documents/{user_id}")
    ref.push({"content": content})

    return jsonify({"message": "Content saved successfully!"})

# 🔷 6️⃣ Fetch Saved Content (Firebase)
@app.route("/get-content/<user_id>", methods=["GET"])
def get_content(user_id):
    ref = db.reference(f"documents/{user_id}")
    saved_content = ref.get()
    return jsonify({"documents": saved_content})

# 🔷 7️⃣ Version Control (Track Changes in Content)
@app.route("/save-version", methods=["POST"])
def save_version():
    data = request.json
    doc_id = data.get("doc_id", "default")
    new_content = data.get("content", "")

    old_content = versions.get(doc_id, "")
    diff = list(difflib.unified_diff(old_content.splitlines(), new_content.splitlines(), lineterm=""))

    versions[doc_id] = new_content  # Update with new version
    return jsonify({"diff": diff})

# 🔷 8️⃣ Poetic Analysis (Suggest Poetic Elements)
poetic_elements = {
    "metaphor": "Your words are fire, burning through my mind.",
    "alliteration": "Silent shadows shift and shatter in the moonlight.",
    "rhyming": "The sky is high, as birds fly by."
}

@app.route("/analyze-poetry", methods=["POST"])
def analyze_poetry():
    data = request.json
    poem = data.get("poem", "").lower()

    suggestions = []
    for element, example in poetic_elements.items():
        if element in poem:
            suggestions.append({element: example})

    return jsonify({"poetic_suggestions": suggestions})

# User Authentication Routes
@app.route("/signup", methods=["POST"])
def signup():
    try:
        data = request.json
        email = data.get("email")
        password = data.get("password")
        name = data.get("name", "")
        
        # Basic validation
        if not email or not password:
            return jsonify({"error": "Email and password are required"}), 400
        
        # Validate email format
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            return jsonify({"error": "Invalid email format"}), 400
            
        # Validate password strength
        if len(password) < 6:
            return jsonify({"error": "Password must be at least 6 characters"}), 400
        
        # Create user in Firebase
        user = auth.create_user(
            email=email,
            password=password,
            display_name=name
        )
        
        # Create user profile in Realtime Database
        ref = db.reference(f"users/{user.uid}")
        ref.set({
            "email": email,
            "name": name,
            "created_at": time.time()
        })
        
        return jsonify({
            "message": "User created successfully",
            "user_id": user.uid
        })
        
    except auth.EmailAlreadyExistsError:
        return jsonify({"error": "Email already exists"}), 400
    except Exception as e:
        print(f"Signup error: {str(e)}")
        return jsonify({"error": "Failed to create user"}), 500

@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.json
        email = data.get("email")
        firebase_token = data.get("firebaseToken")
        
        if not firebase_token:
            return jsonify({"error": "No Firebase token provided"}), 401

        try:
            # Verify the Firebase token
            decoded_token = auth.verify_id_token(firebase_token)
            user_id = decoded_token['uid']
            
            # Get user profile from database
            ref = db.reference(f"users/{user_id}")
            profile = ref.get()
            
            if not profile:
                # Create profile if it doesn't exist
                profile = {
                    "email": email,
                    "name": decoded_token.get('name', ''),
                    "created_at": time.time()
                }
                ref.set(profile)
            
            return jsonify({
                "message": "Login successful",
                "user_id": user_id,
                "profile": profile
            })
            
        except auth.InvalidIdTokenError:
            return jsonify({"error": "Invalid Firebase token"}), 401
        except auth.ExpiredIdTokenError:
            return jsonify({"error": "Expired Firebase token"}), 401
            
    except Exception as e:
        print(f"Login error: {str(e)}")
        return jsonify({"error": "Login failed", "details": str(e)}), 500

@app.route("/user/profile", methods=["GET"])
def get_user_profile():
    try:
        # Get token from header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "No token provided"}), 401
            
        token = auth_header.split(" ")[1]
        
        # Verify token
        decoded_token = auth.verify_id_token(token)
        user_id = decoded_token["uid"]
        
        # Get user profile
        ref = db.reference(f"users/{user_id}")
        profile = ref.get()
        
        if not profile:
            return jsonify({"error": "Profile not found"}), 404
            
        return jsonify(profile)
        
    except Exception as e:
        print(f"Profile fetch error: {str(e)}")
        return jsonify({"error": "Failed to fetch profile"}), 500

@app.route("/user/profile", methods=["PUT"])
def update_user_profile():
    try:
        # Get token from header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "No token provided"}), 401
            
        token = auth_header.split(" ")[1]
        
        # Verify token
        decoded_token = auth.verify_id_token(token)
        user_id = decoded_token["uid"]
        
        # Get update data
        data = request.json
        
        # Update profile in database
        ref = db.reference(f"users/{user_id}")
        ref.update(data)
        
        return jsonify({"message": "Profile updated successfully"})
        
    except Exception as e:
        print(f"Profile update error: {str(e)}")
        return jsonify({"error": "Failed to update profile"}), 500

if __name__ == "__main__":
    app.run(debug=True)

