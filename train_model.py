"""import tensorflow as tf
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.layers import Dense, GlobalAveragePooling2D
from tensorflow.keras.models import Model
import tensorflowjs as tfjs
import os 

print("Loading dataset...")
# Make sure your folders inside 'dataset' are named exactly A, B, C, etc., plus 'Idle'
train_dataset = tf.keras.utils.image_dataset_from_directory(
    'dataset',
    image_size=(224, 224),
    batch_size=32,
    label_mode='categorical'
)

class_names = train_dataset.class_names
print(f"Detected Classes: {class_names}")

# Build the Model (Transfer Learning)
base_model = MobileNetV2(weights='imagenet', include_top=False, input_shape=(224, 224, 3))
base_model.trainable = False 

x = base_model.output
x = GlobalAveragePooling2D()(x)
x = Dense(128, activation='relu')(x)
predictions = Dense(len(class_names), activation='softmax')(x) 

model = Model(inputs=base_model.input, outputs=predictions)
model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])

print("Training model... this will take a few minutes.")
model.fit(train_dataset, epochs=5) 

print("Exporting model to web format...")
tfjs.converters.save_keras_model(model, 'web_model')

# Save class names for the JavaScript engine
with open('web_model/classes.txt', 'w') as f:
    f.write(','.join(class_names))

print("Success! The 'web_model' folder is ready for your web app.")
"""