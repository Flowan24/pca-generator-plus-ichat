"""
Business logic services for the iChat application.
Handles document processing, LLM interaction, and user/conversation management.
"""
import os
import logging
from collections import OrderedDict
from base64 import b64encode

from sqlalchemy.exc import SQLAlchemyError
from langchain_openai import ChatOpenAI
from langchain_classic.memory import ConversationBufferWindowMemory
from langchain_core.messages import HumanMessage
from langchain_core.documents import Document as LangchainDocument
from langchain_community.document_loaders import TextLoader, UnstructuredWordDocumentLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import (
    LLM_MODEL_NAME, LLM_TEMPERATURE, OPENAI_API_KEY,
    ALLOWED_EXTENSIONS, CONVERSATION_MEMORY_MAX_SIZE, CONVERSATION_WINDOW_SIZE,
)
from models import User, Conversation, Message, DBDocument

# --- OCR Dependencies ---
try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    logging.error("pytesseract not installed. OCR features will be limited.")


# --- LRU-bounded Conversation Memory Cache ---
class LRUMemoryCache:
    """Thread-safe-ish LRU cache for conversation memories to prevent unbounded growth."""

    def __init__(self, max_size: int):
        self._max_size = max_size
        self._cache: OrderedDict[str, ConversationBufferWindowMemory] = OrderedDict()

    def get(self, key: str) -> ConversationBufferWindowMemory | None:
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def set(self, key: str, memory: ConversationBufferWindowMemory):
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= self._max_size:
                evicted_key, _ = self._cache.popitem(last=False)
                logging.info(f"Evicted conversation memory: {evicted_key}")
        self._cache[key] = memory

    def __contains__(self, key: str) -> bool:
        return key in self._cache


conversation_memories = LRUMemoryCache(CONVERSATION_MEMORY_MAX_SIZE)


# --- User & Conversation Helpers ---
def get_or_create_user(db, name: str, email: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        try:
            user = User(name=name, email=email)
            db.add(user)
            db.flush()
            logging.info(f"Created new user: {name} ({email})")
        except SQLAlchemyError as e:
            db.rollback()
            logging.error(f"Database error creating user {email}: {e}")
            raise
    return user


def create_conversation(db, user_id: int) -> Conversation:
    try:
        conversation = Conversation(user_id=user_id)
        db.add(conversation)
        db.flush()
        logging.info(f"Created new conversation (ID: {conversation.id}) for user ID {user_id}")
        return conversation
    except SQLAlchemyError as e:
        db.rollback()
        logging.error(f"Database error creating conversation for user ID {user_id}: {e}")
        raise


def get_latest_conversation(db, user_id: int) -> Conversation | None:
    return (
        db.query(Conversation)
        .filter(Conversation.user_id == user_id)
        .order_by(Conversation.start_timestamp.desc())
        .first()
    )


def save_message(db, conversation_id: int, sender: str, content: str,
                 used_web_search: bool = False, document_id: int = None):
    try:
        message = Message(
            conversation_id=conversation_id,
            sender=sender,
            content=content,
            used_web_search=used_web_search,
            document_id=document_id,
        )
        db.add(message)
        db.flush()
        log_meta = []
        if used_web_search:
            log_meta.append("web_search=True")
        if document_id:
            log_meta.append(f"doc_id={document_id}")
        log_suffix = f" ({', '.join(log_meta)})" if log_meta else ""
        logging.info(f"Saved {sender} message for conversation ID {conversation_id}{log_suffix}")
    except SQLAlchemyError as e:
        db.rollback()
        logging.error(f"Database error saving message for conversation ID {conversation_id}: {e}")
        raise


# --- LLM ---
def get_llm_instance(streaming: bool = False) -> ChatOpenAI:
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not set in environment variables.")

    return ChatOpenAI(
        model_name=LLM_MODEL_NAME,
        temperature=LLM_TEMPERATURE,
        streaming=streaming,
        openai_api_key=OPENAI_API_KEY,
        max_tokens=None,
    )


def get_memory_for_conversation(user_email: str, conversation_id: int) -> ConversationBufferWindowMemory:
    """Gets or creates a conversation memory, rehydrating from DB if needed."""
    memory_key = f"{user_email}_{conversation_id}"
    memory = conversation_memories.get(memory_key)
    if memory is None:
        logging.info(f"Creating new conversation memory for key: {memory_key}")
        memory = ConversationBufferWindowMemory(
            k=CONVERSATION_WINDOW_SIZE, memory_key="chat_history", return_messages=True
        )
        # Rehydrate from database so memory survives server restarts
        _rehydrate_memory_from_db(memory, conversation_id)
        conversation_memories.set(memory_key, memory)
    return memory


def _rehydrate_memory_from_db(memory: ConversationBufferWindowMemory, conversation_id: int):
    """Load existing messages from DB into a fresh ConversationBufferWindowMemory."""
    from models import get_db, Message as MessageModel
    try:
        with get_db() as db:
            messages = (
                db.query(MessageModel)
                .filter(MessageModel.conversation_id == conversation_id)
                .order_by(MessageModel.timestamp.asc())
                .all()
            )
            # Group into (user, ai) pairs for save_context
            i = 0
            while i < len(messages):
                if messages[i].sender == 'user':
                    user_content = messages[i].content
                    ai_content = ""
                    if i + 1 < len(messages) and messages[i + 1].sender == 'ai':
                        ai_content = messages[i + 1].content
                        i += 2
                    else:
                        i += 1
                    if ai_content:
                        memory.save_context({"input": user_content}, {"output": ai_content})
                else:
                    i += 1  # skip orphaned ai messages
            if messages:
                logging.info(f"Rehydrated {len(messages)} messages into memory for conversation {conversation_id}")
    except Exception as e:
        logging.error(f"Failed to rehydrate memory for conversation {conversation_id}: {e}")


# --- Document Processing ---
def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def process_image(file_path: str) -> list[LangchainDocument]:
    try:
        with open(file_path, 'rb') as img_file:
            img_data = b64encode(img_file.read()).decode('utf-8')
            image = Image.open(file_path)
            image_url = f"data:image/{image.format.lower()};base64,{img_data}"
            document = LangchainDocument(
                page_content=image_url,
                metadata={
                    "source": file_path,
                    "type": "image",
                    "format": image.format,
                    "size": f"{image.size[0]}x{image.size[1]} pixels",
                },
            )
            return [document]
    except Exception as e:
        logging.error(f"Error processing image {file_path}: {e}")
        raise


def process_document(file_path: str) -> list[LangchainDocument]:
    extension = file_path.rsplit('.', 1)[-1].lower()

    try:
        if extension in ('png', 'jpg', 'jpeg'):
            return process_image(file_path)
        elif extension == 'txt':
            loader = TextLoader(file_path)
        elif extension == 'pdf':
            loader = PyPDFLoader(file_path)
        elif extension in ('doc', 'docx'):
            loader = UnstructuredWordDocumentLoader(file_path)
        else:
            raise ValueError(f"Unsupported file type: {extension}")

        documents = loader.load()
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=2000,
            chunk_overlap=200,
            length_function=len,
        )
        return text_splitter.split_documents(documents)
    except Exception as e:
        logging.error(f"Error processing document {file_path}: {e}")
        raise


# --- Tesseract Check ---
def check_tesseract() -> bool:
    if not TESSERACT_AVAILABLE:
        return False
    try:
        pytesseract.get_tesseract_version()
        logging.info("Tesseract OCR is available and working")
        return True
    except Exception as e:
        logging.error(f"Tesseract OCR is not properly installed: {e}")
        return False
