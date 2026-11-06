const chatMessages = document.getElementById("chat-box") || document.getElementById("chatMessages");
const userInput = document.getElementById("userInput");
const sendBtn = document.querySelector(".send-btn");
const loadingSpinner = document.getElementById("loadingSpinner");
const isDashboardUI = chatMessages && chatMessages.id === "chat-box";
const newChatBtn = document.getElementById("newChatBtn");
const recentChatsList = document.getElementById("recentChatsList");
const suggestionCards = document.querySelectorAll(".suggestion-card");
const financialCard = document.getElementById("financialCard");
const academicCalendarCard = document.getElementById("academicCalendarCard");
const profileDropdownBtn = document.getElementById("profileDropdownBtn");
const profileDropdown = document.getElementById("profileDropdown");
const portalStatus = document.getElementById("portalStatus");

let currentConversationId = null;

/**
 * Toggle layout between welcome view and active conversation
 */
function updateChatLayout() {
    const welcomeContainer = document.getElementById("welcomeContainer");
    const mainContent = document.querySelector(".main-content");
    const hasMessages = chatMessages && chatMessages.children.length > 0;

    if (welcomeContainer) {
        welcomeContainer.style.display = hasMessages ? "none" : "block";
    }
    if (mainContent) {
        mainContent.classList.toggle("chat-active", hasMessages);
    }
}

/**
 * Fetch and display the live status of the academic portal / RAG knowledge base
 */
async function checkPortalStatus() {
    if (!portalStatus) return;

    try {
        const response = await fetch("/health");
        if (response.ok) {
            const data = await response.json();
            if (data.status === "running" && data.data_loaded) {
                portalStatus.className = "status-indicator online";
                portalStatus.innerHTML = `<span class="status-dot online"></span><span class="status-text">Knowledge Base Connected (${data.data_points} chunks)</span>`;
                return;
            } else if (data.status === "running") {
                portalStatus.className = "status-indicator warning";
                portalStatus.innerHTML = `<span class="status-dot warning"></span><span class="status-text">Knowledge Base Initializing</span>`;
                return;
            }
        }
        portalStatus.className = "status-indicator offline";
        portalStatus.innerHTML = `<span class="status-dot offline"></span><span class="status-text">System Offline</span>`;
    } catch (err) {
        portalStatus.className = "status-indicator offline";
        portalStatus.innerHTML = `<span class="status-dot offline"></span><span class="status-text">System Offline</span>`;
    }
}

/**
 * Send user message to backend
 */
async function sendMessage() {
    if (!chatMessages || !userInput || !sendBtn) return;

    const message = userInput.value.trim();
    if (!message) return;

    // Disable send button
    sendBtn.disabled = true;

    // Add user message to chat
    addMessageToChat(message, "user");

    // Clear input
    userInput.value = "";
    userInput.focus();

    // Show loading indicator
    if (loadingSpinner) {
        loadingSpinner.style.display = "inline-flex";
        scrollToBottom();
    }

    try {
        // Send message to Flask backend
        const response = await fetch("/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ message: message, conversation_id: currentConversationId })
        });

        const data = await response.json();

        // Hide loading indicator
        if (loadingSpinner) {
            loadingSpinner.style.display = "none";
        }

        if (response.ok) {
            if (data.conversation_id) {
                currentConversationId = data.conversation_id;
            }
            // Add bot response
            addMessageToChat(data.response, "bot");
            await loadRecentChats();
            setActiveRecentChat(currentConversationId);
        } else {
            addMessageToChat(`Error: ${data.error || "Unable to process query."}`, "bot");
        }
    } catch (error) {
        if (loadingSpinner) {
            loadingSpinner.style.display = "none";
        }
        addMessageToChat(`Network error: ${error.message}`, "bot");
    } finally {
        sendBtn.disabled = false;
        updateChatLayout();
        scrollToBottom();
    }
}

/**
 * Create a new conversation session
 */
async function createNewConversation() {
    try {
        const response = await fetch("/api/conversations", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
        });

        if (!response.ok) return;

        const data = await response.json();
        currentConversationId = data.id;
        clearChat();
        await loadRecentChats();
        setActiveRecentChat(currentConversationId);
    } catch (error) {
        console.error("Failed to create conversation", error);
    }
}

