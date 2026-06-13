# 🔒Secure Ephemeral File Transfer Portal
## A full-stack, Kubernetes-deployed microservice built with Spring Boot that issues ephemeral, single-use cryptographic access links for highly sensitive files. It leverages thread-safe, in-memory data storage to serve files to authorized users and instantly destroys the data upon first view or page refresh to guarantee zero-trace security.
---
## ✨ Key Features
* **Zero-Trace Architecture:** Uploaded files are stored securely in the server's RAM (not on a hard drive) using Java's `ConcurrentHashMap`. 
* **Burn-After-Reading Mechanics:** The moment an authorized user views the file, or attempts to refresh the page, the server instantly drops the byte data from memory and permanently revokes the token, displaying a `410 GONE` security alert.
* **Cryptographic Tokenization:** Every uploaded file is tethered to a unique, randomly generated UUID to prevent URL guessing or traversal attacks.
* **Integrated Security Portal:** Features a sleek, responsive HTML/JS frontend that handles user authentication and seamless file uploads without requiring third-party clients.
* **Cloud-Native Deployment:** Fully containerized with Docker and orchestrated using Kubernetes for high availability and scalable load distribution.
---
## 🛠️ Technology Stack
* **Backend:** Java, Spring Boot, Spring Web
* **Frontend:** HTML5, CSS3, Vanilla JavaScript
* **Containerization & Orchestration:** Docker, Kubernetes
* **Build Tool:** Maven
---
## 🚀 Getting Started
### Prerequisites
* Java 17 or higher
* Maven installed
* Docker Desktop (with Kubernetes enabled)
* `kubectl` CLI tool configured
### 1. Build the Application
Clone the repository and package the Spring Boot application:
```bash
./mvnw clean package -DskipTests
### 2. Containerize the Microservice
Build the Docker image locally:
Bash
docker build -t one-time-link-api .
3. Deploy to Kubernetes
Apply your deployment configuration to the K8s cluster:

Bash
kubectl apply -f k8s-deployment.yaml
Check the status to ensure the pods are running smoothly:

Bash
kubectl get all
4. Port Forwarding (Bypass NAT/Localhost Issues)
Map the Kubernetes service to your local machine on a safe port (e.g., 9999):

Bash
kubectl port-forward svc/secure-link-service 9999:8080
💻 Usage & Demonstration
Access the Portal: Open your web browser and navigate to http://localhost:9999.

Authenticate: Log in to the portal (Default presentation credentials: admin / admin).

Upload: Select an image file (up to 10MB) and generate a secure, one-time link.

View: Click the generated link to view the securely transmitted file.

Verify Destruction: Hit the refresh button on your browser. The system will confirm the memory has been wiped and display the 🛑 410 GONE error.
