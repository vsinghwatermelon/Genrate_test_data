/**
 * Test Data Generator - React Frontend
 * 
 * Features:
 * - Single table mode: Generate data for one table
 * - Database mode: Generate multi-table databases with relationships
 * - Intelligent mode: Auto PK/FK detection using AI agents
 * - Manual mode: Explicit PK/FK definitions
 * - Excel export: Download all tables in one Excel file with multiple sheets
 */

import React, { useState } from 'react';
import './App.css';
import TypeModal from './components/TypeModal';
import allDataTypes from './data/allDataTypes';
import FieldEditor from './components/FieldEditor';
import * as XLSX from 'xlsx';

function App() {
    // ========================================================================
    // STATE MANAGEMENT
    // ========================================================================

    const [mode, setMode] = useState('database');

    // Single table mode state
    const [fields, setFields] = useState([{ name: '', type: 'string', rules: '', example: '' }]);
    const [numRecords, setNumRecords] = useState(5);
    const [correctNumRecords, setCorrectNumRecords] = useState(5);
    const [wrongNumRecords, setWrongNumRecords] = useState(0);
    const [additionalRules, setAdditionalRules] = useState('');

    // Selenium script mode state
    const [seleniumScript, setSeleniumScript] = useState('');
    const [seleniumNumRecords, setSeleniumNumRecords] = useState(5);
    const [seleniumCorrectNumRecords, setSeleniumCorrectNumRecords] = useState(5);
    const [seleniumWrongNumRecords, setSeleniumWrongNumRecords] = useState(0);
    const [seleniumAdditionalRules, setSeleniumAdditionalRules] = useState('');
    // Selenium parse-review-confirm flow
    const [parsedSchema, setParsedSchema] = useState(null);
    const [parsedFields, setParsedFields] = useState(null);
    const [parsedNumRecords, setParsedNumRecords] = useState(5);
    const [parsedCorrectNumRecords, setParsedCorrectNumRecords] = useState(5);
    const [parsedWrongNumRecords, setParsedWrongNumRecords] = useState(0);
    const [parsedAdditionalRules, setParsedAdditionalRules] = useState('');

    // Common state
    const [response, setResponse] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [viewMode, setViewMode] = useState('json');
    const [selectedTable, setSelectedTable] = useState(null);
    const [modelProvider, setModelProvider] = useState('ollama'); // 'ollama' or 'groq'

    // ========================================================================
    // SINGLE TABLE MODE - Field Management
    // ========================================================================
    const addField = () => {
        setFields([...fields, { name: '', type: 'string', rules: '', example: '' }]);
    };

    const removeField = (index) => {
        const newFields = fields.filter((_, i) => i !== index);
        setFields(newFields);
    };

    const updateField = (index, key, value) => {
        const updatedFields = [...fields];
        updatedFields[index][key] = value;
        setFields(updatedFields);
    };

    // Type modal for choosing rich datatypes (banking-focused)
    const [showTypeModal, setShowTypeModal] = useState(false);
    // typeModalTarget describes where to apply the chosen type. Example:
    // { mode: 'single', index: 0 } or { mode: 'table', tableIndex: 0, fieldIndex: 1 }
    const [typeModalTarget, setTypeModalTarget] = useState(null);

    const openTypeModal = (target) => {
        setTypeModalTarget(target);
        setShowTypeModal(true);
    };

    const handleTypeSelect = (typeObj) => {
        if (!typeModalTarget) return;
        // Use defaultRule if available; otherwise fall back to description
        const ruleToApply = typeObj.defaultRule || typeObj.description || '';
        if (typeModalTarget.mode === 'single') {
            const idx = typeModalTarget.index;
            updateField(idx, 'type', typeObj.id || typeObj.name);
            if (typeObj.example) updateField(idx, 'example', typeObj.example);
            // always set rules to either defaultRule or description when selecting a type
            updateField(idx, 'rules', ruleToApply);
        } else if (typeModalTarget.mode === 'parsed') {
            const idx = typeModalTarget.index;
            if (!parsedFields) return;
            const updated = [...parsedFields];
            updated[idx] = updated[idx] || { name: '', type: 'string', rules: '', example: '' };
            updated[idx].type = typeObj.id || typeObj.name;
            if (typeObj.example) updated[idx].example = typeObj.example;
            updated[idx].rules = ruleToApply;
            setParsedFields(updated);
        }
        setShowTypeModal(false);
        setTypeModalTarget(null);
    };

    // ==================== Selenium parse/confirm helpers ====================
    const normalizeIncomingFields = (incoming) => {
        if (!incoming || incoming.length === 0) return [{ name: '', type: 'string', rules: '', example: '' }];
        return incoming.map(f => ({
            name: f.name || f.field || '',
            type: f.type || f.data_type || 'string',
            rules: f.rules || f.description || '',
            example: f.example || f.sample || ''
        }));
    };

    const parseSelenium = async () => {
        if (!seleniumScript) {
            setError('Please paste a Selenium script to parse.');
            return;
        }
        setLoading(true);
        setError('');
        setResponse(null);

        try {
            // Ensure we send the script as a proper string (preserve newlines).
            const payload = {
                selenium_script: String(seleniumScript),
                parse_only: true,
                model_provider: modelProvider
            };

            const res = await fetch('http://localhost:8000/generate-from-selenium', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            // Backend will return parsed_schema and optionally parse_error.
            const data = await res.json();
            if (!res.ok) {
                // If server included parse_error in detail, show it.
                const detail = data.detail || data.parse_error || `Error: ${res.status}`;
                throw new Error(detail);
            }

            // Populate parsed schema (may be empty) so user can inspect it.
            setParsedSchema(data.parsed_schema || null);

            if (data.parsed_schema && data.parsed_schema.length > 0) {
                const normalized = normalizeIncomingFields(data.parsed_schema);
                setParsedFields(normalized);
                setParsedNumRecords(5);
                setParsedCorrectNumRecords(5);
                setParsedWrongNumRecords(0);
                setParsedAdditionalRules('');
            } else {
                // If the backend returned a parse_error, surface it in the UI.
                if (data.parse_error) {
                    setError(data.parse_error);
                } else {
                    setError('Parser returned no schema');
                }
            }
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const updateParsedField = (index, key, value) => {
        const updated = [...parsedFields];
        updated[index][key] = value;
        setParsedFields(updated);
    };

    const addParsedField = () => setParsedFields([...parsedFields, { name: '', type: 'string', rules: '', example: '' }]);
    const removeParsedField = (index) => setParsedFields(parsedFields.filter((_, i) => i !== index));

    const confirmGenerateFromParsed = async () => {
        if (!parsedFields || parsedFields.every(f => !f.name)) {
            setError('Please provide at least one field before generating.');
            return;
        }
        setLoading(true);
        setError('');
        setResponse(null);
        try {
            const res = await fetch('http://localhost:8000/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    schema_fields: parsedFields.filter(f => f.name),
                    num_records: parseInt(parsedNumRecords) || 0,
                    correct_num_records: parseInt(parsedCorrectNumRecords) || 0,
                    wrong_num_records: parseInt(parsedWrongNumRecords) || 0,
                    additional_rules: parsedAdditionalRules || undefined,
                    model_provider: modelProvider
                })
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || `Error: ${res.status}`);
            }

            const data = await res.json();
            setResponse(data);
            // clear parsed preview after generation
            setParsedSchema(null);
            setParsedFields(null);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    // ========================================================================
    // EXPORT FUNCTIONS
    // ========================================================================

    const convertToCSV = (data) => {
        if (!data || data.length === 0) return '';

        const headers = Object.keys(data[0]);
        const csvHeaders = headers.join(',');

        const csvRows = data.map(obj => {
            return headers.map(header => {
                const value = obj[header];
                if (typeof value === 'string' && (value.includes(',') || value.includes('"'))) {
                    return `"${value.replace(/"/g, '""')}"`;
                }
                return value;
            }).join(',');
        });

        return [csvHeaders, ...csvRows].join('\n');
    };

    const downloadCSV = (data, filename = 'test-data.csv') => {
        if (!data || data.length === 0) return;

        const csv = convertToCSV(data);
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    };

    const downloadAllExcel = () => {
        if (!response || !response.tables) return;

        const wb = XLSX.utils.book_new();

        Object.entries(response.tables).forEach(([tableName, data]) => {
            const ws = XLSX.utils.json_to_sheet(data);
            const sheetName = tableName.substring(0, 31);
            XLSX.utils.book_append_sheet(wb, ws, sheetName);
        });

        XLSX.writeFile(wb, 'database.xlsx');
    };

    // ========================================================================
    // API COMMUNICATION
    // ========================================================================

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError('');
        setResponse(null);
        setSelectedTable(null);

        try {
            let endpoint, body;

            if (mode === 'single') {
                endpoint = 'http://localhost:8000/generate';
                body = {
                    schema_fields: fields.filter(f => f.name),
                    num_records: parseInt(numRecords),
                    correct_num_records: parseInt(correctNumRecords),
                    wrong_num_records: parseInt(wrongNumRecords),
                    additional_rules: additionalRules || undefined,
                    model_provider: modelProvider
                };
            } else if (mode === 'selenium') {
                endpoint = 'http://localhost:8000/generate-from-selenium';
                body = {
                    selenium_script: seleniumScript,
                    num_records: parseInt(seleniumNumRecords),
                    correct_num_records: parseInt(seleniumCorrectNumRecords),
                    wrong_num_records: parseInt(seleniumWrongNumRecords),
                    additional_rules: seleniumAdditionalRules || undefined,
                    model_provider: modelProvider
                };
            }

            const res = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });

            if (!res.ok) {
                const errorData = await res.json();
                throw new Error(errorData.detail || `Error: ${res.status}`);
            }

            const data = await res.json();
            setResponse(data);

            if (false) { // Database mode removed
                const firstTable = Object.keys(data.tables)[0];
                setSelectedTable(firstTable);
            }
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    // ========================================================================
    // RENDER
    // ========================================================================

    return (
        <div className="App">
            <h1>🍉 Test Data Generator</h1>

            <div className="mode-selector">
                <button
                    className={mode === 'single' ? 'active' : ''}
                    onClick={() => setMode('single')}
                >
                    Single Table
                </button>
                <button
                    className={mode === 'selenium' ? 'active' : ''}
                    onClick={() => setMode('selenium')}
                >
                    🧾 From Selenium
                </button>
            </div>

            {/* Model Provider Selection */}
            <div className="model-provider-selector">
                <label style={{ fontWeight: 'bold', marginRight: '15px' }}>
                    🤖 AI Model:
                </label>
                <label style={{ marginRight: '20px' }}>
                    <input
                        type="radio"
                        name="modelProvider"
                        value="ollama"
                        checked={modelProvider === 'ollama'}
                        onChange={(e) => setModelProvider(e.target.value)}
                        style={{ marginRight: '5px' }}
                    />
                    Local Ollama (llama3:latest)
                </label>
                <label>
                    <input
                        type="radio"
                        name="modelProvider"
                        value="groq"
                        checked={modelProvider === 'groq'}
                        onChange={(e) => setModelProvider(e.target.value)}
                        style={{ marginRight: '5px' }}
                    />
                    Groq API (Cloud)
                </label>
            </div>

            <form onSubmit={handleSubmit}>
                {mode === 'single' ? (
                    // SINGLE TABLE MODE
                    <>
                        <div className="form-section">
                            <h2>Schema Fields</h2>
                            {fields.map((field, index) => (
                                <FieldEditor
                                    key={index}
                                    field={field}
                                    onChange={(k, v) => updateField(index, k, v)}
                                    onRemove={fields.length > 1 ? () => removeField(index) : null}
                                    openTypeModal={() => openTypeModal({ mode: 'single', index })}
                                />
                            ))}
                            <button type="button" onClick={addField} className="add-btn">
                                + Add Field
                            </button>
                        </div>

                        <div className="form-section">
                            <label>
                                Total Number of Records:
                                <input
                                    type="number"
                                    min="1"
                                    max="100"
                                    value={numRecords}
                                    onChange={(e) => setNumRecords(e.target.value)}
                                />
                            </label>
                        </div>
                        <div className="form-section">
                            <label>
                                Number of Correct Records:
                                <input
                                    type="number"
                                    min="0"
                                    max={numRecords}
                                    value={correctNumRecords}
                                    onChange={(e) => setCorrectNumRecords(e.target.value)}
                                />
                            </label>
                        </div>
                        <div className="form-section">
                            <label>
                                Number of Wrong Records:
                                <input
                                    type="number"
                                    min="0"
                                    max={numRecords}
                                    value={wrongNumRecords}
                                    onChange={(e) => setWrongNumRecords(e.target.value)}
                                />
                            </label>
                        </div>
                        <div className="form-section">
                            <label>
                                Additional Rules (optional):
                                <textarea
                                    value={additionalRules}
                                    onChange={(e) => setAdditionalRules(e.target.value)}
                                    placeholder="Any additional context or rules..."
                                    rows="3"
                                />
                            </label>
                        </div>
                    </>
                ) : mode === 'selenium' ? (
                    // SELENIUM MODE (paste-only)
                    <>
                        <div className="form-section">
                            <h2>Paste Selenium Script</h2>
                            <p className="help-text">Paste a Selenium script (Python/JS) that locates form inputs. Click "Parse Script" to extract a suggested schema you can review.</p>
                            <textarea
                                placeholder="Paste Selenium script here..."
                                value={seleniumScript}
                                onChange={(e) => setSeleniumScript(e.target.value)}
                                rows={12}
                            />

                            <div style={{ marginTop: 12 }}>
                                <button type="button" onClick={parseSelenium} className="parse-btn" disabled={loading}>
                                    {loading ? 'Parsing...' : 'Parse Script'}
                                </button>
                            </div>
                        </div>

                        {/* If parsedFields exists, show editable preview (reuse FieldEditor) */}
                        {parsedFields && (
                            <div className="form-section parsed-schema-section">
                                <h3>Parsed Schema (review & edit)</h3>
                                {parsedFields.map((field, index) => (
                                    <FieldEditor
                                        key={index}
                                        field={field}
                                        onChange={(k, v) => updateParsedField(index, k, v)}
                                        onRemove={parsedFields.length > 1 ? () => removeParsedField(index) : null}
                                        openTypeModal={() => openTypeModal({ mode: 'parsed', index })}
                                    />
                                ))}
                                <button type="button" onClick={addParsedField} className="add-btn">+ Add Field</button>

                                <div className="form-section">
                                    <label>
                                        Total Number of Records:
                                        <input
                                            type="number"
                                            min="1"
                                            max="100"
                                            value={parsedNumRecords}
                                            onChange={(e) => setParsedNumRecords(e.target.value)}
                                        />
                                    </label>
                                </div>
                                <div className="form-section">
                                    <label>
                                        Number of Correct Records:
                                        <input
                                            type="number"
                                            min="0"
                                            max={parsedNumRecords}
                                            value={parsedCorrectNumRecords}
                                            onChange={(e) => setParsedCorrectNumRecords(e.target.value)}
                                        />
                                    </label>
                                </div>
                                <div className="form-section">
                                    <label>
                                        Number of Wrong Records:
                                        <input
                                            type="number"
                                            min="0"
                                            max={parsedNumRecords}
                                            value={parsedWrongNumRecords}
                                            onChange={(e) => setParsedWrongNumRecords(e.target.value)}
                                        />
                                    </label>
                                </div>
                                <div className="form-section">
                                    <label>
                                        Additional Rules (optional):
                                        <textarea
                                            value={parsedAdditionalRules}
                                            onChange={(e) => setParsedAdditionalRules(e.target.value)}
                                            placeholder="Any additional context or rules..."
                                            rows="3"
                                        />
                                    </label>
                                </div>

                                <div style={{ marginTop: 12 }}>
                                    <button type="button" onClick={confirmGenerateFromParsed} className="submit-btn" disabled={loading}>
                                        {loading ? 'Generating...' : 'Confirm & Generate Data'}
                                    </button>
                                </div>
                            </div>
                        )}
                    </>) : null}

                {mode === 'selenium' ? null : (
                    <button type="submit" disabled={loading} className="submit-btn">
                        {loading ? 'Generating...' : 'Generate Data'}
                    </button>
                )}
            </form>

            {error && (
                <div className="error">
                    <h3>Error:</h3>
                    <p>{error}</p>
                </div>
            )}

            {response && (
                <div className="response">
                    <>
                        {mode === 'selenium' && response.parsed_schema && (
                            <div className="parsed-schema">
                                <h3>Parsed Schema</h3>
                                <pre>{JSON.stringify(response.parsed_schema, null, 2)}</pre>
                            </div>
                        )}
                        <h2>Generated Data ({response.count} records)</h2>
                            <div className="view-controls">
                                <button
                                    className={viewMode === 'json' ? 'active' : ''}
                                    onClick={() => setViewMode('json')}
                                >
                                    JSON View
                                </button>
                                <button
                                    className={viewMode === 'csv' ? 'active' : ''}
                                    onClick={() => setViewMode('csv')}
                                >
                                    CSV View
                                </button>
                                <button onClick={() => downloadCSV(response.data)} className="download-btn">
                                    Download CSV
                                </button>
                            </div>
                            <div className="data-table">
                                {viewMode === 'json' ? (
                                    <pre>{JSON.stringify(response.data, null, 2)}</pre>
                                ) : (
                                    <pre>{convertToCSV(response.data)}</pre>
                                )}
                            </div>
                        </>
                </div>
            )}
            <TypeModal
                show={showTypeModal}
                onClose={() => setShowTypeModal(false)}
                types={allDataTypes}
                onSelect={handleTypeSelect}
            />
        </div>
    );
}

export default App;
