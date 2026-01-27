import React, { useState, useRef } from 'react';
import JSZip from 'jszip';
import './ScriptExecutor.css';
import SchemaEditor from './SchemaEditor';
import GroupEditor from './GroupEditor';
import FieldEditor from './FieldEditor';
import TypeModal from './TypeModal';
import allDataTypes from '../data/allDataTypes';

function ScriptExecutor({ onSchemaGenerated }) {
    const [selectedFolder, setSelectedFolder] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [executionResult, setExecutionResult] = useState(null);
    const [headless, setHeadless] = useState(true);
    const [useWire, setUseWire] = useState(false);
    const [parsedSchema, setParsedSchema] = useState(null);
    const [parsing, setParsing] = useState(false);
    const fileInputRef = useRef();

    // Inline Editor States
    const [showEditorInline, setShowEditorInline] = useState(false);
    const [editorFields, setEditorFields] = useState([]);
    const [useGroups, setUseGroups] = useState(true);
    const [groups, setGroups] = useState([
        { name: 'G1', count: 5, correct_fields: [], wrong_fields: [], wrong_field_rules: {} }
    ]);
    const [generationResponse, setGenerationResponse] = useState(null);
    const [isGenerating, setIsGenerating] = useState(false);

    // Type modal states for the inline editor
    const [showTypeModal, setShowTypeModal] = useState(false);
    const [typeModalTarget, setTypeModalTarget] = useState(null);

    const openTypeModal = (index) => {
        setTypeModalTarget(index);
        setShowTypeModal(true);
    };

    const handleTypeSelect = (typeObj) => {
        if (typeModalTarget === null) return;

        const updated = [...editorFields];
        const field = updated[typeModalTarget];

        field.type = typeObj.id || typeObj.name;
        if (typeObj.example) field.example = typeObj.example;
        const ruleToApply = typeObj.defaultRule || typeObj.description || '';
        field.rules = ruleToApply;

        setEditorFields(updated);
        setShowTypeModal(false);
        setTypeModalTarget(null);
    };

    async function zipFiles(files) {
        const zip = new JSZip();
        for (const f of files) {
            const data = await f.arrayBuffer();
            zip.file(f.webkitRelativePath, data);
        }
        return await zip.generateAsync({ type: 'blob' });
    }

    const handleFolderChange = async (e) => {
        setError('');
        setExecutionResult(null);
        const files = Array.from(e.target.files);

        if (files.length > 0) {
            const firstPath = files[0].webkitRelativePath || files[0].name;
            const folderName = firstPath.split('/')[0];
            setSelectedFolder(folderName);
        } else {
            setSelectedFolder('');
        }
    };

    const handleExecuteScript = async () => {
        if (!fileInputRef.current?.files?.length) {
            setError('Please select a folder first');
            return;
        }

        setLoading(true);
        setError('');
        setExecutionResult(null);

        try {
            const files = Array.from(fileInputRef.current.files);

            // Zip the files
            console.log('Zipping files...');
            const zipBlob = await zipFiles(files);

            // Create form data
            const formData = new FormData();
            formData.append('file', zipBlob, 'script_folder.zip');
            formData.append('headless', headless.toString());
            formData.append('use_wire', useWire.toString());

            console.log('Sending request to backend...');
            const response = await fetch('http://localhost:8000/execute-selenium-script', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to execute script');
            }

            const result = await response.json();
            console.log('Execution result:', result);

            setExecutionResult(result.data);
        } catch (err) {
            console.error('Error executing script:', err);
            setError(err.message || 'Failed to execute script');
        } finally {
            setLoading(false);
        }

    };

    const handleAnalyzeScript = async () => {
        if (!fileInputRef.current?.files?.length) {
            setError('Please select a folder first');
            return;
        }

        setLoading(true);
        setError('');
        setExecutionResult(null);

        try {
            const files = Array.from(fileInputRef.current.files);

            // Zip the files
            const zipBlob = await zipFiles(files);

            // Create form data
            const formData = new FormData();
            formData.append('file', zipBlob, 'script_folder.zip');

            const response = await fetch('http://localhost:8000/analyze-selenium-script', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to analyze script');
            }

            const result = await response.json();
            console.log('Analysis result:', result);

            setExecutionResult(result.data);
        } catch (err) {
            console.error('Error analyzing script:', err);
            setError(err.message || 'Failed to analyze script');
        } finally {
            setLoading(false);
        }
    };

    const handleParseOutput = async () => {
        if (!executionResult?.tracked_actions) {
            setError('No execution results to parse');
            return;
        }

        setParsing(true);
        setError('');
        setParsedSchema(null);

        try {
            // HELPER: Strip technical noise and keep only semantic data for LLM
            const cleanForAI = (list) => (list || []).map(el => ({
                locator: el.locator,
                tag_name: el.tag_name,
                text: el.text,
                semantic_type: el.semantic_type,
                exact_purpose: el.exact_purpose,
                role_description: el.role_description,
                input_value: el.input_value,
                context: el.context, // Contains label, container_heading, etc.
                dropdown_options: el.dropdown_options,
                attributes: {
                    id: el.attributes?.id,
                    name: el.attributes?.name,
                    type: el.attributes?.type,
                    placeholder: el.attributes?.placeholder,
                    'aria-label': el.attributes?.['aria-label'],
                    'data-testid': el.attributes?.['data-testid']
                }
            }));

            const requestData = {
                clicked_elements: cleanForAI(executionResult.tracked_actions.clicked_elements),
                filled_fields: cleanForAI(executionResult.tracked_actions.filled_fields)
            };

            console.log('Parsing clicked elements with LLM...');
            const response = await fetch('http://localhost:8000/parse-clicked-elements', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestData),
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to parse output');
            }

            const result = await response.json();
            console.log('Parsed schema:', result);

            // Store the entire result (includes parsed_schema and total_fields)
            setParsedSchema(result);

            // Do NOT automatically navigate — display parsed schema inline in this tab
            // (If parent still wants to be notified, uncomment the next lines)
            // if (onSchemaGenerated && result.parsed_schema) {
            //     onSchemaGenerated(result.parsed_schema);
            // }
        } catch (err) {
            console.error('Error parsing output:', err);
            setError(err.message || 'Failed to parse output');
        } finally {
            setParsing(false);
        }
    };

    const sanitizeFields = (fields) => {
        return fields.map(f => ({
            ...f,
            rules: f.rules === null || f.rules === undefined ? "" : String(f.rules),
            example: f.example === null || f.example === undefined ? "" : String(f.example)
        }));
    };

    const handleGenerateData = async () => {
        setIsGenerating(true);
        setError('');
        setGenerationResponse(null);

        try {
            const validFields = editorFields.filter(f => f.name && f.name.trim() !== '');
            const payload = {
                schema_fields: sanitizeFields(validFields),
                groups: groups,
                model_provider: 'groq' // Defaulting to cloud for speed in executor
            };

            const res = await fetch('http://localhost:8000/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.detail || 'Failed to generate data');
            }

            const result = await res.json();
            setGenerationResponse(result);
        } catch (err) {
            setError(err.message);
        } finally {
            setIsGenerating(false);
        }
    };

    return (
        <div className="script-executor-container">
            <h2>Selenium Script Executor</h2>
            <p className="description">
                Upload a folder containing your Selenium script and watch it execute.
                All clicked buttons and filled fields will be logged and displayed below.
            </p>

            <div className="upload-section">
                <div className="folder-upload">
                    <label htmlFor="folder-input" className="folder-label">
                        📁 Select Folder
                    </label>
                    <input
                        id="folder-input"
                        ref={fileInputRef}
                        type="file"
                        webkitdirectory=""
                        directory=""
                        multiple
                        onChange={handleFolderChange}
                        style={{ display: 'none' }}
                    />
                    {selectedFolder && (
                        <div className="selected-folder">
                            Selected: <strong>{selectedFolder}</strong>
                        </div>
                    )}
                </div>

                <div className="options">
                    <label className="checkbox-label">
                        <input
                            type="checkbox"
                            checked={headless}
                            onChange={(e) => setHeadless(e.target.checked)}
                        />
                        Run in headless mode (no browser window)
                    </label>
                    <label className="checkbox-label" style={{ marginLeft: '20px' }}>
                        <input
                            type="checkbox"
                            checked={useWire}
                            onChange={(e) => setUseWire(e.target.checked)}
                        />
                        Intercept API Calls (Fetch/XHR)
                    </label>
                </div>

                <div className="action-buttons">
                    <button
                        onClick={handleExecuteScript}
                        disabled={!selectedFolder || loading}
                        className="btn btn-primary"
                    >
                        {loading ? '⏳ Executing...' : '▶️ Execute Script'}
                    </button>
                    <button
                        onClick={handleAnalyzeScript}
                        disabled={!selectedFolder || loading}
                        className="btn btn-secondary"
                    >
                        {loading ? '⏳ Analyzing...' : '🔍 Analyze Without Execution'}
                    </button>
                </div>
            </div>

            {error && (
                <div className="error-message">
                    ❌ {error}
                </div>
            )}

            {executionResult && (
                <div className="results-section">
                    <div className="results-header">
                        <h3>Execution Results</h3>
                        {executionResult.tracked_actions && (
                            <button
                                onClick={handleParseOutput}
                                disabled={parsing}
                                className="btn btn-parse"
                            >
                                {parsing ? '🔄 Parsing...' : '🧠 Parse Output with AI'}
                            </button>
                        )}
                    </div>

                    {executionResult.tracked_actions && (
                        <>
                            <div className="summary-cards">
                                <div className="summary-card">
                                    <div className="card-value">
                                        {executionResult.tracked_actions.summary?.total_actions || 0}
                                    </div>
                                    <div className="card-label">Total Actions</div>
                                </div>
                                <div className="summary-card">
                                    <div className="card-value">
                                        {executionResult.tracked_actions.summary?.total_clicks || 0}
                                    </div>
                                    <div className="card-label">Clicks</div>
                                </div>
                                <div className="summary-card">
                                    <div className="card-value">
                                        {executionResult.tracked_actions.summary?.total_inputs || 0}
                                    </div>
                                    <div className="card-label">Field Inputs</div>
                                </div>
                                <div className="summary-card">
                                    <div className="card-value">
                                        {executionResult.tracked_actions.summary?.total_api_calls || 0}
                                    </div>
                                    <div className="card-label">API Calls</div>
                                </div>
                            </div>

                            {executionResult.tracked_actions.screenshots?.length > 0 && (
                                <div className="screenshots-section">
                                    <h4>📸 Execution Visuals</h4>
                                    <div className="screenshots-gallery">
                                        {executionResult.tracked_actions.screenshots.map((ss, idx) => (
                                            <div key={idx} className="screenshot-item">
                                                <div
                                                    className="screenshot-img-container"
                                                    onClick={() => {
                                                        const win = window.open();
                                                        win.document.write(`<img src="${ss.data}" style="width:100%"/>`);
                                                    }}
                                                >
                                                    <img src={ss.data} alt={ss.label} />
                                                </div>
                                                <div className="screenshot-label">{ss.label}</div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {executionResult.tracked_actions.clicked_elements?.length > 0 && (
                                <div className="actions-section">
                                    <h4>🖱️ Clicked Elements</h4>
                                    <div className="actions-list">
                                        {executionResult.tracked_actions.clicked_elements.map((elem, idx) => (
                                            <div key={idx} className="action-item click-item">
                                                <div className="action-header">
                                                    <span className="action-number">#{idx + 1}</span>
                                                    <span className="action-locator">{elem.locator}</span>
                                                </div>
                                                <div className="action-details">
                                                    <div className="detail-row">
                                                        <span className="detail-label">Tag:</span>
                                                        <span className="detail-value"><code>&lt;{elem.tag_name}&gt;</code></span>
                                                    </div>

                                                    {/* Semantic Insights */}
                                                    {(elem.exact_purpose || elem.semantic_type) && (
                                                        <div className="detail-section semantic-insights">
                                                            <div className="detail-section-title">🧠 Semantic Insights</div>
                                                            {elem.exact_purpose && (
                                                                <div className="detail-row">
                                                                    <span className="detail-label">Purpose:</span>
                                                                    <span className="detail-value" style={{ fontWeight: '600', color: '#2980b9' }}>{elem.exact_purpose}</span>
                                                                </div>
                                                            )}
                                                            {elem.semantic_type && (
                                                                <div className="detail-row">
                                                                    <span className="detail-label">Type:</span>
                                                                    <span className="detail-value"><span className="field-type">{elem.semantic_type}</span></span>
                                                                </div>
                                                            )}
                                                            {elem.role_description && (
                                                                <div className="detail-row">
                                                                    <span className="detail-label">Role:</span>
                                                                    <span className="detail-value" style={{ fontStyle: 'italic', fontSize: '12px' }}>{elem.role_description}</span>
                                                                </div>
                                                            )}
                                                        </div>
                                                    )}

                                                    {/* Page Context */}
                                                    {elem.context && Object.values(elem.context).some(v => v) && (
                                                        <div className="detail-section page-context">
                                                            <div className="detail-section-title">🌐 Page Context</div>
                                                            {elem.context.container_heading && (
                                                                <div className="detail-row">
                                                                    <span className="detail-label">Section:</span>
                                                                    <span className="detail-value">{elem.context.container_heading}</span>
                                                                </div>
                                                            )}
                                                            {elem.context.label && (
                                                                <div className="detail-row">
                                                                    <span className="detail-label">Label:</span>
                                                                    <span className="detail-value">{elem.context.label}</span>
                                                                </div>
                                                            )}
                                                            {elem.context.surrounding_text && (
                                                                <div className="detail-row">
                                                                    <span className="detail-label">Nearby Text:</span>
                                                                    <span className="detail-value" style={{ color: '#7f8c8d' }}>{elem.context.surrounding_text}</span>
                                                                </div>
                                                            )}
                                                        </div>
                                                    )}

                                                    {/* Dropdown Options */}
                                                    {elem.dropdown_options && elem.dropdown_options.length > 0 && (
                                                        <div className="detail-section dropdown-options">
                                                            <div className="detail-section-title">📂 Dropdown Options ({elem.dropdown_options.length})</div>
                                                            <div className="options-grid">
                                                                {elem.dropdown_options.slice(0, 15).map((opt, i) => (
                                                                    <div key={i} className={`option-pill ${opt.selected ? 'selected' : ''}`}>
                                                                        {opt.text || opt.value || 'Empty'}
                                                                    </div>
                                                                ))}
                                                                {elem.dropdown_options.length > 15 && (
                                                                    <div className="option-pill more">+{elem.dropdown_options.length - 15} more</div>
                                                                )}
                                                            </div>
                                                        </div>
                                                    )}
                                                    {elem.text && (
                                                        <div className="detail-row">
                                                            <span className="detail-label">Text:</span>
                                                            <span className="detail-value">{elem.text}</span>
                                                        </div>
                                                    )}

                                                    {/* All HTML Attributes */}
                                                    {elem.attributes && Object.keys(elem.attributes).length > 0 && (
                                                        <div className="detail-section">
                                                            <div className="detail-section-title">📋 HTML Attributes</div>
                                                            {Object.entries(elem.attributes).map(([key, value]) => (
                                                                value && (
                                                                    <div key={key} className="detail-row">
                                                                        <span className="detail-label">{key}:</span>
                                                                        <span className="detail-value">{String(value).substring(0, 100)}</span>
                                                                    </div>
                                                                )
                                                            ))}
                                                        </div>
                                                    )}

                                                    {/* Element Properties */}
                                                    {elem.properties && (
                                                        <div className="detail-section">
                                                            <div className="detail-section-title">🔧 Element Properties</div>
                                                            {elem.properties.outerHTML && (
                                                                <div className="detail-row code-row">
                                                                    <span className="detail-label">outerHTML:</span>
                                                                    <pre className="detail-code">{elem.properties.outerHTML.substring(0, 300)}...</pre>
                                                                </div>
                                                            )}
                                                            {elem.properties.innerHTML && (
                                                                <div className="detail-row code-row">
                                                                    <span className="detail-label">innerHTML:</span>
                                                                    <pre className="detail-code">{elem.properties.innerHTML.substring(0, 200)}...</pre>
                                                                </div>
                                                            )}
                                                            {elem.properties.textContent && (
                                                                <div className="detail-row">
                                                                    <span className="detail-label">textContent:</span>
                                                                    <span className="detail-value">{elem.properties.textContent}</span>
                                                                </div>
                                                            )}
                                                            {elem.properties.classList && elem.properties.classList.length > 0 && (
                                                                <div className="detail-row">
                                                                    <span className="detail-label">classList:</span>
                                                                    <span className="detail-value">{elem.properties.classList.join(', ')}</span>
                                                                </div>
                                                            )}
                                                            {elem.properties.dataset && Object.keys(elem.properties.dataset).length > 0 && (
                                                                <div className="detail-row">
                                                                    <span className="detail-label">dataset:</span>
                                                                    <span className="detail-value">{JSON.stringify(elem.properties.dataset)}</span>
                                                                </div>
                                                            )}
                                                            <div className="detail-row">
                                                                <span className="detail-label">dimensions:</span>
                                                                <span className="detail-value">
                                                                    {elem.properties.offsetWidth}×{elem.properties.offsetHeight} px
                                                                </span>
                                                            </div>
                                                            <div className="detail-row">
                                                                <span className="detail-label">children:</span>
                                                                <span className="detail-value">{elem.properties.childElementCount || 0}</span>
                                                            </div>
                                                        </div>
                                                    )}

                                                    {/* Computed Styles */}
                                                    {elem.computed_styles && (
                                                        <div className="detail-section">
                                                            <div className="detail-section-title">🎨 Computed Styles</div>
                                                            {Object.entries(elem.computed_styles).map(([key, value]) => (
                                                                value && (
                                                                    <div key={key} className="detail-row">
                                                                        <span className="detail-label">{key}:</span>
                                                                        <span className="detail-value">{value}</span>
                                                                    </div>
                                                                )
                                                            ))}
                                                        </div>
                                                    )}

                                                    {/* Element State */}
                                                    {elem.state && (
                                                        <div className="detail-section">
                                                            <div className="detail-section-title">🎯 Element State</div>
                                                            <div className="detail-row">
                                                                <span className="detail-label">displayed:</span>
                                                                <span className="detail-value">{String(elem.state.is_displayed)}</span>
                                                            </div>
                                                            <div className="detail-row">
                                                                <span className="detail-label">enabled:</span>
                                                                <span className="detail-value">{String(elem.state.is_enabled)}</span>
                                                            </div>
                                                            {elem.state.is_selected !== null && (
                                                                <div className="detail-row">
                                                                    <span className="detail-label">selected:</span>
                                                                    <span className="detail-value">{String(elem.state.is_selected)}</span>
                                                                </div>
                                                            )}
                                                        </div>
                                                    )}

                                                    {/* Location & Size */}
                                                    {elem.location && elem.size && (
                                                        <div className="detail-section">
                                                            <div className="detail-section-title">📍 Position & Size</div>
                                                            <div className="detail-row">
                                                                <span className="detail-label">location:</span>
                                                                <span className="detail-value">
                                                                    x: {elem.location.x}, y: {elem.location.y}
                                                                </span>
                                                            </div>
                                                            <div className="detail-row">
                                                                <span className="detail-label">size:</span>
                                                                <span className="detail-value">
                                                                    width: {elem.size.width}, height: {elem.size.height}
                                                                </span>
                                                            </div>
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {executionResult.tracked_actions.filled_fields?.length > 0 && (
                                <div className="actions-section">
                                    <h4>📝 Filled Fields</h4>
                                    <div className="actions-list">
                                        {executionResult.tracked_actions.filled_fields.map((field, idx) => (
                                            <div key={idx} className="action-item input-item">
                                                <div className="action-header">
                                                    <span className="action-number">#{idx + 1}</span>
                                                    <span className="action-locator">{field.locator}</span>
                                                </div>
                                                <div className="action-details">
                                                    <div className="detail-row">
                                                        <span className="detail-label">Tag:</span>
                                                        <span className="detail-value"><code>&lt;{field.tag_name}&gt;</code></span>
                                                    </div>

                                                    {/* Semantic Insights */}
                                                    {(field.exact_purpose || field.semantic_type) && (
                                                        <div className="detail-section semantic-insights">
                                                            <div className="detail-section-title">🧠 Semantic Insights</div>
                                                            {field.exact_purpose && (
                                                                <div className="detail-row">
                                                                    <span className="detail-label">Purpose:</span>
                                                                    <span className="detail-value" style={{ fontWeight: '600', color: '#27ae60' }}>{field.exact_purpose}</span>
                                                                </div>
                                                            )}
                                                            {field.semantic_type && (
                                                                <div className="detail-row">
                                                                    <span className="detail-label">Type:</span>
                                                                    <span className="detail-value"><span className="field-type" style={{ background: '#27ae60' }}>{field.semantic_type}</span></span>
                                                                </div>
                                                            )}
                                                        </div>
                                                    )}

                                                    {/* Page Context */}
                                                    {field.context && Object.values(field.context).some(v => v) && (
                                                        <div className="detail-section page-context">
                                                            <div className="detail-section-title">🌐 Page Context</div>
                                                            {field.context.container_heading && (
                                                                <div className="detail-row">
                                                                    <span className="detail-label">Section:</span>
                                                                    <span className="detail-value">{field.context.container_heading}</span>
                                                                </div>
                                                            )}
                                                            {field.context.label && (
                                                                <div className="detail-row">
                                                                    <span className="detail-label">Label:</span>
                                                                    <span className="detail-value">{field.context.label}</span>
                                                                </div>
                                                            )}
                                                        </div>
                                                    )}

                                                    {/* Dropdown Options */}
                                                    {field.dropdown_options && field.dropdown_options.length > 0 && (
                                                        <div className="detail-section dropdown-options">
                                                            <div className="detail-section-title">📂 Dropdown Options ({field.dropdown_options.length})</div>
                                                            <div className="options-grid">
                                                                {field.dropdown_options.slice(0, 15).map((opt, i) => (
                                                                    <div key={i} className={`option-pill ${opt.selected ? 'selected' : ''}`} style={{ borderColor: '#27ae60' }}>
                                                                        {opt.text || opt.value || 'Empty'}
                                                                    </div>
                                                                ))}
                                                            </div>
                                                        </div>
                                                    )}
                                                    {(field.value || field.input_value) && (
                                                        <div className="detail-row">
                                                            <span className="detail-label">Value Entered:</span>
                                                            <span className="detail-value">{field.value || field.input_value}</span>
                                                        </div>
                                                    )}

                                                    {/* All HTML Attributes */}
                                                    {field.attributes && Object.keys(field.attributes).length > 0 && (
                                                        <div className="detail-section">
                                                            <div className="detail-section-title">📋 HTML Attributes</div>
                                                            {Object.entries(field.attributes).map(([key, value]) => (
                                                                value && (
                                                                    <div key={key} className="detail-row">
                                                                        <span className="detail-label">{key}:</span>
                                                                        <span className="detail-value">{String(value).substring(0, 100)}</span>
                                                                    </div>
                                                                )
                                                            ))}
                                                        </div>
                                                    )}

                                                    {/* Element Properties */}
                                                    {field.properties && (
                                                        <div className="detail-section">
                                                            <div className="detail-section-title">🔧 Element Properties</div>
                                                            {field.properties.outerHTML && (
                                                                <div className="detail-row code-row">
                                                                    <span className="detail-label">outerHTML:</span>
                                                                    <pre className="detail-code">{field.properties.outerHTML.substring(0, 300)}...</pre>
                                                                </div>
                                                            )}
                                                            {field.properties.classList && field.properties.classList.length > 0 && (
                                                                <div className="detail-row">
                                                                    <span className="detail-label">classList:</span>
                                                                    <span className="detail-value">{field.properties.classList.join(', ')}</span>
                                                                </div>
                                                            )}
                                                        </div>
                                                    )}

                                                    {/* Computed Styles */}
                                                    {field.computed_styles && Object.keys(field.computed_styles).length > 0 && (
                                                        <div className="detail-section">
                                                            <div className="detail-section-title">🎨 Computed Styles</div>
                                                            {Object.entries(field.computed_styles).map(([key, value]) => (
                                                                value && (
                                                                    <div key={key} className="detail-row">
                                                                        <span className="detail-label">{key}:</span>
                                                                        <span className="detail-value">{value}</span>
                                                                    </div>
                                                                )
                                                            ))}
                                                        </div>
                                                    )}

                                                    {/* Element State */}
                                                    {field.state && (
                                                        <div className="detail-section">
                                                            <div className="detail-section-title">🎯 Element State</div>
                                                            <div className="detail-row">
                                                                <span className="detail-label">displayed:</span>
                                                                <span className="detail-value">{String(field.state.is_displayed)}</span>
                                                            </div>
                                                            <div className="detail-row">
                                                                <span className="detail-label">enabled:</span>
                                                                <span className="detail-value">{String(field.state.is_enabled)}</span>
                                                            </div>
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                            {executionResult.tracked_actions.api_calls?.length > 0 && (
                                <div className="actions-section">
                                    <h4>🌐 Intercepted API Calls (Click-Triggered)</h4>

                                    {(() => {
                                        // Group APIs by the click that triggered them
                                        const apisByClick = {};
                                        executionResult.tracked_actions.api_calls.forEach(call => {
                                            const trigger = call.triggered_by_click || 'No Click Association';
                                            if (!apisByClick[trigger]) {
                                                apisByClick[trigger] = [];
                                            }
                                            apisByClick[trigger].push(call);
                                        });

                                        return (
                                            <div className="api-groups-container">
                                                {Object.entries(apisByClick).map(([clickLocator, apis], groupIdx) => (
                                                    <div key={groupIdx} className="api-group">
                                                        <div className="api-group-header">
                                                            <span className="api-group-icon">🖱️</span>
                                                            <span className="api-group-title">
                                                                Triggered by: <strong>{clickLocator}</strong>
                                                            </span>
                                                            <span className="api-group-count">
                                                                {apis.length} API call{apis.length !== 1 ? 's' : ''}
                                                            </span>
                                                        </div>

                                                        <div className="api-group-items">
                                                            {apis.map((call, idx) => (
                                                                <div key={idx} className="action-item api-item">
                                                                    <div className="action-header">
                                                                        <span className="action-number">#{idx + 1}</span>
                                                                        <span className={`method-badge method-${call.method.toLowerCase()}`}>
                                                                            {call.method}
                                                                        </span>
                                                                        <span className="action-url" title={call.url}>
                                                                            {call.url}
                                                                        </span>
                                                                        {call.response_code && (
                                                                            <span className={`status-badge status-${String(call.response_code)[0]}xx`}>
                                                                                {call.response_code}
                                                                            </span>
                                                                        )}
                                                                        {call.time_after_click !== undefined && (
                                                                            <span className="time-badge" title="Time after click">
                                                                                ⏱️ +{call.time_after_click.toFixed(2)}s
                                                                            </span>
                                                                        )}
                                                                    </div>
                                                                    <div className="action-details">
                                                                        {/* Click Association Info */}
                                                                        {call.triggered_by_click && call.time_after_click !== undefined && (
                                                                            <div className="detail-section click-association">
                                                                                <div className="detail-section-title">🎯 Click Association</div>
                                                                                <div className="detail-row">
                                                                                    <span className="detail-label">Triggered by:</span>
                                                                                    <span className="detail-value" style={{ fontWeight: '600', color: '#e74c3c' }}>
                                                                                        {call.triggered_by_click}
                                                                                    </span>
                                                                                </div>
                                                                                <div className="detail-row">
                                                                                    <span className="detail-label">Time after click:</span>
                                                                                    <span className="detail-value">
                                                                                        {call.time_after_click.toFixed(3)} seconds
                                                                                    </span>
                                                                                </div>
                                                                            </div>
                                                                        )}

                                                                        {call.payload && (
                                                                            <div className="detail-section">
                                                                                <div className="detail-section-title">📦 Payload</div>
                                                                                <div className="detail-row code-row">
                                                                                    <pre className="detail-code">
                                                                                        {typeof call.payload === 'object'
                                                                                            ? JSON.stringify(call.payload, null, 2)
                                                                                            : String(call.payload).substring(0, 500) + (String(call.payload).length > 500 ? '...' : '')}
                                                                                    </pre>
                                                                                </div>
                                                                            </div>
                                                                        )}
                                                                        {call.response_body && (
                                                                            <div className="detail-section">
                                                                                <div className="detail-section-title">📥 Response</div>
                                                                                <div className="detail-row code-row">
                                                                                    <pre className="detail-code">
                                                                                        {typeof call.response_body === 'object'
                                                                                            ? JSON.stringify(call.response_body, null, 2)
                                                                                            : String(call.response_body).substring(0, 500) + (String(call.response_body).length > 500 ? '...' : '')}
                                                                                    </pre>
                                                                                </div>
                                                                            </div>
                                                                        )}
                                                                    </div>
                                                                </div>
                                                            ))}
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        );
                                    })()}
                                </div>
                            )}
                        </>
                    )
                    }

                    {/* For analysis results (without execution) */}
                    {
                        executionResult.actions && (
                            <div className="actions-section">
                                <h4>📋 Expected Actions</h4>
                                <div className="analysis-info">
                                    <p><strong>Script:</strong> {executionResult.script_name}</p>
                                    <p><strong>Target URL:</strong> {executionResult.target_url || 'Not found'}</p>
                                    <p><strong>Total Actions:</strong> {executionResult.total_actions}</p>
                                </div>
                                <div className="actions-list">
                                    {executionResult.actions.map((action, idx) => (
                                        <div key={idx} className="action-item analysis-item">
                                            <span className="action-number">#{idx + 1}</span>
                                            <span className="action-type">{action.action}</span>
                                            <span className="action-locator">{action.locator}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )
                    }
                </div >
            )}

            {
                parsedSchema && (
                    <div className="parsed-schema-section">
                        <h3>🎯 Generated Schema</h3>
                        <div className="schema-info">
                            <p><strong>Total Fields:</strong> {parsedSchema.total_fields}</p>
                            <p><strong>Average Confidence:</strong> {parsedSchema.parsed_schema?.reduce((sum, f) => sum + (f.confidence * 100), 0) / parsedSchema.parsed_schema?.length || 0}%</p>
                        </div>
                        <div className="schema-fields">
                            {parsedSchema.parsed_schema?.map((field, idx) => (
                                <div key={idx} className="schema-field-card">
                                    <div className="field-header">
                                        <span className="field-name">{field.name}</span>
                                        <span className="field-type">{field.type}</span>
                                    </div>
                                    <div className="field-details">
                                        {field.description && (
                                            <div className="field-row">
                                                <span className="field-label">Description:</span>
                                                <span className="field-value">{field.description}</span>
                                            </div>
                                        )}
                                        {field.rules && (
                                            <div className="field-row">
                                                <span className="field-label">Rules:</span>
                                                <span className="field-value">{typeof field.rules === 'string' ? field.rules : field.rules.join(', ')}</span>
                                            </div>
                                        )}
                                        {field.example && (
                                            <div className="field-row">
                                                <span className="field-label">Example:</span>
                                                <span className="field-value">{field.example}</span>
                                            </div>
                                        )}
                                        {field.confidence && (
                                            <div className="field-row">
                                                <span className="field-label">Confidence:</span>
                                                <span className="field-value">{(field.confidence * 100).toFixed(0)}%</span>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                        <div className="schema-note">
                            💡 This schema has been automatically generated from the tracked actions.
                            <div style={{ marginTop: '15px', display: 'flex', gap: '10px' }}>
                                {!showEditorInline ? (
                                    <button
                                        onClick={() => {
                                            setEditorFields(parsedSchema.parsed_schema || []);
                                            setShowEditorInline(true);
                                        }}
                                        className="btn btn-primary"
                                        style={{ width: 'auto' }}
                                    >
                                        📝 Edit Schema & Configure Groups
                                    </button>
                                ) : (
                                    <button
                                        onClick={() => setShowEditorInline(false)}
                                        className="btn btn-secondary"
                                        style={{ width: 'auto' }}
                                    >
                                        Hide Editor
                                    </button>
                                )}
                            </div>
                        </div>

                        {showEditorInline && (
                            <div className="inline-editor-container" style={{
                                marginTop: '20px',
                                padding: '20px',
                                background: '#f8f9fa',
                                borderRadius: '12px',
                                border: '1px solid #e9ecef'
                            }}>
                                <h3 style={{ marginBottom: '20px' }}>🛠️ Professional Schema Editor</h3>

                                {/* Field Editor Section */}
                                <div className="form-section">
                                    <h4 style={{ color: '#2c3e50', marginBottom: '15px' }}>Field Definitions</h4>
                                    {editorFields.map((field, index) => (
                                        <FieldEditor
                                            key={index}
                                            field={field}
                                            onChange={(k, v) => {
                                                const updated = [...editorFields];
                                                updated[index][k] = v;
                                                setEditorFields(updated);
                                            }}
                                            onRemove={() => {
                                                setEditorFields(editorFields.filter((_, i) => i !== index));
                                            }}
                                            openTypeModal={() => openTypeModal(index)}
                                            hideExample={true}
                                        />
                                    ))}
                                    <button
                                        className="btn btn-secondary"
                                        style={{ marginTop: '10px' }}
                                        onClick={() => setEditorFields([...editorFields, { name: '', type: 'string', rules: '', example: '' }])}
                                    >
                                        + Add Field
                                    </button>
                                </div>

                                {/* Group Configuration Section */}
                                <div className="form-section" style={{ marginTop: '30px' }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
                                        <h4 style={{ color: '#2c3e50', margin: 0 }}>📊 Target Data Groups</h4>
                                        <button
                                            className="btn btn-primary"
                                            onClick={() => setGroups([...groups, { name: `G${groups.length + 1}`, count: 5, correct_fields: [], wrong_fields: [], wrong_field_rules: {} }])}
                                        >
                                            + Add Group
                                        </button>
                                    </div>
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
                                        {groups.map((group, index) => (
                                            <GroupEditor
                                                key={index}
                                                group={group}
                                                fields={editorFields.filter(f => f.name)}
                                                onChange={(k, v) => {
                                                    const updated = [...groups];
                                                    updated[index][k] = v;
                                                    setGroups(updated);
                                                }}
                                                onRemove={() => setGroups(groups.filter((_, i) => i !== index))}
                                            />
                                        ))}
                                    </div>
                                </div>

                                <div style={{ marginTop: '30px', borderTop: '2px solid #eee', paddingTop: '20px', display: 'flex', justifyContent: 'flex-end' }}>
                                    <button
                                        className="btn btn-generate"
                                        style={{
                                            padding: '12px 30px',
                                            fontSize: '16px',
                                            fontWeight: 'bold',
                                            background: '#27ae60',
                                            color: 'white',
                                            border: 'none',
                                            borderRadius: '8px',
                                            cursor: 'pointer'
                                        }}
                                        onClick={handleGenerateData}
                                        disabled={isGenerating}
                                    >
                                        {isGenerating ? '⏳ Generating Test Data...' : '🚀 Generate Test Data Now'}
                                    </button>
                                </div>

                                {generationResponse && (
                                    <div className="generation-results" style={{ marginTop: '30px' }}>
                                        <h3 style={{ color: '#27ae60' }}>✅ Successfully Generated {generationResponse.count} Records</h3>
                                        <div className="data-preview" style={{
                                            background: '#1e272e',
                                            color: '#ecf0f1',
                                            padding: '15px',
                                            borderRadius: '8px',
                                            maxHeight: '400px',
                                            overflow: 'auto',
                                            marginTop: '10px'
                                        }}>
                                            <pre style={{ margin: 0, fontSize: '13px' }}>
                                                {JSON.stringify(generationResponse.data, null, 2)}
                                            </pre>
                                        </div>
                                        <div style={{ marginTop: '15px' }}>
                                            <button
                                                className="btn btn-secondary"
                                                onClick={() => {
                                                    const csvContent = "data:text/csv;charset=utf-8,"
                                                        + Object.keys(generationResponse.data[0]).join(",") + "\n"
                                                        + generationResponse.data.map(row => Object.values(row).join(",")).join("\n");
                                                    const encodedUri = encodeURI(csvContent);
                                                    const link = document.createElement("a");
                                                    link.setAttribute("href", encodedUri);
                                                    link.setAttribute("download", "generated_test_data.csv");
                                                    document.body.appendChild(link);
                                                    link.click();
                                                }}
                                            >
                                                📥 Download as CSV
                                            </button>
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                )
            }
            {/* Rich Type Selector Modal */}
            <TypeModal
                show={showTypeModal}
                onClose={() => setShowTypeModal(false)}
                types={allDataTypes}
                onSelect={handleTypeSelect}
            />
        </div >
    );
}

export default ScriptExecutor;
