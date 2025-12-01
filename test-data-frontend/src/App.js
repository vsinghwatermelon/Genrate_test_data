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

    // Database mode state
    const [dbName, setDbName] = useState('');
    const [intelligentMode, setIntelligentMode] = useState(true);
    const [tables, setTables] = useState([
        {
            table_name: '',
            num_records: 5,
            correct_num_records: 5,
            wrong_num_records: 0,
            additional_context: '',
            fields: [{ name: '', type: 'string', rules: '', example: '' }]
        }
    ]);

    // Natural Language mode state
    const [naturalLanguageText, setNaturalLanguageText] = useState('');
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
        } else if (typeModalTarget.mode === 'table') {
            const { tableIndex, fieldIndex } = typeModalTarget;
            updateFieldInTable(tableIndex, fieldIndex, 'type', typeObj.id || typeObj.name);
            if (typeObj.example) updateFieldInTable(tableIndex, fieldIndex, 'example', typeObj.example);
            updateFieldInTable(tableIndex, fieldIndex, 'rules', ruleToApply);
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
    // DATABASE MODE - Table Management
    // ========================================================================

    const addTable = () => {
        setTables([
            ...tables,
            {
                table_name: '',
                num_records: 5,
                correct_num_records: 5,
                wrong_num_records: 0,
                additional_context: '',
                fields: [{ name: '', type: 'string', rules: '', example: '' }]
            }
        ]);
    };

    const removeTable = (tableIndex) => {
        setTables(tables.filter((_, i) => i !== tableIndex));
    };

    const updateTable = (tableIndex, key, value) => {
        const updatedTables = [...tables];
        updatedTables[tableIndex][key] = value;
        setTables(updatedTables);
    };

    // ========================================================================
    // DATABASE MODE - Field Management
    // ========================================================================
    const addFieldToTable = (tableIndex) => {
        const updatedTables = [...tables];
        updatedTables[tableIndex].fields.push({
            name: '',
            type: 'string',
            rules: '',
            example: '',
            references: null
        });
        setTables(updatedTables);
    };

    const removeFieldFromTable = (tableIndex, fieldIndex) => {
        const updatedTables = [...tables];
        updatedTables[tableIndex].fields = updatedTables[tableIndex].fields.filter((_, i) => i !== fieldIndex);
        setTables(updatedTables);
    };

    const updateFieldInTable = (tableIndex, fieldIndex, key, value) => {
        const updatedTables = [...tables];
        updatedTables[tableIndex].fields[fieldIndex][key] = value;
        setTables(updatedTables);
    };

    const toggleReference = (tableIndex, fieldIndex) => {
        const updatedTables = [...tables];
        const field = updatedTables[tableIndex].fields[fieldIndex];

        if (field.references) {
            field.references = null;
        } else {
            field.references = { table: '', field: 'id' };
        }

        setTables(updatedTables);
    };

    const updateReference = (tableIndex, fieldIndex, key, value) => {
        const updatedTables = [...tables];
        updatedTables[tableIndex].fields[fieldIndex].references[key] = value;
        setTables(updatedTables);
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
            } else if (mode === 'natural') {
                endpoint = 'http://localhost:8000/generate-from-text';
                body = {
                    user_text: naturalLanguageText,
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
            } else {
                endpoint = 'http://localhost:8000/generate-db';
                body = {
                    db_schema: {
                        db_name: dbName || 'my_database',
                        use_intelligent_mode: intelligentMode,
                        model_provider: modelProvider,
                        tables: tables
                            .filter(t => t.table_name)
                            .map(t => ({
                                ...t,
                                fields: t.fields.filter(f => f.name).map(f => {
                                    const field = { ...f };
                                    if (intelligentMode) {
                                        delete field.references;
                                    } else {
                                        if (field.references && !field.references.table) {
                                            delete field.references;
                                        }
                                    }
                                    return field;
                                })
                            }))
                    }
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

            if ((mode === 'database' || mode === 'natural') && data.tables) {
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
            <h1>🧪 Test Data Generator</h1>

            <div className="mode-selector">
                <button
                    className={mode === 'single' ? 'active' : ''}
                    onClick={() => setMode('single')}
                >
                    Single Table
                </button>
                <button
                    className={mode === 'database' ? 'active' : ''}
                    onClick={() => setMode('database')}
                >
                    Full Database
                </button>
                <button
                    className={mode === 'natural' ? 'active' : ''}
                    onClick={() => setMode('natural')}
                >
                    🤖 Natural Language
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
                {mode === 'natural' ? (
                    // NATURAL LANGUAGE MODE
                    <>
                        <div className="form-section natural-language-section">
                            <h2>🤖 Describe Your Database in Plain English</h2>
                            <p className="help-text">
                                Simply describe what database you want to create. Our AI agents will automatically:
                                <br />✨ Parse your description and extract tables, fields, relationships
                                <br />🧠 Infer missing fields and data types intelligently
                                <br />🔗 Detect primary and foreign key relationships
                                <br />✅ Validate schema completeness
                                <br />🎲 Generate realistic test data
                            </p>

                            <div className="example-prompts">
                                <h3>Example Prompts:</h3>
                                <div className="example-grid">
                                    <button
                                        type="button"
                                        className="example-btn"
                                        onClick={() => setNaturalLanguageText("Create a college database with departments, employees, and salaries. Departments should have name and building. Employees work in departments and have email addresses. Salaries are associated with employees. Generate 5 departments, 20 employees, and 20 salary records.")}
                                    >
                                        🎓 College Database
                                    </button>
                                    <button
                                        type="button"
                                        className="example-btn"
                                        onClick={() => setNaturalLanguageText("Generate an e-commerce database with customers, products, and orders. Customers should have contact info. Products have prices and stock. Orders link customers to products. Include 15 customers, 50 products, and 30 orders.")}
                                    >
                                        🛒 E-commerce System
                                    </button>
                                    <button
                                        type="button"
                                        className="example-btn"
                                        onClick={() => setNaturalLanguageText("Create a hospital management system with patients, doctors, and appointments. Patients have medical records. Doctors have specializations. Appointments connect patients with doctors. Generate 30 patients, 10 doctors, and 50 appointments.")}
                                    >
                                        🏥 Hospital System
                                    </button>
                                    <button
                                        type="button"
                                        className="example-btn"
                                        onClick={() => setNaturalLanguageText("Make a library database with books, authors, members, and borrowing records. Books are written by authors. Members borrow books. Create 100 books, 20 authors, 50 members, and 75 borrowing records.")}
                                    >
                                        📚 Library System
                                    </button>
                                </div>
                            </div>

                            <textarea
                                className="natural-language-input"
                                placeholder="Example: Create a company database with 3 departments, 15 employees, and 15 salary records. Employees should work in departments and have contact information..."
                                value={naturalLanguageText}
                                onChange={(e) => setNaturalLanguageText(e.target.value)}
                                rows={8}
                                required
                            />

                            <div className="info-box">
                                <strong>💡 Tips:</strong>
                                <ul>
                                    <li>Mention table names and relationships between them</li>
                                    <li>Specify how many records you want for each table</li>
                                    <li>Include any specific fields you need (email, phone, address, etc.)</li>
                                    <li>The AI will automatically infer missing fields and relationships</li>
                                </ul>
                            </div>
                        </div>
                    </>
                ) : mode === 'single' ? (
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
                    </>
                ) : (
                    // DATABASE MODE
                    <>
                        <div className="form-section">
                            <label>
                                Database Name:
                                <input
                                    type="text"
                                    placeholder="e.g., college_db"
                                    value={dbName}
                                    onChange={(e) => setDbName(e.target.value)}
                                />
                            </label>
                        </div>

                        <div className="form-section intelligent-mode-section">
                            <label className="intelligent-toggle">
                                <input
                                    type="checkbox"
                                    checked={intelligentMode}
                                    onChange={(e) => setIntelligentMode(e.target.checked)}
                                />
                                <span className="toggle-label">
                                    🤖 <strong>Intelligent Mode</strong> - AI agents auto-detect primary keys and foreign keys
                                </span>
                            </label>
                            {!intelligentMode && (
                                <p className="mode-hint">
                                    ⚙️ Manual mode: You'll need to specify primary keys and foreign key relationships using the 🔗 button
                                </p>
                            )}
                            {intelligentMode && (
                                <p className="mode-hint">
                                    ✨ Just provide table and field names - AI will figure out the relationships!
                                </p>
                            )}
                        </div>

                        <div className="form-section">
                            <h2>Tables ({tables.length})</h2>

                            {tables.map((table, tableIndex) => (
                                <div key={tableIndex} className="table-card">
                                    <div className="table-header">
                                        <input
                                            type="text"
                                            placeholder="Table Name (e.g., students)"
                                            value={table.table_name}
                                            onChange={(e) => updateTable(tableIndex, 'table_name', e.target.value)}
                                            className="table-name-input"
                                            required
                                        />
                                        {tables.length > 1 && (
                                            <button
                                                type="button"
                                                onClick={() => removeTable(tableIndex)}
                                                className="remove-table-btn"
                                            >
                                                🗑️ Remove Table
                                            </button>
                                        )}
                                    </div>

                                    <div className="table-context">
                                        <label>
                                            <span className="context-label">
                                                💡 Additional Context (helps AI understand the table):
                                            </span>
                                            <textarea
                                                value={table.additional_context || ''}
                                                onChange={(e) => updateTable(tableIndex, 'additional_context', e.target.value)}
                                                placeholder="e.g., 'University departments with diverse disciplines' or 'Student enrollment records'"
                                                rows="2"
                                            />
                                        </label>
                                    </div>

                                    <div className="table-counts">
                                        <label>
                                            Total Records:
                                            <input
                                                type="number"
                                                min="1"
                                                value={table.num_records}
                                                onChange={(e) => updateTable(tableIndex, 'num_records', e.target.value)}
                                            />
                                        </label>
                                        <label>
                                            Valid:
                                            <input
                                                type="number"
                                                min="0"
                                                max={table.num_records}
                                                value={table.correct_num_records}
                                                onChange={(e) => updateTable(tableIndex, 'correct_num_records', e.target.value)}
                                            />
                                        </label>
                                        <label>
                                            Invalid:
                                            <input
                                                type="number"
                                                min="0"
                                                max={table.num_records}
                                                value={table.wrong_num_records}
                                                onChange={(e) => updateTable(tableIndex, 'wrong_num_records', e.target.value)}
                                            />
                                        </label>
                                    </div>

                                    <h4>Fields:</h4>
                                    {table.fields.map((field, fieldIndex) => (
                                        <div key={fieldIndex} className="field-row">
                                            <input
                                                type="text"
                                                placeholder="Field Name"
                                                value={field.name}
                                                onChange={(e) => updateFieldInTable(tableIndex, fieldIndex, 'name', e.target.value)}
                                                required
                                            />
                                            <FieldEditor
                                                field={field}
                                                onChange={(k, v) => updateFieldInTable(tableIndex, fieldIndex, k, v)}
                                                onRemove={table.fields.length > 1 ? () => removeFieldFromTable(tableIndex, fieldIndex) : null}
                                                openTypeModal={() => openTypeModal({ mode: 'table', tableIndex, fieldIndex })}
                                            />
                                            <input
                                                type="text"
                                                placeholder="Rules"
                                                value={field.rules || ''}
                                                onChange={(e) => updateFieldInTable(tableIndex, fieldIndex, 'rules', e.target.value)}
                                            />
                                            <input
                                                type="text"
                                                placeholder="Example"
                                                value={field.example || ''}
                                                onChange={(e) => updateFieldInTable(tableIndex, fieldIndex, 'example', e.target.value)}
                                            />

                                            {!intelligentMode && (
                                                <button
                                                    type="button"
                                                    onClick={() => toggleReference(tableIndex, fieldIndex)}
                                                    className="fk-btn"
                                                    title="Add Foreign Key"
                                                >
                                                    🔗
                                                </button>
                                            )}

                                            {table.fields.length > 1 && (
                                                <button
                                                    type="button"
                                                    onClick={() => removeFieldFromTable(tableIndex, fieldIndex)}
                                                    className="remove-btn"
                                                >
                                                    ✕
                                                </button>
                                            )}

                                            {!intelligentMode && field.references && (
                                                <div className="reference-row">
                                                    <span>References:</span>
                                                    <select
                                                        value={field.references.table}
                                                        onChange={(e) => updateReference(tableIndex, fieldIndex, 'table', e.target.value)}
                                                    >
                                                        <option value="">Select Table</option>
                                                        {tables
                                                            .filter((_, i) => i !== tableIndex)
                                                            .map((t, i) => (
                                                                <option key={i} value={t.table_name}>
                                                                    {t.table_name || `Table ${i + 1}`}
                                                                </option>
                                                            ))}
                                                    </select>
                                                    <input
                                                        type="text"
                                                        placeholder="Field (e.g., id)"
                                                        value={field.references.field}
                                                        onChange={(e) => updateReference(tableIndex, fieldIndex, 'field', e.target.value)}
                                                    />
                                                </div>
                                            )}
                                        </div>
                                    ))}

                                    <button
                                        type="button"
                                        onClick={() => addFieldToTable(tableIndex)}
                                        className="add-btn"
                                    >
                                        + Add Field
                                    </button>
                                </div>
                            ))}

                            <button type="button" onClick={addTable} className="add-table-btn">
                                + Add Table
                            </button>
                        </div>
                    </>
                )}

                {mode === 'selenium' ? null : (
                    <button type="submit" disabled={loading} className="submit-btn">
                        {loading ? 'Generating...' : `Generate ${mode === 'database' ? 'Database' : 'Data'}`}
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
                    {(mode === 'single' || mode === 'selenium') ? (
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
                    ) : (
                        <>
                            <h2>Generated Database: {response.db_name}</h2>
                            <div className="db-stats">
                                <p><strong>Total Records:</strong> {response.total_records}</p>
                                <p><strong>Total Tables:</strong> {response.total_tables}</p>
                                <p><strong>Generation Order:</strong> {response.generation_order?.join(' → ')}</p>
                            </div>

                            <div className="table-selector">
                                <h3>Select Table:</h3>
                                <div className="table-buttons">
                                    {Object.keys(response.tables).map((tableName) => (
                                        <button
                                            key={tableName}
                                            className={selectedTable === tableName ? 'active' : ''}
                                            onClick={() => setSelectedTable(tableName)}
                                        >
                                            {tableName} ({response.tables[tableName].length})
                                        </button>
                                    ))}
                                </div>
                                <button onClick={downloadAllExcel} className="download-all-btn">
                                    📦 Download All Tables (Excel)
                                </button>
                            </div>

                            {selectedTable && (
                                <>
                                    <h3>Table: {selectedTable}</h3>
                                    <div className="table-info">
                                        <span>Total: {response.counts[selectedTable]?.total}</span>
                                        <span className="valid">Valid: {response.counts[selectedTable]?.valid}</span>
                                        <span className="invalid">Invalid: {response.counts[selectedTable]?.invalid}</span>
                                    </div>

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
                                        <button
                                            onClick={() => downloadCSV(response.tables[selectedTable], `${selectedTable}.csv`)}
                                            className="download-btn"
                                        >
                                            Download {selectedTable}.csv
                                        </button>
                                    </div>

                                    <div className="data-table">
                                        {viewMode === 'json' ? (
                                            <pre>{JSON.stringify(response.tables[selectedTable], null, 2)}</pre>
                                        ) : (
                                            <pre>{convertToCSV(response.tables[selectedTable])}</pre>
                                        )}
                                    </div>
                                </>
                            )}
                        </>
                    )}
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
