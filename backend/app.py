"""
Flask backend application for the iChat App.

Handles API requests for:
- Chat interactions (streaming responses, context handling, web search, document Q&A)
- User authentication (simple email/name based)
- File uploads (text, PDF, Word, images)
- Conversation history storage and retrieval (using SQLite)

Uses Langchain with OpenAI for LLM interactions and document processing.
"""
import os
import logging
from flask import Flask, request, jsonify, Response, stream_with_context, send_from_directory
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
from langchain_openai import ChatOpenAI
from langchain.memory import ConversationBufferMemory
# ConversationChain might be removed if not used elsewhere, keep for now
from langchain.chains import ConversationChain
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from base64 import b64encode
from email_validator import validate_email, EmailNotValidError
import re
import werkzeug
from werkzeug.utils import secure_filename
from langchain_community.document_loaders import TextLoader, UnstructuredWordDocumentLoader, PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document as LangchainDocument

# Load environment variables (for OPENAI_API_KEY)
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Constants ---
MAX_MESSAGE_LENGTH = 10000000
MAX_NAME_LENGTH = 80
# --- Flask App Setup ---
app = Flask(__name__)
CORS(app)  # Allow all origins in development

# Ensure uploads directory exists
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = None  # max file size, e.g., for 5MB write 5 * 1024 * 1024


# Setup rate limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["1000000 per day", "100 per minute"],
    storage_uri="memory://"
)

# Input validation
def validate_user_input(name=None, email=None, message=None):
    errors = []

    if name is not None:
        if not name or len(name.strip()) == 0:
            errors.append("Name is required")
        elif len(name) > MAX_NAME_LENGTH:
            errors.append(f"Name must be less than {MAX_NAME_LENGTH} characters")
        elif not re.match(r"^[a-zA-Z0-9\s\-_]+$", name):
            errors.append("Name contains invalid characters")

    if email is not None:
        try:
            validate_email(email)
        except EmailNotValidError:
            errors.append("Invalid email format")

    if message is not None:
        if not message or len(message.strip()) == 0:
            errors.append("Message cannot be empty")
        elif len(message) > MAX_MESSAGE_LENGTH:
            errors.append(f"Message must be less than {MAX_MESSAGE_LENGTH} characters")

    return errors

# --- Database Setup (SQLite) ---
DATABASE_URL = "sqlite:///chat_history.db"
# Add check_same_thread=False for SQLite when used with Flask/multiple threads
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- Database Models ---
class DBDocument(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String)
    content = Column(Text)
    user_id = Column(Integer, ForeignKey("users.id"))
    upload_timestamp = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="documents")

class User(Base):
    documents = relationship("DBDocument", back_populates="user")
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    conversations = relationship("Conversation", back_populates="user") # Link User to Conversations

class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    start_timestamp = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation") # Link Conversation to Messages

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id")) # Link Message to Conversation
    timestamp = Column(DateTime, default=datetime.utcnow)
    sender = Column(String) # 'user' or 'ai'
    content = Column(Text)
    used_web_search = Column(Boolean, default=False, nullable=False) # Track if web search was used for the prompt generating this response (applies mainly to user messages)
    document_id = Column(Integer, ForeignKey('documents.id'), nullable=True) # Link to a document if relevant to the prompt
    conversation = relationship("Conversation", back_populates="messages")
    document = relationship("DBDocument") # Relationship to access the linked document easily

# Create database tables if they don't exist
# It's safer to handle migrations properly in production, but for simplicity:
try:
    Base.metadata.create_all(bind=engine)
    logging.info("Database tables checked/created.")
except Exception as e:
    logging.error(f"Error creating database tables: {e}")

# --- Helper Functions ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_or_create_user(db, name: str, email: str):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        try:
            user = User(name=name, email=email)
            db.add(user)
            db.commit()
            db.refresh(user)
            logging.info(f"Created new user: {name} ({email})")
        except SQLAlchemyError as e:
            db.rollback()
            logging.error(f"Database error creating user {email}: {e}")
            raise
    return user