/**
 * Load list of user conversations in sidebar
 */
async function loadRecentChats() {
    if (!recentChatsList) return;

    try {
        const response = await fetch("/api/conversations");
        if (!response.ok) {
            recentChatsList.innerHTML = '<div class="recent-chat-empty">Unable to load recent chats.</div>';
            return;
        }

        const data = await response.json();
        const items = Array.isArray(data.items) ? data.items : [];

        if (!items.length) {
            recentChatsList.innerHTML = '<div class="recent-chat-empty">No recent chats yet.</div>';
            return;
        }

        recentChatsList.innerHTML = "";

        items.forEach((item) => {
            const row = document.createElement("div");
            row.className = "recent-chat-row";
            row.dataset.id = String(item.id);

            const button = document.createElement("button");
            button.type = "button";
            button.className = "recent-chat-item";
            button.textContent = item.title || `Conversation ${item.id}`;
            button.title = item.title || `Conversation ${item.id}`;
            button.addEventListener("click", () => loadConversation(item.id));

            const deleteBtn = document.createElement("button");
            deleteBtn.type = "button";
            deleteBtn.className = "delete-chat-btn";
            deleteBtn.title = "Delete conversation";
            deleteBtn.setAttribute("aria-label", "Delete conversation");
            deleteBtn.innerHTML = '<i class="fas fa-trash-alt"></i>';
            deleteBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                deleteConversation(item.id);
            });

            row.appendChild(button);
            row.appendChild(deleteBtn);
            recentChatsList.appendChild(row);
        });

        if (!currentConversationId && items.length) {
            currentConversationId = items[0].id;
            await loadConversation(currentConversationId);
        }

        setActiveRecentChat(currentConversationId);
    } catch (error) {
        recentChatsList.innerHTML = '<div class="recent-chat-empty">Unable to load recent chats.</div>';
    }
}

/**
 * Highlight active conversation in sidebar
 */
function setActiveRecentChat(conversationId) {
    if (!recentChatsList) return;
    const elements = recentChatsList.querySelectorAll(".recent-chat-row");
    elements.forEach((element) => {
        const isActive = Number(element.dataset.id) === Number(conversationId);
        element.classList.toggle("active", isActive);
    });
}

/**
 * Load a specific conversation's messages
 */
async function loadConversation(conversationId) {
    try {
        const response = await fetch(`/api/conversations/${conversationId}`);
        if (!response.ok) return;

        const data = await response.json();
        currentConversationId = data.id;

        if (chatMessages) {
            chatMessages.innerHTML = "";
        }

        const messages = Array.isArray(data.messages) ? data.messages : [];
        messages.forEach((message) => {
            const sender = message.role === "user" ? "user" : "bot";
            addMessageToChat(message.content, sender);
        });

        setActiveRecentChat(currentConversationId);
        updateChatLayout();
        scrollToBottom();

        if (userInput) {
            userInput.focus();
        }
    } catch (error) {
        console.error("Failed to load conversation", error);
    }
}

/**
 * Delete a conversation
 */
async function deleteConversation(conversationId) {
    if (!confirm("Are you sure you want to delete this conversation?")) {
        return;
    }

    try {
        const response = await fetch(`/api/conversations/${conversationId}`, {
            method: "DELETE"
        });

        if (!response.ok) {
            alert("Failed to delete conversation.");
            return;
        }

        // If currently open conversation was deleted, clear to fresh empty state
        if (Number(currentConversationId) === Number(conversationId)) {
            currentConversationId = null;
            clearChat();
        }

        await loadRecentChats();
    } catch (error) {
        console.error("Failed to delete conversation", error);
        alert("Network error while deleting conversation.");
    }
}

/**
 * Add message to chat display
 */
function addMessageToChat(message, sender) {
    if (!chatMessages) return null;

    if (isDashboardUI) {
        const messageElement = document.createElement("p");
        messageElement.className = sender === "user" ? "user-msg" : "bot-msg";

        if (sender === "bot") {
            messageElement.innerHTML = convertUrlsToLinks(escapeHtml(message)).replace(/\n/g, "<br>");
        } else {
            messageElement.textContent = message;
        }

        chatMessages.appendChild(messageElement);
        updateChatLayout();
        scrollToBottom();
        return messageElement;
    }

    const messageDiv = document.createElement("div");
    messageDiv.className = `message ${sender}-message`;
    const formattedMessage = formatMessage(message);

    const now = new Date();
    const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    messageDiv.innerHTML = `
        <div class="message-content">
            ${formattedMessage}
        </div>
        <span class="message-time">${timeStr}</span>
    `;

    chatMessages.appendChild(messageDiv);
    updateChatLayout();
    scrollToBottom();
    return messageDiv;
}

