# Het kothari

from flask import Flask, request, jsonify
from flask_cors import CORS
import groq
import firebase_admin
from firebase_admin import credentials, db
import requests
import difflib
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend communication

# 🔹 Groq API Client
groq_client = groq.Groq(api_key=os.getenv('GROQ_API_KEY'))

# 🔹 RunwayML API Key (Load from environment variable)
RUNWAY_API_KEY = os.getenv('RUNWAY_API_KEY')

# 🔹 Firebase setup
cred = credentials.Certificate("firebase_key.json")  # 🔹 Add your Firebase service key file
# firebase_admin.initialize_app(cred, {"databaseURL": "YOUR_FIREBASE_DATABASE_URL"})

# 🔹 Dictionary to store version history (Temporary; can be stored in DB)
versions = {}

# 🔷 1️⃣ Home Route (Health Check)
@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "AI Copilot Backend Running"}), 200

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

# 🔷 4️⃣ AI Video Generation (RunwayML)
@app.route("/generate-video", methods=["POST"])
def generate_video():
    data = request.json
    prompt = data.get("script", "")

    headers = {"Authorization": f"Bearer {RUNWAY_API_KEY}"}
    payload = {"prompt": prompt, "resolution": "1080p"}

    try:
        response = requests.post("https://api.runwayml.com/v1/generate-video", json=payload, headers=headers)
        video_url = response.json().get("url", "")
        return jsonify({"video_url": video_url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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

if __name__ == "__main__":
    app.run(debug=True)