def create_conversation(db, user_id: int):
    """Creates a new conversation for a user."""
    try:
        conversation = Conversation(user_id=user_id)
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        logging.info(f"Created new conversation (ID: {conversation.id}) for user ID {user_id}")
        return conversation
    except SQLAlchemyError as e:
        db.rollback()
        logging.error(f"Database error creating conversation for user ID {user_id}: {e}")
        raise

def get_latest_conversation(db, user_id: int):
    """Gets the most recent conversation for a user."""
    return db.query(Conversation).filter(Conversation.user_id == user_id).order_by(Conversation.start_timestamp.desc()).first()

def save_message(db, conversation_id: int, sender: str, content: str, used_web_search: bool = False, document_id: int = None):
    """
    Saves a message associated with a specific conversation, optionally including
    metadata about web search usage or linked documents relevant to the prompt.
    """
    # Ensure content is not excessively long if needed, or handle large text appropriately
    try:
        message = Message(
            conversation_id=conversation_id,
            sender=sender,
            content=content,
            used_web_search=used_web_search, # Add this
            document_id=document_id         # Add this
        )
        db.add(message)
        db.commit()
        # Include metadata in log if present
        log_meta = []
        if used_web_search: log_meta.append("web_search=True")
        if document_id: log_meta.append(f"doc_id={document_id}")
        log_suffix = f" ({', '.join(log_meta)})" if log_meta else ""
        logging.info(f"Saved {sender} message for conversation ID {conversation_id}{log_suffix}")
    except SQLAlchemyError as e:
        db.rollback()
        logging.error(f"Database error saving message for conversation ID {conversation_id}: {e}")
        # Re-raise the exception so the endpoint can handle it
        raise

# --- Langchain Setup ---
# In-memory store for conversation memories (keyed by user email + conversation_id for potential future use)
# NOTE: Still simple, not production-ready for scaling or persistence across restarts.
conversation_memories = {}

# Updated memory function to ensure return_messages=True
def get_memory_for_conversation(user_email: str, conversation_id: int):
    """Gets or creates a conversation memory buffer for a specific user conversation."""
    memory_key = f"{user_email}_{conversation_id}"
    if memory_key not in conversation_memories:
        logging.info(f"Creating new conversation memory for key: {memory_key}")
        # return_messages=True is crucial for passing history to llm.stream
        conversation_memories[memory_key] = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
        # Potentially load history from DB here if implementing persistence
    return conversation_memories[memory_key]

def allowed_file(filename):
    """Check if uploaded file has an allowed extension."""
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'doc', 'docx', 'png', 'jpg', 'jpeg'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Import OCR dependencies
try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    logging.error("pytesseract not installed. OCR features will be limited.")

def process_image(file_path):
    """Process image file for GPT vision model analysis.
    
    Converts the image to base64 and creates a Langchain Document object with
    the encoded image and metadata. This format is required for the vision model
    to analyze image content.
    
    Args:
        file_path (str): Path to the image file
        
    Returns:
        list[LangchainDocument]: Single-item list containing document with encoded image
        
    Raises:
        Exception: If image processing or encoding fails
        
    Note:
        The returned document's page_content contains a data URI with the base64 image,
        and metadata includes image format and dimensions.
    """
    try:
        # Open image file and get basic information
        with open(file_path, 'rb') as img_file:
            # Convert image to base64
            img_data = b64encode(img_file.read()).decode('utf-8')
            image = Image.open(file_path)
            image_url = f"data:image/{image.format.lower()};base64,{img_data}"

            # Create document with the base64 image URL and metadata
            document = LangchainDocument(
                page_content=image_url,
                metadata={
                    "source": file_path,
                    "type": "image",
                    "format": image.format,
                    "size": f"{image.size[0]}x{image.size[1]} pixels"
                }
            )
            return [document]
    except Exception as e:
        logging.error(f"Error processing image {file_path}: {e}")
        raise

