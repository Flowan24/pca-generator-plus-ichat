"""
Flask backend application for the iChat App.

Handles API requests for:
- Chat interactions (streaming responses, context handling, web search, document Q&A)
- User authentication (simple email/name based)
- File uploads (text, PDF, Word, images)
- Conversation history storage and retrieval (using SQLite)
"""
import os
import logging

from flask import Flask, request, jsonify, Response, stream_with_context, send_from_directory
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.utils import secure_filename
from datetime import datetime
from langchain_core.messages import HumanMessage, SystemMessage

from config import (
    MAX_MESSAGE_LENGTH, MAX_CONTENT_LENGTH_BYTES,
    UPLOAD_FOLDER, CORS_ORIGINS, DEFAULT_RATE_LIMITS,
    CHAT_RATE_LIMIT, UPLOAD_RATE_LIMIT, HISTORY_RATE_LIMIT,
    OPENAI_API_KEY, SYSTEM_PROMPT,
)
from models import User, Conversation, Message, DBDocument, get_db
from services import (
    get_or_create_user, create_conversation, get_latest_conversation,
    save_message, get_llm_instance, get_memory_for_conversation,
    allowed_file, process_document, check_tesseract,
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Flask App Setup ---
app = Flask(__name__)


# CORS: restrict to actual deployment origin
def _parse_cors_origins(origins_str: str) -> list[str]:
    return [o.strip() for o in origins_str.split(",") if o.strip()]


CORS(app, origins=_parse_cors_origins(CORS_ORIGINS))

# File upload config
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH_BYTES

# Rate limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=DEFAULT_RATE_LIMITS,
    storage_uri="memory://",
)

# Security headers
@app.after_request
def set_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response


# --- Input Validation ---
def validate_message(message):
    if not message or len(message.strip()) == 0:
        return "Message cannot be empty"
    if len(message) > MAX_MESSAGE_LENGTH:
        return f"Message must be less than {MAX_MESSAGE_LENGTH} characters"
    return None


# --- API Endpoints ---
@app.route('/api/chat', methods=['POST'])
@limiter.limit(CHAT_RATE_LIMIT)
def chat_endpoint():
    data = request.json
    if not data:
        return jsonify({"error": "Invalid request format"}), 400

    user_message = data.get('message')
    user_name = data.get('name')
    user_email = data.get('email')
    use_web_search = data.get('useWebSearch', False)

    if not user_email:
        return jsonify({"error": "Email is required"}), 400

    msg_error = validate_message(user_message)
    if msg_error:
        return jsonify({"error": msg_error}), 400

    with get_db() as db:
        try:
            # --- User Handling ---
            user = db.query(User).filter(User.email == user_email).first()
            if not user and user_name:
                user = get_or_create_user(db, user_name, user_email)
            elif not user:
                return jsonify({"error": "User not found. Please return to login."}), 401

            # --- Conversation Handling ---
            if user_name:
                conversation_obj = create_conversation(db, user.id)
            else:
                conversation_obj = get_latest_conversation(db, user.id)
                if not conversation_obj:
                    conversation_obj = create_conversation(db, user.id)

            if not conversation_obj:
                return jsonify({"error": "Failed to establish conversation context."}), 500

            # Save user message
            doc_context = data.get('documentContext')
            doc_id_for_db = doc_context.get('documentId') if doc_context else None
            save_message(db, conversation_obj.id, 'user', user_message,
                         used_web_search=use_web_search, document_id=doc_id_for_db)

            logging.info(f"Processing message for conversation {conversation_obj.id} (User: {user.email})")

            # --- Context Handling ---
            document_context = data.get('documentContext')
            is_image_query = False
            image_content_uri = None
            original_user_message = user_message

            if document_context:
                doc_id = document_context.get('documentId')
                if doc_id:
                    document = db.query(DBDocument).filter(DBDocument.id == doc_id).first()
                    if document:
                        if document.content and document.content.startswith("data:image"):
                            is_image_query = True
                            image_content_uri = document.content
                            logging.info(f"Identified image query for document ID: {doc_id}")
                        else:
                            logging.info(f"Identified text document query for document ID: {doc_id}")
                            user_message = (
                                f"Based on the document '{document.filename}', with content:\n\n"
                                f"{document.content}\n\n"
                                f"Question/Request: {user_message}"
                            )

            # --- LLM Interaction ---
            # Extract IDs before leaving the db context — streaming generators
            # manage their own sessions for saving after the stream completes.
            conv_id = conversation_obj.id
            user_email_val = user.email

        except ValueError as ve:
            logging.error(f"Configuration error: {ve}")
            return jsonify({"error": "Server configuration error. AI features unavailable."}), 500
        except Exception as e:
            logging.error(f"Error in chat endpoint: {e}", exc_info=True)
            return jsonify({"error": "An internal server error occurred"}), 500

    # Return streaming response OUTSIDE the db context manager
    # so the session is properly closed before streaming begins.
    if is_image_query:
        return _handle_image_query(conv_id, original_user_message, image_content_uri)
    elif use_web_search:
        return _handle_web_search_query(conv_id, user_email_val, user_message)
    else:
        return _handle_standard_query(conv_id, user_email_val, user_message)

