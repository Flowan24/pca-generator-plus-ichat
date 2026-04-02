# Pedagogical Conversational Agent (PCA) Generator Meets iChat a Trilingual AI Chat Application
The aim of this project is to provide a simple interface to enbale teacher to built their own PCA with the help of an AI chatbot to use them in their class rooms. The interface allows teacher to describe PCA based on 6 identified dimension process: Domain Model, Learner Model, Tutor-Model, Feedback-Model, Educator-Model. After the teacher described these dimension they can download a PCA-file which they can further distrubted to their students to learn with the support of an PCA.

## iChat - Trilingual AI Chat Application

A modern Flask-based chat application with multilingual support (English, German, Spanish) that uses OpenAI's API to provide conversational AI capabilities with document upload and web search features.

## 📋 Version History

### v0.2 (current)
- **Modular backend**: Split monolithic `app.py` into `config.py`, `models.py`, `services.py`, `app.py`
- **GPT-5.4 Mini**: Upgraded from GPT-4.1
- **Pedagogy-focused system prompt**: AI acts as a professional learning designer and education expert
- **Windowed conversation memory**: Sliding window (last 20 exchanges) prevents token overflow; rehydrated from DB on restart
- **Security hardening**: CORS restricted to production domain, rate limiting, XSS protection via DOMPurify, security headers
- **Unicode name support**: Accepts names in any script (Arabic, Chinese, Cyrillic, etc.)
- **LRU memory cache**: Bounded at 200 conversations, prevents unbounded memory growth
- **Package upgrades**: LangChain 1.x, OpenAI SDK 2.x, Flask 3.x
- **Bug fixes**: DB session/streaming conflict, chat memory persistence across restarts

### v0.1
- Original monolithic application with single-file backend
- GPT-4.1, no system prompt, unbounded memory, basic validation

## ✨ Features

- **Trilingual Interface**: Full support for English, German, and Spanish with dynamic language switching
- **AI Conversations**: Powered by OpenAI's GPT models with streaming responses
- **Document Upload**: Support for TXT, PDF, DOC, DOCX, PNG, JPG, JPEG files (up to 5MB)
- **Web Search Integration**: Optional web search capability for AI responses
- **Responsive Design**: Optimized for desktop and mobile devices with efficient space utilization
- **Chat History**: Download conversation history as formatted text files
- **Real-time Typing Indicators**: Visual feedback during AI response generation
- **Copy to Clipboard**: Easy copying of AI responses
- **Persistent Sessions**: User sessions maintained across browser sessions

## 🌍 Language Support

The application automatically detects and remembers user language preferences:

- **English (en)**: Default language
- **German (de)**: Full German localization
- **Spanish (es)**: Complete Spanish translation

Language switching is seamless and affects all UI elements, error messages, and user interactions.

## 🚀 Deployment Instructions for Render.com

1. Fork this repository
2. Create a new Web Service on render.com:
   - Connect your GitHub account
   - Select this repository
   - Select the "Python" environment
   - Set the following:
     - Build Command: `cd backend && pip install -r requirements.txt`
     - Start Command: `cd backend && gunicorn app:app`

3. Add Environment Variables in render.com dashboard:
   ```
   OPENAI_API_KEY=your_api_key_here
   FLASK_ENV=production
   FLASK_DEBUG=0
   LOG_LEVEL=INFO
   MAX_CONTENT_LENGTH=5
   ```

4. Deploy the frontend:
   - Create a new Static Site on render.com
   - Connect your GitHub account
   - Select this repository
   - Set the following:
     - Build Command: (leave empty)
     - Publish Directory: `frontend`

5. Update CORS settings:
   - In the Web Service settings, add your static site's URL to the allowed origins

## 🖥️ Server Deployment (Linux)

### Prerequisites

- Linux server with sudo access
- Python 3.8+ installed
- Nginx installed
- Systemd for service management
- OpenAI API key

### Installation Steps

1. Clone the repository to your server:
```bash
git clone https://github.com/Flowan24/pca-generator-plus-ichat /home/yourusername/iChat
```

2. Create and activate a virtual environment:
```bash
cd /home/yourusername/iChat/backend
python -m venv venv
source venv/bin/activate # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
pip install gunicorn
```