def process_document(file_path):
    """Process uploaded document and extract content based on file type.
    
    Supports multiple file types:
    - Images (.png, .jpg, .jpeg): Converts to analyzable format for vision model
    - Text (.txt): Direct text extraction
    - PDF (.pdf): Extracts text from all pages
    - Word (.doc, .docx): Extracts formatted text content
    
    Args:
        file_path (str): Path to the uploaded file
        
    Returns:
        list[LangchainDocument]: List of document chunks with extracted content
            For images: Single document with encoded image
            For text documents: Multiple chunks split by RecursiveCharacterTextSplitter
            
    Raises:
        ValueError: If file type is not supported
        Exception: If document processing fails
        
    Note:
        Text documents are split into chunks with 2000 character size and
        200 character overlap for optimal processing by the LLM.
    """
    extension = file_path.split('.')[-1].lower()

    try:
        if extension in ['png', 'jpg', 'jpeg']:
            # For images, return the processed document list
            return process_image(file_path)
        elif extension == 'txt':
            loader = TextLoader(file_path)
        elif extension == 'pdf':
            loader = PyPDFLoader(file_path)
        elif extension in ['doc', 'docx']:
            loader = UnstructuredWordDocumentLoader(file_path)
        else:
            raise ValueError(f"Unsupported file type: {extension}")

        # For text-based documents
        documents = loader.load()

        # Split text into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=2000,
            chunk_overlap=200,
            length_function=len
        )

        splits = text_splitter.split_documents(documents)
        return splits
    except Exception as e:
        logging.error(f"Error processing document {file_path}: {e}")
        raise

# This function is already present from the previous attempt, no changes needed here.
def get_llm_instance(streaming: bool = False):
    """Creates a ChatOpenAI instance."""
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY not set in environment variables.")

    # Increase max_tokens for non-streaming (image analysis) calls
    # to ensure output isn't prematurely cut off.
    # Input token limits are usually separate and handled by the API/model itself.
    max_output_tokens = None # 16000 if not streaming else 1000 # Adjusted non-streaming limit

    # Set the desired model name
    model_name = "gpt-4.1-mini"
    logging.info(f"Using model: {model_name}")

    return ChatOpenAI(
        model_name=model_name,
        temperature=0.7,
        streaming=streaming,
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        max_tokens=max_output_tokens
    )

# This function is already present from the previous attempt, no changes needed here.
def get_conversation_chain(user_email: str, conversation_id: int):
    """Gets or creates a conversation chain for a specific user conversation."""
    # Use a composite key to potentially handle multiple conversations per user if needed later
    memory_key = f"{user_email}_{conversation_id}"
    if memory_key not in conversation_memories:
        logging.info(f"Creating new conversation memory for key: {memory_key}")

        # Get a streaming LLM instance for the conversation chain
        streaming_llm = get_llm_instance(streaming=True)

        memory = ConversationBufferMemory(return_messages=True)

        # Potentially load history from DB here if implementing persistence
        # For now, each server run starts fresh memory for a conversation
        conversation_memories[memory_key] = ConversationChain(
            llm=streaming_llm,
            memory=memory,
            verbose=False # Set to True for debugging if needed
        )
    return conversation_memories[memory_key]
