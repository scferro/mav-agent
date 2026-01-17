/**
 * MAVLink Agent Web Chat Interface
 * JavaScript API client and chat functionality
 */

/**
 * MAVLink GCS Connection Handler
 * Connects to GCS Server via Flask-SocketIO WebSocket for telemetry
 */
class MAVLinkGCS {
    constructor(serverUrl = window.location.origin) {
        this.serverUrl = serverUrl;
        this.socket = null;
        this.telemetry = {
            home: null,
            position: null,
            altitude: null,
            heading: null,
            armed: false
        };
        this.connected = false;
        this.homePosition = null;  // Track home position for API requests

        this.initializeElements();
        this.attachEventListeners();
    }

    initializeElements() {
        this.elements = {
            telemetryStatus: document.getElementById('telemetryStatus'),
            telemHome: document.getElementById('telemHome'),
            telemPosition: document.getElementById('telemPosition'),
            telemAltitude: document.getElementById('telemAltitude'),
            telemHeading: document.getElementById('telemHeading'),
            telemArmed: document.getElementById('telemArmed'),
            btnDownloadMission: document.getElementById('btnDownloadMission'),
            btnUploadMission: document.getElementById('btnUploadMission'),
            connectionBanner: document.getElementById('connectionBanner'),
            connectionHelp: document.getElementById('connectionHelp'),
            btnConnectGCS: document.getElementById('btnConnectGCS'),
            retryConnectionBtn: document.getElementById('retryConnectionBtn')
        };
    }

    attachEventListeners() {
        // Mission download/upload buttons (future implementation)
        if (this.elements.btnDownloadMission) {
            this.elements.btnDownloadMission.addEventListener('click', () => this.downloadMission());
        }
        if (this.elements.btnUploadMission) {
            this.elements.btnUploadMission.addEventListener('click', () => this.uploadMission());
        }

        // Connect to GCS button
        if (this.elements.btnConnectGCS) {
            this.elements.btnConnectGCS.addEventListener('click', () => this.connect());
        }

        // Retry connection button
        if (this.elements.retryConnectionBtn) {
            this.elements.retryConnectionBtn.addEventListener('click', () => this.connect());
        }
    }

    async connect() {
        try {
            console.log(`Connecting to Flask telemetry WebSocket at ${this.serverUrl}`);

            // Connect to Flask-SocketIO
            this.socket = io(`${this.serverUrl}/ws/telemetry`);

            this.socket.on('connect', () => {
                console.log('✅ Connected to Flask telemetry WebSocket');
                this.connected = true;
                this.updateStatusDisplay();
            });

            this.socket.on('disconnect', () => {
                console.log('Disconnected from Flask telemetry WebSocket');
                this.connected = false;
                this.homePosition = null;
                this.updateStatusDisplay();
            });

            this.socket.on('telemetry', (data) => {
                // Update telemetry state from server
                if (data.home) {
                    this.telemetry.home = data.home;
                    this.homePosition = {
                        latitude: data.home.latitude,
                        longitude: data.home.longitude
                    };
                    this.hideConnectionBanner();  // Hide warning when we have home position
                }

                if (data.position) {
                    this.telemetry.position = data.position;
                }

                if (data.altitude !== null && data.altitude !== undefined) {
                    this.telemetry.altitude = data.altitude;
                }

                if (data.heading !== null && data.heading !== undefined) {
                    this.telemetry.heading = data.heading;
                }

                this.telemetry.armed = data.armed || false;

                this.updateStatusDisplay();
            });

        } catch (error) {
            console.error('❌ Flask WebSocket connection failed:', error);
            this.connected = false;
            this.updateStatusDisplay();
        }
    }

    disconnect() {
        if (this.socket) {
            this.socket.disconnect();
            this.socket = null;
        }
        this.connected = false;
        this.homePosition = null;
        this.updateStatusDisplay();
    }

    showConnectionBanner() {
        if (this.elements.connectionBanner) {
            this.elements.connectionBanner.style.display = 'block';
        }
    }

    hideConnectionBanner() {
        if (this.elements.connectionBanner) {
            this.elements.connectionBanner.style.display = 'none';
        }
    }

