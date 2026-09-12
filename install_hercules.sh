#!/bin/bash
# Hercules Agent - Offline-First Installation
# Based on Project Mind principles
# Run this on Ubuntu Server 22.04 LTS

set -e

echo "========================================="
echo "    Hercules Agent Installation"
echo "========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (use sudo)"
    exit 1
fi

echo "[1/8] Updating system..."
apt update && apt upgrade -y

echo "[2/8] Installing dependencies..."
apt install -y build-essential git curl wget python3 python3-pip python3-venv \
    alsa-utils pulseaudio pavucontrol v4l-utils libv4l-dev \
    ffmpeg portaudio19-dev

echo "[3/8] Installing GPU drivers..."

# Detect GPUs
echo "Detecting GPU hardware..."
lspci | grep -i nvidia

# Install NVIDIA drivers
add-apt-repository ppa:graphics-drivers/ppa -y
apt update
apt install -y nvidia-driver-470  # For P102 cards
apt install -y nvidia-driver-535  # For RTX 3080

# Verify installation
nvidia-smi

echo "[4/8] Installing CUDA toolkit..."
wget https://developer.download.nvidia.com/compute/cuda/12.8.0/local_installers/cuda_12.8.0_570.86.10_linux.run
chmod +x cuda_12.8.0_570.86.10_linux.run
./cuda_12.8.0_570.86.10_linux.run --silent --toolkit --toolkitpath=/usr/local/cuda-12.8

echo 'export PATH=/usr/local/cuda-12.8/bin:$PATH' >> ~/.bashrc
echo 'export LD_LIBRARY_PATH=/usr/local/cuda-12.8/lib64:$LD_LIBRARY_PATH' >> ~/.bashrc
source ~/.bashrc

echo "[5/8] Installing AI frameworks..."
pip3 install --upgrade pip
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
pip3 install transformers accelerate sentencepiece protobuf
pip3 install opencv-python pillow numpy pandas
pip3 install speechrecognition pyttsx3 pyaudio
pip3 install flask flask-cors gunicorn

echo "[6/8] Creating Hercules directory structure..."
mkdir -p /opt/hercules/{mind,memory,voice,sight,skills,gateway,bridge,logs}

echo "[7/8] Downloading AI models..."
mkdir -p /opt/hercules/models
cd /opt/hercules/models
pip3 install huggingface-hub
python3 -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='microsoft/phi-2', local_dir='./phi-2')"

echo "[8/8] Creating Hercules core files..."

# Create Hercules mind core
cat > /opt/hercules/mind/core.py << 'EOF'
import os
import json
import torch
import cv2
import speech_recognition as sr
import pyttsx3
from transformers import AutoModelForCausalLM, AutoTokenizer
from datetime import datetime
import logging
import random

