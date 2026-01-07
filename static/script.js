/**
 * MAVLink Agent Web Chat Interface
 * JavaScript API client and chat functionality
 */

class MAVLinkAgentClient {
    constructor() {
        this.baseUrl = window.location.origin;
        this.currentMode = 'mission';
        this.isConnected = false;
        this.isProcessing = false;
        
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
            
            // Takeoff Settings elements (Mission Mode)
            takeoffSettingsPanel: document.getElementById('takeoffSettingsPanel'),
            takeoffSettingsHeader: document.getElementById('takeoffSettingsHeader'),
            takeoffSettingsToggle: document.getElementById('takeoffSettingsToggle'),
            takeoffSettingsContent: document.getElementById('takeoffSettingsContent'),
            takeoffCollapsedInfo: document.getElementById('takeoffCollapsedInfo'),
            takeoffCurrentSettings: document.getElementById('takeoffCurrentSettings'),
            takeoffLatitudeInput: document.getElementById('takeoffLatitudeInput'),
            takeoffLongitudeInput: document.getElementById('takeoffLongitudeInput'),
            takeoffAltitudeInput: document.getElementById('takeoffAltitudeInput'),
            takeoffAltitudeUnitsInput: document.getElementById('takeoffAltitudeUnitsInput'),
            takeoffHeadingInput: document.getElementById('takeoffHeadingInput'),
            setTakeoffBtn: document.getElementById('setTakeoffBtn'),
            
            // Current Action elements (Command Mode)
            currentActionPanel: document.getElementById('currentActionPanel'),
            currentActionHeader: document.getElementById('currentActionHeader'),
            currentActionToggle: document.getElementById('currentActionToggle'),
            currentActionContent: document.getElementById('currentActionContent'),
            actionCollapsedInfo: document.getElementById('actionCollapsedInfo'),
            actionCurrentSettings: document.getElementById('actionCurrentSettings'),
            actionTypeInput: document.getElementById('actionTypeInput'),
            actionLatitudeInput: document.getElementById('actionLatitudeInput'),
            actionLongitudeInput: document.getElementById('actionLongitudeInput'),
            actionAltitudeInput: document.getElementById('actionAltitudeInput'),
            actionAltitudeUnitsInput: document.getElementById('actionAltitudeUnitsInput'),
            actionRadiusInput: document.getElementById('actionRadiusInput'),
            actionRadiusUnitsInput: document.getElementById('actionRadiusUnitsInput'),
            actionHeadingInput: document.getElementById('actionHeadingInput'),
            actionSearchTargetInput: document.getElementById('actionSearchTargetInput'),
            actionDetectionBehaviorInput: document.getElementById('actionDetectionBehaviorInput'),
            setCurrentActionBtn: document.getElementById('setCurrentActionBtn'),
            radiusRow: document.getElementById('radiusRow'),
            searchRow: document.getElementById('searchRow'),
            headingRow: document.getElementById('headingRow'),
            
            // Loading elements
            loadingOverlay: document.getElementById('loadingOverlay')
        };
    }
    
    attachEventListeners() {
        // Mode switching
        this.elements.missionModeBtn.addEventListener('click', () => this.switchMode('mission'));
        this.elements.commandModeBtn.addEventListener('click', () => this.switchMode('command'));
        
        // Remove Enter key handling - now only use send button
        
        this.elements.messageInput.addEventListener('input', () => {
            this.updateSendButton();
        });
        
        this.elements.sendButton.addEventListener('click', () => this.sendMessage());
        
        // Takeoff Settings panel handling (Mission Mode)
        this.elements.takeoffSettingsHeader.addEventListener('click', () => this.toggleTakeoffSettings());
        this.elements.setTakeoffBtn.addEventListener('click', () => this.updateTakeoffSettings());
        
        // Takeoff settings input validation
        [this.elements.takeoffLatitudeInput, this.elements.takeoffLongitudeInput, this.elements.takeoffAltitudeInput, this.elements.takeoffHeadingInput].forEach(input => {
            input.addEventListener('input', () => this.validateTakeoffSettingsForm());
        });
        
        // Current Action panel handling (Command Mode)
        this.elements.currentActionHeader.addEventListener('click', () => this.toggleCurrentActionSettings());
        this.elements.setCurrentActionBtn.addEventListener('click', () => this.updateCurrentActionSettings());
        
        // Action type change handler for dynamic fields
        this.elements.actionTypeInput.addEventListener('change', () => this.updateActionTypeFields());
        
        // Current action input validation
        [this.elements.actionLatitudeInput, this.elements.actionLongitudeInput, this.elements.actionAltitudeInput, 
         this.elements.actionRadiusInput, this.elements.actionHeadingInput, this.elements.actionSearchTargetInput, 
         this.elements.actionDetectionBehaviorInput].forEach(input => {
            input.addEventListener('input', () => this.validateCurrentActionForm());
        });
        
        // Initial state
        this.updateSendButton();
        this.loadCurrentSettings();
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
        
        // Switch settings panels based on mode
        if (mode === 'mission') {
            // Show takeoff settings panel, hide current action panel
            this.elements.takeoffSettingsPanel.style.display = 'block';
            this.elements.currentActionPanel.style.display = 'none';
        } else {
            // Show current action panel, hide takeoff settings panel
            this.elements.takeoffSettingsPanel.style.display = 'none';
            this.elements.currentActionPanel.style.display = 'block';
        }
        
        // Clear chat and mission state when switching modes
        this.clearChat();
        this.clearMissionState();
        
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
        if (message.toLowerCase() === 'show' || message.toLowerCase() === 'review') {
            this.showMissionReview();
            this.elements.messageInput.value = '';
            this.updateSendButton();
            return;
        }
        
        if (message.toLowerCase() === 'clear') {
            this.clearChat();
            this.elements.messageInput.value = '';
            this.updateSendButton();
            return;
        }
        
        // Add user message to chat
        this.addMessage('user', message);
        
        // Clear input and show loading
        this.elements.messageInput.value = '';
        this.updateSendButton();
        this.showLoading(true);
        this.isProcessing = true;
        
        try {
            // Send request to appropriate endpoint
            const endpoint = this.currentMode === 'mission' ? '/api/mission' : '/api/command';
            const response = await fetch(`${this.baseUrl}${endpoint}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    user_input: message
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                // Add agent response
                if (result.output) {
                    this.addMessage('agent', result.output);
                }
                
                // Update mission state
                if (result.mission_state) {
                    this.updateMissionState(result.mission_state);
                }
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
    
    async showMissionReview() {
        this.showLoading(true);
        
        try {
            const response = await fetch(`${this.baseUrl}/api/mission/show`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.addMessage('agent', result.output || 'Mission reviewed');
                if (result.mission_state) {
                    this.updateMissionState(result.mission_state);
                }
            } else {
                this.addMessage('error', `Error: ${result.error || 'Failed to show mission'}`);
            }
            
        } catch (error) {
            console.error('Mission review failed:', error);
            this.addMessage('error', `Connection failed: ${error.message}`);
        } finally {
            this.showLoading(false);
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
    
    updateMissionState(missionState) {
        if (!missionState || !missionState.items || missionState.items.length === 0) {
            this.elements.missionItems.innerHTML = '<div class="empty-mission">No mission items yet</div>';
            return;
        }
        
        const itemsHtml = missionState.items.map((item, index) => {
            const commandType = item.command_type || 'unknown';
            const emoji = this.getCommandEmoji(commandType);
            
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
                <div class="mission-item">
                    <div class="mission-item-header">
                        ${emoji} ${index + 1}. ${commandType.toUpperCase()}
                    </div>
                    <div class="mission-item-details">
                        ${details.map(detail => `<div>${detail}</div>`).join('')}
                    </div>
                </div>
            `;
        }).join('');
        
        this.elements.missionItems.innerHTML = itemsHtml;
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
    
    toggleTakeoffSettings() {
        const content = this.elements.takeoffSettingsContent;
        const toggle = this.elements.takeoffSettingsToggle;
        
        if (content.classList.contains('collapsed')) {
            content.classList.remove('collapsed');
            toggle.classList.remove('collapsed');
            toggle.textContent = '▼';
        } else {
            content.classList.add('collapsed');
            toggle.classList.add('collapsed');
            toggle.textContent = '▶';
        }
    }
    
    toggleCurrentActionSettings() {
        const content = this.elements.currentActionContent;
        const toggle = this.elements.currentActionToggle;
        
        if (content.classList.contains('collapsed')) {
            content.classList.remove('collapsed');
            toggle.classList.remove('collapsed');
            toggle.textContent = '▼';
        } else {
            content.classList.add('collapsed');
            toggle.classList.add('collapsed');
            toggle.textContent = '▶';
        }
    }
    
    async loadCurrentSettings() {
        // Load both takeoff settings and current action settings
        await this.loadTakeoffSettings();
        await this.loadCurrentActionSettings();
    }
    
    async loadTakeoffSettings() {
        try {
            const response = await fetch(`${this.baseUrl}/api/settings/takeoff`);
            const result = await response.json();
            
            if (result.success) {
                const settings = result.settings;
                const displayText = `${settings.latitude.toFixed(6)}, ${settings.longitude.toFixed(6)}, ${settings.altitude} ${settings.altitude_units}, ${settings.heading}`;
                
                // Update expanded current settings display
                this.elements.takeoffCurrentSettings.innerHTML = `
                    <div class="current-value">
                        Current: ${displayText}
                    </div>
                `;
                
                // Update collapsed info display
                this.elements.takeoffCollapsedInfo.textContent = displayText;
                
                // Prefill form fields with current values
                this.elements.takeoffLatitudeInput.value = settings.latitude;
                this.elements.takeoffLongitudeInput.value = settings.longitude;
                this.elements.takeoffAltitudeInput.value = settings.altitude;
                this.elements.takeoffAltitudeUnitsInput.value = settings.altitude_units;
                this.elements.takeoffHeadingInput.value = settings.heading || '';
                
                this.validateTakeoffSettingsForm(); // Enable button if form is now valid
            } else {
                this.elements.takeoffCurrentSettings.innerHTML = `
                    <div class="current-value">Failed to load takeoff settings</div>
                `;
                this.elements.takeoffCollapsedInfo.textContent = 'Failed to load';
            }
        } catch (error) {
            console.error('Failed to load takeoff settings:', error);
            this.elements.takeoffCurrentSettings.innerHTML = `
                <div class="current-value">Error loading settings</div>
            `;
            this.elements.takeoffCollapsedInfo.textContent = 'Error loading';
        }
    }
    
    async loadCurrentActionSettings() {
        try {
            const response = await fetch(`${this.baseUrl}/api/settings/current-action`);
            const result = await response.json();
            
            if (result.success) {
                const settings = result.settings;
                const displayText = `${settings.type}: ${settings.latitude.toFixed(6)}, ${settings.longitude.toFixed(6)}, ${settings.altitude} ${settings.altitude_units}`;
                
                // Update expanded current settings display
                this.elements.actionCurrentSettings.innerHTML = `
                    <div class="current-value">
                        Current: ${displayText}
                    </div>
                `;
                
                // Update collapsed info display
                this.elements.actionCollapsedInfo.textContent = displayText;
                
                // Update form fields with current values
                this.elements.actionTypeInput.value = settings.type;
                this.elements.actionLatitudeInput.value = settings.latitude;
                this.elements.actionLongitudeInput.value = settings.longitude;
                this.elements.actionAltitudeInput.value = settings.altitude;
                this.elements.actionAltitudeUnitsInput.value = settings.altitude_units;
                this.elements.actionRadiusInput.value = settings.radius;
                this.elements.actionRadiusUnitsInput.value = settings.radius_units;
                this.elements.actionHeadingInput.value = settings.heading || '';
                this.elements.actionSearchTargetInput.value = settings.search_target || '';
                this.elements.actionDetectionBehaviorInput.value = settings.detection_behavior || '';
                
                this.updateActionTypeFields(); // Update visibility based on type
                
            } else {
                this.elements.actionCurrentSettings.innerHTML = `
                    <div class="current-value">Failed to load current action settings</div>
                `;
                this.elements.actionCollapsedInfo.textContent = 'Failed to load';
            }
        } catch (error) {
            console.error('Failed to load current action settings:', error);
            this.elements.actionCurrentSettings.innerHTML = `
                <div class="current-value">Error loading settings</div>
            `;
            this.elements.actionCollapsedInfo.textContent = 'Error loading';
        }
    }
    
    validateTakeoffSettingsForm() {
        const lat = this.elements.takeoffLatitudeInput.value.trim();
        const lon = this.elements.takeoffLongitudeInput.value.trim();
        const alt = this.elements.takeoffAltitudeInput.value.trim();
        const heading = this.elements.takeoffHeadingInput.value.trim();
        
        // Check if individual fields are valid when filled
        const latValid = !lat || (!isNaN(lat) && lat >= -90 && lat <= 90);
        const lonValid = !lon || (!isNaN(lon) && lon >= -180 && lon <= 180);
        const altValid = !alt || (!isNaN(alt) && alt > 0);
        const headingValid = true; // Dropdown always valid
        
        // Check if at least one field has content
        const hasContent = lat || lon || alt || heading;
        
        // All filled fields must be valid AND at least one field must have content
        const formValid = latValid && lonValid && altValid && headingValid && hasContent;
        this.elements.setTakeoffBtn.disabled = !formValid;
    }
    
    validateCurrentActionForm() {
        const lat = this.elements.actionLatitudeInput.value.trim();
        const lon = this.elements.actionLongitudeInput.value.trim();
        const alt = this.elements.actionAltitudeInput.value.trim();
        const radius = this.elements.actionRadiusInput.value.trim();
        const searchTarget = this.elements.actionSearchTargetInput.value.trim();
        const detectionBehavior = this.elements.actionDetectionBehaviorInput.value.trim();
        
        // Check if individual fields are valid when filled
        const latValid = !lat || (!isNaN(lat) && lat >= -90 && lat <= 90);
        const lonValid = !lon || (!isNaN(lon) && lon >= -180 && lon <= 180);
        const altValid = !alt || (!isNaN(alt) && alt > 0);
        const radiusValid = !radius || (!isNaN(radius) && radius > 0);
        const searchValid = true; // Search fields are always valid (text/dropdown)
        
        // Check if at least one field has content
        const hasContent = lat || lon || alt || radius || searchTarget || detectionBehavior;
        
        // All filled fields must be valid AND at least one field must have content
        const formValid = latValid && lonValid && altValid && radiusValid && searchValid && hasContent;
        this.elements.setCurrentActionBtn.disabled = !formValid;
        
        return formValid;
    }
    
    updateActionTypeFields() {
        const actionType = this.elements.actionTypeInput.value;
        
        // Show/hide radius field based on action type
        if (actionType === 'loiter' || actionType === 'survey') {
            this.elements.radiusRow.style.display = 'flex';
        } else {
            this.elements.radiusRow.style.display = 'none';
        }
        
        // Show search fields for waypoint, loiter, and survey (not takeoff)
        if (actionType === 'waypoint' || actionType === 'loiter' || actionType === 'survey') {
            this.elements.searchRow.style.display = 'flex';
        } else {
            this.elements.searchRow.style.display = 'none';
        }
        
        // Show heading only for takeoff (VTOL transition direction)
        if (actionType === 'takeoff') {
            this.elements.headingRow.style.display = 'flex';
        } else {
            this.elements.headingRow.style.display = 'none';
        }
    }
    
    async updateCurrentActionSettings() {
        const actionType = this.elements.actionTypeInput.value;
        const latitude = this.elements.actionLatitudeInput.value.trim();
        const longitude = this.elements.actionLongitudeInput.value.trim(); 
        const altitude = this.elements.actionAltitudeInput.value.trim();
        const altitudeUnits = this.elements.actionAltitudeUnitsInput.value;
        const radius = this.elements.actionRadiusInput.value.trim();
        const radiusUnits = this.elements.actionRadiusUnitsInput.value;
        const heading = this.elements.actionHeadingInput.value;
        const searchTarget = this.elements.actionSearchTargetInput.value.trim();
        const detectionBehavior = this.elements.actionDetectionBehaviorInput.value;
        
        const requestData = {};
        
        // Always include action type
        requestData.type = actionType;
        
        // Add other fields only if they have values
        if (latitude) requestData.latitude = parseFloat(latitude);
        if (longitude) requestData.longitude = parseFloat(longitude);
        if (altitude) requestData.altitude = parseFloat(altitude);
        if (altitudeUnits) requestData.altitude_units = altitudeUnits;
        if (radius) requestData.radius = parseFloat(radius);
        if (radiusUnits) requestData.radius_units = radiusUnits;
        if (heading) requestData.heading = heading;
        if (searchTarget) requestData.search_target = searchTarget;
        if (detectionBehavior) requestData.detection_behavior = detectionBehavior;
        
        try {
            const response = await fetch(`${this.baseUrl}/api/settings/current-action`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestData)
            });
            
            const result = await response.json();
            
            if (result.success) {
                // Clear form inputs
                this.elements.actionLatitudeInput.value = '';
                this.elements.actionLongitudeInput.value = '';
                this.elements.actionAltitudeInput.value = '';
                this.elements.actionRadiusInput.value = '';
                this.elements.actionHeadingInput.value = '';
                this.elements.actionSearchTargetInput.value = '';
                this.elements.actionDetectionBehaviorInput.value = '';
                
                // Reload settings to show updated values
                this.loadCurrentActionSettings();
                
                this.addMessage('agent', `Current action updated: ${result.message}`);
            } else {
                this.addMessage('agent', `Failed to update current action: ${result.error}`);
            }
        } catch (error) {
            console.error('Error updating current action settings:', error);
            this.addMessage('agent', 'Error updating current action settings');
        }
    }
    
    async updateTakeoffSettings() {
        if (!this.validateTakeoffSettingsForm()) {
            this.addMessage('error', 'Please provide at least one valid field.');
            return;
        }
        
        // Build request with only filled fields
        const requestData = {};
        const lat = this.elements.takeoffLatitudeInput.value.trim();
        const lon = this.elements.takeoffLongitudeInput.value.trim();
        const alt = this.elements.takeoffAltitudeInput.value.trim();
        const altUnits = this.elements.takeoffAltitudeUnitsInput.value;
        const heading = this.elements.takeoffHeadingInput.value.trim();
        
        if (lat) requestData.latitude = parseFloat(lat);
        if (lon) requestData.longitude = parseFloat(lon);
        if (alt) requestData.altitude = parseFloat(alt);
        if (altUnits) requestData.altitude_units = altUnits;
        if (heading) requestData.heading = heading;
        
        try {
            this.elements.setTakeoffBtn.disabled = true;
            this.elements.setTakeoffBtn.textContent = 'Setting...';
            
            const response = await fetch(`${this.baseUrl}/api/settings/takeoff`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestData)
            });
            
            const result = await response.json();
            
            if (result.success) {
                const settings = result.settings;
                const updatedFields = [];
                if (requestData.latitude !== undefined) updatedFields.push(`Lat: ${settings.latitude.toFixed(6)}`);
                if (requestData.longitude !== undefined) updatedFields.push(`Lon: ${settings.longitude.toFixed(6)}`);
                if (requestData.altitude !== undefined) updatedFields.push(`Alt: ${settings.altitude} ${settings.altitude_units}`);
                if (requestData.heading !== undefined) updatedFields.push(`Heading: ${settings.heading}`);
                
                this.addMessage('agent', `✅ Takeoff settings updated: ${updatedFields.join(', ')}`);
                
                // Clear form
                this.elements.takeoffLatitudeInput.value = '';
                this.elements.takeoffLongitudeInput.value = '';
                this.elements.takeoffAltitudeInput.value = '';
                this.elements.takeoffHeadingInput.value = '';
                
                // Reload current settings display
                this.loadTakeoffSettings();
                
            } else {
                this.addMessage('error', `Failed to update settings: ${result.error}`);
            }
            
        } catch (error) {
            console.error('Settings update failed:', error);
            this.addMessage('error', `Connection failed: ${error.message}`);
        } finally {
            this.elements.setTakeoffBtn.disabled = false;
            this.elements.setTakeoffBtn.textContent = 'Set Location';
            this.validateTakeoffSettingsForm();
        }
    }
}

// Initialize the client when the page loads
document.addEventListener('DOMContentLoaded', () => {
    window.mavlinkClient = new MAVLinkAgentClient();
});