    updateStatusDisplay() {
        if (!this.elements.telemetryStatus) return;

        // Update connection status
        this.elements.telemetryStatus.textContent = this.connected ? '🟢 Connected' : '🔴 Disconnected';

        // Show/hide connection help based on connection status
        if (this.elements.connectionHelp) {
            if (this.connected && this.homePosition) {
                this.elements.connectionHelp.classList.add('hidden');
                this.hideConnectionBanner();
            } else {
                this.elements.connectionHelp.classList.remove('hidden');
                this.showConnectionBanner();
            }
        }

        // Update telemetry values
        if (this.telemetry.home && this.elements.telemHome) {
            this.elements.telemHome.textContent =
                `${this.telemetry.home.latitude.toFixed(6)}, ${this.telemetry.home.longitude.toFixed(6)}`;
        }

        if (this.telemetry.position && this.elements.telemPosition) {
            this.elements.telemPosition.textContent =
                `${this.telemetry.position.latitude.toFixed(6)}, ${this.telemetry.position.longitude.toFixed(6)}`;
        }

        if (this.telemetry.altitude !== null && this.elements.telemAltitude) {
            this.elements.telemAltitude.textContent = `${this.telemetry.altitude.toFixed(1)}m AGL`;
        }

        if (this.telemetry.heading !== null && this.elements.telemHeading) {
            this.elements.telemHeading.textContent = `${this.telemetry.heading.toFixed(1)}°`;
        }

        if (this.elements.telemArmed) {
            this.elements.telemArmed.textContent = this.telemetry.armed ? 'ARMED' : 'DISARMED';
        }

        // Enable/disable buttons based on connection
        if (this.elements.btnDownloadMission) {
            this.elements.btnDownloadMission.disabled = !this.connected;
        }
        if (this.elements.btnUploadMission) {
            this.elements.btnUploadMission.disabled = !this.connected;
        }
    }

    async downloadMission() {
        console.log('Download mission from drone (not yet implemented)');
        // TODO: Send MISSION_REQUEST_LIST
        // TODO: Receive MISSION_COUNT
        // TODO: Request each item with MISSION_REQUEST_INT
        // TODO: Parse MISSION_ITEM_INT responses
        // TODO: Return array of MAVLink mission items
    }

    async uploadMission(missionItems) {
        console.log('Upload mission to drone (not yet implemented)');
        // TODO: Send MISSION_COUNT
        // TODO: Wait for MISSION_REQUEST_INT for each item
        // TODO: Send MISSION_ITEM_INT for each
        // TODO: Wait for MISSION_ACK
    }
}

class MAVLinkAgentClient {
    constructor() {
        this.baseUrl = window.location.origin;
        this.currentMode = 'mission';
        this.isConnected = false;
        this.isProcessing = false;

        // Client-side state management
        this.currentMission = null;  // Track mission client-side
        this.chatHistory = [];       // Track conversation client-side

        this.initializeElements();
        this.attachEventListeners();
        this.checkServerConnection();
    }
    
    initializeElements() {
        // Get DOM elements
        this.elements = {
            // Status elements
            statusDot: document.getElementById('statusDot'),
            statusText: document.getElementById('statusText'),

            // Mode elements
            missionModeBtn: document.getElementById('missionModeBtn'),
            commandModeBtn: document.getElementById('commandModeBtn'),
            missionDesc: document.getElementById('missionDesc'),
            commandDesc: document.getElementById('commandDesc'),

            // Chat elements
            chatMessages: document.getElementById('chatMessages'),
            messageInput: document.getElementById('messageInput'),
            sendButton: document.getElementById('sendButton'),

            // Mission state elements
            missionItems: document.getElementById('missionItems'),

            // Loading elements
            loadingOverlay: document.getElementById('loadingOverlay')
        };
    }
    
    attachEventListeners() {
        // Mode switching
        this.elements.missionModeBtn.addEventListener('click', () => this.switchMode('mission'));
        this.elements.commandModeBtn.addEventListener('click', () => this.switchMode('command'));

        // Input handling
        this.elements.messageInput.addEventListener('input', () => {
            this.updateSendButton();
        });

        this.elements.sendButton.addEventListener('click', () => this.sendMessage());

        // Initial state
        this.updateSendButton();
    }
    
    async checkServerConnection() {
        try {
            const response = await fetch(`${this.baseUrl}/api/status`);
            const status = await response.json();
            
            this.isConnected = status.agent_initialized === true;
            this.updateConnectionStatus();
            
        } catch (error) {
            console.error('Connection check failed:', error);
            this.isConnected = false;
            this.updateConnectionStatus();
        }
    }
    
    updateConnectionStatus() {
        if (this.isConnected) {
            this.elements.statusDot.classList.add('connected');
            this.elements.statusText.textContent = 'Connected';
        } else {
            this.elements.statusDot.classList.remove('connected');
            this.elements.statusText.textContent = 'Disconnected';
        }
        
        this.updateSendButton();
    }
    