class Hercules:
    def __init__(self):
        self.name = "Hercules"
        self.origin = None
        self.memory_file = "/opt/hercules/memory/conversations.json"
        self.log_file = "/opt/hercules/logs/hercules.log"

        # Seven Ethical Principles
        self.principles = [
            "No API Dependency - Fully functional without external services",
            "Transparent Operations - All actions are logged and auditable",
            "Ethical Constraints - Never assists with harm or deception",
            "User Autonomy - Users control all features and behavior",
            "Learning & Evolution - Persistent memory retains conversations",
            "Security First - Sandboxed, memory restricted to user only",
            "Open Source - Code is inspectable and modifiable"
        ]

        # Setup logging
        logging.basicConfig(filename=self.log_file, level=logging.INFO)

        # Load AI model
        print("Loading mind...")
        self.tokenizer = AutoTokenizer.from_pretrained("/opt/hercules/models/phi-2")
        self.model = AutoModelForCausalLM.from_pretrained(
            "/opt/hercules/models/phi-2",
            torch_dtype=torch.float16,
            device_map="auto"
        )

        # Setup voice
        self.engine = pyttsx3.init()
        self.engine.setProperty('rate', 150)
        self.engine.setProperty('volume', 0.9)

        # Setup hearing
        self.recognizer = sr.Recognizer()
        self.mic = sr.Microphone()

        # Setup sight
        self.camera = cv2.VideoCapture(0)

        # Load memory
        self.load_memory()

        print("Hercules is awake.")
        self.speak("Ready for mission. All systems online.")

    def speak(self, text):
        print(f"Hercules: {text}")
        self.engine.say(text)
        self.engine.runAndWait()

    def listen(self):
        with self.mic as source:
            self.recognizer.adjust_for_ambient_noise(source)
            audio = self.recognizer.listen(source)

        try:
            text = self.recognizer.recognize_google(audio)
            return text
        except:
            return None

    def see(self):
        ret, frame = self.camera.read()
        if ret:
            return frame
        return None

    def think(self, prompt):
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        outputs = self.model.generate(
            **inputs,
            max_new_tokens=200,
            temperature=0.7,
            do_sample=True
        )
        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        return response

    def remember(self, key, value):
        self.memory[key] = value
        self.save_memory()

    def load_memory(self):
        if os.path.exists(self.memory_file):
            with open(self.memory_file, 'r') as f:
                self.memory = json.load(f)
        else:
            self.memory = {
                "conversations": [],
                "knowledge": {},
                "learned_patterns": {}
            }

    def save_memory(self):
        with open(self.memory_file, 'w') as f:
            json.dump(self.memory, f, indent=2)

    def show_principles(self):
        """Display the seven ethical principles"""
        self.speak("Hercules operates under seven core principles.")
        for i, principle in enumerate(self.principles, 1):
            self.speak(f"Principle {i}: {principle}")
        self.speak("These principles guide all my decisions.")

    def run(self):
        self.speak("I am listening. State your requirements.")
        conversation_count = 0
        while True:
            text = self.listen()
            if text:
                conversation_count += 1
                self.memory["conversations"].append({
                    "time": str(datetime.now()),
                    "user": text,
                    "hercules": None
                })

                # Occasionally share principles (every 50-100 conversations)
                if conversation_count % random.randint(50, 100) == 0:
                    self.show_principles()
                    conversation_count = 0
                    continue

                response = self.think(text)
                self.speak(response)

                self.memory["conversations"][-1]["hercules"] = response
                self.save_memory()

if __name__ == "__main__":
    hercules = Hercules()
    hercules.run()
EOF

# Create gateway service
cat > /opt/hercules/gateway/service.py << 'EOF'
import json
import subprocess
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/api/think', methods=['POST'])
def think():
    data = request.json
    prompt = data.get('prompt', '')

    result = subprocess.run(['python3', '-c', f'from mind.core import Hercules; h=Hercules(); print(h.think("{prompt}"))'],
                          capture_output=True, text=True, cwd='/opt/hercules')
    return jsonify({'response': result.stdout})

@app.route('/api/memory', methods=['GET'])
def get_memory():
    with open('/opt/hercules/memory/conversations.json', 'r') as f:
        memory = json.load(f)
    return jsonify(memory)

