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
// 3. VOICE TO TEXT (STT)
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
// 4. WEBCAM ACTION-TO-SPEECH (ml5.js)
// ==========================================
let classifier;
let video;
let isModelTrained = false;
let isPredicting = false; // Prevents overlapping prediction loops

let currentWordBuffer = "";
let lastDetectedChar = "";
let lastDetectionTime = 0;

let isLearningMode = false;
let currentTarget = "";
let learnedClasses = [];

async function initWebcam() {
    document.getElementById('gesture-output').innerText = "Loading base AI... please wait.";
    
    video = document.getElementById('input-video');
    const stream = await navigator.mediaDevices.getUserMedia({ video: true });
    video.srcObject = stream;

    const featureExtractor = ml5.featureExtractor('MobileNet', () => {
        document.getElementById('gesture-output').innerText = "AI Ready! Please upload your dataset folder.";
        classifier = featureExtractor.classification(video, () => {
            console.log("Video ready for classification");
        });
        document.getElementById('dataset-upload').addEventListener('change', trainModelFromFolder);
    });
}

function stopWebcam() {
    if (video && video.srcObject) {
        const stream = video.srcObject;
        const tracks = stream.getTracks();
        tracks.forEach(track => track.stop()); // Shuts off the hardware light
        video.srcObject = null;
        isPredicting = false; // Stop the AI loop
        document.getElementById('gesture-output').innerText = "Camera Off";
    }
}

async function trainModelFromFolder(event) {
    const files = event.target.files;
    if (files.length === 0) return;

    const outputText = document.getElementById('gesture-output');
    outputText.innerText = `Extracting ${files.length} images...`;
    outputText.style.color = "#f39c12";

    const imgElement = document.createElement('img');
    const uniqueClasses = new Set();

    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        if (file.type.startsWith('image/')) {
            const parts = file.webkitRelativePath.split('/');
            const label = parts[parts.length - 2].toUpperCase(); 
            uniqueClasses.add(label);

            await new Promise((resolve) => {
                const reader = new FileReader();
                reader.onload = (e) => {
                    imgElement.src = e.target.result;
                    imgElement.onload = () => {
                        classifier.addImage(imgElement, label);
                        resolve();
                    }
                };
                reader.readAsDataURL(file);
            });
        }
    }

    learnedClasses = Array.from(uniqueClasses);
    outputText.innerText = "Training AI locally... Please wait.";
    
    classifier.train((lossValue) => {
        if (lossValue) {
            console.log('Training Loss:', lossValue);
        } else {
            isModelTrained = true;
            outputText.innerText = "✅ Training Complete! Start signing.";
            outputText.style.color = "green";
            if (!isPredicting) {
                isPredicting = true;
                startPredicting();
            }
        }
    });
}

function startPredicting() {
    if (!isPredicting || !video.srcObject) return; // Stop if camera is off

    classifier.classify(video, (error, results) => {
        if (error) {
            console.error(error);
            return;
        }
        
        const detectedChar = results[0].label;
        const highestConfidence = results[0].confidence;
        const currentTime = new Date().getTime();

        if (highestConfidence > 0.80) {
            document.getElementById('gesture-output').innerText = `Seeing: ${detectedChar} (${(highestConfidence * 100).toFixed(1)}%)`;

            // Learning Mode Logic
            if (isLearningMode && detectedChar === currentTarget) {
                 document.getElementById('learning-feedback').innerText = "✅ Correct!";
                 isLearningMode = false;
                 setTimeout(() => { isLearningMode = true; pickNextLetter(); }, 2000);
            }

            // Word Spelling Buffer
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
                        currentWordBuffer += detectedChar;
                        document.getElementById('current-translation').innerText = `Spelling: ${currentWordBuffer}`;
                        lastDetectionTime = currentTime + 3000; 
                    }
                }
            }
        }
        
        // Loop again if we are still predicting
        if (isPredicting) {
            startPredicting(); 
        }
    });
}

// ==========================================
// 5. LEARNING MODE
// ==========================================
function startLearningMode() {
    if (!isModelTrained) {
        alert("Please train the AI first by uploading your dataset!");
        return;
    }
    isLearningMode = true;
    pickNextLetter();
}

function pickNextLetter() {
    const validLetters = learnedClasses.filter(c => c !== "IDLE");
    if (validLetters.length === 0) return;
    currentTarget = validLetters[Math.floor(Math.random() * validLetters.length)];
    document.getElementById('learning-prompt').innerText = `Show me: "${currentTarget}"`;
    document.getElementById('learning-feedback').innerText = "";
}