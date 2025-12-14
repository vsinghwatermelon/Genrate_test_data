import React from 'react';
import './GroupEditor.css';

/**
 * GroupEditor Component
 * 
 * Allows users to create and manage test data groups with field-level
 * correct/wrong configuration.
 * 
 * Props:
 * - group: Group object {name, count, correct_fields, wrong_fields}
 * - fields: Array of schema field objects [{name, type, ...}]
 * - onChange: Callback (key, value) when group properties change
 * - onRemove: Callback when remove button is clicked (null to hide button)
 */
function GroupEditor({ group, fields, onChange, onRemove }) {
    const handleFieldToggle = (fieldName, correctOrWrong) => {
        const correctFields = group.correct_fields || [];
        const wrongFields = group.wrong_fields || [];

        if (correctOrWrong === 'correct') {
            // Toggle correct field
            if (correctFields.includes(fieldName)) {
                // Remove from correct
                onChange('correct_fields', correctFields.filter(f => f !== fieldName));
            } else {
                // Add to correct, remove from wrong if present
                onChange('correct_fields', [...correctFields, fieldName]);
                onChange('wrong_fields', wrongFields.filter(f => f !== fieldName));
            }
        } else {
            // Toggle wrong field
            if (wrongFields.includes(fieldName)) {
                // Remove from wrong
                onChange('wrong_fields', wrongFields.filter(f => f !== fieldName));
            } else {
                // Add to wrong, remove from correct if present
                onChange('wrong_fields', [...wrongFields, fieldName]);
                onChange('correct_fields', correctFields.filter(f => f !== fieldName));
            }
        }
    };

    const isCorrect = (fieldName) => (group.correct_fields || []).includes(fieldName);
    const isWrong = (fieldName) => (group.wrong_fields || []).includes(fieldName);

    const markAllCorrect = () => {
        const allFieldNames = fields.map(f => f.name);
        onChange('correct_fields', allFieldNames);
        onChange('wrong_fields', []);
    };

    const markAllWrong = () => {
        const allFieldNames = fields.map(f => f.name);
        onChange('wrong_fields', allFieldNames);
        onChange('correct_fields', []);
    };

    const clearAll = () => {
        onChange('correct_fields', []);
        onChange('wrong_fields', []);
    };

    return (
        <div className="group-editor">
            <div className="group-header">
                <input
                    type="text"
                    placeholder="Group Name (e.g., G1)"
                    value={group.name || ''}
                    onChange={(e) => onChange('name', e.target.value)}
                    className="group-name-input"
                />
                <input
                    type="number"
                    min="1"
                    max="50"
                    placeholder="Count"
                    value={group.count || ''}
                    onChange={(e) => onChange('count', parseInt(e.target.value) || 0)}
                    className="group-count-input"
                />
                {onRemove && (
                    <button type="button" onClick={onRemove} className="remove-group-btn">
                        ✕
                    </button>
                )}
            </div>

            <div className="quick-actions">
                <button type="button" onClick={markAllCorrect} className="quick-btn correct-btn">
                    ✓ All Correct
                </button>
                <button type="button" onClick={markAllWrong} className="quick-btn wrong-btn">
                    ✗ All Wrong
                </button>
                <button type="button" onClick={clearAll} className="quick-btn clear-btn">
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
                                checked={isCorrect(field.name)}
                                onChange={() => handleFieldToggle(field.name, 'correct')}
                            />
                        </label>
                        <label className="checkbox-label">
                            <input
                                type="checkbox"
                                checked={isWrong(field.name)}
                                onChange={() => handleFieldToggle(field.name, 'wrong')}
                            />
                        </label>
                    </div>
                ))}
            </div>

            <div className="group-summary">
                <small>
                    {group.count || 0} records: 
                    {(group.correct_fields?.length || 0) > 0 && 
                        ` ${group.correct_fields.length} correct field(s)`}
                    {(group.wrong_fields?.length || 0) > 0 && 
                        `, ${group.wrong_fields.length} wrong field(s)`}
                    {(!group.correct_fields?.length && !group.wrong_fields?.length) && 
                        ' all fields valid'}
                </small>
            </div>
        </div>
    );
}

export default GroupEditor;
