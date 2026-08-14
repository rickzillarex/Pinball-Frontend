javascript
let folderHandle = null;
let config = {};
let tables = [];
let mediaFiles = [];

// Step 1: Open folder for file access
document.getElementById('openFolderBtn').addEventListener('click', async () => {
    try {
        folderHandle = await window.showDirectoryPicker();
        document.getElementById('folderStatus').textContent = '✓ Folder access granted';
        document.getElementById('folderStatus').classList.add('success');
        
        // Load existing config and tables
        await loadConfig();
        await loadTables();
    } catch (err) {
        document.getElementById('folderStatus').textContent = '✗ Error: ' + err.message;
        document.getElementById('folderStatus').classList.add('error');
    }
});

// Load config.json
async function loadConfig() {
    if (!folderHandle) return;
    try {
        const configFile = await folderHandle.getFileHandle('config.json');
        const file = await configFile.getFile();
        const text = await file.text();
        config = JSON.parse(text);
        
        document.getElementById('vpxExePath').value = config.vpx_exe_path || '';
        document.getElementById('tablesPath').value = config.table_folder_path || '';
        document.getElementById('mediaPath').value = config.media_folder_path || '';
        document.getElementById('rotation').value = config.rotation_angle || '0';
        document.getElementById('fontSize').value = config.font_size || '24';
        document.getElementById('windowWidth').value = config.window_width || '3840';
        document.getElementById('windowHeight').value = config.window_height || '2160';
    } catch (err) {
        config = {
            vpx_exe_path: '',
            table_folder_path: '',
            media_folder_path: '',
            rotation_angle: 0,
            font_size: 24,
            window_width: 3840,
            window_height: 2160
        };
    }
}

// Load tables.json
async function loadTables() {
    if (!folderHandle) return;
    try {
        const tablesFile = await folderHandle.getFileHandle('tables.json');
        const file = await tablesFile.getFile();
        const text = await file.text();
        tables = JSON.parse(text);
        renderTablesList();
    } catch (err) {
        tables = [];
    }
}

// Step 2: Save paths to config
document.getElementById('savePathsBtn').addEventListener('click', async () => {
    if (!folderHandle) {
        document.getElementById('pathStatus').textContent = '✗ Please grant folder access first';
        document.getElementById('pathStatus').classList.add('error');
        return;
    }

    config.vpx_exe_path = document.getElementById('vpxExePath').value;
    config.table_folder_path = document.getElementById('tablesPath').value;
    config.media_folder_path = document.getElementById('mediaPath').value;

    try {
        const configFile = await folderHandle.getFileHandle('config.json', { create: true });
        const writable = await configFile.createWritable();
        await writable.write(JSON.stringify(config, null, 2));
        await writable.close();
        
        document.getElementById('pathStatus').textContent = '✓ Paths saved successfully';
        document.getElementById('pathStatus').classList.add('success');
    } catch (err) {
        document.getElementById('pathStatus').textContent = '✗ Error saving: ' + err.message;
        document.getElementById('pathStatus').classList.add('error');
    }
});

// Step 3: Save settings to config
document.getElementById('saveSettingsBtn').addEventListener('click', async () => {
    if (!folderHandle) {
        document.getElementById('settingsStatus').textContent = '✗ Please grant folder access first';
        document.getElementById('settingsStatus').classList.add('error');
        return;
    }

    config.rotation_angle = parseInt(document.getElementById('rotation').value);
    config.font_size = parseInt(document.getElementById('fontSize').value);
    config.window_width = parseInt(document.getElementById('windowWidth').value);
    config.window_height = parseInt(document.getElementById('windowHeight').value);

    try {
        const configFile = await folderHandle.getFileHandle('config.json', { create: true });
        const writable = await configFile.createWritable();
        await writable.write(JSON.stringify(config, null, 2));
        await writable.close();
        
        document.getElementById('settingsStatus').textContent = '✓ Settings saved successfully';
        document.getElementById('settingsStatus').classList.add('success');
    } catch (err) {
        document.getElementById('settingsStatus').textContent = '✗ Error saving: ' + err.message;
        document.getElementById('settingsStatus').classList.add('error');
    }
});

