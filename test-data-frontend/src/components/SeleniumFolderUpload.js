import React, { useState, useRef } from 'react';
import TypeModal from './TypeModal';
import allDataTypes from '../data/allDataTypes';
import SchemaEditor from './SchemaEditor';
// import SchemaEditor from './SchemaEditor';
import GroupEditor from './GroupEditor';
import JSZip from 'jszip';
import FieldEditor from './FieldEditor';

function SeleniumFolderUpload() {
    const [error, setError] = useState('');
    // const [folderName, setFolderName] = useState(''); // removed unused variable
    const [fields, setFields] = useState([]);
    const [extractedDetails, setExtractedDetails] = useState([]);
    const [loading, setLoading] = useState(false);
    const [aiModel, setAiModel] = useState('groq'); // default to groq
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
        try {
            const formData = new FormData();
            const zipFile = new File([zipBlob], 'upload.zip', { type: 'application/zip' });
            formData.append('file', zipFile);
            formData.append('ai_model', aiModel); // send selected model
            const res = await fetch('http://localhost:8000/extract-fields-from-folder', {
                method: 'POST',
                body: formData,
            });
            if (!res.ok) {
                let err = 'Backend error';
                try { err = (await res.json()).detail || err; } catch { }
                setError(err);
                setLoading(false);
                return;
            }
            const data = await res.json();
            setExtractedDetails(data.fields || []);
            // Always show parsed_schema for review/edit, even if empty or parse_error
            if (Array.isArray(data.parsed_schema)) {
                setSchema(data.parsed_schema);
                setShowSchemaEditor(true);
            } else if (data.schema) {
                setSchema(data.schema);
                setShowSchemaEditor(true);
            } else {
                setSchema([]);
                setShowSchemaEditor(true);
            }
            // Show parse_error if present
            if (data.parse_error) {
                setError('Schema extraction error: ' + data.parse_error);
            }
        } catch (e) {
            setError('Network or backend error');
        }
        setLoading(false);
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
            <h2>Upload Selenium Folder</h2>
            <div style={{ marginBottom: 10 }}>
                <label style={{ marginRight: 10 }}>AI Model:</label>
                <select value={aiModel} onChange={e => setAiModel(e.target.value)}>
                    <option value="groq">Groq API (Cloud)</option>
                    <option value="ollama">Local Ollama</option>
                </select>
            </div>
            <div style={{ margin: '16px 0' }}>
                <label htmlFor="selenium-folder-upload-input">
                    <button type="button" style={{ padding: '8px 18px', fontSize: 16, cursor: 'pointer', background: '#4f46e5', color: 'white', border: 'none', borderRadius: 6 }}
                        onClick={() => fileInputRef.current && fileInputRef.current.click()}>
                        📁 Select Selenium Folder
                    </button>
                </label>
                <input
                    id="selenium-folder-upload-input"
                    ref={fileInputRef}
                    type="file"
                    style={{ display: 'none' }}
                    webkitdirectory="true"
                    directory="true"
                    multiple
                    onChange={handleFolderChange}
                />
                {selectedFolder && <span style={{ marginLeft: 12, fontWeight: 500 }}>Selected: {selectedFolder}</span>}
            </div>
            {error && <div className="error">{error}</div>}
            {loading && <div>Loading...</div>}
            {fields.length > 0 && (
                <div className="fields-preview">
                    <h3>Extracted Locators</h3>
                    <ul>
                        {fields.map(f => (
                            <li key={f}><strong>{f}</strong></li>
                        ))}
                    </ul>
                </div>
            )}
            {extractedDetails.length > 0 && (
                <div className="fields-preview">
                    <h3>Extracted Field Details</h3>
                    <ul>
                        {extractedDetails.map(field => (
                            <li key={field.locator}>
                                <strong>{field.locator}</strong>
                                {field.matches.length > 0 ? (
                                    <ul>
                                        {field.matches.map((m, idx) => (
                                            <li key={idx}>
                                                Tag: {m.tag}, Name: {m.name}, ID: {m.id}, Type: {m.type}, Placeholder: {m.placeholder}, Source: {m.source}
                                            </li>
                                        ))}
                                    </ul>
                                ) : <span> (No matches found)</span>}
                            </li>
                        ))}
                    </ul>
                </div>
            )}
            {showSchemaEditor && (
                <div className="schema-editor-section">
                    <h3>Parsed Schema (review & edit)</h3>
                    {schema && schema.length > 0 && schema.map((field, index) => (
                        <FieldEditor
                            key={index}
                            field={field}
                            onChange={(k, v) => {
                                const updated = schema.map((f, i) => i === index ? { ...f, [k]: v } : f);
                                setSchema(updated);
                            }}
                            onRemove={schema.length > 1 ? () => {
                                const updated = schema.filter((_, i) => i !== index);
                                setSchema(updated);
                            } : null}
                            openTypeModal={() => openTypeModal(index)}
                        />
                    ))}
                    <TypeModal
                        show={showTypeModal}
                        onClose={() => setShowTypeModal(false)}
                        types={allDataTypes}
                        onSelect={handleTypeSelect}
                    />
                    <button type="button" onClick={() => setSchema([...schema, { name: '', type: 'string', rules: '', example: '' }])} className="add-btn">+ Add Field</button>
                    <GroupEditor group={groups[0]} fields={schema} onChange={(key, value) => {
                        const newGroups = [...groups];
                        newGroups[0] = { ...newGroups[0], [key]: value };
                        setGroups(newGroups);
                    }} />
                    <button onClick={handleConfirmGenerate} style={{ marginTop: 16 }}>Confirm & Generate Data</button>
                </div>
            )}
            {generatedData && (
                <div className="generated-data-section">
                    <h3>Generated Test Data</h3>
                    <pre style={{ maxHeight: 300, overflow: 'auto', background: '#f8f8f8', padding: 8 }}>{JSON.stringify(generatedData, null, 2)}</pre>
                </div>
            )}
        </div>
    );
}

export default SeleniumFolderUpload;
