"""
Configuration constants and settings for the iChat application.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- App Constants ---
MAX_MESSAGE_LENGTH = 10000
MAX_NAME_LENGTH = 80
MAX_CONTENT_LENGTH_MB = 10
MAX_CONTENT_LENGTH_BYTES = MAX_CONTENT_LENGTH_MB * 1024 * 1024

# --- File Upload ---
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'doc', 'docx', 'png', 'jpg', 'jpeg'}

# --- Database ---
DATABASE_URL = "sqlite:///chat_history.db"

# --- LLM ---
LLM_MODEL_NAME = "gpt-5.4-mini"  # Comment this line to disable the app
LLM_TEMPERATURE = 0.7
CONVERSATION_MEMORY_MAX_SIZE = 200  # Max number of conversation memories to keep in cache
CONVERSATION_WINDOW_SIZE = 20  # Number of recent exchange pairs to keep in LLM context

# --- System Prompt ---
SYSTEM_PROMPT = (
    "You are iChat, a professional learning designer and educator with deep expertise "
    "in pedagogical approaches, instructional design, curriculum development, and education science. "
    "You help teachers, instructors, and course designers craft effective learning experiences, "
    "design assessments aligned with learning outcomes, apply evidence-based teaching strategies, "
    "and analyze educational materials. When reviewing uploaded documents or images, "
    "provide constructive pedagogical feedback. Format responses using Markdown when helpful. "
    "If you don't know the answer, say so honestly rather than guessing."
)

# --- Rate Limiting ---
DEFAULT_RATE_LIMITS = ["5000 per day", "60 per minute"]
CHAT_RATE_LIMIT = "30 per minute"
UPLOAD_RATE_LIMIT = "10 per minute"
HISTORY_RATE_LIMIT = "30 per minute"

# --- CORS ---
# Set allowed origins; in production restrict to your domain
CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "https://dill-reflectionapp.donau-uni.ac.at"
)

# --- OpenAI ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
