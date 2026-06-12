from flask import Flask, request, jsonify
from flask_cors import CORS
import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image
import io
import json

app = Flask(__name__)
CORS(app) # Allows your HTML Live Server to talk to this Python server

# 1. Load the Classes
with open('classes.json', 'r') as f:
    class_names = json.load(f)

# 2. Rebuild the Model Architecture
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = models.mobilenet_v2(weights=None)
model.classifier[1] = nn.Linear(model.classifier[1].in_features, len(class_names))

# 3. Load Your Trained Brain!
model.load_state_dict(torch.load('sign_model.pth', map_location=device, weights_only=True))
model = model.to(device)
model.eval() # Set to prediction mode

# 4. Image Pre-processor (Must match training exactly)
transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

@app.route('/predict', methods=['POST'])
def predict():
    if 'image' not in request.files:
        return jsonify({'error': 'No image sent'}), 400
        
    file = request.files['image']
    image = Image.open(io.BytesIO(file.read())).convert('RGB')
    
    # Process the image and predict
    input_tensor = transform(image).unsqueeze(0).to(device)
    
    with torch.no_grad():
        outputs = model(input_tensor)
        probabilities = torch.nn.functional.softmax(outputs[0], dim=0)
        confidence, predicted_idx = torch.max(probabilities, 0)
        
    predicted_char = class_names[predicted_idx.item()]
    
    return jsonify({
        'character': predicted_char,
        'confidence': float(confidence.item())
    })

if __name__ == '__main__':
    print("🚀 Flask AI Server running on http://127.0.0.1:5000")
    app.run(port=5000, debug=False)