import React, { useState, useRef } from 'react';
import TypeModal from './TypeModal';
import allDataTypes from '../data/allDataTypes';
import SchemaEditor from './SchemaEditor';
// import SchemaEditor from './SchemaEditor';
import GroupEditor from './GroupEditor';
import JSZip from 'jszip';
import FieldEditor from './FieldEditor';
import './SeleniumFolderUpload.css';

function SeleniumFolderUpload({ onExtract }) {
    const [error, setError] = useState('');
    // const [folderName, setFolderName] = useState(''); // removed unused variable
    const [fields, setFields] = useState([]);
    const [extractedDetails, setExtractedDetails] = useState([]);
    const [loading, setLoading] = useState(false);
    const [isExtracting, setIsExtracting] = useState(false);
    const [aiModel, setAiModel] = useState('groq'); // default to groq
    const [logs, setLogs] = useState([]);
    const [schema, setSchema] = useState([]); // editable schema
    const [groups, setGroups] = useState([{ name: 'G1', count: 5, correct_fields: [], wrong_fields: [], wrong_field_rules: {} }]);
    const [showSchemaEditor, setShowSchemaEditor] = useState(false);
    const [generatedData, setGeneratedData] = useState(null);

    // TypeModal state for type selection
    const [showTypeModal, setShowTypeModal] = useState(false);
    const [typeModalTarget, setTypeModalTarget] = useState(null); // { index }
    async function zipFiles(files) {
        const zip = new JSZip();
        for (const f of files) {
            const data = await f.arrayBuffer();
            zip.file(f.webkitRelativePath, data);
        }
        return await zip.generateAsync({ type: 'blob' });
    }

    // User-friendly folder upload
    const [selectedFolder, setSelectedFolder] = useState('');
    const fileInputRef = useRef();
    const handleFolderChange = async (e) => {
        setError('');
        setFields([]);
        setExtractedDetails([]);
        setLoading(true);
        const files = Array.from(e.target.files);
        if (files.length > 0) {
            // Try to get the top-level folder name
            const firstPath = files[0].webkitRelativePath || files[0].name;
            const folderName = firstPath.split('/')[0];
            setSelectedFolder(folderName);
        } else {
            setSelectedFolder('');
        }
        if (!files.length) {
            setError('No files selected.');
            setLoading(false);
            return;
        }
        // Find main Selenium script (any .py file with driver.get and helper patterns) and locators_config.py
        const locFile = files.find(f => f.webkitRelativePath.endsWith('locators_config.py'));

        // Find all .py files that could be Selenium scripts (exclude config files)
        const pyFiles = files.filter(f =>
            f.name.endsWith('.py') &&
            !f.name.includes('locators_config') &&
            !f.name.includes('__init__') &&
            !f.name.includes('conftest')
        );

        // Find the main Selenium script by checking for driver.get() and helper patterns
        let mainScript = null;
        let mainScriptText = '';
        for (const pyFile of pyFiles) {
            const text = await pyFile.text();
            const hasDriverGet = text.includes('driver.get(');
            const hasHelper = text.includes('helper.');
            if (hasDriverGet && hasHelper) {
                // Prefer larger files as they likely have more logic
                if (!mainScript || text.length > mainScriptText.length) {
                    mainScript = pyFile;
                    mainScriptText = text;
                }
            }
        }

        if (!mainScript || !locFile) {
            let missing = [];
            if (!mainScript) missing.push('Selenium script (.py with driver.get and helper patterns)');
            if (!locFile) missing.push('locators_config.py');
            setError(`Required files not found: ${missing.join(', ')}`);
            setLoading(false);
            return;
        }

        // Extract locator keys from the main script
        const locatorRegex = /helper\.click\(["'](locator_[^"']+)["']\)/g;
        const keys = Array.from(mainScriptText.matchAll(locatorRegex)).map(m => m[1]);
        setFields(keys);
        // Zip the folder and send to backend
        let zipBlob;
        try {
            zipBlob = await zipFiles(files);
            if (!zipBlob || zipBlob.size === 0) {
                setError('Zipped folder is empty.');
                setLoading(false);
                return;
            }
        } catch (e) {
            setError('Failed to zip folder.');
            setLoading(false);
            return;
        }

        // Send to backend
        setLoading(false);
        setIsExtracting(true);
        setLogs(['[SYSTEM] Initializing extraction pipeline...', '[SYSTEM] Zipping folder contents...']);

        try {
            const formData = new FormData();
            const zipFile = new File([zipBlob], 'upload.zip', { type: 'application/zip' });
            formData.append('file', zipFile);
            formData.append('ai_model', aiModel); // send selected model

            setLogs(prev => [...prev, '[SYSTEM] Uploading to backend server...', '[SYSTEM] Waiting for processing...']);

            const res = await fetch('http://localhost:8000/extract-fields-from-folder', {
                method: 'POST',
                body: formData,
            });

            if (!res.ok) {
                let err = 'Backend error';
                try { err = (await res.json()).detail || err; } catch { }
                setError(err);
                setIsExtracting(false);
                return;
            }

            const data = await res.json();

            if (data.logs) {
                setLogs(data.logs);
            }

            setExtractedDetails(data.consolidated_fields || []);

            // Always show parsed_schema for review/edit
            if (Array.isArray(data.parsed_schema)) {
                setSchema(data.parsed_schema);
                setShowSchemaEditor(true);
                if (onExtract) onExtract(data.parsed_schema);
            } else {
                setSchema([]);
                setShowSchemaEditor(false);
            }

            // Show errors if present but keep the UI
            if (data.schema_errors) {
                console.warn('Schema validation issues:', data.schema_errors);
            }
        } catch (e) {
            setError('Network or backend error: ' + e.message);
            setLogs(prev => [...prev, '[ERROR] Pipeline failed: ' + e.message]);
        }
        setIsExtracting(false);
    };

    // Handler for schema/group changes
    const handleSchemaChange = (newSchema) => setSchema(newSchema);
    // const handleGroupsChange = (newGroups) => setGroups(newGroups); // removed unused variable

    // Handler for confirm & generate data
    const handleConfirmGenerate = async () => {
        setError('');
        setLoading(true);
        setGeneratedData(null);
        try {
            const res = await fetch('http://localhost:8000/generate-data-from-schema', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    schema,
                    groups,
                    ai_model: aiModel
                })
            });
            if (!res.ok) {
                let err = 'Backend error';
                try { err = (await res.json()).detail || err; } catch { }
                setError(err);
                setLoading(false);
                return;
            }
            const data = await res.json();
            setGeneratedData(data.test_data || []);
        } catch (e) {
            setError('Network or backend error');
        }
        setLoading(false);
    };

    // Handler for opening the type modal for a specific field
    const openTypeModal = (index) => {
        setTypeModalTarget({ index });
        setShowTypeModal(true);
    };

    // Handler for selecting a type from the modal
    const handleTypeSelect = (typeObj) => {
        if (!typeModalTarget) return;
        const idx = typeModalTarget.index;
        const updated = schema.map((f, i) => {
            if (i !== idx) return f;
            return {
                ...f,
                type: typeObj.id || typeObj.name,
                example: typeObj.example || f.example,
                rules: typeObj.defaultRule || typeObj.description || f.rules || ''
            };
        });
        setSchema(updated);
        setShowTypeModal(false);
        setTypeModalTarget(null);
    };

    return (
        <div className="selenium-folder-upload">
            <h2>Selenium Folder Intelligence</h2>

            <div className="model-selector-card">
                <label>AI Intelligence Level:</label>
                <select value={aiModel} onChange={e => setAiModel(e.target.value)}>
                    <option value="groq">Senior QA Architect (Groq Cloud)</option>
                    <option value="ollama">Standard Analyst (Local Ollama)</option>
                </select>
            </div>

            <div className="upload-section">
                <button
                    type="button"
                    className="upload-btn"
                    onClick={() => fileInputRef.current && fileInputRef.current.click()}
                >
                    📁 {loading ? 'Zipping...' : 'Upload Selenium Automation Folder'}
                </button>
                <input
                    ref={fileInputRef}
                    type="file"
                    style={{ display: 'none' }}
                    webkitdirectory="true"
                    directory="true"
                    multiple
                    onChange={handleFolderChange}
                />
                {selectedFolder && <span style={{ marginLeft: 16, fontWeight: 600, color: '#4f46e5' }}>Selected: {selectedFolder}</span>}
            </div>

            {error && <div style={{ borderLeft: '4px solid #ef4444', background: '#fef2f2', padding: '12px', color: '#b91c1c', borderRadius: 8, marginBottom: 24 }}>{error}</div>}

            {(isExtracting || logs.length > 0) && (
                <div className="pipeline-terminal">
                    <div className="terminal-header">
                        <div className="dot red"></div>
                        <div className="dot yellow"></div>
                        <div className="dot green"></div>
                        <span style={{ marginLeft: 8, color: '#94a3b8', fontSize: 12 }}>EXTRACTION_PIPELINE.LOG</span>
                    </div>
                    {logs.map((log, idx) => {
                        let className = 'log-entry';
                        if (log.includes('[STEP')) className += ' step';
                        else if (log.startsWith('   ✓') || log.startsWith('   ⚠') || log.startsWith('     ')) className += ' detail';
                        else if (log.includes('✓')) className += ' success';
                        else if (log.includes('⚠')) className += ' warning';
                        else if (log.includes('✗') || log.includes('[ERROR]')) className += ' error';
                        else if (log.includes('[SYSTEM]')) className += ' system';

                        return <div key={idx} className={className}>{log}</div>;
                    })}
                    {isExtracting && <div className="log-entry system">Running extraction... <span className="blink">|</span></div>}
                </div>
            )}

            {showSchemaEditor && (
                <div className="extraction-complete-banner" style={{
                    marginTop: 24,
                    padding: 24,
                    background: 'linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%)',
                    border: '2px solid #10b981',
                    borderRadius: 20,
                    textAlign: 'center',
                    boxShadow: '0 10px 25px -5px rgba(16, 185, 129, 0.1)'
                }}>
                    <div style={{ fontSize: '40px', marginBottom: '12px' }}>✅</div>
                    <h3 style={{ color: '#065f46', margin: '0 0 8px 0', fontSize: '20px', fontWeight: 700 }}>Extraction Successful</h3>
                    <p style={{ color: '#047857', margin: 0, fontSize: '15px' }}>
                        We found <strong>{schema.length}</strong> fields in your automation script.
                    </p>
                    <p style={{ color: '#059669', marginTop: '4px', fontSize: '14px', fontWeight: 500 }}>
                        Please scroll down to configure your generation groups.
                    </p>
                </div>
            )}
        </div>
    );
}

export default SeleniumFolderUpload;