def _handle_image_query(conversation_id, user_message, image_uri):
    """Handle image-based queries with vision model."""
    logging.info(f"Handling image query for conversation {conversation_id}")
    llm = get_llm_instance(streaming=False)

    image_message_content = [
        {"type": "text", "text": user_message},
        {"type": "image_url", "image_url": {"url": image_uri, "detail": "auto"}},
    ]

    def stream_response():
        full_response = ""
        try:
            for chunk in llm.stream([SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=image_message_content)]):
                content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                if content:
                    full_response += content
                    yield content
        except Exception as e:
            logging.error(f"Error in image LLM stream: {e}", exc_info=True)
            full_response = "[Error analyzing image]"
            yield full_response
        finally:
            if full_response:
                try:
                    with get_db() as save_db:
                        save_message(save_db, conversation_id, 'ai', full_response)
                except Exception as save_err:
                    logging.error(f"Failed to save AI image response: {save_err}")

    return Response(stream_with_context(stream_response()), mimetype='text/plain')


def _handle_web_search_query(conversation_id, user_email, user_message):
    """Handle queries with web search enabled (non-streaming)."""
    logging.info(f"Handling web search query for conversation {conversation_id}")
    memory = get_memory_for_conversation(user_email, conversation_id)
    chat_history = memory.load_memory_variables({}).get("chat_history", [])
    messages_for_llm = [SystemMessage(content=SYSTEM_PROMPT)] + chat_history + [HumanMessage(content=user_message)]

    llm = get_llm_instance(streaming=False)
    full_response = "[Error: Failed to process web search response]"

    try:
        response_obj = llm.invoke(messages_for_llm, tools=[{"type": "web_search"}])
        logging.info(f"Web search response type: {type(response_obj)}")

        if hasattr(response_obj, 'content'):
            content_data = response_obj.content
            if isinstance(content_data, str):
                full_response = content_data
            elif isinstance(content_data, list) and content_data:
                texts = [item.get('text') for item in content_data
                         if isinstance(item, dict) and 'text' in item]
                if texts:
                    full_response = "".join(texts)
    except Exception as e:
        logging.error(f"Error in web search LLM invoke: {e}", exc_info=True)
        full_response = "[Error generating AI response with web search]"

    # Save to memory and DB
    if not full_response.startswith("[Error"):
        try:
            memory.save_context({"input": user_message}, {"output": full_response})
            with get_db() as save_db:
                save_message(save_db, conversation_id, 'ai', full_response)
        except Exception as save_err:
            logging.error(f"Failed to save web search response: {save_err}")

    def stream_complete():
        yield full_response

    return Response(stream_with_context(stream_complete()), mimetype='text/plain')


def _handle_standard_query(conversation_id, user_email, user_message):
    """Handle standard text queries with streaming."""
    logging.info(f"Handling standard query for conversation {conversation_id}")
    memory = get_memory_for_conversation(user_email, conversation_id)
    chat_history = memory.load_memory_variables({}).get("chat_history", [])
    messages_for_llm = [SystemMessage(content=SYSTEM_PROMPT)] + chat_history + [HumanMessage(content=user_message)]
    llm = get_llm_instance(streaming=True)

    def stream_response():
        full_response = ""
        try:
            for chunk in llm.stream(messages_for_llm):
                content = chunk.content
                if content:
                    full_response += content
                    yield content
        except Exception as e:
            logging.error(f"Error in standard LLM stream: {e}", exc_info=True)
            full_response = "[Error generating AI response]"
            yield full_response
        finally:
            if full_response and not full_response.startswith("[Error"):
                try:
                    memory.save_context({"input": user_message}, {"output": full_response})
                    with get_db() as save_db:
                        save_message(save_db, conversation_id, 'ai', full_response)
                except Exception as save_err:
                    logging.error(f"Failed to save standard response: {save_err}")

    return Response(stream_with_context(stream_response()), mimetype='text/plain')