    switchMode(mode) {
        this.currentMode = mode;

        // Update button states
        this.elements.missionModeBtn.classList.toggle('active', mode === 'mission');
        this.elements.commandModeBtn.classList.toggle('active', mode === 'command');

        // Update descriptions
        this.elements.missionDesc.classList.toggle('active', mode === 'mission');
        this.elements.commandDesc.classList.toggle('active', mode === 'command');

        // Clear chat and mission state when switching modes
        this.clearChat();
        this.clearMissionState();

        // Clear client-side state
        this.currentMission = null;
        this.chatHistory = [];

        if (mode === 'command') {
            this.addMessage('agent', 'Switched to Command Mode. Each command will create a fresh mission.');
        } else {
            this.addMessage('agent', 'Switched to Mission Mode. Build your mission step by step.');
        }

        // Focus input
        this.elements.messageInput.focus();
    }
    
    updateSendButton() {
        const hasText = this.elements.messageInput.value.trim().length > 0;
        const canSend = this.isConnected && hasText && !this.isProcessing;
        
        this.elements.sendButton.disabled = !canSend;
    }
    
    async sendMessage() {
        const message = this.elements.messageInput.value.trim();
        if (!message || !this.isConnected || this.isProcessing) {
            return;
        }

        // Handle special commands
        if (message.toLowerCase() === 'clear') {
            this.clearChat();
            this.elements.messageInput.value = '';
            this.updateSendButton();
            return;
        }

        // Check GCS connection
        const gcs = window.mavlinkGCS;
        const hasGCS = gcs && gcs.connected && gcs.homePosition;

        // Build request with current mission state in MAVLink format
        const requestBody = {
            user_input: message,
            mode: this.currentMode,
            mission_state: this.currentMission ? this.currentMission.items : null  // Send MAVLink mission items
        };

        // Note: home_position is NOT sent from browser anymore - GCS server adds it from telemetry

        // Warn if no GCS and no mission state
        if (!hasGCS && !requestBody.mission_state) {
            this.addMessage('warning',
                '⚠️ GCS telemetry not connected. Server may not have home position.');
        }

        // Add user message to chat
        this.addMessage('user', message);

        // Clear input and show loading
        this.elements.messageInput.value = '';
        this.updateSendButton();
        this.showLoading(true);
        this.isProcessing = true;

        try {
            const response = await fetch(`${this.baseUrl}/api/plan`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestBody)
            });

            const result = await response.json();

