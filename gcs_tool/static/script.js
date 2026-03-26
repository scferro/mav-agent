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
            armed: false,
            vehicle_type: null
        };
        this.connected = false;
        this.homePosition = null;
        this.autoSendToDrone = false;

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
            telemVehicleType: document.getElementById('telemVehicleType'),
            mavlinkDot: document.getElementById('mavlinkDot'),
            mavlinkText: document.getElementById('mavlinkText'),
            btnArm: document.getElementById('btnArm'),
            btnDisarm: document.getElementById('btnDisarm'),
            btnSendMission: document.getElementById('btnSendMission'),
            btnSendCommand: document.getElementById('btnSendCommand'),
            droneSendStatus: document.getElementById('droneSendStatus')
        };
    }

    attachEventListeners() {
        if (this.elements.btnArm) {
            this.elements.btnArm.addEventListener('click', () => this.armDrone());
        }
        if (this.elements.btnDisarm) {
            this.elements.btnDisarm.addEventListener('click', () => this.disarmDrone());
        }
        if (this.elements.btnSendMission) {
            this.elements.btnSendMission.addEventListener('click', () => this.sendMission());
        }
        if (this.elements.btnSendCommand) {
            this.elements.btnSendCommand.addEventListener('click', () => this.sendCommand());
        }
    }

    async connect() {
        try {
            console.log(`Connecting to Flask telemetry WebSocket at ${this.serverUrl}`);

            // Fetch auto_send_to_drone status from GCS server
            try {
                const statusResp = await fetch(`${this.serverUrl}/api/status`);
                const statusData = await statusResp.json();
                this.autoSendToDrone = statusData.auto_send_to_drone || false;
            } catch (e) {
                console.warn('Could not fetch auto_send_to_drone status:', e);
            }

            this.socket = io(`${this.serverUrl}/ws/telemetry`);

            this.socket.on('connect', () => {
                console.log('Connected to Flask telemetry WebSocket');
                this.updateStatusDisplay();
            });

            this.socket.on('disconnect', () => {
                console.log('Disconnected from Flask telemetry WebSocket');
                this.connected = false;
                this.homePosition = null;
                this.updateStatusDisplay();
            });

            this.socket.on('telemetry', (data) => {
                // Track drone MAVLink connection, not WebSocket connection
                this.connected = data.connected || false;

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

                if (data.vehicle_type !== null && data.vehicle_type !== undefined) {
                    this.telemetry.vehicle_type = data.vehicle_type;
                }

                this.updateStatusDisplay();
            });

        } catch (error) {
            console.error('Flask WebSocket connection failed:', error);
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

    vehicleTypeLabel(t) {
        const m = {1: 'Fixed Wing', 2: 'Quadrotor', 3: 'Coaxial Heli', 4: 'Helicopter',
                   10: 'Rover', 11: 'Boat', 19: 'VTOL Tailsitter', 20: 'VTOL Tiltrotor',
                   21: 'VTOL Fixed Rotor', 22: 'VTOL Fixed-Wing'};
        return m[t] || (t != null ? `MAV_TYPE ${t}` : '--');
    }

    updateStatusDisplay() {
        // Update MAVLink dot in header
        if (this.elements.mavlinkDot) {
            if (this.connected) {
                this.elements.mavlinkDot.classList.add('connected');
            } else {
                this.elements.mavlinkDot.classList.remove('connected');
            }
        }
        if (this.elements.mavlinkText) {
            this.elements.mavlinkText.textContent = this.connected ? 'MAVLink' : 'MAVLink';
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
            this.elements.telemArmed.className = this.telemetry.armed ? 'armed-status armed' : 'armed-status disarmed';
        }

        if (this.elements.telemVehicleType) {
            this.elements.telemVehicleType.textContent = this.vehicleTypeLabel(this.telemetry.vehicle_type);
        }

        // Arm/disarm buttons: enable based on connection, disable when already in target state
        if (this.elements.btnArm) {
            this.elements.btnArm.disabled = !this.connected || this.telemetry.armed;
        }
        if (this.elements.btnDisarm) {
            this.elements.btnDisarm.disabled = !this.connected || !this.telemetry.armed;
        }

        // Enable/disable send buttons based on connection + having mission data
        const client = window.mavlinkClient;
        const hasMission = client && client.currentMission && client.currentMission.items && client.currentMission.items.length > 0;

        if (this.elements.btnSendMission) {
            this.elements.btnSendMission.disabled = !this.connected || !hasMission || this.autoSendToDrone;
        }
        if (this.elements.btnSendCommand) {
            this.elements.btnSendCommand.disabled = !this.connected || !hasMission || this.autoSendToDrone;
        }
    }

    showDroneSendStatus(message, isSuccess) {
        if (this.elements.droneSendStatus) {
            this.elements.droneSendStatus.style.display = 'block';
            this.elements.droneSendStatus.textContent = message;
            this.elements.droneSendStatus.className = `drone-send-status ${isSuccess ? 'send-success' : 'send-error'}`;
        }
    }

    async armDrone() {
        this.elements.btnArm.disabled = true;
        this.elements.btnArm.textContent = 'Arming...';

        try {
            const response = await fetch(`${this.serverUrl}/api/arm`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'arm', force: false })
            });

            const result = await response.json();
            this.showDroneSendStatus(result.message, result.success);

            const client = window.mavlinkClient;
            if (result.success) {
                if (client) client.addMessage('agent', `Drone armed: ${result.message}`);
            } else {
                if (client) client.addMessage('error', `Arm failed: ${result.message}`);
            }
        } catch (error) {
            this.showDroneSendStatus(`Arm error: ${error.message}`, false);
        } finally {
            this.elements.btnArm.textContent = 'Arm';
            this.updateStatusDisplay();
        }
    }

    async disarmDrone() {
        this.elements.btnDisarm.disabled = true;
        this.elements.btnDisarm.textContent = 'Disarming...';

        try {
            const response = await fetch(`${this.serverUrl}/api/arm`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'disarm', force: false })
            });

            const result = await response.json();
            this.showDroneSendStatus(result.message, result.success);

            const client = window.mavlinkClient;
            if (result.success) {
                if (client) client.addMessage('agent', `Drone disarmed: ${result.message}`);
            } else {
                if (client) client.addMessage('error', `Disarm failed: ${result.message}`);
            }
        } catch (error) {
            this.showDroneSendStatus(`Disarm error: ${error.message}`, false);
        } finally {
            this.elements.btnDisarm.textContent = 'Disarm';
            this.updateStatusDisplay();
        }
    }

    async sendMission() {
        const client = window.mavlinkClient;
        if (!client || !client.currentMission || !client.currentMission.items) return;

        this.elements.btnSendMission.disabled = true;
        this.elements.btnSendMission.textContent = 'Sending...';

        try {
            const response = await fetch(`${this.serverUrl}/api/send_mission`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mission_items: client.currentMission.items })
            });

            const result = await response.json();
            this.showDroneSendStatus(result.message, result.success);

            if (result.success) {
                client.addMessage('agent', `Mission sent to drone: ${result.message}`);
            } else {
                client.addMessage('error', `Send failed: ${result.message}`);
            }
        } catch (error) {
            this.showDroneSendStatus(`Send error: ${error.message}`, false);
            client.addMessage('error', `Send error: ${error.message}`);
        } finally {
            this.elements.btnSendMission.textContent = 'Send & Execute Mission';
            this.updateStatusDisplay();
        }
    }

    async sendCommand() {
        const client = window.mavlinkClient;
        if (!client || !client.currentMission || !client.currentMission.items || !client.currentMission.items.length) return;

        this.elements.btnSendCommand.disabled = true;
        this.elements.btnSendCommand.textContent = 'Sending...';

        try {
            const response = await fetch(`${this.serverUrl}/api/send_command`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ command_item: client.currentMission.items[0] })
            });

            const result = await response.json();
            this.showDroneSendStatus(result.message, result.success);

            if (result.success) {
                client.addMessage('agent', `Command sent to drone: ${result.message}`);
            } else {
                client.addMessage('error', `Send failed: ${result.message}`);
            }
        } catch (error) {
            this.showDroneSendStatus(`Send error: ${error.message}`, false);
            client.addMessage('error', `Send error: ${error.message}`);
        } finally {
            this.elements.btnSendCommand.textContent = 'Send Command';
            this.updateStatusDisplay();
        }
    }
}