// Step 4: Scan folders
document.getElementById('scanBtn').addEventListener('click', async () => {
    if (!config.table_folder_path || !config.media_folder_path) {
        document.getElementById('scanStatus').textContent = '✗ Please set Tables and Media folder paths first';
        document.getElementById('scanStatus').classList.add('error');
        return;
    }

    document.getElementById('scanStatus').textContent = '⏳ Scanning...';
    document.getElementById('scanStatus').classList.remove('success', 'error');

    try {
        // Scan tables folder
        const tablesFolderHandle = await window.showDirectoryPicker();
        tables = [];

        const vpxFiles = [];
        for await (const entry of tablesFolderHandle.values()) {
            if (entry.kind === 'file' && entry.name.endsWith('.vpx')) {
                vpxFiles.push(entry.name);
            }
        }
        vpxFiles.sort();

        // Scan media folder
        const mediaFolderHandle = await window.showDirectoryPicker();
        mediaFiles = [];
        const imageExts = ['.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif'];

        for await (const entry of mediaFolderHandle.values()) {
            if (entry.kind === 'file') {
                const ext = entry.name.substring(entry.name.lastIndexOf('.')).toLowerCase();
                if (imageExts.includes(ext)) {
                    mediaFiles.push(entry.name);
                }
            }
        }
        mediaFiles.sort();

        // Create table entries and auto-match media
        vpxFiles.forEach(vpxFile => {
            const tableName = vpxFile.replace('.vpx', '');
            const matchedMedia = autoMatchMedia(tableName);
            
            tables.push({
                filename: vpxFile,
                display_name: tableName,
                visible: true,
                media_file: matchedMedia
            });
        });

        renderTablesList();
        document.getElementById('scanStatus').textContent = `✓ Found ${tables.length} tables, ${mediaFiles.length} media files`;
        document.getElementById('scanStatus').classList.add('success');
    } catch (err) {
        document.getElementById('scanStatus').textContent = '✗ Error scanning: ' + err.message;
        document.getElementById('scanStatus').classList.add('error');
    }
});

// Auto-match media to table by filename
function autoMatchMedia(tableName) {
    const normalized = tableName.toLowerCase().replace(/[^a-z0-9]/g, '');
    
    for (let media of mediaFiles) {
        const mediaNormalized = media.replace(/\.[^/.]+$/, '').toLowerCase().replace(/[^a-z0-9]/g, '');
        if (mediaNormalized === normalized) {
            return media;
        }
    }
    return '';
}

// Render tables list as editable grid
function renderTablesList() {
    const tbody = document.getElementById('tablesList');
    
    if (tables.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="placeholder">No tables scanned yet. Complete Steps 2-4 above.</td></tr>';
        return;
    }

    tbody.innerHTML = tables.map((table, index) => `
        <tr>
            <td>
                <input type="checkbox" class="table-visible" data-index="${index}" ${table.visible ? 'checked' : ''}>
            </td>
            <td class="filename">${table.filename}</td>
            <td>
                <input type="text" class="table-display-name" data-index="${index}" value="${table.display_name}">
            </td>
            <td class="media-file">${table.media_file || '(none)'}</td>
            <td>
                <button class="btn-pick-media" data-index="${index}">Pick Media</button>
            </td>
        </tr>
    `).join('');

    // Add event listeners for visibility toggles
    document.querySelectorAll('.table-visible').forEach(checkbox => {
        checkbox.addEventListener('change', (e) => {
            const index = parseInt(e.target.dataset.index);
            tables[index].visible = e.target.checked;
        });
    });

    // Add event listeners for display name edits
    document.querySelectorAll('.table-display-name').forEach(input => {
        input.addEventListener('change', (e) => {
            const index = parseInt(e.target.dataset.index);
            tables[index].display_name = e.target.value;
        });
    });

    // Add event listeners for media picker buttons
    document.querySelectorAll('.btn-pick-media').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const index = parseInt(e.target.dataset.index);
            showMediaPicker(index);
        });
    });
}

// Show media picker for a specific table
function showMediaPicker(index) {
    const mediaOptions = mediaFiles.map((file, i) => `
        <div class="media-option" data-media="${file}">
            <input type="radio" name="media-pick" value="${file}" id="media-${i}" ${tables[index].media_file === file ? 'checked' : ''}>
            <label for="media-${i}">${file}</label>
        </div>
    `).join('');

    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.innerHTML = `
        <div class="modal-content">
            <h3>Select Media for: ${tables[index].display_name}</h3>
            <div class="media-picker">
                <div class="media-option">
                    <input type="radio" name="media-pick" value="" id="media-none" ${!tables[index].media_file ? 'checked' : ''}>
                    <label for="media-none">(none)</label>
                </div>
                ${mediaOptions}
            </div>
            <div class="modal-buttons">
                <button class="btn btn-primary" id="confirmMediaBtn">Confirm</button>
                <button class="btn btn-secondary" id="cancelMediaBtn">Cancel</button>
            </div>
        </div>
    `;

    document.body.appendChild(modal);

    document.getElementById('confirmMediaBtn').addEventListener('click', () => {
        const selected = document.querySelector('input[name="media-pick"]:checked').value;
        tables[index].media_file = selected;
        renderTablesList();
        modal.remove();
    });

    document.getElementById('cancelMediaBtn').addEventListener('click', () => {
        modal.remove();
    });
}

