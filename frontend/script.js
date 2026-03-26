/**
 * @file script.js
 * @description Frontend logic for the iChat App.
 * Handles user login, message sending/display, file uploads,
 * API communication, internationalization (i18n), and UI updates.
 */

// Wait for the DOM to be fully loaded before executing script
document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Element References ---
        // DOM Elements
        const userForm = document.getElementById('user-form');
        const initialScreen = document.getElementById('initial-screen');
        const chatScreen = document.getElementById('chat-screen');
        const messageDisplay = document.getElementById('message-display');
        const messageInput = document.getElementById('user-message');
        const sendButton = document.getElementById('send-button');
        const userInfoDisplay = document.getElementById('user-info');
        const errorNotification = document.getElementById('error-notification');
        const errorMessage = document.getElementById('error-message');
        const logoutButton = document.getElementById('logout-button');
        const fileUpload = document.getElementById('file-upload');
        // const imageUpload = document.getElementById('image-upload'); // Removed
        const uploadButton = document.querySelector('.upload-button');
        const downloadChatButton = document.getElementById('download-chat-button');
        const webSearchToggleButton = document.getElementById('web-search-toggle'); // Added web search button
    
        // Update title for single upload button
        // uploadButton.setAttribute('title', 'Upload File (TXT, PDF, DOC, DOCX, PNG, JPG, JPEG)'); // Title set by translation
    
    // --- Application Constants ---
        /** @constant {number} Maximum allowed length for a user message. */
        /** @constant {number} Maximum allowed file size for uploads in bytes (5MB). */
        /** @constant {string[]} Array of allowed file extensions for uploads. */
        /** @constant {number} Maximum number of retries for failed API calls. */
        /** @constant {number} Delay in milliseconds between API call retries. */
        /** @constant {string} URL endpoint for the backend chat API. */
        /** @constant {string} URL endpoint for the backend file upload API. */
        // Constants
    /**
         * @typedef {Object.<string, Object.<string, string>>} Translations
         * @description Contains UI string translations for different languages (en, de).
         *              Keys are language codes (e.g., 'en'), values are objects
         *              mapping translation keys (e.g., 'loginTitle') to translated strings.
         */
        /** @type {Translations} */
        const MAX_MESSAGE_LENGTH = 10000;
        const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB
        const ALLOWED_FILE_TYPES = ['.txt', '.pdf', '.doc', '.docx', '.png', '.jpg', '.jpeg'];
        const MAX_RETRIES = 3;
        const RETRY_DELAY = 1000; // milliseconds
        // Use relative URLs for API endpoints to work with any server configuration
        const API_ENDPOINT = '/ichat/api/chat'; // Backend API endpoint
        const UPLOAD_ENDPOINT = '/ichat/api/upload'; // File upload endpoint
        const HISTORY_ENDPOINT = '/ichat/api/conversation/history';

        // --- Shared Helpers ---
        /** Render markdown with DOMPurify sanitization. */
        function renderMarkdown(text) {
            const raw = marked.parse(text, { gfm: true, breaks: true });
            return DOMPurify.sanitize(raw);
        }

        /** Create a copy button for AI messages. */
        function createCopyButton(getTextFn) {
            const langTranslations = translations[currentLanguage] || translations.en;
            const btn = document.createElement('button');
            btn.className = 'copy-button';
            btn.title = langTranslations.copyButton || 'Copy to clipboard';
            btn.textContent = langTranslations.copyButton || 'Copy';
            btn.addEventListener('click', async () => {
                try {
                    await navigator.clipboard.writeText(getTextFn());
                    btn.classList.add('copied');
                    btn.textContent = langTranslations.copyButtonCopied || 'Copied!';
                    setTimeout(() => {
                        btn.classList.remove('copied');
                        btn.textContent = langTranslations.copyButton || 'Copy';
                        btn.title = langTranslations.copyButton || 'Copy to clipboard';
                    }, 2000);
                } catch (err) {
                    console.error('Failed to copy:', err);
                    showError('errorClipboard');
                }
            });
            return btn;
        }

        /** Extract just the message text from an AI message element (excluding the copy button text). */
        function getMessageText(element) {
            const clone = element.cloneNode(true);
            const btn = clone.querySelector('.copy-button');
            if (btn) btn.remove();
            return clone.textContent.trim();
        }

        // --- Translations ---
        const translations = {
            en: {
                loginTitle: "iChat",
                nameLabel: "Name:",
                emailLabel: "Email:",
                startChatButton: "Start Chatting",
                chatTitle: "iChat",
                userInfo: "Logged in as: {userName} ({userEmail})",
                downloadButtonTitle: "Download Chat History",
                logoutButton: "Logout",
                uploadButtonTitle: "Upload File (TXT, PDF, DOC, DOCX, PNG, JPG, JPEG)",
                webSearchButtonTitle: "Toggle Web Search (Next Message)",
                webSearchActiveTitle: "Web Search ON (Next Message)",
                messagePlaceholder: "Type your message...",
                sendButtonLabel: "Send message",
                aiTyping: "AI is typing",
                copyButton: "Copy",
                copyButtonCopied: "Copied!",
                errorNoHistory: "No conversation history found to download.",
                errorUserNotFound: "Cannot download history: User email not found.",
                errorUploadSize: `File exceeds ${MAX_FILE_SIZE / 1024 / 1024}MB limit.`, // Use constant
                errorUploadType: `Invalid file type. Allowed types: ${ALLOWED_FILE_TYPES.join(', ')}`, // Use constant
                errorUploadGeneral: "File upload failed.",
                errorLoginGeneric: "Login failed. Please try again.",
                errorSendGeneric: "Failed to send message. Please try again.",
                errorFetchHistory: "Failed to fetch chat history.",
                uploadSuccess: "Successfully uploaded {filename}", // Used in displayMessage potentially
                uploadProcessing: "Processing {filename}...", // Not currently used, but good to have
                uploadMessageUser: "{icon} Uploaded: {filename}", // For user message display
                uploadFollowupPlaceholder: "Ask a question about {filename}...", // Placeholder after upload
                errorGeneric: "An error occurred: {message}", // Generic error display
                errorRetry: "Connection failed. Retrying... ({count}/{max})", // Retry message
                errorStreaming: "[Error during streaming]", // Append to message on stream error
                errorNoResponse: "[No response received from AI]", // If stream ends with no data
                errorClipboard: "Failed to copy to clipboard.",
                // Language switcher titles
                switchToEnglish: "Switch to English",
                switchToGerman: "Auf Deutsch wechseln",
                switchToSpanish: "Cambiar a Español",
            },
            de: {
                loginTitle: "iChat",
                nameLabel: "Name:",
                emailLabel: "E-Mail:",
                startChatButton: "Chat starten",
                chatTitle: "iChat",
                userInfo: "Angemeldet als: {userName} ({userEmail})",
                downloadButtonTitle: "Chatverlauf herunterladen",
                logoutButton: "Abmelden",
                uploadButtonTitle: "Datei hochladen (TXT, PDF, DOC, DOCX, PNG, JPG, JPEG)",
                webSearchButtonTitle: "Websuche umschalten (Nächste Nachricht)",
                webSearchActiveTitle: "Websuche EIN (Nächste Nachricht)",
                messagePlaceholder: "Nachricht eingeben...",
                sendButtonLabel: "Nachricht senden",
                aiTyping: "KI schreibt",
                copyButton: "Kopieren",
                copyButtonCopied: "Kopiert!",
                errorNoHistory: "Kein Chatverlauf zum Herunterladen gefunden.",
                errorUserNotFound: "Verlauf kann nicht heruntergeladen werden: Benutzer-E-Mail nicht gefunden.",
                errorUploadSize: `Datei überschreitet das Limit von ${MAX_FILE_SIZE / 1024 / 1024}MB.`, // Use constant
                errorUploadType: `Ungültiger Dateityp. Erlaubt: ${ALLOWED_FILE_TYPES.join(', ')}`, // Use constant
                errorUploadGeneral: "Datei-Upload fehlgeschlagen.",
                errorLoginGeneric: "Anmeldung fehlgeschlagen. Bitte versuchen Sie es erneut.",
                errorSendGeneric: "Nachricht konnte nicht gesendet werden. Bitte versuchen Sie es erneut.",
                errorFetchHistory: "Chatverlauf konnte nicht abgerufen werden.",
                uploadSuccess: "{filename} erfolgreich hochgeladen", // Used in displayMessage potentially
                uploadProcessing: "Verarbeite {filename}...", // Not currently used, but good to have
                uploadMessageUser: "{icon} Hochgeladen: {filename}", // For user message display
                uploadFollowupPlaceholder: "Stellen Sie eine Frage zu {filename}...", // Placeholder after upload
                errorGeneric: "Ein Fehler ist aufgetreten: {message}", // Generic error display
                errorRetry: "Verbindung fehlgeschlagen. Wiederhole... ({count}/{max})", // Retry message
                errorStreaming: "[Fehler während des Streamings]", // Append to message on stream error
                errorNoResponse: "[Keine Antwort von KI erhalten]", // If stream ends with no data
                errorClipboard: "Kopieren in die Zwischenablage fehlgeschlagen.",
                // Language switcher titles
                switchToEnglish: "Switch to English",
                switchToGerman: "Auf Deutsch wechseln",
                switchToSpanish: "Cambiar a Español",
            },
            es: {
                loginTitle: "iChat",
                nameLabel: "Nombre:",
                emailLabel: "Correo electrónico:",
                startChatButton: "Iniciar Chat",
                chatTitle: "iChat",
                userInfo: "Conectado como: {userName} ({userEmail})",
                downloadButtonTitle: "Descargar Historial de Chat",
                logoutButton: "Cerrar Sesión",
                uploadButtonTitle: "Subir Archivo (TXT, PDF, DOC, DOCX, PNG, JPG, JPEG)",
                webSearchButtonTitle: "Alternar Búsqueda Web (Siguiente Mensaje)",
                webSearchActiveTitle: "Búsqueda Web ACTIVADA (Siguiente Mensaje)",
                messagePlaceholder: "Escribe tu mensaje...",
                sendButtonLabel: "Enviar mensaje",
                aiTyping: "IA está escribiendo",
                copyButton: "Copiar",
                copyButtonCopied: "¡Copiado!",
                errorNoHistory: "No se encontró historial de conversación para descargar.",
                errorUserNotFound: "No se puede descargar historial: Correo de usuario no encontrado.",
                errorUploadSize: `El archivo excede el límite de ${MAX_FILE_SIZE / 1024 / 1024}MB.`, // Use constant
                errorUploadType: `Tipo de archivo inválido. Tipos permitidos: ${ALLOWED_FILE_TYPES.join(', ')}`, // Use constant
                errorUploadGeneral: "Error al subir archivo.",
                errorLoginGeneric: "Error de inicio de sesión. Por favor intenta de nuevo.",
                errorSendGeneric: "Error al enviar mensaje. Por favor intenta de nuevo.",
                errorFetchHistory: "Error al obtener historial de chat.",
                uploadSuccess: "{filename} subido exitosamente", // Used in displayMessage potentially
                uploadProcessing: "Procesando {filename}...", // Not currently used, but good to have
                uploadMessageUser: "{icon} Subido: {filename}", // For user message display
                uploadFollowupPlaceholder: "Haz una pregunta sobre {filename}...", // Placeholder after upload
                errorGeneric: "Ocurrió un error: {message}", // Generic error display
                errorRetry: "Conexión fallida. Reintentando... ({count}/{max})", // Retry message
                errorStreaming: "[Error durante la transmisión]", // Append to message on stream error
                errorNoResponse: "[No se recibió respuesta de la IA]", // If stream ends with no data
                errorClipboard: "Error al copiar al portapapeles.",
                // Language switcher titles
                switchToEnglish: "Switch to English",
                switchToGerman: "Auf Deutsch wechseln",
                switchToSpanish: "Cambiar a Español",
            }
        };
        let currentLanguage = 'en'; // Default language
    
        // Document context storage
        let currentDocumentContext = null;
        // messageInput.placeholder = 'Type your message...'; // Placeholder will be set by applyTranslations
    
        // Web search state
        let isWebSearchEnabled = false;
    
        // --- Translation Functions ---
        function setLanguage(lang) {
            if (translations[lang]) {
                currentLanguage = lang;
                localStorage.setItem('preferredLanguage', lang); // Store preference
                applyTranslations();
            } else {
                console.warn(`Language '${lang}' not found.`);
            }
        }
    
        function applyTranslations() {
            const langTranslations = translations[currentLanguage];
            if (!langTranslations) {
                console.error(`Translations for language '${currentLanguage}' not found.`);
                return;
            }
    
            // Set HTML lang attribute
            document.documentElement.lang = currentLanguage;
    
            document.querySelectorAll('[data-i18n-key]').forEach(element => {
                const key = element.getAttribute('data-i18n-key');
                let translation = langTranslations[key];
    
                if (translation !== undefined) {
                    // Handle placeholders like {userName}
                    if (translation.includes('{userName}')) {
                        translation = translation.replace('{userName}', userName || '');
                    }
                    if (translation.includes('{userEmail}')) {
                        translation = translation.replace('{userEmail}', userEmail || '');
                    }
    
                    // Apply translation based on element type/attribute
                    if (element.tagName === 'TITLE') {
                        document.title = translation;
                    } else if (element.hasAttribute('placeholder')) {
                        element.placeholder = translation;
                    } else if (element.hasAttribute('title')) {
                        element.title = translation;
                    } else if (element.hasAttribute('aria-label')) {
                        element.setAttribute('aria-label', translation);
                        // Also update textContent if it's a button with text and no icon (like logout)
                        if (element.tagName === 'BUTTON' && !element.querySelector('svg') && !element.querySelector('img')) {
                             // Check if it's the logout button specifically or similar text-only buttons
    /**
         * Updates the `title` and `aria-label` attributes of dynamic elements
         * (like buttons with changing states) based on the current language and application state.
         * This includes the web search toggle, upload button, download button, send button,
         * and language switcher buttons.
         */
                             if (key === 'logoutButton' || key === 'startChatButton') {
                                element.textContent = translation;
                             }
                        }
                    } else if (element.tagName === 'LABEL' && element.htmlFor) {
                        // Update label text, preserving any child elements like input fields if necessary
                        // Find the text node directly within the label, if any
                        let textNode = Array.from(element.childNodes).find(node => node.nodeType === Node.TEXT_NODE && node.textContent.trim());
                        if (textNode) {
                            textNode.textContent = translation;
                        } else {
                            // Fallback if no direct text node (e.g., label wraps input)
                            element.textContent = translation; // This might overwrite other content, use with caution
                        }
                    }
                    else {
                        element.textContent = translation;
                    }
                } else {
                    console.warn(`Translation key '${key}' not found for language '${currentLanguage}'.`);
                }
            });
    
            // Update dynamic elements that might change state or content
            updateDynamicTitles();
            updateUserInfoDisplay(); // Ensure user info uses the correct language string
            updateDynamicPlaceholders(); // Update placeholders that might depend on context
            updateDynamicTextContent(); // Update other dynamic text like AI typing indicator
        }
    
        function updateDynamicTitles() {
            const langTranslations = translations[currentLanguage];
            if (!langTranslations) return;
    
    /**
         * Updates the user information display element (`userInfoDisplay`)
         * with the logged-in user's name and email, using the appropriate translated string.
         * Clears the display if the user is not logged in.
         */
            // Update web search button title based on current state and language
            const webSearchKey = isWebSearchEnabled ? 'webSearchActiveTitle' : 'webSearchButtonTitle';
            webSearchToggleButton.title = langTranslations[webSearchKey] || webSearchToggleButton.title; // Fallback to existing title
            webSearchToggleButton.setAttribute('aria-label', webSearchToggleButton.title); // Update aria-label too
    
            // Update upload button title (label element)
            const uploadKey = 'uploadButtonTitle';
            const uploadLabelElement = document.querySelector('label[for="file-upload"]');
            if (uploadLabelElement) {
    /**
         * Updates the placeholder text and aria-label of the message input field (`messageInput`).
         * Uses a specific placeholder if `currentDocumentContext` is set (prompting for questions about the file),
         * otherwise uses the default message placeholder for the current language.
         */
                uploadLabelElement.title = langTranslations[uploadKey] || uploadLabelElement.title;
                uploadLabelElement.setAttribute('aria-label', uploadLabelElement.title); // Update aria-label too
            }
    
            // Update download button title
            const downloadKey = 'downloadButtonTitle';
            downloadChatButton.title = langTranslations[downloadKey] || downloadChatButton.title;
            downloadChatButton.setAttribute('aria-label', downloadChatButton.title); // Update aria-label too
    
    /**
          * Updates the text content of dynamic elements that might change during the chat,
          * such as the AI typing indicator and the text/title of copy buttons on existing messages.
          * Ensures these elements reflect the current language.
          */
            // Update send button aria-label
            const sendKey = 'sendButtonLabel';
            sendButton.setAttribute('aria-label', langTranslations[sendKey] || 'Send message');
    
            // Update language switcher titles and active state
            const langEnButton = document.getElementById('lang-en');
            const langDeButton = document.getElementById('lang-de');
            const langEsButton = document.getElementById('lang-es');
            if (langEnButton) {
                langEnButton.title = langTranslations['switchToEnglish'] || 'Switch to English';
                langEnButton.classList.toggle('active-lang', currentLanguage === 'en'); // Add active class toggle
            }
            if (langDeButton) {
                langDeButton.title = langTranslations['switchToGerman'] || 'Auf Deutsch wechseln';
                langDeButton.classList.toggle('active-lang', currentLanguage === 'de'); // Add active class toggle
            }
            if (langEsButton) {
                langEsButton.title = langTranslations['switchToSpanish'] || 'Cambiar a Español';
                langEsButton.classList.toggle('active-lang', currentLanguage === 'es'); // Add active class toggle
            }
        }
    
        function updateUserInfoDisplay() {
            const langTranslations = translations[currentLanguage];
    /**
         * Validates a file based on allowed types and maximum size.
         * @param {File} file - The file object to validate.
         * @returns {{valid: boolean, error?: string}} An object indicating if the file is valid.
         *                                             If invalid, includes a translated error message.
         */
            if (!langTranslations) return;
    
            if (userName && userEmail) {
                let userInfoText = langTranslations.userInfo || "Logged in as: {userName} ({userEmail})";
                userInfoText = userInfoText.replace('{userName}', userName).replace('{userEmail}', userEmail);
                userInfoDisplay.textContent = userInfoText;
            } else {
                userInfoDisplay.textContent = ''; // Clear if not logged in
            }
    /**
         * Handles the file upload process: validates the file, sends it to the backend,
         * displays an "Uploaded" message for the user, stores the document context,
         * and updates the input placeholder to prompt for questions about the file.
         * Shows errors if validation or upload fails.
         * @param {File} file - The file selected by the user.
         * @returns {Promise<void>}
         */
        }
    
        function updateDynamicPlaceholders() {
            const langTranslations = translations[currentLanguage];
            if (!langTranslations) return;
    
            // Update message input placeholder based on context
            if (currentDocumentContext && currentDocumentContext.filename) {
                 let placeholderText = langTranslations.uploadFollowupPlaceholder || "Ask a question about {filename}...";
                 messageInput.placeholder = placeholderText.replace('{filename}', currentDocumentContext.filename);
            } else {
                 messageInput.placeholder = langTranslations.messagePlaceholder || "Type your message...";
            }
            // Update aria-label as well
            messageInput.setAttribute('aria-label', messageInput.placeholder);
        }
    
         function updateDynamicTextContent() {
            const langTranslations = translations[currentLanguage] || translations.en;
            if (!langTranslations) return;
    
            // Update existing AI typing indicator if present
            const typingIndicator = messageDisplay.querySelector('.ai-typing');
            if (typingIndicator) {
                typingIndicator.textContent = langTranslations.aiTyping || 'AI is typing';
            }
    
            // Update copy buttons on existing messages
            messageDisplay.querySelectorAll('.message.ai-message .copy-button').forEach(button => {
                // Update title attribute as well
                button.title = langTranslations.copyButton || 'Copy to clipboard';
                if (button.classList.contains('copied')) {
                    button.textContent = langTranslations.copyButtonCopied || 'Copied!';
                } else {
                    button.textContent = langTranslations.copyButton || 'Copy';
                }
            });
        }
    
        // --- Helper Functions (Existing) ---
        function validateFile(file) {
            const langTranslations = translations[currentLanguage] || translations.en; // Fallback to English for errors
            const extension = '.' + file.name.split('.').pop().toLowerCase();
            if (!ALLOWED_FILE_TYPES.includes(extension)) {
                // Use the specific error key from translations
                return { valid: false, error: langTranslations.errorUploadType || `Invalid file type. Allowed types: ${ALLOWED_FILE_TYPES.join(', ')}` };
            }
            if (file.size > MAX_FILE_SIZE) {
                 // Use the specific error key from translations
                return { valid: false, error: langTranslations.errorUploadSize || `File size exceeds ${MAX_FILE_SIZE / 1024 / 1024}MB limit` };
            }
            return { valid: true };
        }
    
        async function handleFileUpload(file) {
            const validation = validateFile(file);
            if (!validation.valid) {
                showError(validation.error); // Show the potentially translated error
                return;
            }
    
            // Create form data
            const formData = new FormData();
            formData.append('file', file);
            formData.append('email', userEmail);
            // Only send name if it's the first message overall, might need adjustment
            // For simplicity, let's assume backend handles user creation if needed
            if (isFirstMessage) {
                 formData.append('name', userName);
            }
    
            // Add uploading class for animation (targets the single button's parent)
            uploadButton.parentElement.classList.add('uploading'); // Assuming label is the button visually
    
            try {
                const response = await fetch(UPLOAD_ENDPOINT, {
                    method: 'POST',
                    body: formData
                });
    
                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({ error: 'Unknown server error' }));
                    // Use translated general upload error key
                    throw new Error(translations[currentLanguage]?.errorUploadGeneral || `Upload failed: ${errorData.error}`);
                }
    
                const data = await response.json(); // Should now contain { message: "Confirmation", filename, documentId }
                const langTranslations = translations[currentLanguage] || translations.en;
    
                // Determine if it was an image or document based on file type
                const isImage = file.type.startsWith('image/');
                const fileTypeIcon = isImage ? '🖼️' : '📄';
                // const fileTypeString = isImage ? (langTranslations.imageType || 'image') : (langTranslations.documentType || 'document'); // For translated message
    
                // Store context (useful for follow-up questions about the specific file)
                currentDocumentContext = {
                    filename: file.name, // Use original filename
                    documentId: data.documentId
                };
    
                // Display uploaded file message (using original filename and translated template)
                let uploadMsg = langTranslations.uploadMessageUser || "{icon} Uploaded: {filename}";
                uploadMsg = uploadMsg.replace('{icon}', fileTypeIcon).replace('{filename}', file.name);
                displayMessage(uploadMsg, 'user-message');
    
                // --- Removed display of AI response ---
                // The backend no longer sends an AI analysis in the upload response.
                // We only show the confirmation message logged by the backend implicitly via the user message above.
    
                // Update input placeholder using translated template
                updateDynamicPlaceholders(); // Use the function to handle this
                messageInput.focus();
    
            } catch (error) {
                console.error('Error uploading file:', error);
                showError(error.message); // Show the potentially translated error
                currentDocumentContext = null; // Clear context on error
            } finally {
                // Remove uploading animation
                 uploadButton.parentElement.classList.remove('uploading');
            }
        }
    
        // Single file upload event listener for the merged input
        fileUpload.addEventListener('change', (event) => {
            const file = event.target.files[0];
            if (file) {
                handleFileUpload(file); // Call the updated handler
            }
            // Reset file input to allow uploading the same file again
            event.target.value = '';
        });
    
        // Removed the separate image upload event listener block
    
        let userName = sessionStorage.getItem('userName') || '';
        let userEmail = sessionStorage.getItem('userEmail') || '';
        let isFirstMessage = true;
    
        // --- Initialization (on DOMContentLoaded) ---
    
        // Initialize language (before setting user info or showing screens)
        const preferredLanguage = localStorage.getItem('preferredLanguage');
        // Don't call applyTranslations here yet, wait until user info is potentially loaded
    
        // Check if user is already logged in
        if (userName && userEmail) {
            // User info is available, set language and apply translations
            setLanguage(preferredLanguage || 'en');
            // userInfoDisplay.textContent = `Logged in as: ${userName} (${userEmail})`; // Handled by applyTranslations -> updateUserInfoDisplay
            // updateUserInfoDisplay(); // Called by setLanguage -> applyTranslations
            initialScreen.style.display = 'none';
            chatScreen.style.display = 'flex';
            chatScreen.style.flexDirection = 'column';
            messageDisplay.style.display = 'flex';
            messageDisplay.style.flexDirection = 'column';
        } else {
            // Not logged in, apply translations for the login screen
            setLanguage(preferredLanguage || 'en');
            initialScreen.style.display = 'block'; // Ensure login screen is visible
    /**
         * Sends the user's message to the backend API.
         * Displays the user's message in the chat, clears the input field,
         * prepares the payload (including user info, document context, and web search flag),
         * resets document context if applicable, calls the `callChatAPI` function,
         * and updates the `isFirstMessage` flag.
         */
            chatScreen.style.display = 'none';
        }
    
        // --- Initial Screen Logic ---
        userForm.addEventListener('submit', (event) => {
            event.preventDefault();
            userName = document.getElementById('name').value.trim();
            userEmail = document.getElementById('email').value.trim();
    
            if (userName && userEmail) {
                // Save to session storage
                sessionStorage.setItem('userName', userName);
                sessionStorage.setItem('userEmail', userEmail);
    
                // Update display using translation function (already called by applyTranslations)
                // updateUserInfoDisplay();
                // Apply all translations again to update user info string and potentially other elements
                applyTranslations();
    
                initialScreen.style.display = 'none';
                chatScreen.style.display = 'flex';
                chatScreen.style.flexDirection = 'column';
                messageDisplay.style.display = 'flex';
                messageDisplay.style.flexDirection = 'column';
                messageInput.focus();
            } else {
                 // Optional: Show login error using translated key
                 showError('errorLoginGeneric');
            }
        });
    
        // --- Chat Screen Logic ---
        sendButton.addEventListener('click', sendMessage);
    
        // Send message on Enter key press, allow Shift+Enter for newline
        messageInput.addEventListener('keydown', function(event) {
            // Check if the key pressed was Enter
            if (event.key === 'Enter') {
                if (!event.shiftKey) {
    /**
         * Appends a message to the chat display area.
         * Handles different styling for user and AI messages.
         * Renders AI messages using marked.js for Markdown support.
         * Adds a copy button to AI messages.
         * Scrolls the chat display to the bottom.
         * @param {string} text - The message content.
         * @param {'user-message' | 'ai-message' | 'ai-message error'} type - The type of message (determines styling and features).
         */
                    // --- Enter key pressed WITHOUT Shift key ---
                    // Prevent the default action (which is usually adding a newline in a textarea,
                    // but can also submit forms if not prevented)
                    event.preventDefault();
                    // Call the sendMessage function
                    sendMessage();
                }
                // Implicit else:
                // --- Enter key pressed WITH Shift key ---
                // The default action (inserting a newline) is allowed to happen.
                // No event.preventDefault() here.
            }
        });
    
        // Auto-resize textarea height on input
        messageInput.addEventListener('input', function() {
            this.style.height = 'auto'; // Reset height to recalculate
            this.style.height = (this.scrollHeight) + 'px'; // Set height to scroll height
        });
    
        function sendMessage() {
            const messageText = messageInput.value.trim();
            if (!messageText) return;
    
            displayMessage(messageText, 'user-message');
            messageInput.value = '';
            // Reset textarea height after sending
            messageInput.style.height = 'auto';
            messageInput.style.height = (messageInput.scrollHeight) + 'px';
            messageInput.focus();
    
    
            // Prepare data for backend
            const payload = {
                message: messageText,
                email: userEmail, // Send email with every request for identification
                documentContext: currentDocumentContext // Include document context if available
            };
            if (isFirstMessage) {
                payload.name = userName; // Send name only on the first message
            }
    
            // Reset document context and update placeholder after processing a document-related query
    /**
         * Displays an error message in the notification bar.
         * Looks up the message text using the provided key in the current language's translations.
         * If the key is not found, the provided string is displayed directly.
         * Supports replacing placeholders (e.g., `{count}`) in the translated string using the `params` object.
         * The notification automatically hides after 5 seconds.
         * @param {string} messageKeyOrText - The translation key or the literal error message text.
         * @param {Object.<string, string|number>} [params={}] - Optional parameters to replace placeholders in the message.
         */
            if (currentDocumentContext) {
                currentDocumentContext = null;
                updateDynamicPlaceholders(); // Reset placeholder to default translated version
            }
    
            // Add the web search flag to the payload
            payload.useWebSearch = isWebSearchEnabled;
    
            // Call backend API
            callChatAPI(payload);
    
            // Set isFirstMessage to false after first message
    /**
         * Validates a user message before sending it to the API.
         * Checks if the message is empty or exceeds the maximum length.
         * @param {string} message - The message text to validate.
         * @returns {{valid: boolean, error?: string}} An object indicating if the message is valid.
         *                                             If invalid, includes an error message (currently not translated).
         */
            isFirstMessage = false;
    
            // Reset web search toggle and update its title after sending message
            if (isWebSearchEnabled) {
                isWebSearchEnabled = false;
                webSearchToggleButton.classList.remove('active');
                updateDynamicTitles(); // Update title based on new state and language
    /**
         * Calls the backend chat API to get a response from the AI.
         * Handles streaming responses, displaying a typing indicator, rendering Markdown,
         * adding copy buttons, and managing errors with a retry mechanism.
         *
         * Process:
         * 1. Validates the message payload.
         * 2. Sends the payload to the `API_ENDPOINT`.
         * 3. If the response is OK (2xx status):
         *    a. Displays a typing indicator.
         *    b. Reads the response body as a stream.
         *    c. For each chunk received:
         *       i. Removes the typing indicator (on the first chunk).
         *       ii. Appends the chunk to the `currentAIResponse`.
         *       iii. Renders the `currentAIResponse` as Markdown in the AI message element.
         *       iv. Adds/updates a copy button.
         *       v. Scrolls the chat display down.
         *    d. Handles cases where the stream ends with no data or errors occur during streaming.
         * 4. If the response is not OK or a network error occurs:
         *    a. Removes the typing indicator.
         *    b. If the error is retryable (network error or 5xx) and retries < MAX_RETRIES:
         *       i. Shows a translated retry message.
         *       ii. Waits for `RETRY_DELAY` (increasing with each retry).
         *       iii. Calls `callChatAPI` again recursively.
         *    c. If the error is not retryable or max retries are reached:
         *       i. Appends a translated error message to the AI message element if it was partially displayed.
         *       ii. Displays a generic translated error message if the AI message element wasn't displayed.
         *       iii. Shows a generic translated error in the notification bar.
         *
         * @param {object} payload - The data object to send to the API.
         * @param {string} payload.message - The user's message.
         * @param {string} payload.email - The user's email.
         * @param {string} [payload.name] - The user's name (sent only on the first message).
         * @param {DocumentContext | null} payload.documentContext - Context about a previously uploaded document, if any.
         * @param {boolean} payload.useWebSearch - Flag indicating whether to use web search for this query.
         * @param {number} [retryCount=0] - The current retry attempt number (used internally for recursion).
         * @returns {Promise<void>}
         */
            }
        }
    
        function displayMessage(text, type) {
            console.log('Displaying message:', { text, type });
    
            const messageElement = document.createElement('div');
            messageElement.classList.add('message', type);
            const langTranslations = translations[currentLanguage] || translations.en;
    
            // Handle multiline text and code blocks
            if (type === 'ai-message' || type === 'ai-message error') {
                const textToCopy = text;
                messageElement.innerHTML = renderMarkdown(text);
                messageElement.appendChild(createCopyButton(() => textToCopy));
            } else {
                // For user messages, just display the text with basic line breaks
                messageElement.textContent = text;
            }
            messageDisplay.appendChild(messageElement);
            messageDisplay.scrollTop = messageDisplay.scrollHeight;
        }
    
        function showError(messageKeyOrText, params = {}) {
            const langTranslations = translations[currentLanguage] || translations.en;
            let messageText = langTranslations[messageKeyOrText] || messageKeyOrText; // Use key if found, else assume it's literal text
    
            // Replace placeholders in the message text
            for (const key in params) {
                messageText = messageText.replace(`{${key}}`, params[key]);
            }
    
            errorMessage.textContent = messageText;
            errorNotification.style.display = 'block';
            // Optionally hide after some time
            setTimeout(() => {
                errorNotification.style.display = 'none';
            }, 5000);
        }
    
        // --- API Call Logic ---
        // Validate message before sending (Use translated errors - though currently not shown directly)
        function validateMessage(message) {
            // const langTranslations = translations[currentLanguage] || translations.en;
            if (!message.trim()) {
                // return { valid: false, error: langTranslations.errorEmptyMessage || 'Message cannot be empty' };
                return { valid: false, error: 'Message cannot be empty' }; // Keep simple for now
            }
            if (message.length > MAX_MESSAGE_LENGTH) {
                // return { valid: false, error: langTranslations.errorMessageTooLong || `Message cannot exceed ${MAX_MESSAGE_LENGTH} characters` };
                 return { valid: false, error: `Message cannot exceed ${MAX_MESSAGE_LENGTH} characters` }; // Keep simple
            }
            return { valid: true };
        }
    
        // API call with retry mechanism
        async function callChatAPI(payload, retryCount = 0) {
            console.log('Calling backend with:', payload);
            let aiMessageElement = null;
            let currentAIResponse = '';
            const langTranslations = translations[currentLanguage] || translations.en;
    
            try {
                // Validate message before sending
                const validation = validateMessage(payload.message);
                if (!validation.valid) {
                    // Maybe show a validation error using showError?
                    // showError(validation.error); // Or use a specific key if defined
                    return;
                }
    
                const response = await fetch(API_ENDPOINT, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(payload),
                });
    
                if (!response.ok) {
                     const errorData = await response.json().catch(() => ({ error: 'Unknown server error' }));
                     throw new Error(`HTTP error! status: ${response.status} - ${errorData.error}`);
                }
    
                // Handle streaming response
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
    
                // Show typing indicator (using translated text)
                const typingIndicator = document.createElement('div');
                typingIndicator.classList.add('ai-typing');
                typingIndicator.textContent = langTranslations.aiTyping || 'AI is typing';
                messageDisplay.appendChild(typingIndicator);
                messageDisplay.scrollTop = messageDisplay.scrollHeight;
    
                // Create the actual message element but don't append yet
                aiMessageElement = document.createElement('div');
                aiMessageElement.classList.add('message', 'ai-message');
                // aiMessageElement.style.display = 'none'; // Don't hide initially
    
                let messageAppended = false; // Flag to track if message element was added
    
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) {
                        break;
                    }
                    const chunk = decoder.decode(value, { stream: true });
                    currentAIResponse += chunk;
    
                    // If we receive the first chunk, remove indicator and append the message element
                    if (!messageAppended && currentAIResponse.trim()) { // Check if chunk is not just whitespace
                        typingIndicator.remove();
                        messageDisplay.appendChild(aiMessageElement);
                        messageAppended = true;
                    }
    
                    // Only update innerHTML if the element has been appended
                    if (messageAppended) {
                        aiMessageElement.innerHTML = renderMarkdown(currentAIResponse);

                        // Add copy button once
                        let copyButton = aiMessageElement.querySelector('.copy-button');
                        if (!copyButton) {
                            copyButton = createCopyButton(() => getMessageText(aiMessageElement));
                            aiMessageElement.appendChild(copyButton);
                        }

                        messageDisplay.scrollTop = messageDisplay.scrollHeight;
                    }
                }
    
                // After loop: Ensure indicator is removed if it wasn't already
                if (typingIndicator.parentNode === messageDisplay) {
                    typingIndicator.remove();
                }
    
                // If no response was received at all, display a translated message
                if (!messageAppended && !currentAIResponse) {
                     // Create element if it wasn't created
                     if (!aiMessageElement) {
                         aiMessageElement = document.createElement('div');
                         aiMessageElement.classList.add('message', 'ai-message', 'error'); // Add error class
                     }
                     aiMessageElement.textContent = langTranslations.errorNoResponse || "[No response received from AI]";
                     messageDisplay.appendChild(aiMessageElement); // Append the error message
                     messageDisplay.scrollTop = messageDisplay.scrollHeight;
                } else if (!messageAppended && currentAIResponse) {
                     // If stream ended but element wasn't appended (e.g., only one chunk received and loop exited)
                     // This case might be less likely now with the trim() check
                     messageDisplay.appendChild(aiMessageElement);
                     messageDisplay.scrollTop = messageDisplay.scrollHeight;
                } else if (messageAppended && !aiMessageElement.querySelector('.copy-button')) {
                     aiMessageElement.appendChild(createCopyButton(() => getMessageText(aiMessageElement)));
                }
    
    
            } catch (error) {
                console.error('Error calling chat API:', error);
    
                // Remove typing indicator if it exists
                const typingIndicator = messageDisplay.querySelector('.ai-typing');
                if (typingIndicator) {
                    typingIndicator.remove();
                }
    
                // Retry logic for network errors or 5xx server errors
                if (retryCount < MAX_RETRIES &&
                    (error.message.includes('Failed to fetch') ||
                     error.message.includes('status: 5'))) {
                    console.log(`Retrying... Attempt ${retryCount + 1} of ${MAX_RETRIES}`);
                    // Use translated retry message
                    showError('errorRetry', { count: retryCount + 1, max: MAX_RETRIES });
    
                    // Wait before retrying
                    await new Promise(resolve => setTimeout(resolve, RETRY_DELAY * (retryCount + 1)));
                    return callChatAPI(payload, retryCount + 1);
                }
    
                // Handle message element state after final error
                if (aiMessageElement && messageAppended) {
                    // If message was appended but an error occurred later, append translated error
                    const errorSpan = document.createElement('span');
                    errorSpan.textContent = ` ${langTranslations.errorStreaming || '[Error during streaming]'}`;
                    errorSpan.style.color = '#721c24'; // Keep error color distinct
                    aiMessageElement.appendChild(errorSpan);
                    aiMessageElement.classList.add('error'); // Add error class for potential styling
                } else {
                    // If error happened before the first chunk or max retries reached
                    // Use translated generic error message
                    let genericErrorMsg = langTranslations.errorSendGeneric || "Failed to send message. Please try again.";
                    displayMessage(`${genericErrorMsg} (${error.message})`, 'ai-message error');
                }
    
                // Show error in notification bar using translated generic error
                 showError('errorGeneric', { message: error.message });
            }
        }
    
        // --- Web Search Toggle Logic ---
        webSearchToggleButton.addEventListener('click', () => {
            isWebSearchEnabled = !isWebSearchEnabled; // Toggle state
            webSearchToggleButton.classList.toggle('active', isWebSearchEnabled); // Toggle class based on state
            updateDynamicTitles(); // Update title based on new state and language
            // Optionally provide visual/audio feedback
            console.log(`Web search for next message: ${isWebSearchEnabled ? 'ENABLED' : 'DISABLED'}`);
        });
    
        // --- Language Switcher Logic ---
        // Add event listeners for language buttons (assuming IDs lang-en, lang-de, lang-es)
        const langEnButton = document.getElementById('lang-en');
        const langDeButton = document.getElementById('lang-de');
        const langEsButton = document.getElementById('lang-es');

        if (langEnButton) {
            langEnButton.addEventListener('click', () => setLanguage('en'));
        }
        if (langDeButton) {
            langDeButton.addEventListener('click', () => setLanguage('de'));
        }
        if (langEsButton) {
            langEsButton.addEventListener('click', () => setLanguage('es'));
        }
    
        // --- Logout Logic ---
        logoutButton.addEventListener('click', () => {
            // Clear session storage
            sessionStorage.removeItem('userName');
            sessionStorage.removeItem('userEmail');
            localStorage.removeItem('preferredLanguage'); // Also clear language preference
    
            // Reset variables
            userName = '';
            userEmail = '';
            isFirstMessage = true;
    
            // Clear messages
            messageDisplay.innerHTML = '';
    
            // Switch back to initial screen and apply default language translations
            setLanguage('en'); // Reset to default language
            chatScreen.style.display = 'none';
            initialScreen.style.display = 'block';
    
            // Clear input fields on login screen
            document.getElementById('name').value = '';
            document.getElementById('email').value = '';
            messageInput.value = ''; // Clear chat input too
        });
    
        // --- Download Chat Logic ---
        downloadChatButton.addEventListener('click', async () => {
            const langTranslations = translations[currentLanguage] || translations.en;
            if (!userEmail) {
                showError('errorUserNotFound'); // Use translated error key
                return;
            }
    
            console.log("Attempting to download chat history for:", userEmail);
    
            // Add loading state visually without removing icon
            downloadChatButton.disabled = true;
            downloadChatButton.classList.add('loading');
            // downloadChatButton.textContent = 'Downloading...'; // REMOVED
    
            try {
                // Fetch history from the new backend endpoint
                const response = await fetch(`${HISTORY_ENDPOINT}?email=${encodeURIComponent(userEmail)}`, {
                    headers: {
                        'Accept': 'application/json',
                    }
                });
    
                if (!response.ok) {
                     const errorData = await response.json().catch(() => ({ error: 'Unknown server error fetching history' }));
                     throw new Error(`Failed to fetch history: ${response.status} - ${errorData.error}`);
                }
    
                const data = await response.json();
                const messages = data.messages;
    
                if (!messages || messages.length === 0) {
                    showError('errorNoHistory'); // Use translated error key
                    return;
                }
    
                // Format the history into a plain text string
                let formattedHistory = `Chat History for ${userName} (${userEmail})\n`;
                formattedHistory += `Downloaded on: ${new Date().toLocaleString()}\n\n`;
                formattedHistory += "========================================\n\n";
    
                messages.forEach(msg => {
                    const timestamp = new Date(msg.timestamp).toLocaleString();
                    const sender = msg.sender === 'user' ? userName : 'AI'; // Use user's name
                    formattedHistory += `[${timestamp}] ${sender}:\n${msg.content}\n\n`;
                    formattedHistory += "----------------------------------------\n\n";
                });
    
                // Create a Blob and trigger download
                const blob = new Blob([formattedHistory], { type: 'text/plain;charset=utf-8' });
                const url = URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.href = url;
                // Create a filename with date/time
                const now = new Date();
                const dateStr = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}`;
                const timeStr = `${String(now.getHours()).padStart(2, '0')}${String(now.getMinutes()).padStart(2, '0')}`;
                link.download = `chat_history_${userName}_${dateStr}_${timeStr}.txt`;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                URL.revokeObjectURL(url); // Clean up the object URL
    
                console.log("Chat history download triggered.");
    
            } catch (error) {
                console.error('Error downloading chat history:', error);
                showError('errorFetchHistory'); // Use translated error key
                // Optionally add specific error message: showError('errorGeneric', { message: error.message });
            } finally {
                // Remove loading state
                downloadChatButton.disabled = false;
                downloadChatButton.classList.remove('loading');
                // downloadChatButton.textContent = 'Download'; // REMOVED
            }
        });
    
    });