@app.route('/api/upload', methods=['POST'])
@limiter.limit(UPLOAD_RATE_LIMIT)
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    user_email = request.form.get('email')
    user_name = request.form.get('name')

    if not user_email:
        return jsonify({"error": "Email is required"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "File type not allowed"}), 400

    file_path = None
    try:
        original_filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        unique_filename = f"{timestamp}_{original_filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

        file.save(file_path)
        logging.info(f"Saved uploaded file to: {file_path}")

        # Process the document
        try:
            processed_docs = process_document(file_path)
        except Exception as processing_error:
            logging.error(f"Error processing document {file_path}: {processing_error}", exc_info=True)
            _cleanup_file(file_path)
            return jsonify({"error": f"Error processing document: {processing_error}"}), 500

        with get_db() as db:
            user = db.query(User).filter(User.email == user_email).first()
            if not user:
                if not user_name:
                    _cleanup_file(file_path)
                    return jsonify({"error": "User not found and no name provided"}), 401
                user = get_or_create_user(db, user_name, user_email)

            conversation = get_latest_conversation(db, user.id)
            if not conversation:
                conversation = create_conversation(db, user.id)

            # Determine content for DB
            is_image = processed_docs and processed_docs[0].metadata.get('type') == 'image'
            if is_image:
                db_content = processed_docs[0].page_content if processed_docs else "[Image data unavailable]"
            else:
                db_content = "\n".join(d.page_content for d in processed_docs) if processed_docs else "[Document content unavailable]"

            # Save document record
            doc = DBDocument(
                filename=original_filename,
                content=db_content,
                user_id=user.id,
            )
            db.add(doc)
            db.flush()

            # Save user upload message
            upload_msg = f"[Uploaded {'image' if is_image else 'document'}: {original_filename}]"
            save_message(db, conversation.id, 'user', upload_msg)

            logging.info(f"Processed upload: {original_filename}, DB ID: {doc.id}, Stored as: {unique_filename}")
            return jsonify({
                "message": f"Successfully uploaded {original_filename}",
                "filename": original_filename,
                "documentId": doc.id,
            })

    except Exception as e:
        logging.error(f"Unexpected error during file upload: {type(e).__name__} - {e}", exc_info=True)
        if file_path:
            _cleanup_file(file_path)
        return jsonify({"error": "Failed to process upload"}), 500


@app.route('/api/conversation/history', methods=['GET'])
@limiter.limit(HISTORY_RATE_LIMIT)
def get_conversation_history():
    user_email = request.args.get('email')
    if not user_email:
        return jsonify({"error": "Email parameter is required"}), 400

    with get_db() as db:
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        conversation = get_latest_conversation(db, user.id)
        if not conversation:
            return jsonify({"messages": []}), 200

        messages = (
            db.query(Message)
            .filter(Message.conversation_id == conversation.id)
            .order_by(Message.timestamp.asc())
            .all()
        )
        history = [
            {"sender": msg.sender, "content": msg.content, "timestamp": msg.timestamp.isoformat()}
            for msg in messages
        ]
        return jsonify({"messages": history})


@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok"})


# --- Static File Serving ---
@app.route('/')
def index():
    frontend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../frontend')
    return send_from_directory(frontend_path, 'index.html')


@app.route('/<path:path>')
def serve_static(path):
    frontend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../frontend')
    return send_from_directory(frontend_path, path)


# --- Helpers ---
def _cleanup_file(file_path):
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
            logging.info(f"Cleaned up file: {file_path}")
        except OSError as e:
            logging.error(f"Error removing file {file_path}: {e}")


# --- Main ---
if __name__ == '__main__':
    if not OPENAI_API_KEY:
        logging.error("OPENAI_API_KEY environment variable not set.")
        exit("Error: OPENAI_API_KEY not set.")

    check_tesseract()
    app.run(host='0.0.0.0', port=5001)