// Step 5: Save all changes to tables.json
document.getElementById('saveTablesBtn').addEventListener('click', async () => {
    if (!folderHandle) {
        document.getElementById('tablesStatus').textContent = '✗ Please grant folder access first';
        document.getElementById('tablesStatus').classList.add('error');
        return;
    }

    try {
        const tablesFile = await folderHandle.getFileHandle('tables.json', { create: true });
        const writable = await tablesFile.createWritable();
        await writable.write(JSON.stringify(tables, null, 2));
        await writable.close();
        
        document.getElementById('tablesStatus').textContent = '✓ Tables saved successfully';
        document.getElementById('tablesStatus').classList.add('success');
    } catch (err) {
        document.getElementById('tablesStatus').textContent = '✗ Error saving: ' + err.message;
        document.getElementById('tablesStatus').classList.add('error');
    }
});

// Initial load
window.addEventListener('load', () => {
    document.getElementById('folderStatus').textContent = 'Ready to grant access';
});
// Load tables.json
async function loadTables() {
    if (!folderHandle) return;
    try {
        const tablesFile = await folderHandle.getFileHandle('tables.json');
        const file = await tablesFile.getFile();
        const text = await file.text();
        tables = JSON.parse(text);
        renderTablesList();
    } catch (err) {
        tables = [];
    }
}

// Save paths to config.json
document.getElementById('savePathsBtn').addEventListener('click', async () => {
    if (!folderHandle) {
        document.getElementById('pathStatus').textContent = '✗ Please grant folder access first';
        document.getElementById('pathStatus').classList.add('error');
        return;
    }

    config.vex_path = document.getElementById('vexPath').value;
    config.tables_path = document.getElementById('tablesPath').value;

    try {
        const configFile = await folderHandle.getFileHandle('config.json', { create: true });
        const writable = await configFile.createWritable();
        await writable.write(JSON.stringify(config, null, 2));
        await writable.close();
        
        document.getElementById('pathStatus').textContent = '✓ Paths saved successfully';
        document.getElementById('pathStatus').classList.add('success');
    } catch (err) {
        document.getElementById('pathStatus').textContent = '✗ Error saving: ' + err.message;
        document.getElementById('pathStatus').classList.add('error');
    }
});

// Scan tables folder
document.getElementById('scanBtn').addEventListener('click', async () => {
    if (!config.tables_path) {
        document.getElementById('scanStatus').textContent = '✗ Please set Tables Folder Path first';
        document.getElementById('scanStatus').classList.add('error');
        return;
    }

    document.getElementById('scanStatus').textContent = '⏳ Scanning...';
    document.getElementById('scanStatus').classList.remove('success', 'error');

    try {
        // For web, we'll simulate scanning by asking the user to select the tables folder
        const tablesFolderHandle = await window.showDirectoryPicker();
        tables = [];

        for await (const entry of tablesFolderHandle.values()) {
            if (entry.kind === 'file' && entry.name.endsWith('.vpx')) {
                tables.push({
                    name: entry.name.replace('.vpx', ''),
                    filename: entry.name,
                    visible: true
                });
            }
        }

        renderTablesList();
        document.getElementById('scanStatus').textContent = `✓ Found ${tables.length} tables`;
        document.getElementById('scanStatus').classList.add('success');
    } catch (err) {
        document.getElementById('scanStatus').textContent = '✗ Error scanning: ' + err.message;
        document.getElementById('scanStatus').classList.add('error');
    }
});

// Render tables list
function renderTablesList() {
    const container = document.getElementById('tablesList');
    
    if (tables.length === 0) {
        container.innerHTML = '<p class="placeholder">No tables found.</p>';
        return;
    }

    container.innerHTML = tables.map((table, index) => `
        <div class="table-item">
            <div class="table-info">
                <h3>${table.name}</h3>
                <p>${table.filename}</p>
            </div>
            <div class="table-control">
                <label>
                    <input type="checkbox" class="table-visible" data-index="${index}" ${table.visible ? 'checked' : ''}>
                    Visible
                </label>
            </div>
        </div>
    `).join('');

    // Add event listeners for visibility toggles
    document.querySelectorAll('.table-visible').forEach(checkbox => {
        checkbox.addEventListener('change', (e) => {
            const index = parseInt(e.target.dataset.index);
            tables[index].visible = e.target.checked;
        });
    });
}

// Save tables to tables.json
document.getElementById('saveTablesBtn').addEventListener('click', async () => {
    if (!folderHandle) {
        document.getElementById('tablesStatus').textContent = '✗ Please grant folder access first';
        document.getElementById('tablesStatus').classList.add('error');
        return;
    }

    try {
        const tablesFile = await folderHandle.getFileHandle('tables.json', { create: true });
        const writable = await tablesFile.createWritable();
        await writable.write(JSON.stringify(tables, null, 2));
        await writable.close();
        
        document.getElementById('tablesStatus').textContent = '✓ Tables saved successfully';
        document.getElementById('tablesStatus').classList.add('success');
    } catch (err) {
        document.getElementById('tablesStatus').textContent = '✗ Error saving: ' + err.message;
        document.getElementById('tablesStatus').classList.add('error');
    }
});

// Initial load
window.addEventListener('load', () => {
    document.getElementById('folderStatus').textContent = 'Ready to grant access';
});