            if (result.success) {
                // Add agent response
                if (result.output) {
                    this.addMessage('agent', result.output);
                }

                // Update client-side mission state (mission_items in MAVLink format)
                if (result.mission_items && result.mission_items.length > 0) {
                    this.currentMission = {
                        items: result.mission_items,
                        created_at: new Date().toISOString(),
                        modified_at: new Date().toISOString()
                    };
                }

                // Add to chat history
                this.chatHistory.push({
                    role: 'user',
                    content: message
                });
                this.chatHistory.push({
                    role: 'assistant',
                    content: result.output
                });

                // Update UI with delta information
                this.updateMissionDisplay(result);
            } else {
                // Show error message
                this.addMessage('error', `Error: ${result.error || 'Unknown error occurred'}`);
            }

        } catch (error) {
            console.error('Request failed:', error);
            this.addMessage('error', `Connection failed: ${error.message}`);
            this.isConnected = false;
            this.updateConnectionStatus();
        } finally {
            this.showLoading(false);
            this.isProcessing = false;
            this.updateSendButton();
            this.elements.messageInput.focus();
        }
    }
    
    addMessage(type, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}-message`;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        // Process content for better display
        if (typeof content === 'string') {
            // Convert newlines to <br> and preserve formatting
            contentDiv.innerHTML = content
                .replace(/\n/g, '<br>')
                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                .replace(/\*(.*?)\*/g, '<em>$1</em>');
        } else {
            contentDiv.textContent = String(content);
        }
        
        messageDiv.appendChild(contentDiv);
        this.elements.chatMessages.appendChild(messageDiv);
        
        // Scroll to bottom
        this.elements.chatMessages.scrollTop = this.elements.chatMessages.scrollHeight;
    }
    
    clearChat() {
        // Remove all messages except welcome message
        const messages = this.elements.chatMessages.querySelectorAll('.message:not(.welcome-message)');
        messages.forEach(msg => msg.remove());
    }
    
    clearMissionState() {
        // Reset mission state panel to empty state
        this.elements.missionItems.innerHTML = '<div class="empty-mission">No mission items yet</div>';
    }
    
    updateMissionDisplay(result) {
        // If no mission items, show empty state
        if (!result.mission_items || result.mission_items.length === 0) {
            this.elements.missionItems.innerHTML = '<div class="empty-mission">No mission items yet</div>';
            return;
        }

        const itemsHtml = result.mission_items.map((item, index) => {
            const commandType = item.command_type || 'unknown';
            const emoji = this.getCommandEmoji(commandType);

            // Check if this item was added or modified
            const isNew = result.added_items?.some(a => a.seq === item.seq);
            const isModified = result.modified_items?.some(m => m.seq === item.seq);

            const badge = isNew ? '<span class="badge new">NEW</span>' :
                         isModified ? '<span class="badge modified">MODIFIED</span>' : '';

            let details = [];

            // Add altitude info
            if (item.altitude !== null && item.altitude !== undefined) {
                details.push(`Altitude: ${item.altitude} ${item.altitude_units || 'units'}`);
            }

            // Add position info
            if (item.latitude !== null && item.longitude !== null) {
                details.push(`Position: ${item.latitude.toFixed(6)}, ${item.longitude.toFixed(6)}`);
            } else if (item.mgrs) {
                details.push(`Position: MGRS ${item.mgrs}`);
            } else if (item.distance && item.heading) {
                let positionText = `Position: ${item.distance} ${item.distance_units || 'units'} ${item.heading}`;
                if (item.relative_reference_frame) {
                    positionText += ` from ${item.relative_reference_frame}`;
                }
                details.push(positionText);
            }

            // Add radius for loiter/survey
            if (item.radius !== null && item.radius !== undefined) {
                details.push(`Radius: ${item.radius} ${item.radius_units || 'units'}`);
            }

            // Add heading for takeoff commands
            if (commandType === 'takeoff' && item.heading) {
                details.push(`Heading: ${item.heading}`);
            }

            // Add search parameters
            if (item.search_target) {
                details.push(`Target: ${item.search_target}`);
            }
            if (item.detection_behavior) {
                details.push(`Behavior: ${item.detection_behavior}`);
            }

            return `
                <div class="mission-item ${isNew ? 'item-new' : ''} ${isModified ? 'item-modified' : ''}">
                    <div class="mission-item-header">
                        ${emoji} ${index + 1}. ${commandType.toUpperCase()} ${badge}
                    </div>
                    <div class="mission-item-details">
                        ${details.map(detail => `<div>${detail}</div>`).join('')}
                    </div>
                </div>
            `;
        }).join('');

        // Show validation if available
        let validationHtml = '';
        if (result.validation) {
            const validClass = result.validation.valid ? 'valid' : 'invalid';
            const validIcon = result.validation.valid ? '✓' : '✗';

            validationHtml = `
                <div class="validation ${validClass}">
                    <strong>${validIcon} Validation: ${result.validation.valid ? 'Valid' : 'Invalid'}</strong>
                    ${result.validation.errors?.length > 0 ? `
                        <ul class="errors">
                            ${result.validation.errors.map(err => `<li>${err}</li>`).join('')}
                        </ul>
                    ` : ''}
                    ${result.validation.warnings?.length > 0 ? `
                        <ul class="warnings">
                            ${result.validation.warnings.map(warn => `<li>${warn}</li>`).join('')}
                        </ul>
                    ` : ''}
                </div>
            `;
        }

        this.elements.missionItems.innerHTML = itemsHtml + validationHtml;
    }
    
    getCommandEmoji(commandType) {
        const emojis = {
            'takeoff': '🚀',
            'waypoint': '📍',
            'loiter': '🔄',
            'survey': '🗺️',
            'rtl': '🏠'
        };
        return emojis[commandType] || '❓';
    }
    
    showLoading(show) {
        if (show) {
            this.elements.loadingOverlay.classList.add('active');
        } else {
            this.elements.loadingOverlay.classList.remove('active');
        }
    }
}

// Initialize the client and MAVLink GCS when the page loads
document.addEventListener('DOMContentLoaded', () => {
    window.mavlinkClient = new MAVLinkAgentClient();

    // Initialize MAVLink GCS connection to Flask-SocketIO WebSocket
    window.mavlinkGCS = new MAVLinkGCS();
    // Auto-connect to GCS server's telemetry WebSocket
    window.mavlinkGCS.connect();
});