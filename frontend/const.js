const MAX_MESSAGE_LENGTH = 10000;
const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB
const ALLOWED_FILE_TYPES = ['.txt', '.pdf', '.doc', '.docx', '.png', '.jpg', '.jpeg'];
const MAX_RETRIES = 3;
const RETRY_DELAY = 1000; // milliseconds
// Use relative URLs for API endpoints to work with any server configuration
const API_ENDPOINT = '/ichat/api/chat'; // Backend API endpoint
const UPLOAD_ENDPOINT = '/ichat/api/upload'; // File upload endpoint
const HISTORY_ENDPOINT = '/ichat/api/conversation/history';
const DEFAULT_LANGUAGE = 'de'; // Default language for internationalization