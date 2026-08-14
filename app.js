javascript
let folderHandle = null;
let config = {};
let tables = [];

// Open folder for file access
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
        
        document.getElementById('vexPath').value = config.vex_path || '';
        document.getElementById('tablesPath').value = config.tables_path || '';
    } catch (err) {
        config = { vex_path: '', tables_path: '' };
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
