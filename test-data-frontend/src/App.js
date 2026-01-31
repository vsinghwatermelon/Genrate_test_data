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
import GroupEditor from './components/GroupEditor';
import GroupEditModal from './components/GroupEditModal';
import SchemaEditor from './components/SchemaEditor';
import * as XLSX from 'xlsx';
import SeleniumFolderUpload from './components/SeleniumFolderUpload';
import ScriptExecutor from './components/ScriptExecutor';

function App() {
    // ========================================================================
    // STATE MANAGEMENT
    // ========================================================================

    const [mode, setMode] = useState('database');

    // Single table mode state
    const [fields, setFields] = useState([{ name: '', type: 'string', rules: '', example: '' }]);

    // NEW: Group-based generation mode toggle
    const [useGroups, setUseGroups] = useState(true);
    const [groups, setGroups] = useState([
        { name: 'G1', count: 5, correct_fields: [], wrong_fields: [], wrong_field_rules: {} }
    ]);

    // Legacy: Simple correct/wrong counts - REMOVED


    const [additionalRules, setAdditionalRules] = useState('');

    // Parsed schema state (for Folder Upload / Script Executor)
    const [parsedFields, setParsedFields] = useState(null);
    const [parsedSchema, setParsedSchema] = useState(null);
    const [parsedGroups, setParsedGroups] = useState([
        { name: 'G1', count: 5, correct_fields: [], wrong_fields: [], wrong_field_rules: {} }
    ]);

    // Common state
    const [response, setResponse] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [viewMode, setViewMode] = useState('json');
    const [selectedTable, setSelectedTable] = useState(null);
    const [modelProvider, setModelProvider] = useState('ollama'); // 'ollama' or 'groq'

    // Group edit modal state
    const [showGroupEditModal, setShowGroupEditModal] = useState(false);
    const [editingGroup, setEditingGroup] = useState(null);
    const [editingGroupIndex, setEditingGroupIndex] = useState(null);
    const [regeneratingGroup, setRegeneratingGroup] = useState(false);
    const [generatedSchema, setGeneratedSchema] = useState(null); // Store schema used for generation

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
            updateParsedField(idx, 'type', typeObj.id || typeObj.name);
            if (typeObj.example) updateParsedField(idx, 'example', typeObj.example);
            updateParsedField(idx, 'rules', ruleToApply);
        }
        setShowTypeModal(false);
        setTypeModalTarget(null);
    };

    // ========================================================================
    // GROUP MANAGEMENT (for single table mode)
    // ========================================================================
    const addGroup = () => {
        setGroups([...groups, {
            name: `G${groups.length + 1}`,
            count: 1,
            correct_fields: [],
            wrong_fields: [],
            wrong_field_rules: {}
        }]);
    };

    const removeGroup = (index) => {
        setGroups(groups.filter((_, i) => i !== index));
    };

    const updateGroup = (index, key, value) => {
        const updated = [...groups];
        updated[index][key] = value;
        setGroups(updated);
    };

    // ========================================================================
    // GROUP MANAGEMENT (for parsed/selenium mode)
    // ========================================================================
    const addParsedGroup = () => {
        setParsedGroups([...parsedGroups, {
            name: `G${parsedGroups.length + 1}`,
            count: 1,
            correct_fields: [],
            wrong_fields: [],
            wrong_field_rules: {}
        }]);
    };

    const removeParsedGroup = (index) => {
        setParsedGroups(parsedGroups.filter((_, i) => i !== index));
    };

    const updateParsedGroup = (index, key, value) => {
        const updated = [...parsedGroups];
        updated[index][key] = value;
        setParsedGroups(updated);
    };

    // ========================================================================
    // GROUP EDIT MODAL HANDLERS (for regenerating group data)
    // ========================================================================
    const handleEditGroupClick = (groupData, index) => {
        setEditingGroup(groupData);
        setEditingGroupIndex(index);
        setShowGroupEditModal(true);
    };

    // ========================================================================
    // SCRIPT EXECUTOR SCHEMA HANDLER
    // ========================================================================
    const handleSchemaGenerated = (schema, options = {}) => {
        // Convert parsed schema to parsed fields format
        if (schema && Array.isArray(schema)) {
            setParsedFields(schema);
            setParsedSchema(schema);
            // Default to group-based generation for a richer experience
            // Switch to selenium mode to show the schema editor unless caller requested inline behavior
            if (!options.inline) {
                // If specific mode needed, handle here. Currently script-executor handles its own display
            }
        }
    };

    const sanitizeFields = (fields) => {
        return fields.map(f => ({
            ...f,
            rules: f.rules === null || f.rules === undefined ? "" : String(f.rules),
            example: f.example === null || f.example === undefined ? "" : String(f.example)
        }));
    };

    const handleGroupEditSave = async (editMode, updatedGroup, prompt) => {
        setRegeneratingGroup(true);
        setError('');

        try {
            // Use the schema that was used for generation, or fall back to current fields
            const schemaToUse = generatedSchema && generatedSchema.length > 0 ? generatedSchema : fields;

            // Filter out fields with empty names before sending
            const validFields = schemaToUse.filter(f => f.name && f.name.trim() !== '');

            if (validFields.length === 0) {
                throw new Error('No valid fields defined. Please add at least one field with a name.');
            }

            // Build the payload to regenerate ONLY this specific group
            const payload = {
                schema_fields: sanitizeFields(validFields),  // Backend expects 'schema_fields' with valid field names
                groups: [{
                    name: updatedGroup.name,
                    count: updatedGroup.count,
                    correct_fields: updatedGroup.correct_fields,
                    wrong_fields: updatedGroup.wrong_fields,
                    wrong_field_rules: updatedGroup.wrong_field_rules || {}
                }],
                // For prompt mode, use the prompt; for manual mode, construct rules from wrong_field_rules
                additional_rules: editMode === 'prompt'
                    ? prompt
                    : (updatedGroup.wrong_field_rules && Object.keys(updatedGroup.wrong_field_rules).length > 0)
                        ? "For invalid fields, follow these rules: " + Object.entries(updatedGroup.wrong_field_rules)
                            .filter(([field]) => updatedGroup.wrong_fields.includes(field))
                            .map(([field, rule]) => `${field}: ${rule}`)
                            .join('; ')
                        : '',
                model_provider: modelProvider
            };

            console.log('Sending payload:', JSON.stringify(payload, null, 2));

            const res = await fetch('http://localhost:8000/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!res.ok) {
                const data = await res.json().catch(() => ({}));
                const errorMsg = typeof data.detail === 'string'
                    ? data.detail
                    : data.message || JSON.stringify(data.detail) || 'Failed to regenerate group';
                throw new Error(errorMsg);
            }

            const newGroupData = await res.json();

            // Update the response by replacing ONLY the old group's data with new data
            if (response && response.data && response.groups) {
                const oldGroupName = editingGroup.group_name;

                // Filter out ONLY the records from the group being edited
                const filteredData = response.data.filter(
                    record => record._group !== oldGroupName
                );

                // Add the newly generated data for this group
                const updatedData = [...filteredData, ...newGroupData.data];

                // Update the group breakdown info for this specific group
                const updatedGroups = [...response.groups];
                updatedGroups[editingGroupIndex] = {
                    group_name: updatedGroup.name,
                    count: newGroupData.count,
                    correct_fields: updatedGroup.correct_fields,
                    wrong_fields: updatedGroup.wrong_fields,
                    wrong_field_rules: updatedGroup.wrong_field_rules || {}
                };

                setResponse({
                    ...response,
                    data: updatedData,
                    count: updatedData.length,
                    groups: updatedGroups
                });
            }

            setShowGroupEditModal(false);
            setEditingGroup(null);
            setEditingGroupIndex(null);
        } catch (err) {
            console.error('Group regeneration error:', err);
            const errorMsg = err.message || String(err) || 'Unknown error occurred';
            setError(`Failed to regenerate group: ${errorMsg}`);
        } finally {
            setRegeneratingGroup(false);
        }
    };

    // Selenium parse functions removed


    const updateParsedField = (index, key, value) => {
        const updated = [...parsedFields];
        updated[index][key] = value;
        setParsedFields(updated);
    };

    const addParsedField = () => setParsedFields([...parsedFields, { name: '', type: 'string', rules: '', example: '' }]);
    const removeParsedField = (index) => setParsedFields(parsedFields.filter((_, i) => i !== index));



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
                const validFields = fields.filter(f => f.name);

                body = {
                    schema_fields: sanitizeFields(validFields),
                    groups: groups,
                    additional_rules: additionalRules || undefined,
                    model_provider: modelProvider
                };

            } else if (mode === 'selenium-folder') {
                // If we've extracted fields from a folder, we use the parsedFields and parsedGroups
                endpoint = 'http://localhost:8000/generate';
                const validFields = parsedFields?.filter(f => f.name) || [];

                if (validFields.length === 0) {
                    throw new Error('No fields extracted yet. Please upload a folder first.');
                }

                body = {
                    schema_fields: sanitizeFields(validFields),
                    groups: parsedGroups,
                    model_provider: modelProvider
                };
            } else if (parsedFields && Array.isArray(parsedFields) && parsedFields.length > 0) {
                // If parsedFields exists (from script executor or folder), treat like single-mode generation
                endpoint = 'http://localhost:8000/generate';
                const validFields = parsedFields.filter(f => f.name && f.name.trim() !== '');
                body = {
                    schema_fields: sanitizeFields(validFields),
                    groups: parsedGroups,
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

            // Store the schema that was used for this generation
            if (mode === 'single') {
                const validFields = fields.filter(f => f.name);
                setGeneratedSchema(validFields);
            }

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
                    className={mode === 'selenium-folder' ? 'active' : ''}
                    onClick={() => setMode('selenium-folder')}
                >
                    📁 Selenium Folder Extractor
                </button>
                <button
                    className={mode === 'script-executor' ? 'active' : ''}
                    onClick={() => setMode('script-executor')}
                >
                    ▶️ Script Executor
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
                            <h3>Data Groups</h3>
                            <p className="help-text">
                                Create groups with different combinations of correct and wrong fields.
                                Each group can have specific fields marked as valid or invalid.
                            </p>
                            {groups.map((group, index) => (
                                <GroupEditor
                                    key={index}
                                    group={group}
                                    fields={fields.filter(f => f.name)}
                                    onChange={(k, v) => updateGroup(index, k, v)}
                                    onRemove={groups.length > 1 ? () => removeGroup(index) : null}
                                />
                            ))}
                            <button type="button" onClick={addGroup} className="add-btn">
                                + Add Group
                            </button>
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
                ) : mode === 'selenium-folder' ? (
                    <>
                        <SeleniumFolderUpload onExtract={(f) => {
                            setParsedFields(f);
                            // Groups mode is now always enabled by default
                        }} />

                        {parsedFields && (
                            <div className="form-section parsed-schema-section" style={{ marginTop: '30px' }}>
                                <h3>📊 Extraction Configuration</h3>
                                <p className="help-text">Review the extracted schema and configure data generation groups.</p>

                                <div className="form-section">
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
                                        <h4>Schema Fields</h4>
                                        <button type="button" onClick={addParsedField} className="add-btn">+ Add Field</button>
                                    </div>
                                    {parsedFields.map((field, index) => (
                                        <FieldEditor
                                            key={index}
                                            field={field}
                                            onChange={(k, v) => updateParsedField(index, k, v)}
                                            onRemove={parsedFields.length > 1 ? () => removeParsedField(index) : null}
                                            openTypeModal={() => openTypeModal({ mode: 'parsed', index })}
                                        />
                                    ))}
                                </div>

                                <div className="form-section" style={{ marginTop: '30px' }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
                                        <h4 style={{ margin: 0 }}>Data Groups</h4>
                                        <button type="button" onClick={addParsedGroup} className="add-btn">+ Add Group</button>
                                    </div>
                                    {parsedGroups.map((group, index) => (
                                        <GroupEditor
                                            key={index}
                                            group={group}
                                            fields={parsedFields.filter(f => f.name)}
                                            onChange={(k, v) => updateParsedGroup(index, k, v)}
                                            onRemove={parsedGroups.length > 1 ? () => removeParsedGroup(index) : null}
                                        />
                                    ))}
                                </div>

                                <div style={{ marginTop: '40px', display: 'flex', justifyContent: 'center' }}>
                                    <button
                                        type="submit"
                                        className="generate-big-btn"
                                        disabled={loading}
                                    >
                                        {loading ? '⏳ Generating...' : '🚀 Generate High-Fidelity Test Data'}
                                    </button>
                                </div>
                            </div>
                        )}
                    </>
                ) : mode === 'script-executor' ? (
                    <ScriptExecutor />
                ) : null}

                {mode === 'single' ? (
                    <button type="submit" disabled={loading} className="submit-btn">
                        {loading ? 'Generating...' : 'Generate Data'}
                    </button>
                ) : null}
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
                        {/* Remove old table-style parsed schema display for selenium mode. Always use FieldEditor-based UI below. */}

                        {/* Show group breakdown if available */}
                        {response.groups && response.groups.length > 0 && (
                            <div className="group-breakdown">
                                <h3>📊 Group Breakdown</h3>
                                <div className="group-summary-cards">
                                    {response.groups.map((grp, idx) => (
                                        <div key={idx} className="group-card">
                                            <div className="group-card-header">
                                                <div className="group-card-title">
                                                    <strong>{grp.group_name}</strong>
                                                    <span className="group-count-badge">{grp.count} records</span>
                                                </div>
                                                <button
                                                    className="edit-group-btn"
                                                    onClick={() => handleEditGroupClick(grp, idx)}
                                                    title="Edit and regenerate this group"
                                                >
                                                    ✏️ Edit
                                                </button>
                                            </div>
                                            {grp.correct_fields && grp.correct_fields.length > 0 && (
                                                <div className="group-card-fields correct">
                                                    <span className="field-label">✓ Correct:</span>
                                                    <span className="field-list">{grp.correct_fields.join(', ')}</span>
                                                </div>
                                            )}
                                            {grp.wrong_fields && grp.wrong_fields.length > 0 && (
                                                <div className="group-card-fields wrong">
                                                    <span className="field-label">✗ Wrong:</span>
                                                    <span className="field-list">{grp.wrong_fields.join(', ')}</span>
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        <h2>Generated Data ({response.count} records)</h2>
                        {response.groups && response.groups.length > 0 && (
                            <p className="metadata-note">
                                <strong>Note:</strong> Each record includes metadata fields:
                                <code>_group</code> (group name) and <code>_wrong_fields</code> (fields intentionally made invalid)
                            </p>
                        )}
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
            <GroupEditModal
                show={showGroupEditModal}
                group={editingGroup}
                fields={fields}
                onClose={() => {
                    setShowGroupEditModal(false);
                    setEditingGroup(null);
                    setEditingGroupIndex(null);
                }}
                onSave={handleGroupEditSave}
                loading={regeneratingGroup}
            />
        </div>
    );
}

export default App;
