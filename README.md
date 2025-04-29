# iChat - AI Chat Application (Render Deployment)

This is the render-ready version of iChat, configured for deployment on render.com.

## Deployment Instructions

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

## Development Setup

For local development:

1. Create a virtual environment:
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create `.env` file with your OpenAI API key:
```
OPENAI_API_KEY=your_api_key_here
FLASK_ENV=development
FLASK_DEBUG=1
LOG_LEVEL=INFO
MAX_CONTENT_LENGTH=5
```

4. Run the backend:
```bash
python app.py
```

5. Serve the frontend:
```bash
cd frontend
python -m http.server 8000
```

## Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| PORT | Port for the server | No | 5000 |
| OPENAI_API_KEY | Your OpenAI API key | Yes | None |
| FLASK_ENV | Environment (development/production) | No | production |
| FLASK_DEBUG | Enable debug mode | No | 0 |
| LOG_LEVEL | Logging level | No | INFO |
| MAX_CONTENT_LENGTH | Max upload size in MB | No | 5 |

## Render.com Specific Notes

- The app uses the PORT environment variable provided by render.com
- Database is SQLite-based, stored in the /backend directory
- File uploads are stored in /backend/uploads
- Frontend makes API calls to the render.com backend URL
- CORS is configured to allow requests from your static site

## Troubleshooting

1. If the frontend can't connect to the backend:
   - Check the backend URL in frontend/script.js
   - Verify CORS settings in the render.com dashboard
   - Check browser console for error messages

2. If file uploads fail:
   - Verify the uploads directory exists and is writable
   - Check MAX_CONTENT_LENGTH setting
   - Monitor render.com logs for errors

3. If the database doesn't persist:
   - Use render.com disk for persistent storage
   - Consider migrating to PostgreSQL for production

## License

This project is licensed under the MIT License.
