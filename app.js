const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

// ==========================================
// 1. UI & LOGIN
// ==========================================
function login() {
    const name = document.getElementById('username').value;
    if (name) {
        document.getElementById('login-screen').style.display = 'none';
        document.getElementById('dashboard').style.display = 'grid';
        document.getElementById('greeting').innerText = `Welcome, ${name}`;
    }
}

// ==========================================
// 2. TEXT & VOICE TO DATASET DISPLAY
// ==========================================
function manualTextSubmit() {
    const text = document.getElementById('text-input').value;
    if (text) processInput(text);
}

function processInput(text) {
    const utterance = new SpeechSynthesisUtterance(text);
    window.speechSynthesis.speak(utterance);
    displaySignSequence(text);
}

async function displaySignSequence(text) {
    const displayImg = document.getElementById('sign-display');
    const translationText = document.getElementById('current-translation');
    
    translationText.innerText = `Translating: "${text}"`;
    const cleanText = text.toUpperCase().replace(/[^A-Z0-9 ]/g, ""); 
    const chars = cleanText.split('');

    for (let i = 0; i < chars.length; i++) {
        if (chars[i] === ' ') {
            displayImg.src = "assets/idle.jpeg"; 
            await sleep(600); 
            continue;
        }
        displayImg.src = `assets/${chars[i]}.jpeg`; 
        await sleep(800); 
    }
    displayImg.src = "assets/idle.jpeg";
    translationText.innerText = "Ready...";
}

// ==========================================
// 3. VOICE TO TEXT
// ==========================================
function startListening() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    document.getElementById('voice-output').innerText = "Listening...";
    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        document.getElementById('voice-output').innerText = `Heard: "${transcript}"`;
        processInput(transcript); 
    };
    recognition.start();
}

// ==========================================
// 4. WEBCAM ACTION-TO-SPEECH (PyTorch Link)
// ==========================================
let video;
let isPredicting = false;
let currentWordBuffer = "";
let lastDetectedChar = "";
let lastDetectionTime = 0;

let isLearningMode = false;
let currentTarget = "";
// The 36 classes PyTorch trained on
const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789".split(""); 

async function initWebcam() {
    video = document.getElementById('input-video');
    const stream = await navigator.mediaDevices.getUserMedia({ video: true });
    video.srcObject = stream;
    document.getElementById('gesture-output').innerText = "Camera Active. Connecting to Python AI...";
    document.getElementById('gesture-output').style.color = "#2ecc71";
    
    isPredicting = true;
    // Wait 1 second for the camera to adjust to light, then start sending frames
    setTimeout(sendFrameToPython, 1000); 
}

function stopWebcam() {
    if (video && video.srcObject) {
        const stream = video.srcObject;
        const tracks = stream.getTracks();
        tracks.forEach(track => track.stop()); 
        video.srcObject = null;
        isPredicting = false; 
        document.getElementById('gesture-output').innerText = "Camera Off";
        document.getElementById('gesture-output').style.color = "#e74c3c";
    }
}

function sendFrameToPython() {
    if (!isPredicting || !video.srcObject) return;

    // Draw the current video frame onto the hidden canvas
    const canvas = document.getElementById('hidden-canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    // Convert canvas to an image and send it to Flask
    canvas.toBlob(async (blob) => {
        const formData = new FormData();
        formData.append('image', blob, 'frame.jpg');

        try {
            // POST request to your Python server
            const response = await fetch('http://127.0.0.1:5000/predict', {
                method: 'POST',
                body: formData
            });
            const result = await response.json();
            
            if (result.character) {
                processAIResult(result.character, result.confidence);
            }
        } catch (error) {
            console.error("Python Server Offline:", error);
            document.getElementById('gesture-output').innerText = "Error: Python Server Offline!";
        }

        // Loop: Send another frame in 300ms (keeps app fast but doesn't crash Python)
        if (isPredicting) {
            setTimeout(sendFrameToPython, 300);
        }
    }, 'image/jpeg');
}

function processAIResult(detectedChar, confidence) {
    // Only act if Python is >80% confident
    if (confidence > 0.80) {
        document.getElementById('gesture-output').innerText = `Seeing: ${detectedChar} (${(confidence * 100).toFixed(1)}%)`;
        const currentTime = new Date().getTime();

        // Learning Mode Loop
        if (isLearningMode && detectedChar === currentTarget) {
            document.getElementById('learning-feedback').innerText = "✅ Correct!";
            isLearningMode = false;
            setTimeout(() => { isLearningMode = true; pickNextLetter(); }, 2000);
            return;
        }

        // Buffer Loop (Build words!)
        if (!isLearningMode) {
            if (detectedChar === "IDLE") {
                if (currentWordBuffer.length > 0) {
                    processInput(currentWordBuffer); 
                    currentWordBuffer = ""; 
                    lastDetectedChar = "";
                }
            } else {
                if (detectedChar !== lastDetectedChar) {
                    lastDetectedChar = detectedChar;
                    lastDetectionTime = currentTime;
                } else if (currentTime - lastDetectionTime > 1500) {
                    // Lock in letter after 1.5 seconds of holding it
                    currentWordBuffer += detectedChar;
                    document.getElementById('current-translation').innerText = `Spelling: ${currentWordBuffer}`;
                    lastDetectionTime = currentTime + 3000; 
                }
            }
        }
    }
}

// ==========================================
// 5. LEARNING MODE
// ==========================================
function startLearningMode() {
    isLearningMode = true;
    pickNextLetter();
}

function pickNextLetter() {
    currentTarget = alphabet[Math.floor(Math.random() * alphabet.length)];
    document.getElementById('learning-prompt').innerText = `Show me: "${currentTarget}"`;
    document.getElementById('learning-feedback').innerText = "";
}