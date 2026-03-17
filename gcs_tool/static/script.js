/**
 * MAVLink Agent Web Chat Interface
 * JavaScript API client and chat functionality
 */

// Well-known MAV_CMD name lookup
const MAV_CMD_NAMES = {
    16: 'NAV_WAYPOINT',
    17: 'NAV_LOITER_UNLIM',
    18: 'NAV_LOITER_TURNS',
    19: 'NAV_LOITER_TIME',
    20: 'NAV_RETURN_TO_LAUNCH',
    21: 'NAV_LAND',
    22: 'NAV_TAKEOFF',
    201: 'DO_SET_ROI',
};

function cmdName(cmdNum) {
    return MAV_CMD_NAMES[cmdNum] || String(cmdNum);
}

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
        this.homePosition = null;

        this.initializeElements();
        this.attachEventListeners();
    }

    initializeElements() {
        this.elements = {
            mavlinkDot: document.getElementById('mavlinkDot'),
            mavlinkText: document.getElementById('mavlinkText'),
            telemHome: document.getElementById('telemHome'),
            telemPosition: document.getElementById('telemPosition'),
            telemAltitude: document.getElementById('telemAltitude'),
            telemHeading: document.getElementById('telemHeading'),
            telemArmed: document.getElementById('telemArmed'),
            btnReconnect: document.getElementById('btnReconnect'),
        };
    }

    attachEventListeners() {
        if (this.elements.btnReconnect) {
            this.elements.btnReconnect.addEventListener('click', () => this.reconnect());
        }
    }

    async connect() {
        try {
            this.socket = io(`${this.serverUrl}/ws/telemetry`);

            this.socket.on('connect', () => {
                this.connected = true;
                this.updateStatusDisplay();
            });

            this.socket.on('disconnect', () => {
                this.connected = false;
                this.homePosition = null;
                this.updateStatusDisplay();
            });

            this.socket.on('telemetry', (data) => {
                if (data.home) {
                    this.telemetry.home = data.home;
                    this.homePosition = {
                        latitude: data.home.latitude,
                        longitude: data.home.longitude
                    };
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
            console.error('WebSocket connection failed:', error);
            this.connected = false;
            this.updateStatusDisplay();
        }
    }

    async reconnect() {
        try {
            const response = await fetch(`${this.serverUrl}/api/reconnect`, { method: 'POST' });
            const result = await response.json();
            if (!result.success) {
                console.error('Reconnect failed:', result.error);
            }
            // Also reconnect the websocket
            if (this.socket) {
                this.socket.disconnect();
            }
            await this.connect();
        } catch (error) {
            console.error('Reconnect error:', error);
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

    updateStatusDisplay() {
        if (this.elements.mavlinkDot) {
            if (this.connected) {
                this.elements.mavlinkDot.classList.add('connected');
            } else {
                this.elements.mavlinkDot.classList.remove('connected');
            }
        }
        if (this.elements.mavlinkText) {
            this.elements.mavlinkText.textContent = this.connected ? 'Connected' : 'Disconnected';
        }

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
            this.elements.telemHeading.textContent = `${this.telemetry.heading.toFixed(1)}deg`;
        }
        if (this.elements.telemArmed) {
            this.elements.telemArmed.textContent = this.telemetry.armed ? 'ARMED' : 'DISARMED';
        }

        // Update send-to-drone button state
        const sendBtn = document.getElementById('btnSendToDrone');
        if (sendBtn && window.mavlinkClient) {
            sendBtn.disabled = !this.connected || !window.mavlinkClient.lastResult;
        }
    }

}

class MAVLinkAgentClient {
    constructor() {
        this.baseUrl = window.location.origin;
        this.currentMode = 'mission';
        this.isConnected = false;
        this.isProcessing = false;

        this.currentMission = null;
        this.chatHistory = [];
        this.lastResult = null;  // Track last result for send-to-drone

        this.initializeElements();
        this.attachEventListeners();
        this.checkServerConnection();
    }

    initializeElements() {
        this.elements = {
            statusDot: document.getElementById('statusDot'),
            statusText: document.getElementById('statusText'),
            missionModeBtn: document.getElementById('missionModeBtn'),
            commandModeBtn: document.getElementById('commandModeBtn'),
            missionDesc: document.getElementById('missionDesc'),
            commandDesc: document.getElementById('commandDesc'),
            chatMessages: document.getElementById('chatMessages'),
            messageInput: document.getElementById('messageInput'),
            sendButton: document.getElementById('sendButton'),
            missionItems: document.getElementById('missionItems'),
            loadingOverlay: document.getElementById('loadingOverlay'),
            btnSendToDrone: document.getElementById('btnSendToDrone'),
        };
    }

    attachEventListeners() {
        this.elements.missionModeBtn.addEventListener('click', () => this.switchMode('mission'));
        this.elements.commandModeBtn.addEventListener('click', () => this.switchMode('command'));
        this.elements.messageInput.addEventListener('input', () => this.updateSendButton());
        this.elements.sendButton.addEventListener('click', () => this.sendMessage());

        if (this.elements.btnSendToDrone) {
            this.elements.btnSendToDrone.addEventListener('click', () => this.sendToDrone());
        }

        this.updateSendButton();
    }

    async checkServerConnection() {
        try {
            const response = await fetch(`${this.baseUrl}/api/status`);
            const status = await response.json();
            this.isConnected = status.agent_initialized === true;
            this.updateConnectionStatus();
        } catch (error) {
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
        this.elements.missionModeBtn.classList.toggle('active', mode === 'mission');
        this.elements.commandModeBtn.classList.toggle('active', mode === 'command');
        this.elements.missionDesc.classList.toggle('active', mode === 'mission');
        this.elements.commandDesc.classList.toggle('active', mode === 'command');

        this.clearChat();
        this.clearMissionState();
        this.currentMission = null;
        this.chatHistory = [];
        this.lastResult = null;
        this.updateSendToDroneButton();

        if (mode === 'command') {
            this.addMessage('agent', 'Switched to Command Mode. Each command creates a single COMMAND_INT.');
        } else {
            this.addMessage('agent', 'Switched to Mission Mode. Build your mission step by step.');
        }
        this.elements.messageInput.focus();
    }

    updateSendButton() {
        const hasText = this.elements.messageInput.value.trim().length > 0;
        const canSend = this.isConnected && hasText && !this.isProcessing;
        this.elements.sendButton.disabled = !canSend;
    }

    updateSendToDroneButton() {
        if (this.elements.btnSendToDrone) {
            const gcs = window.mavlinkGCS;
            const gcsConnected = gcs && gcs.connected;
            this.elements.btnSendToDrone.disabled = !gcsConnected || !this.lastResult;
        }
    }

    async sendMessage() {
        const message = this.elements.messageInput.value.trim();
        if (!message || !this.isConnected || this.isProcessing) return;

        if (message.toLowerCase() === 'clear') {
            this.clearChat();
            this.elements.messageInput.value = '';
            this.updateSendButton();
            return;
        }

        const gcs = window.mavlinkGCS;
        const hasGCS = gcs && gcs.connected && gcs.homePosition;

        const requestBody = {
            user_input: message,
            mode: this.currentMode,
            mission_state: this.currentMission ? this.currentMission.items : null
        };

        if (!hasGCS && !requestBody.mission_state) {
            this.addMessage('warning',
                'GCS telemetry not connected. Server may not have home position.');
        }

        this.addMessage('user', message);
        this.elements.messageInput.value = '';
        this.updateSendButton();
        this.showLoading(true);
        this.isProcessing = true;

        try {
            const response = await fetch(`${this.baseUrl}/api/plan`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestBody)
            });

            const result = await response.json();

            if (result.success) {
                if (result.output) {
                    this.addMessage('agent', result.output);
                }

                // Store result for send-to-drone
                this.lastResult = result;

                // Update client-side mission state
                if (result.mission_items && result.mission_items.length > 0) {
                    this.currentMission = {
                        items: result.mission_items,
                        created_at: new Date().toISOString(),
                        modified_at: new Date().toISOString()
                    };
                } else if (result.command) {
                    // Command mode: store the single command
                    this.currentMission = null;
                }

                this.chatHistory.push({ role: 'user', content: message });
                this.chatHistory.push({ role: 'assistant', content: result.output });

                this.updateMissionDisplay(result);
                this.updateSendToDroneButton();
            } else {
                this.addMessage('error', `Error: ${result.error || 'Unknown error occurred'}`);
            }

        } catch (error) {
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

    async sendToDrone() {
        if (!this.lastResult) return;

        const gcs = window.mavlinkGCS;
        if (!gcs || !gcs.connected) {
            this.addMessage('error', 'GCS not connected. Cannot send to drone.');
            return;
        }

        try {
            let response;
            if (this.lastResult.command) {
                // Send single COMMAND_INT
                response = await fetch(`${this.baseUrl}/api/send-command`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ command_data: this.lastResult.command })
                });
            } else if (this.lastResult.mission_items) {
                // Upload mission
                response = await fetch(`${this.baseUrl}/api/upload-mission`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mission_items: this.lastResult.mission_items })
                });
            } else {
                this.addMessage('error', 'No command or mission to send.');
                return;
            }

            const result = await response.json();
            if (result.success) {
                this.addMessage('agent', `Sent to drone: ${result.message}`);
            } else {
                this.addMessage('error', `Send failed: ${result.error || result.message}`);
            }
        } catch (error) {
            this.addMessage('error', `Send failed: ${error.message}`);
        }
    }

    addMessage(type, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}-message`;

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';

        if (typeof content === 'string') {
            contentDiv.innerHTML = content
                .replace(/\n/g, '<br>')
                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                .replace(/\*(.*?)\*/g, '<em>$1</em>');
        } else {
            contentDiv.textContent = String(content);
        }

        messageDiv.appendChild(contentDiv);
        this.elements.chatMessages.appendChild(messageDiv);
        this.elements.chatMessages.scrollTop = this.elements.chatMessages.scrollHeight;
    }

    clearChat() {
        const messages = this.elements.chatMessages.querySelectorAll('.message:not(.welcome-message)');
        messages.forEach(msg => msg.remove());
    }

    clearMissionState() {
        this.elements.missionItems.innerHTML = '<div class="empty-mission">No mission items yet</div>';
    }

    updateMissionDisplay(result) {
        // Command mode: show COMMAND_INT key-value
        if (result.command) {
            const cmd = result.command;
            const name = cmdName(cmd.command);
            let html = '<div class="mavlink-kv">';
            html += `<div class="kv-title">COMMAND_INT (${name})</div>`;
            html += '<table class="mavlink-table">';
            const fields = [
                ['target_system', cmd.target_system],
                ['target_component', cmd.target_component],
                ['frame', cmd.frame],
                ['command', `${cmd.command} (${name})`],
                ['current', cmd.current],
                ['autocontinue', cmd.autocontinue],
                ['param1', cmd.param1],
                ['param2', cmd.param2],
                ['param3', cmd.param3],
                ['param4', cmd.param4],
                ['x', cmd.x],
                ['y', cmd.y],
                ['z', cmd.z],
            ];
            for (const [key, val] of fields) {
                html += `<tr><td class="kv-key">${key}</td><td class="kv-val">${val}</td></tr>`;
            }
            html += '</table></div>';

            // Validation
            html += this.renderValidation(result.validation);

            this.elements.missionItems.innerHTML = html;
            return;
        }

        // Mission mode: show MISSION_ITEM_INT table
        if (!result.mission_items || result.mission_items.length === 0) {
            this.elements.missionItems.innerHTML = '<div class="empty-mission">No mission items yet</div>';
            return;
        }

        const cols = ['seq', 'frame', 'command', 'current', 'autocontinue',
                       'param1', 'param2', 'param3', 'param4', 'x', 'y', 'z'];

        let html = '<div class="mavlink-table-wrap"><table class="mavlink-table mission-table">';
        html += '<thead><tr>';
        for (const col of cols) {
            html += `<th>${col}</th>`;
        }
        html += '<th>name</th></tr></thead><tbody>';

        for (const item of result.mission_items) {
            html += '<tr>';
            for (const col of cols) {
                let val = item[col];
                if (val === undefined || val === null) val = 0;
                html += `<td>${val}</td>`;
            }
            html += `<td class="cmd-name">${cmdName(item.command)}</td>`;
            html += '</tr>';
        }
        html += '</tbody></table></div>';

        // Validation
        html += this.renderValidation(result.validation);

        this.elements.missionItems.innerHTML = html;
    }

    renderValidation(validation) {
        if (!validation) return '';
        const validClass = validation.valid ? 'valid' : 'invalid';
        const validIcon = validation.valid ? 'Valid' : 'Invalid';

        let html = `<div class="validation ${validClass}"><strong>Validation: ${validIcon}</strong>`;
        if (validation.errors && validation.errors.length > 0) {
            html += '<ul class="errors">';
            for (const err of validation.errors) {
                html += `<li>${err}</li>`;
            }
            html += '</ul>';
        }
        html += '</div>';
        return html;
    }

    showLoading(show) {
        if (show) {
            this.elements.loadingOverlay.classList.add('active');
        } else {
            this.elements.loadingOverlay.classList.remove('active');
        }
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    window.mavlinkClient = new MAVLinkAgentClient();
    window.mavlinkGCS = new MAVLinkGCS();
    window.mavlinkGCS.connect();
});