# --- API Endpoints ---
@app.route('/api/chat', methods=['POST'])
@limiter.limit("10 per minute")  # Rate limit per user
def chat_endpoint():
    data = request.json
    if not data:
        return jsonify({"error": "Invalid request format"}), 400

    user_message = data.get('message')
    user_name = data.get('name')    # Included only on first message
    user_email = data.get('email')  # Included with every message
    useWebSearch = data.get('useWebSearch', False) # Get the new flag

    # Validate inputs
    validation_errors = []
    if user_name:
        validation_errors.extend(validate_user_input(name=user_name))
    validation_errors.extend(validate_user_input(email=user_email, message=user_message))

    if validation_errors:
        return jsonify({"error": validation_errors[0]}), 400

    db = next(get_db())
    user = None
    conversation_obj = None

    try:
        # --- User Handling ---
        # First, try to find existing user by email
        user = db.query(User).filter(User.email == user_email).first()

        # If user not found and we have a name, create new user
        if not user and user_name:
            user = get_or_create_user(db, user_name, user_email)
        # If user not found and no name provided
        elif not user:
            logging.error(f"User with email {user_email} not found and no name provided for creation")
            return jsonify({"error": "User not found. Please return to login."}), 401

        # --- Conversation Handling ---
        if user_name: # First message triggers new conversation
            conversation_obj = create_conversation(db, user.id)
        else:
            conversation_obj = get_latest_conversation(db, user.id)
            if not conversation_obj:
                logging.warning(f"No existing conversation found for user {user.email}. Creating a new one.")
                conversation_obj = create_conversation(db, user.id)

        if not conversation_obj:
             logging.error(f"Failed to find or create a conversation for user {user.email}")
             return jsonify({"error": "Failed to establish conversation context."}), 500

        # Extract web search flag and document ID for saving with the user message
        web_search_used = data.get('useWebSearch', False)
        doc_context = data.get('documentContext')
        # Ensure doc_context is not None before trying to get 'documentId'
        doc_id_for_db = doc_context.get('documentId') if doc_context else None

        # Save user message (passing new flags)
        # Note: user_message might be modified later if context is prepended, but we save the original prompt intent here.
        # If we wanted to save the *modified* message, this call would need to move after context handling.
        # For now, saving the original message with its metadata seems correct.
        save_message(db, conversation_obj.id, 'user', user_message, used_web_search=web_search_used, document_id=doc_id_for_db)

        # --- Langchain Interaction ---
        logging.info(f"Processing message for conversation {conversation_obj.id} (User: {user.email}): {user_message}")

        # --- Context Handling ---
        document_context = data.get('documentContext')
        is_image_query = False
        image_content_uri = None
        original_user_message = user_message # Keep original message for image prompts

        if document_context:
            doc_id = document_context.get('documentId')
            if doc_id:
                document = db.query(DBDocument).filter(DBDocument.id == doc_id).first()
                if document:
                    # Check if the document content is an image data URI
                    if document.content and document.content.startswith("data:image"):
                        is_image_query = True
                        image_content_uri = document.content
                        logging.info(f"Identified image query for document ID: {doc_id}")
                        # DO NOT modify user_message for image queries
                    else:
                        # It's a text document, prepend content to the user message
                        logging.info(f"Identified text document query for document ID: {doc_id}")
                        context_message = (
                            f"Based on the document '{document.filename}', with content:\n\n"
                            f"{document.content}\n\n"
                            f"Question/Request: {user_message}"
                        )
                        user_message = context_message # Overwrite user_message for text context
                else:
                     logging.warning(f"Document context provided but document ID {doc_id} not found.")
                     # Proceed without context if doc not found
            else:
                 logging.warning("Document context provided but 'documentId' missing.")
                 # Proceed without context if ID missing

        # --- LLM Interaction ---
        try:
            if is_image_query:
                # --- Handle Image Query Directly ---
                logging.info(f"Handling image query directly for conversation {conversation_obj.id}")
                llm = get_llm_instance(streaming=False) # Get non-streaming instance

                # Construct the multimodal message list
                image_message_content = [
                    {"type": "text", "text": original_user_message}, # Use the original user question
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_content_uri,
                            "detail": "auto"
                        }
                    }
                ]

                # Define a streaming function for the direct image call
                def stream_image_response():
                    full_ai_response = ""
                    try:
                        # Use llm.stream if available and works for multimodal, otherwise invoke and yield
                        # Let's try llm.stream first for better UX
                        logging.info("Streaming non-streaming LLM for image analysis...")
                        # Ensure the input format for stream matches invoke for multimodal
                        for chunk in llm.stream([HumanMessage(content=image_message_content)]):
                             # Adjust based on actual chunk structure from llm.stream
                             content_chunk = chunk.content if hasattr(chunk, 'content') else str(chunk)
                             if content_chunk:
                                 full_ai_response += content_chunk
                                 yield content_chunk
                        logging.info("Image analysis streaming successful.")

                    except Exception as img_llm_error:
                        logging.error(f"Error invoking/streaming LLM for image query: {img_llm_error}", exc_info=True)
                        full_ai_response = "[Error analyzing image]"
                        yield full_ai_response # Yield error message
                    finally:
                        # Save the full AI response after streaming/invocation
                        if full_ai_response:
                            try:
                                # User message was already saved before context handling
                                save_message(db, conversation_obj.id, 'ai', full_ai_response)
                                logging.info(f"Saved AI response for image query in conversation {conversation_obj.id}")
                            except Exception as save_error:
                                logging.error(f"Failed to save AI response for image query: {save_error}")
                        else:
                            logging.warning(f"No AI response generated for image query in conversation {conversation_obj.id}")

                return Response(stream_with_context(stream_image_response()), mimetype='text/plain')

            else:
                # --- Handle Text Query using direct LLM call with memory ---
                logging.info(f"Handling text query (native search: {useWebSearch}) for conversation {conversation_obj.id}")

                # Get memory and load history
                memory = get_memory_for_conversation(user.email, conversation_obj.id)
                # The key "chat_history" is defined in get_memory_for_conversation
                chat_history = memory.load_memory_variables({}).get("chat_history", [])

                # Prepare tools list if web search is enabled
                tools_list = []
                if useWebSearch:
                    tools_list = [{"type": "web_search"}]
                    logging.info(f"Native web search requested via tools parameter for conversation {conversation_obj.id}")
                # else: # No tools needed if web search is off
                #     logging.info(f"Native web search is OFF for conversation {conversation_obj.id}")

                # Construct messages list (history + current message)
                # Optional: Add a system message if desired
                # messages_for_llm = [SystemMessage(content="You are a helpful assistant.")] + chat_history + [HumanMessage(content=user_message)]
                messages_for_llm = chat_history + [HumanMessage(content=user_message)]

                # --- Choose Streaming vs Non-Streaming based on Web Search ---
                if useWebSearch:
                    # --- Non-Streaming for Web Search ---
                    logging.info(f"Using non-streaming invoke for web search query.")
                    llm_non_streaming = get_llm_instance(streaming=False) # Get non-streaming instance
                    # Initialize full_ai_response as an error string *before* the try block
                    full_ai_response = "[Error: Failed to process web search response]"
                    try:
                        # --- Start of the single try block for invoke + extraction ---
                        invoke_args = {}
                        if tools_list:
                            invoke_args["tools"] = tools_list

                        # Make the non-streaming call
                        response_obj = llm_non_streaming.invoke(messages_for_llm, **invoke_args)
                        logging.info(f"Raw web search response object type: {type(response_obj)}")
                        logging.debug(f"Raw web search response object: {response_obj}") # Debug level logging

                        extracted_text = None
                        # Extract content, checking for list structure first
                        if hasattr(response_obj, 'content'):
                            content_data = response_obj.content
                            logging.info(f"Web search response content type: {type(content_data)}")
                            logging.debug(f"Web search response content data: {content_data}") # Debug level logging

                            if isinstance(content_data, str):
                                extracted_text = content_data
                            elif isinstance(content_data, list) and content_data:
                                # Attempt to join text from all dicts in the list
                                texts = [item.get('text') for item in content_data if isinstance(item, dict) and 'text' in item]
                                if texts:
                                    extracted_text = "".join(texts) # Concatenate all text parts
                                else:
                                    logging.warning(f"Web search response content list did not contain expected dict structure: {content_data}")
                            else:
                                logging.warning(f"Web search response content had unexpected type ({type(content_data)}): {content_data}")

                            if extracted_text is not None:
                                full_ai_response = extracted_text # Assign the extracted STRING if successful
                                logging.info("Successfully invoked LLM with web search and extracted text.")
                            else:
                                # Keep the default error string, log details
                                logging.error(f"Could not extract text content from web search response content: {content_data}")
                                # full_ai_response remains "[Error: Failed to process web search response]"
                        else:
                            logging.error(f"Web search response object missing 'content' attribute: {response_obj}")
                            # full_ai_response remains "[Error: Failed to process web search response]"
                        # --- End of the single try block ---

                    except Exception as invoke_error:
                        # --- Start of the single except block ---
                        logging.error(f"Error during LLM non-streaming invocation or text extraction (web search): {type(invoke_error).__name__} - {invoke_error}", exc_info=True)
                        full_ai_response = "[Error generating AI response with web search]" # Overwrite default error on exception
                        # --- End of the single except block ---

                    # --- Logic AFTER try/except (equivalent to finally but outside) ---
                    # Save context/message AFTER the invocation attempt
                    # At this point, full_ai_response MUST be a string (either extracted text or an error message)
                    if isinstance(full_ai_response, str) and full_ai_response and not full_ai_response.startswith("[Error"):
                        try:
                            memory.save_context({"input": user_message}, {"output": full_ai_response})
                            save_message(db, conversation_obj.id, 'ai', full_ai_response)
                            logging.info(f"Saved context/message (native search: True, non-streaming) for conversation {conversation_obj.id}")
                        except Exception as save_error:
                            logging.error(f"Failed to save context/message after web search invoke: {save_error}")
                    # Log if it's an error string or empty
                    elif isinstance(full_ai_response, str) and full_ai_response.startswith("[Error"):
                         logging.warning(f"AI response was an error (native search: True, non-streaming): {full_ai_response}")
                    else: # Handles empty string or non-string cases (though should be string now)
                         logging.warning(f"No valid AI response generated or extracted (native search: True, non-streaming) for conversation {conversation_obj.id}. Response: {full_ai_response}")

                    # Stream the complete response back (ensure it's a string)
                    def stream_complete_response():
                        # full_ai_response is guaranteed to be a string here due to initialization and try/except logic
                        yield full_ai_response

                    return Response(stream_with_context(stream_complete_response()), mimetype='text/plain')

                else: # useWebSearch is False
                    # --- Standard Streaming for Non-Web Search ---
                    llm = get_llm_instance(streaming=True) # Get streaming instance
                    def stream_standard_response():
                        full_ai_response = ""
                        try:
                            # Standard streaming loop
                            for chunk in llm.stream(messages_for_llm): # No tools needed here
                                content_chunk = chunk.content
                                if content_chunk:
                                    full_ai_response += content_chunk
                                    yield content_chunk
                        except Exception as stream_error:
                            logging.error(f"Error during LLM standard streaming: {type(stream_error).__name__} - {stream_error}", exc_info=True)
                            full_ai_response = "[Error generating AI response]"
                            yield full_ai_response
                        finally:
                            # Save context/message AFTER streaming
                            if full_ai_response and not full_ai_response.startswith("[Error"):
                                try:
                                    memory.save_context({"input": user_message}, {"output": full_ai_response})
                                    save_message(db, conversation_obj.id, 'ai', full_ai_response)
                                    logging.info(f"Saved context/message (native search: False) for conversation {conversation_obj.id}")
                                except Exception as save_error:
                                    logging.error(f"Failed to save context/message after standard stream: {save_error}")
                            elif not full_ai_response:
                                logging.warning(f"No AI response generated (native search: False) for conversation {conversation_obj.id}")

                    return Response(stream_with_context(stream_standard_response()), mimetype='text/plain')

        except ValueError as ve: # Catch API key error from get_llm_instance
             logging.error(f"Configuration error: {ve}")
             return jsonify({"error": "Server configuration error. AI features unavailable."}), 500
        except Exception as e:
            # General error during LLM interaction setup or invocation choice
            logging.error(f"Error during LLM interaction setup/dispatch for conversation {conversation_obj.id}: {e}", exc_info=True)
            return jsonify({"error": "Failed to get response from AI due to an internal error."}), 500

    except SQLAlchemyError as e:
         logging.error(f"Database operation failed: {e}", exc_info=True)
         # Rollback might be needed here if not handled in helpers
         db.rollback()
         return jsonify({"error": "Database error occurred"}), 500
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred"}), 500
    finally:
        if db:
            db.close()