/**
 * Format message with link detection
 */
function formatMessage(text) {
    text = escapeHtml(text);
    text = text.replace(
        /https?:\/\/[^\s]+/g,
        '<a href="$&" target="_blank" rel="noopener noreferrer" style="color: inherit; text-decoration: underline;">$&</a>'
    );
    const lines = text.split('\n');
    const paragraphs = lines.map(line => {
        if (line.trim().startsWith('-') || line.trim().startsWith('•')) {
            return line;
        }
        return line ? `<p>${line}</p>` : '';
    }).join('');
    return paragraphs || '<p>No response</p>';
}

/**
 * Scroll chat box to bottom
 */
function scrollToBottom() {
    setTimeout(() => {
        if (chatMessages) {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
    }, 10);
}

/**
 * Clear entire chat and return to welcome state
 */
function clearChat() {
    if (!chatMessages) return;
    chatMessages.innerHTML = "";
    updateChatLayout();
    if (userInput) {
        userInput.focus();
    }
}

/**
 * Convert URLs into clickable HTML anchors
 */
function convertUrlsToLinks(text) {
    return text.replace(
        /https?:\/\/[^\s]+/g,
        '<a href="$&" target="_blank" rel="noopener noreferrer">$&</a>'
    );
}

/**
 * Escape HTML special characters
 */
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

/**
 * Initialize on page load
 */
window.addEventListener("load", () => {
    if (userInput) {
        userInput.focus();
    }

    // Check knowledge base status
    checkPortalStatus();

    // Load user's conversations
    loadRecentChats();

    // Initialize layout
    updateChatLayout();

    // New Chat button
    if (newChatBtn) {
        newChatBtn.addEventListener("click", createNewConversation);
    }

    // Profile Dropdown Setup
    if (profileDropdownBtn && profileDropdown) {
        profileDropdownBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            const isOpen = profileDropdown.style.display === "block";
            profileDropdown.style.display = isOpen ? "none" : "block";
            profileDropdownBtn.setAttribute("aria-expanded", !isOpen);
        });

        document.addEventListener("click", (e) => {
            if (!profileDropdown.contains(e.target) && e.target !== profileDropdownBtn) {
                profileDropdown.style.display = "none";
                profileDropdownBtn.setAttribute("aria-expanded", "false");
            }
        });

        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape" && profileDropdown.style.display === "block") {
                profileDropdown.style.display = "none";
                profileDropdownBtn.setAttribute("aria-expanded", "false");
            }
        });
    }

    // Financial queries suggestion card
    if (financialCard) {
        financialCard.addEventListener("click", () => {
            const sampleQuery = financialCard.dataset.query || "Show me information about tuition fees and financial matters.";
            if (userInput) {
                userInput.value = sampleQuery;
                userInput.focus();
            }
        });
    }

    // Academic Calendar suggestion card (submits through normal chat flow)
    if (academicCalendarCard) {
        academicCalendarCard.addEventListener("click", () => {
            const query = academicCalendarCard.dataset.query || "When are the final examinations scheduled for the semester?";
            if (userInput) {
                userInput.value = query;
                sendMessage();
            }
        });
    }

    // Other suggestion cards
    suggestionCards.forEach((card) => {
        if (card !== financialCard && card !== academicCalendarCard) {
            card.addEventListener("click", () => {
                const sampleQuery = card.dataset.query || "";
                if (userInput && sampleQuery) {
                    userInput.value = sampleQuery;
                    userInput.focus();
                }
            });
        }
    });

    console.log("✓ UIU ChatAssist initialized successfully");
});

/**
 * Send button and keyboard Enter triggers
 */
if (sendBtn) {
    sendBtn.addEventListener("click", sendMessage);
}

if (userInput) {
    userInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
}