class MAVLinkAgentClient {
    constructor() {
        this.baseUrl = window.location.origin;
        this.currentMode = 'mission';
        this.isConnected = false;
        this.isProcessing = false;

        // Client-side state management
        this.currentMission = null;
        this.chatHistory = [];

        this.initializeElements();
        this.attachEventListeners();
        this.checkServerConnection();
    }

    initializeElements() {
        this.elements = {
            serverDot: document.getElementById('serverDot'),
            serverText: document.getElementById('serverText'),

            missionModeBtn: document.getElementById('missionModeBtn'),
            commandModeBtn: document.getElementById('commandModeBtn'),
            missionDesc: document.getElementById('missionDesc'),
            commandDesc: document.getElementById('commandDesc'),

            chatMessages: document.getElementById('chatMessages'),
            messageInput: document.getElementById('messageInput'),
            sendButton: document.getElementById('sendButton'),

            missionItems: document.getElementById('missionItems'),

            loadingOverlay: document.getElementById('loadingOverlay')
        };
    }

    attachEventListeners() {
        this.elements.missionModeBtn.addEventListener('click', () => this.switchMode('mission'));
        this.elements.commandModeBtn.addEventListener('click', () => this.switchMode('command'));

        this.elements.messageInput.addEventListener('input', () => {
            this.updateSendButton();
        });

        this.elements.sendButton.addEventListener('click', () => this.sendMessage());

        this.updateSendButton();
    }