@app.route('/api/upload', methods=['POST'])
@limiter.limit("5 per minute")  # Stricter rate limit for file uploads
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

    try:
        # Secure filename and create unique name for storage
        original_filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f") # Added microseconds for better uniqueness
        unique_filename = f"{timestamp}_{original_filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

        # Save file with unique name
        file.save(file_path)
        logging.info(f"Saved uploaded file temporarily to: {file_path}")

        # Process the document/image using the saved file path
        try:
            processed_docs = process_document(file_path)
        except Exception as processing_error:
             logging.error(f"Error processing document {file_path}: {processing_error}", exc_info=True)
             # Clean up failed upload attempt
             if os.path.exists(file_path):
                 try:
                     os.remove(file_path)
                     logging.info(f"Cleaned up failed upload: {file_path}")
                 except OSError as remove_error:
                      logging.error(f"Error removing failed upload file {file_path}: {remove_error}")
             return jsonify({"error": f"Error processing document: {processing_error}"}), 500

        # Get user and conversation
        db = next(get_db())
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            if not user_name:
                 # Clean up file if user not found and no name provided
                 if os.path.exists(file_path):
                     try:
                         os.remove(file_path)
                         logging.info(f"Cleaned up upload for non-existent user: {file_path}")
                     except OSError as remove_error:
                          logging.error(f"Error removing file for non-existent user {file_path}: {remove_error}")
                 # Ensure db is closed before returning
                 if db:
                     db.close()
                 return jsonify({"error": "User not found and no name provided"}), 401
            user = get_or_create_user(db, user_name, user_email)

        conversation = get_latest_conversation(db, user.id)
        if not conversation:
            conversation = create_conversation(db, user.id)

        # Determine content for DB based on file type BEFORE saving
        is_image = processed_docs and processed_docs[0].metadata.get('type') == 'image'
        if is_image:
            db_content = processed_docs[0].page_content if processed_docs else "[Image data unavailable]"
        else:
            db_content = "\n".join(p_doc.page_content for p_doc in processed_docs) if processed_docs else "[Document content unavailable]"

        # --- LLM Invocation Removed ---

        # --- Save Document and User Upload Message Only ---
        doc = None # Initialize doc to None
        try:
            # Save the document record using the ORIGINAL filename
            doc = DBDocument(
                filename=original_filename, # Use original filename here
                content=db_content,
                user_id=user.id
            )
            db.add(doc)
            db.commit()
            db.refresh(doc)

            # Save ONLY the user upload message using the ORIGINAL filename
            upload_message_content = f"[Uploaded {'image' if is_image else 'document'}: {original_filename}]" # Use original filename here
            save_message(db, conversation.id, 'user', upload_message_content)
            logging.info(f"Saved user upload notification for {original_filename}")

        except SQLAlchemyError as db_error:
             logging.error(f"Database error saving document record for {original_filename}: {db_error}", exc_info=True)
             db.rollback()
             # Clean up file if DB save fails
             if os.path.exists(file_path):
                 try:
                     os.remove(file_path)
                     logging.info(f"Cleaned up file due to DB error: {file_path}")
                 except OSError as remove_error:
                      logging.error(f"Error removing file after DB error {file_path}: {remove_error}")
             # Ensure db is closed before returning
             if db:
                 db.close()
             return jsonify({"error": "Failed to save upload details to database."}), 500

        # --- File Deletion Removed ---
        # We no longer delete the file from the uploads folder on success.
        # if os.path.exists(file_path):
        #     os.remove(file_path)
        #     logging.info(f"Cleaned up temporary file: {file_path}")
        logging.info(f"Keeping uploaded file: {file_path}")

        # Ensure doc object was created before returning its ID
        if doc is None:
             logging.error(f"DBDocument object 'doc' was None after commit for {original_filename}.")
             # File should still exist here if DB commit failed silently, attempt cleanup
             if os.path.exists(file_path):
                 try:
                     os.remove(file_path)
                     logging.info(f"Cleaned up file due to missing DB doc object: {file_path}")
                 except OSError as remove_error:
                      logging.error(f"Error removing file after missing DB doc {file_path}: {remove_error}")
             # Ensure db is closed before returning error
             if db:
                 db.close()
             return jsonify({"error": "Failed to create document record in database."}), 500

        logging.info(f"Successfully processed and saved upload: {original_filename}, DB ID: {doc.id}, Stored as: {unique_filename}")
        # Return confirmation message, ORIGINAL filename, and document ID
        if db: # Ensure db is closed on successful completion
            db.close()
        return jsonify({
            "message": f"Successfully uploaded {original_filename}", # Simple confirmation
            "filename": original_filename, # Original filename for context
            "documentId": doc.id # ID for future reference
        })

    except Exception as e:
        # Add more detailed logging including the exception type and traceback
        logging.error(f"An unexpected error occurred during file upload: {type(e).__name__} - {e}", exc_info=True)
        # Clean up file if it exists and an error occurred before successful processing/DB save
        # Use 'file_path' which includes the unique name if it was assigned
        current_file_path = locals().get('file_path')
        if current_file_path and os.path.exists(current_file_path):
             try:
                 os.remove(current_file_path)
                 logging.info(f"Cleaned up file due to unexpected error: {current_file_path}")
             except OSError as remove_error:
                  logging.error(f"Error removing file after unexpected error {current_file_path}: {remove_error}")
        # Ensure db is closed in the final exception handler if it exists and wasn't closed
        db_session = locals().get('db') # Use locals().get to safely access db
        if db_session and hasattr(db_session, 'is_active') and db_session.is_active:
            db_session.close()
            logging.info("DB session closed in final exception handler.")
        elif db_session and not hasattr(db_session, 'is_active'): # Fallback for sessions without is_active
             try:
                 db_session.close()
                 logging.info("DB session closed via fallback in final exception handler.")
             except Exception as close_err:
                 logging.error(f"Error closing DB session on fallback: {close_err}")
        # Return the generic error message that the user sees
        return jsonify({"error": "Failed to process upload"}), 500

