import React, { useState, useEffect } from 'react';
import './GroupEditModal.css';

/**
 * GroupEditModal Component
 * 
 * Modal for editing generated group data with two modes:
 * 1. Manual Mode: Directly edit correct/wrong field selections
 * 2. Prompt Mode: Use natural language prompt to regenerate data
 * 
 * Props:
 * - show: Boolean to control modal visibility
 * - group: Group object {group_name, count, correct_fields, wrong_fields}
 * - fields: Array of all schema fields [{name, type, ...}]
 * - onClose: Callback to close modal
 * - onSave: Callback (editMode, updatedGroup, prompt) when save is clicked
 * - loading: Boolean indicating if regeneration is in progress
 */
function GroupEditModal({ show, group, fields, onClose, onSave, loading }) {
    const [editMode, setEditMode] = useState('manual'); // 'manual' or 'prompt'
    const [correctFields, setCorrectFields] = useState([]);
    const [wrongFields, setWrongFields] = useState([]);
    const [recordCount, setRecordCount] = useState(5);
    const [prompt, setPrompt] = useState('');
    const [wrongFieldRules, setWrongFieldRules] = useState({});

    // Reset state when modal opens with new group
    useEffect(() => {
        if (show && group) {
            setCorrectFields(group.correct_fields || []);
            setWrongFields(group.wrong_fields || []);
            setWrongFieldRules(group.wrong_field_rules || {});
            setRecordCount(group.count || 5);
            setPrompt('');
            setEditMode('manual');
        }
    }, [show, group]);

    if (!show || !group) return null;

    const handleFieldToggle = (fieldName, type) => {
        if (type === 'correct') {
            if (correctFields.includes(fieldName)) {
                setCorrectFields(correctFields.filter(f => f !== fieldName));
            } else {
                setCorrectFields([...correctFields, fieldName]);
                setWrongFields(wrongFields.filter(f => f !== fieldName));
            }
        } else {
            if (wrongFields.includes(fieldName)) {
                setWrongFields(wrongFields.filter(f => f !== fieldName));
            } else {
                setWrongFields([...wrongFields, fieldName]);
                setCorrectFields(correctFields.filter(f => f !== fieldName));
            }
        }
    };

    const handleWrongRuleChange = (fieldName, value) => {
        const rules = { ...wrongFieldRules };
        if (value) {
            rules[fieldName] = value;
        } else {
            delete rules[fieldName];
        }
        setWrongFieldRules(rules);
    };

    const handleSave = () => {
        if (editMode === 'manual') {
            const updatedGroup = {
                ...group,
                name: group.group_name,
                count: recordCount,
                correct_fields: correctFields,
                wrong_fields: wrongFields,
                wrong_field_rules: wrongFieldRules
            };
            onSave('manual', updatedGroup, null);
        } else {
            const updatedGroup = {
                ...group,
                name: group.group_name,
                count: recordCount,
                correct_fields: correctFields,
                wrong_fields: wrongFields,
                wrong_field_rules: wrongFieldRules
            };
            onSave('prompt', updatedGroup, prompt);
        }
    };

    const markAllCorrect = () => {
        const allFieldNames = fields.map(f => f.name);
        setCorrectFields(allFieldNames);
        setWrongFields([]);
    };

    const markAllWrong = () => {
        const allFieldNames = fields.map(f => f.name);
        setWrongFields(allFieldNames);
        setCorrectFields([]);
    };

    const clearAll = () => {
        setCorrectFields([]);
        setWrongFields([]);
    };

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-content group-edit-modal" onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                    <h2>Edit Group: {group.group_name}</h2>
                    <button className="modal-close" onClick={onClose}>&times;</button>
                </div>

                <div className="modal-body">
                    <div className="edit-info-banner">
                        ℹ️ You are editing only <strong>{group.group_name}</strong>'s data.
                        All other groups will remain unchanged.
                    </div>

                    {/* Edit Mode Toggle */}
                    <div className="edit-mode-selector">
                        <button
                            className={`mode-btn ${editMode === 'manual' ? 'active' : ''}`}
                            onClick={() => setEditMode('manual')}
                        >
                            ✏️ Manual Edit
                        </button>
                        <button
                            className={`mode-btn ${editMode === 'prompt' ? 'active' : ''}`}
                            onClick={() => setEditMode('prompt')}
                        >
                            🤖 Prompt-Based
                        </button>
                    </div>

                    {/* Record Count */}
                    <div className="form-group">
                        <label>
                            Number of Records:
                            <input
                                type="number"
                                min="1"
                                max="50"
                                value={recordCount}
                                onChange={(e) => setRecordCount(parseInt(e.target.value) || 1)}
                                className="record-count-input"
                            />
                        </label>
                    </div>

                    {editMode === 'manual' ? (
                        <div className="manual-edit-section">
                            <h3>Field Configuration for {group.group_name}</h3>
                            <p className="mode-description">
                                Select which fields should be correct (✓) or wrong (✗) for this group's records.
                            </p>
                            <div className="quick-actions">
                                <button onClick={markAllCorrect} className="quick-btn correct-btn">
                                    ✓ All Correct
                                </button>
                                <button onClick={markAllWrong} className="quick-btn wrong-btn">
                                    ✗ All Wrong
                                </button>
                                <button onClick={clearAll} className="quick-btn clear-btn">
                                    Clear All
                                </button>
                            </div>

                            <div className="field-selection">
                                <div className="field-selection-header">
                                    <span>Field</span>
                                    <span>✓ Correct</span>
                                    <span>✗ Wrong</span>
                                </div>
                                {fields.map((field, idx) => (
                                    <div key={idx} className="field-row">
                                        <span className="field-name">{field.name || `Field ${idx + 1}`}</span>
                                        <label className="checkbox-label">
                                            <input
                                                type="checkbox"
                                                checked={correctFields.includes(field.name)}
                                                onChange={() => handleFieldToggle(field.name, 'correct')}
                                            />
                                        </label>
                                        <label className="checkbox-label">
                                            <input
                                                type="checkbox"
                                                checked={wrongFields.includes(field.name)}
                                                onChange={() => handleFieldToggle(field.name, 'wrong')}
                                            />
                                        </label>
                                        {wrongFields.includes(field.name) && (
                                            <input
                                                type="text"
                                                placeholder="e.g. invalid email, empty"
                                                style={{ marginLeft: 8, width: 180 }}
                                                value={wrongFieldRules[field.name] || ''}
                                                onChange={e => handleWrongRuleChange(field.name, e.target.value)}
                                            />
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>
                    ) : (
                        <div className="prompt-edit-section">
                            <h3>Describe the Data for {group.group_name}</h3>
                            <p className="prompt-help">
                                Use natural language to describe how you want <strong>this group's</strong> data to be generated.
                                The AI will regenerate only the records in <strong>{group.group_name}</strong> based on your instructions.
                            </p>
                            <textarea
                                value={prompt}
                                onChange={(e) => setPrompt(e.target.value)}
                                placeholder="Example: Generate banking transactions where 30% have invalid account numbers and 20% have amounts exceeding the daily limit of $10,000"
                                rows="6"
                                className="prompt-textarea"
                            />
                            <div className="prompt-examples">
                                <strong>Example prompts:</strong>
                                <ul>
                                    <li>"Make all email fields invalid with common typos"</li>
                                    <li>"Generate 50% records with postal codes from California only"</li>
                                    <li>"Create data where phone numbers are in incorrect format"</li>
                                </ul>
                            </div>
                        </div>
                    )}
                </div>

                <div className="modal-footer">
                    <button className="cancel-btn" onClick={onClose} disabled={loading}>
                        Cancel
                    </button>
                    <button
                        className="save-btn"
                        onClick={handleSave}
                        disabled={loading || (editMode === 'prompt' && !prompt.trim())}
                    >
                        {loading ? 'Regenerating...' : 'Save & Regenerate'}
                    </button>
                </div>
            </div>
        </div>
    );
}

export default GroupEditModal;