    async checkServerConnection() {
        try {
            const response = await fetch(`${this.baseUrl}/api/status`);
            this.isConnected = response.ok;
        } catch (error) {
            this.isConnected = false;
        }
        this.updateConnectionStatus();
        setTimeout(() => this.checkServerConnection(), 5000);
    }

    updateConnectionStatus() {
        if (this.isConnected) {
            this.elements.serverDot.classList.add('connected');
            this.elements.serverText.textContent = 'Server';
        } else {
            this.elements.serverDot.classList.remove('connected');
            this.elements.serverText.textContent = 'Server';
        }

        this.updateSendButton();
    }

    switchMode(mode) {
        this.currentMode = mode;

        this.elements.missionModeBtn.classList.toggle('active', mode === 'mission');
        this.elements.commandModeBtn.classList.toggle('active', mode === 'command');

        this.elements.missionDesc.classList.toggle('active', mode === 'mission');
        this.elements.commandDesc.classList.toggle('active', mode === 'command');

        // Toggle send button visibility based on mode
        const gcs = window.mavlinkGCS;
        if (gcs) {
            if (gcs.elements.btnSendMission) {
                gcs.elements.btnSendMission.style.display = mode === 'mission' ? 'inline-block' : 'none';
            }
            if (gcs.elements.btnSendCommand) {
                gcs.elements.btnSendCommand.style.display = mode === 'command' ? 'inline-block' : 'none';
            }
        }

        // Clear chat and mission state when switching modes
        this.clearChat();
        this.clearMissionState();

        this.currentMission = null;
        this.chatHistory = [];

        if (mode === 'command') {
            this.addMessage('agent', 'Switched to Command Mode. Each command will create a fresh mission.');
        } else {
            this.addMessage('agent', 'Switched to Mission Mode. Build your mission step by step.');
        }

        this.elements.messageInput.focus();

        // Update send buttons state
        if (gcs) gcs.updateStatusDisplay();
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
            mission_state: this.currentMission ? this.currentMission.items : null,
            vehicle_type: gcs ? gcs.telemetry.vehicle_type : null
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
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestBody)
            });

            const result = await response.json();

            if (result.success) {
                if (result.output) {
                    this.addMessage('agent', result.output);
                }

                // Update client-side mission state
                if (result.mission_items && result.mission_items.length > 0) {
                    this.currentMission = {
                        items: result.mission_items,
                        created_at: new Date().toISOString(),
                        modified_at: new Date().toISOString()
                    };
                }

                this.chatHistory.push({
                    role: 'user',
                    content: message
                });
                this.chatHistory.push({
                    role: 'assistant',
                    content: result.output
                });

                this.updateMissionDisplay(result);

                // Check for auto-send result
                if (result.drone_send) {
                    const ds = result.drone_send;
                    const statusMsg = ds.success
                        ? `Auto-sent to drone: ${ds.message}`
                        : `Auto-send failed: ${ds.message}`;
                    this.addMessage(ds.success ? 'agent' : 'error', statusMsg);

                    if (gcs) {
                        gcs.showDroneSendStatus(ds.message, ds.success);
                    }
                }

                // Update send button state after we have mission data
                if (gcs) gcs.updateStatusDisplay();

            } else {
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

    mavCmdName(cmd) {
        const names = {
            16: 'NAV_WAYPOINT', 17: 'NAV_LOITER_UNLIM', 18: 'NAV_LOITER_TURNS',
            19: 'NAV_LOITER_TIME', 20: 'NAV_RETURN_TO_LAUNCH', 21: 'NAV_LAND',
            22: 'NAV_TAKEOFF', 84: 'NAV_VTOL_TAKEOFF', 85: 'NAV_VTOL_LAND',
            192: 'DO_REPOSITION', 201: 'DO_SET_ROI'
        };
        return names[cmd] || `CMD_${cmd}`;
    }

    mavCmdEmoji(cmd) {
        const emojis = {16: '📍', 17: '🔄', 20: '🏠', 21: '🛬', 22: '🚀'};
        return emojis[cmd] || '❓';
    }

    mavCmdParamNames(cmd) {
        const defs = {
            16:  ['hold(s)', 'accept_r(m)', 'pass_r(m)', 'yaw(°)',       'lat', 'lon', 'alt(m)'],
            17:  ['—',       '—',           'radius(m)', 'yaw(°)',       'lat', 'lon', 'alt(m)'],
            18:  ['turns',   'hdg_req',     'radius(m)', 'xtrack(m)',    'lat', 'lon', 'alt(m)'],
            19:  ['time(s)', 'hdg_req',     'radius(m)', 'xtrack(m)',    'lat', 'lon', 'alt(m)'],
            20:  ['—',       '—',           '—',         '—',            '—',   '—',   '—'     ],
            21:  ['abort_alt','land_mode',  '—',         'yaw(°)',       'lat', 'lon', 'alt(m)'],
            22:  ['min_pitch','—',          '—',         'yaw(°)',       'lat', 'lon', 'alt(m)'],
            84:  ['—',       'hdg_mode',    '—',         'yaw(°)',       'lat', 'lon', 'alt(m)'],
            85:  ['—',       '—',           '—',         'yaw(°)',       'lat', 'lon', 'alt(m)'],
            192: ['speed(m/s)','bitmask',   'radius(m)', 'yaw(°)',       'lat', 'lon', 'alt(m)'],
        };
        return defs[cmd] || ['param1','param2','param3','param4','x','y','z'];
    }

    mavFrameName(frame) {
        const frames = {
            0: 'GLOBAL', 1: 'LOCAL_NED', 2: 'MISSION',
            3: 'GLOBAL_REL_ALT', 4: 'LOCAL_ENU', 5: 'GLOBAL_INT',
            6: 'GLOBAL_REL_ALT_INT', 7: 'LOCAL_OFFSET_NED',
            8: 'BODY_NED', 9: 'BODY_OFFSET_NED', 10: 'GLOBAL_TERRAIN_ALT',
            11: 'GLOBAL_TERRAIN_ALT_INT'
        };
        return frames[frame] ? `${frame} (${frames[frame]})` : `${frame}`;
    }

    updateMissionDisplay(result) {
        if (!result.mission_items || result.mission_items.length === 0) {
            this.elements.missionItems.innerHTML = '<div class="empty-mission">No mission items yet</div>';
            return;
        }

        const itemsHtml = result.mission_items.map((item) => {
            const cmd = item.command;
            const cmdName = this.mavCmdName(cmd);
            const emoji = this.mavCmdEmoji(cmd);
            const labels = this.mavCmdParamNames(cmd);

            const isNew = result.added_items?.some(a => a.seq === item.seq);
            const isModified = result.modified_items?.some(m => m.seq === item.seq);

            const badge = isNew ? '<span class="badge new">NEW</span>' :
                         isModified ? '<span class="badge modified">MODIFIED</span>' : '';

            const rawLat = item.x / 1e7;
            const rawLon = item.y / 1e7;
            const latVal = (item.x === 0 && item.y === 0) ? '—' : rawLat.toFixed(7);
            const lonVal = (item.x === 0 && item.y === 0) ? '—' : rawLon.toFixed(7);
            const altVal = typeof item.z === 'number' ? item.z.toFixed(2) : item.z;

            const paramVals = [item.param1, item.param2, item.param3, item.param4, latVal, lonVal, altVal];

            const rows = labels.map((label, i) => {
                const raw = paramVals[i];
                const val = (raw === undefined || raw === null || (typeof raw === 'number' && isNaN(raw))) ? '' : raw;
                return `<tr><td>${label}</td><td>${val}</td></tr>`;
            }).join('');

            return `
                <div class="mission-item ${isNew ? 'item-new' : ''} ${isModified ? 'item-modified' : ''}">
                    <div class="mission-item-header">
                        ${emoji} ${item.seq}. ${cmdName} (${cmd}) ${badge}
                    </div>
                    <div class="mission-item-details">
                        <table class="mission-item-table">
                            ${rows}
                            <tr><td>frame</td><td>${this.mavFrameName(item.frame)}</td></tr>
                            <tr><td>autocontinue</td><td>${item.autocontinue}</td></tr>
                        </table>
                    </div>
                </div>
            `;
        }).join('');

        this.elements.missionItems.innerHTML = itemsHtml;
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