# --- New Endpoint for Conversation History ---
@app.route('/api/conversation/history', methods=['GET'])
@limiter.limit("10 per minute") # Apply rate limiting
def get_conversation_history():
    user_email = request.args.get('email')
    if not user_email:
        return jsonify({"error": "Email parameter is required"}), 400

    db = next(get_db())
    try:
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            # It's better to close the session before returning
            db.close()
            return jsonify({"error": "User not found"}), 404

        conversation = get_latest_conversation(db, user.id)
        if not conversation:
            # Close session before returning
            db.close()
            return jsonify({"messages": []}), 200 # Return empty list if no conversation

        messages = db.query(Message)\
                     .filter(Message.conversation_id == conversation.id)\
                     .order_by(Message.timestamp.asc())\
                     .all()

        # Format messages for JSON response
        history = [{"sender": msg.sender, "content": msg.content, "timestamp": msg.timestamp.isoformat()} for msg in messages]

        logging.info(f"Retrieved conversation history for user {user_email}, conversation {conversation.id}")
        return jsonify({"messages": history})

    except SQLAlchemyError as e:
        logging.error(f"Database error fetching history for {user_email}: {e}", exc_info=True)
        return jsonify({"error": "Database error occurred"}), 500
    except Exception as e:
        logging.error(f"Unexpected error fetching history for {user_email}: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred"}), 500
    finally:
        # Ensure DB session is always closed
        if db:
            db.close()

