import os
# 🔥 THE FIX: Tell PyTorch to save downloads in your local project folder to bypass Windows security!
os.environ['TORCH_HOME'] = './models_cache'

import torch
import torch.nn as nn
import torch.optim as optim
from torchvision import datasets, transforms, models
import json

# 1. Setup GPU/CPU
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"🚀 Training starting on: {device.type.upper()}")

# 2. Prepare the Dataset
transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

print("📂 Loading dataset...")
# Make sure your raw images are inside folders like dataset/A, dataset/B, dataset/IDLE
dataset = datasets.ImageFolder('dataset', transform=transform)
dataloader = torch.utils.data.DataLoader(dataset, batch_size=16, shuffle=True)

class_names = dataset.classes
print(f"✅ Found {len(class_names)} classes: {class_names}")

# Save the class names so the JS frontend knows what to speak
with open('classes.json', 'w') as f:
    json.dump(class_names, f)

# 3. Build the Neural Network
print("🧠 Downloading and building MobileNetV2 architecture...")
model = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.DEFAULT)

# Freeze the base layers so we only train the new classes
for param in model.parameters():
    param.requires_grad = False

# Swap the final output layer to match your 36 classes
model.classifier[1] = nn.Linear(model.classifier[1].in_features, len(class_names))
model = model.to(device)

criterion = nn.CrossEntropyLoss()
optimizer = optim.Adam(model.classifier.parameters(), lr=0.001)

# 4. Train the Model
epochs = 5
print("🔥 Starting training loop...")

for epoch in range(epochs):
    model.train()
    running_loss = 0.0
    correct = 0
    total = 0
    
    for inputs, labels in dataloader:
        inputs, labels = inputs.to(device), labels.to(device)

        optimizer.zero_grad()
        outputs = model(inputs)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()

        running_loss += loss.item()
        
        _, predicted = torch.max(outputs.data, 1)
        total += labels.size(0)
        correct += (predicted == labels).sum().item()

    accuracy = 100 * correct / total
    print(f"Epoch {epoch+1}/{epochs} | Loss: {running_loss/len(dataloader):.4f} | Accuracy: {accuracy:.2f}%")

# 5. Export the trained brain
torch.save(model.state_dict(), 'sign_model.pth')
print("🎉 Training complete! Model saved as 'sign_model.pth'")