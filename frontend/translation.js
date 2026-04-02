/**
 * @file script.js
 * @description Frontend logic for the iChat App.
 * Handles user login, message sending/display, file uploads,
 * API communication, internationalization (i18n), and UI updates.
 */

function getTranslationDictionary() {
    return {
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
                // Tutor input placeholders
                tutorGoalPlaceholder: "What is the tutor's main goal?",
                tutorModelDomainPlaceholder: "What is the tutor's learning domain?",
                tutorModelLearnerPlaceholder: "What is the profile or persona of the learners?",
                tutorModelTutorPlaceholder: "From a pedagogical and didactic perspective, how should the tutor behave and adapt toward the learner?",
                tutorModelFeedbackPlaceholder: "How should the tutor provide feedback to the learner?",
                tutorModelEducatorPlaceholder: "As an educator, what do you need from the tutor in order to evaluate the tutor’s performance?",
                mainObjectiveLabel: "Main Objective:",
                domainModelLabel: "Domain Model:",
                learnerModelLabel: "Learner Model:",
                tutorModelLabel: "Tutor Model:",
                feedbackModelLabel: "Feedback Model:",
                educatorModelLabel: "Educator Model:"   
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
                // Tutor input placeholders
                tutorGoalPlaceholder: "Was ist das Hauptziel des Tutors?",
                tutorModelDomainPlaceholder: "Was ist die Lerndomäne des Tutors?",
                tutorModelLearnerPlaceholder: "Wie sieht das Profil oder die Persona der Lernenden aus?",
                tutorModelTutorPlaceholder: "Wie sollte sich der Tutor aus pädagogischer und didaktischer Sicht gegenüber dem Lernenden verhalten und anpassen?",
                tutorModelFeedbackPlaceholder: "Wie soll der Tutor Feedback an den Lernenden geben?",
                tutorModelEducatorPlaceholder: "Was benötigen Sie als Lehrender von dem Tutor, um die Ergebnisse der Lehrenden bewerten zu können?",
                mainObjectiveLabel: "Hauptziel:",
                domainModelLabel: "Domain Model:",
                learnerModelLabel: "Learner Model:",
                tutorModelLabel: "Tutor Model:",
                feedbackModelLabel: "Feedback Model:",
                educatorModelLabel: "Educator Model:"
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
                // Tutor input placeholders
                tutorGoalPlaceholder:"¿Cuál es el objetivo principal del tutor?",
                tutorModelDomainPlaceholder:"¿Cuál es el ámbito de aprendizaje del tutor?",
                tutorModelLearnerPlaceholder:"¿Cuál es el perfil o la personalidad de los alumnos?",
                tutorModelTutorPlaceholder:"¿Cómo debería comportarse y adaptarse el tutor ante el alumno desde el punto de vista pedagógico y didáctico?",
                tutorModelFeedbackPlaceholder:"¿Cómo debe el tutor proporcionar retroalimentación al alumno?",
                tutorModelEducatorPlaceholder:"Como docente, ¿qué necesita del tutor para poder evaluar los resultados de los alumnos?",
                mainObjectiveLabel: "Objetivo Principal:",
                domainModelLabel: "Domain Model:",
                learnerModelLabel: "Learner Model:",
                tutorModelLabel: "Tutor Model:",
                feedbackModelLabel: "Feedback Model:",
                educatorModelLabel: "Educator Model:"
            }
        }
}