def check_tesseract():
    """Check if tesseract is properly installed and accessible."""
    if not TESSERACT_AVAILABLE:
        return False
    try:
        pytesseract.get_tesseract_version()
        logging.info("Tesseract OCR is available and working")
        return True
    except Exception as e:
        logging.error(f"Tesseract OCR is not properly installed: {e}")
        logging.error("Please install tesseract-ocr using your system package manager")
        return False


# Add before the if __name__ == '__main__' block
@app.route('/')
def index():
    # Use relative path from backend to frontend for Gunicorn compatibility
    frontend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../frontend')
    return send_from_directory(frontend_path, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    # Use relative path from backend to frontend for Gunicorn compatibility
    frontend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../frontend')
    return send_from_directory(frontend_path, path)


if __name__ == '__main__':
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        logging.error("OPENAI_API_KEY environment variable not set. AI features will not work.")
        exit("Error: OPENAI_API_KEY not set.")

    # Check Tesseract availability at startup
    OCR_ENABLED = check_tesseract()
    if not OCR_ENABLED:
        logging.warning("OCR features will be limited to basic image information")

    # Ensure the backend directory exists if running from root
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(backend_dir, "chat_history.db")
    logging.info(f"Database path: {db_path}")

    # Production configuration
    os.environ['FLASK_ENV'] = 'production'
    app.config['DEBUG'] = False
    app.config['TESTING'] = False
    app.config['PROPAGATE_EXCEPTIONS'] = True

    # Use gunicorn in production
    if os.getenv('FLASK_ENV') == 'production':
        # Gunicorn will be used to run the app
        pass
    else:
        app.run(host='0.0.0.0', port=5001)
