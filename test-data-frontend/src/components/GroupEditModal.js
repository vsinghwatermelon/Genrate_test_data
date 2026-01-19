import React, { useState, useEffect } from 'react';
import './GroupEditModal.css';

/**
 * GroupEditModal Component
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
        const updatedGroup = {
            ...group,
            name: group.group_name,
            count: recordCount,
            correct_fields: correctFields,
            wrong_fields: wrongFields,
            wrong_field_rules: wrongFieldRules
        };
        onSave(editMode, updatedGroup, prompt);
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
        <div className="gem-overlay" onClick={onClose}>
            <div className="gem-content" onClick={(e) => e.stopPropagation()}>
                <div className="gem-header">
                    <h2>Edit Group: {group.group_name}</h2>
                    <button className="gem-close" onClick={onClose}>&times;</button>
                </div>

                <div className="gem-body">
                    <div className="gem-info-banner">
                        ℹ️ You are editing only <strong>{group.group_name}</strong>'s data.
                    </div>

                    <div className="gem-mode-selector">
                        <button
                            className={`gem-mode-btn ${editMode === 'manual' ? 'gem-active' : ''}`}
                            onClick={() => setEditMode('manual')}
                        >
                            ✏️ Manual Edit
                        </button>
                        <button
                            className={`gem-mode-btn ${editMode === 'prompt' ? 'gem-active' : ''}`}
                            onClick={() => setEditMode('prompt')}
                        >
                            🤖 Prompt-Based
                        </button>
                    </div>

                    <div className="gem-form-group">
                        <label>
                            Number of Records:
                            <input
                                type="number"
                                min="1"
                                max="50"
                                value={recordCount}
                                onChange={(e) => setRecordCount(parseInt(e.target.value) || 1)}
                                className="gem-record-count-input"
                            />
                        </label>
                    </div>

                    {editMode === 'manual' ? (
                        <div className="gem-manual-section">
                            <div className="gem-quick-actions">
                                <button onClick={markAllCorrect} className="gem-quick-btn gem-correct-btn">
                                    ✓ All Correct
                                </button>
                                <button onClick={markAllWrong} className="gem-quick-btn gem-wrong-btn">
                                    ✗ All Wrong
                                </button>
                                <button onClick={clearAll} className="gem-quick-btn gem-clear-btn">
                                    Clear All
                                </button>
                            </div>

                            <div className="gem-field-selection">
                                <div className="gem-field-selection-header">
                                    <span className="gem-h-field">Data Field</span>
                                    <span className="gem-h-status">Condition</span>
                                    <span className="gem-h-details">Validation / Error Rule</span>
                                </div>
                                {fields.map((field, idx) => {
                                    const status = correctFields.includes(field.name) ? 'correct' : wrongFields.includes(field.name) ? 'wrong' : 'default';
                                    return (
                                        <div key={idx} className={`gem-field-row gem-status-${status}`}>
                                            <div className="gem-field-info">
                                                <span className="gem-field-icon">󱔗</span>
                                                <span className="gem-field-name">{field.name}</span>
                                            </div>

                                            <div className="gem-status-picker">
                                                <button
                                                    className={`gem-status-btn gem-btn-correct ${status === 'correct' ? 'gem-active' : ''}`}
                                                    onClick={() => handleFieldToggle(field.name, 'correct')}
                                                    title="Mark as Correct"
                                                >
                                                    ✓
                                                </button>
                                                <button
                                                    className={`gem-status-btn gem-btn-wrong ${status === 'wrong' ? 'gem-active' : ''}`}
                                                    onClick={() => handleFieldToggle(field.name, 'wrong')}
                                                    title="Mark as Wrong"
                                                >
                                                    ✗
                                                </button>
                                            </div>

                                            <div className="gem-field-details">
                                                {status === 'wrong' ? (
                                                    <div className="gem-rule-container">
                                                        <span className="gem-rule-prefix">Rule:</span>
                                                        <input
                                                            type="text"
                                                            placeholder="e.g. invalid, empty..."
                                                            className="gem-wrong-rule-input"
                                                            value={wrongFieldRules[field.name] || ''}
                                                            onChange={e => handleWrongRuleChange(field.name, e.target.value)}
                                                        />
                                                    </div>
                                                ) : (
                                                    <span className="gem-valid-label">
                                                        {status === 'correct' ? '✦ Explicitly valid' : '✧ System default'}
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    ) : (
                        <div className="gem-prompt-section">
                            <textarea
                                value={prompt}
                                onChange={(e) => setPrompt(e.target.value)}
                                placeholder="Example: Generate banking transactions where 30% have invalid account numbers..."
                                rows="6"
                                className="gem-prompt-textarea"
                            />
                        </div>
                    )}
                </div>

                <div className="gem-footer">
                    <button className="gem-cancel-btn" onClick={onClose} disabled={loading}>
                        Cancel
                    </button>
                    <button
                        className="gem-save-btn"
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