4. Create a `.env` file in the iChat root directory:
```
OPENAI_API_KEY=your_api_key_here
FLASK_ENV=production
FLASK_DEBUG=0
```

5. Set up the systemd service:
```bash
sudo nano /etc/systemd/system/ichat.service
```

Add the following content (replace `yourusername` with your actual username):
```
[Unit]
Description=Gunicorn instance to serve iChat
After=network.target

[Service]
User=yourusername
Group=yourusername
WorkingDirectory=/home/yourusername/iChat/backend
EnvironmentFile=/home/yourusername/iChat/.env
ExecStart=/home/yourusername/iChat/backend/venv/bin/gunicorn --workers 3 --worker-class sync --bind 127.0.0.1:8001 wsgi:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

6. Start and enable the service:
```bash
sudo systemctl daemon-reload
sudo systemctl start ichat.service
sudo systemctl enable ichat.service
```

7. Configure Nginx:
```bash
sudo nano /etc/nginx/sites-available/ichat
```

For a standalone deployment:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        include proxy_params;
        proxy_pass http://127.0.0.1:8001/;
        proxy_read_timeout 86400;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

For running alongside another application:
```nginx
server {
    server_name your-domain.com;

    # Configuration for your main application
    location / {
        include proxy_params;
        proxy_pass http://unix:/path/to/main/app.sock;
    }

    # Configuration for iChat under /ichat/ path
    location /ichat/ {
        include proxy_params;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_pass http://127.0.0.1:8001/;
        proxy_read_timeout 86400;
    }

    # SSL configuration (if using Let's Encrypt)
    listen 443 ssl;
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
}

server {
    if ($host = your-domain.com) {
        return 301 https://$host$request_uri;
    }
    listen 80;
    server_name your-domain.com;
    return 404;
}
```

8. Enable the site and reload Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/ichat /etc/nginx/sites-enabled/
sudo nginx -t  # Test the configuration
sudo systemctl reload nginx
```

9. Set up SSL with Let's Encrypt (optional):
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## 🛠️ Development Setup

For local development:

1. Clone the repository:
```bash
git clone https://github.com/Flowan24/pca-generator-plus-ichat
cd iChat
```

2. Create a virtual environment:
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create `.env` file with your OpenAI API key:
```
OPENAI_API_KEY=your_api_key_here
FLASK_ENV=development
FLASK_DEBUG=1
LOG_LEVEL=INFO
MAX_CONTENT_LENGTH=5
```

5. Run the backend:
```bash
python app.py
```

6. Serve the frontend:
```bash
cd ../frontend
python -m http.server 8000
```

Open your browser to `http://localhost:8000`

## ⚙️ Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| PORT | Port for the server | No | 5000 |
| OPENAI_API_KEY | Your OpenAI API key | Yes | None |
| FLASK_ENV | Environment (development/production) | No | production |
| FLASK_DEBUG | Enable debug mode | No | 0 |
| LOG_LEVEL | Logging level | No | INFO |
| MAX_CONTENT_LENGTH | Max upload size in MB | No | 5 |

## 🎨 UI/UX Improvements

### Recent Enhancements

- **Optimized Horizontal Space**: Enhanced message bubble sizing for better screen utilization
- **Compact Vertical Spacing**: Reduced gaps between messages and UI elements
- **Improved List Formatting**: Optimized spacing for bullet points and numbered lists in AI responses
- **Responsive Design**: Adaptive layout for different screen sizes
- **Modern Interface**: Clean, professional design with smooth animations

### Responsive Breakpoints

- **Large screens (≥1024px)**: Messages use 75% max-width for optimal space usage
- **Medium screens (601px-1023px)**: Messages use 85% max-width for balanced display
- **Small screens (≤600px)**: Messages use 88% max-width for mobile readability

## 🔧 Updating the Application

To update your deployment:

1. **Graceful Updates** (preserves active connections):
```bash
cd /home/yourusername/iChat
git pull
sudo pkill -HUP -f "gunicorn.*app:app"
```
2. **Full Restart** (if needed):
```bash
sudo systemctl restart ichat.service
```

***Distributed under the MIT license***
