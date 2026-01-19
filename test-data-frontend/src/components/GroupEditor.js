import React from 'react';
import './GroupEditor.css';

/**
 * GroupEditor Component
 */
function GroupEditor({ group, fields, onChange, onRemove }) {
    const handleFieldToggle = (fieldName, correctOrWrong) => {
        const correctFields = group.correct_fields || [];
        const wrongFields = group.wrong_fields || [];

        if (correctOrWrong === 'correct') {
            if (correctFields.includes(fieldName)) {
                onChange('correct_fields', correctFields.filter(f => f !== fieldName));
            } else {
                onChange('correct_fields', [...correctFields, fieldName]);
                onChange('wrong_fields', wrongFields.filter(f => f !== fieldName));
            }
        } else {
            if (wrongFields.includes(fieldName)) {
                onChange('wrong_fields', wrongFields.filter(f => f !== fieldName));
            } else {
                onChange('wrong_fields', [...wrongFields, fieldName]);
                onChange('correct_fields', correctFields.filter(f => f !== fieldName));
            }
        }
    };

    const isCorrect = (fieldName) => (group.correct_fields || []).includes(fieldName);
    const isWrong = (fieldName) => (group.wrong_fields || []).includes(fieldName);

    const handleWrongRuleChange = (fieldName, value) => {
        const rules = { ...(group.wrong_field_rules || {}) };
        if (value) {
            rules[fieldName] = value;
        } else {
            delete rules[fieldName];
        }
        onChange('wrong_field_rules', rules);
    };

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
        <div className="ge-container">
            <div className="ge-header">
                <input
                    type="text"
                    placeholder="Group Name (e.g., G1)"
                    value={group.name || ''}
                    onChange={(e) => onChange('name', e.target.value)}
                    className="ge-name-input"
                />
                <input
                    type="number"
                    min="1"
                    max="50"
                    placeholder="Count"
                    value={group.count || ''}
                    onChange={(e) => onChange('count', parseInt(e.target.value) || 0)}
                    className="ge-count-input"
                />
                {onRemove && (
                    <button type="button" onClick={onRemove} className="ge-remove-btn">
                        ✕
                    </button>
                )}
            </div>

            <div className="ge-quick-actions">
                <button type="button" onClick={markAllCorrect} className="ge-quick-btn ge-correct-btn">
                    ✓ All Correct
                </button>
                <button type="button" onClick={markAllWrong} className="ge-quick-btn ge-wrong-btn">
                    ✗ All Wrong
                </button>
                <button type="button" onClick={clearAll} className="ge-quick-btn ge-clear-btn">
                    Clear All
                </button>
            </div>

            <div className="ge-field-selection">
                <div className="ge-field-selection-header">
                    <span className="ge-h-field">Data Field</span>
                    <span className="ge-h-status">Condition</span>
                    <span className="ge-h-details">Validation / Error Rule</span>
                </div>
                {fields.map((field, idx) => {
                    const status = isCorrect(field.name) ? 'correct' : isWrong(field.name) ? 'wrong' : 'default';
                    return (
                        <div key={idx} className={`ge-field-row ge-status-${status}`}>
                            <div className="ge-field-info">
                                <span className="ge-field-icon">󱔗</span>
                                <span className="ge-field-name">{field.name}</span>
                            </div>

                            <div className="ge-status-picker">
                                <button
                                    className={`ge-status-btn ge-btn-correct ${status === 'correct' ? 'ge-active' : ''}`}
                                    onClick={() => handleFieldToggle(field.name, 'correct')}
                                    title="Mark as Correct"
                                >
                                    ✓
                                </button>
                                <button
                                    className={`ge-status-btn ge-btn-wrong ${status === 'wrong' ? 'ge-active' : ''}`}
                                    onClick={() => handleFieldToggle(field.name, 'wrong')}
                                    title="Mark as Wrong"
                                >
                                    ✗
                                </button>
                            </div>

                            <div className="ge-field-details">
                                {status === 'wrong' ? (
                                    <div className="ge-rule-container">
                                        <span className="ge-rule-prefix">Rule:</span>
                                        <input
                                            type="text"
                                            placeholder="e.g. out of range, invalid..."
                                            className="ge-wrong-rule-input"
                                            value={group.wrong_field_rules?.[field.name] || ''}
                                            onChange={e => handleWrongRuleChange(field.name, e.target.value)}
                                        />
                                    </div>
                                ) : (
                                    <span className="ge-valid-label">
                                        {status === 'correct' ? '✦ Explicitly valid' : '✧ System default'}
                                    </span>
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>

            <div className="ge-summary">
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