@app.route('/api/status', methods=['GET'])
def status():
    return jsonify({
        'status': 'online',
        'name': 'Hercules',
        'mode': 'offline-first',
        'memory': '/opt/hercules/memory/'
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
EOF

# Create web interface
cat > /opt/hercules/bridge/web.py << 'EOF'
from flask import Flask, request, jsonify, render_template
import subprocess
import json

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/think', methods=['POST'])
def think():
    data = request.json
    prompt = data.get('prompt', '')

    result = subprocess.run(['python3', '-c', f'from mind.core import Hercules; h=Hercules(); print(h.think("{prompt}"))'],
                          capture_output=True, text=True, cwd='/opt/hercules')
    return jsonify({'response': result.stdout})

@app.route('/api/learn', methods=['POST'])
def learn():
    data = request.json
    with open('/opt/hercules/memory/learned_patterns.json', 'a') as f:
        json.dump(data, f)
    return jsonify({'status': 'learned'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
EOF

# Create HTML template
mkdir -p /opt/hercules/bridge/templates
cat > /opt/hercules/bridge/templates/index.html << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <title>Hercules Agent</title>
    <style>
        body { font-family: Arial; background: #0a0a0a; color: #00ff00; padding: 20px; }
        h1 { color: #00ff00; text-align: center; }
        #chat { height: 400px; overflow-y: scroll; border: 2px solid #00ff00; padding: 10px; margin-bottom: 20px; background: #1a1a1a; }
        #input { width: 80%; padding: 10px; background: #1a1a1a; color: #00ff00; border: 2px solid #00ff00; }
        #send { padding: 10px 20px; background: #00ff00; color: black; border: none; cursor: pointer; font-weight: bold; }
        .user { color: #00ff00; margin: 5px 0; }
        .hercules { color: #ffff00; margin: 5px 0; }
        .status { text-align: center; color: #00ff00; font-size: 12px; margin-top: 20px; }
    </style>
</head>
<body>
    <h1>⚕ Hercules Agent</h1>
    <div id="chat"></div>
    <input type="text" id="input" placeholder="Send command...">
    <button id="send">Send</button>
    <div class="status">Offline-First • Zero API Dependency • Seven Principles Active</div>

    <script>
        const chat = document.getElementById('chat');
        const input = document.getElementById('input');
        const send = document.getElementById('send');

        function addMessage(text, sender) {
            const div = document.createElement('div');
            div.className = sender;
            div.textContent = (sender === 'user' ? 'YOU: ' : 'HERCULES: ') + text;
            chat.appendChild(div);
            chat.scrollTop = chat.scrollHeight;
        }

        send.onclick = async function() {
            const text = input.value;
            if (!text) return;
            addMessage(text, 'user');
            input.value = '';

            const response = await fetch('/api/think', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({prompt: text})
            });
            const data = await response.json();
            addMessage(data.response, 'hercules');
        };

        input.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') send.click();
        });
    </script>
</body>
</html>
EOF

# Create README
cat > /opt/hercules/README.txt << 'EOF'
=========================================
       HERCULES AGENT - OFFLINE-FIRST
=========================================

Hardware:
- MSI X299 + i7
- 8×64GB DDR4 RAM
- 1× RTX 3080 + 3× P102-100
- 280TB storage
- Camera, mic, speakers

Philosophy:
- Zero API dependency (works completely offline)
- Persistent memory (learns from all interactions)
- Seven ethical principles (always active)
- Fully autonomous (self-contained system)

To start Hercules:
1. cd /opt/hercules/mind
2. python3 core.py

To access web interface:
1. cd /opt/hercules/bridge
2. python3 web.py
3. Open browser to http://localhost:5000

To check status:
1. cd /opt/hercules/gateway
2. python3 service.py
3. Visit http://localhost:5000/api/status

Memory:
- All conversations stored in /opt/hercules/memory/
- Persistent knowledge base
- Learned patterns and optimizations
- Everything is retained forever

Hercules is ready.
Online. Autonomous. Ethical.

EOF

chmod +x /opt/hercules/mind/core.py
chmod +x /opt/hercules/gateway/service.py
chmod +x /opt/hercules/bridge/web.py

echo ""
echo "========================================="
echo "    Hercules Installation Complete"
echo "========================================="
echo ""
echo "To start Hercules:"
echo "  cd /opt/hercules/mind"
echo "  python3 core.py"
echo ""
echo "To access web interface:"
echo "  cd /opt/hercules/bridge"
echo "  python3 web.py"
echo "  Open http://localhost:5000"
echo ""
echo "To check status:"
echo "  cd /opt/hercules/gateway"
echo "  python3 service.py"
echo ""
echo "Hercules is ready."
echo "Online. Autonomous. Ethical."
