import React, { useMemo } from 'react';
import allDataTypes from '../data/allDataTypes';
import { generateSample } from '../utils/generators';
import './FieldEditor.css';

export default function FieldEditor({
    field,
    onChange,
    onRemove,
    openTypeModal
}) {
    // Ensure rules is always a string for display
    let rulesString = '';
    if (typeof field.rules === 'string') {
        rulesString = field.rules;
    } else if (Array.isArray(field.rules)) {
        rulesString = field.rules.join('; ');
    } else if (field.rules && typeof field.rules === 'object') {
        rulesString = JSON.stringify(field.rules);
    }

    // Handle type change
    const handleTypeChange = (newType) => {
        onChange('type', newType);
    };

    // Generate preview sample
    const preview = useMemo(() => {
        try {
            return generateSample(field);
        } catch (e) {
            return 'N/A';
        }
    }, [field]);

    return (
        <div className="field-editor">
            <input
                type="text"
                className="fe-name"
                placeholder="Field Name"
                value={field.name || ''}
                onChange={(e) => onChange('name', e.target.value)}
                required
            />

            <div className="fe-type-wrap">
                <select
                    className="fe-type"
                    value={field.type || 'string'}
                    onChange={(e) => handleTypeChange(e.target.value)}
                >
                    <optgroup label="Common types">
                        <option value="string">String</option>
                        <option value="integer">Integer</option>
                        <option value="float">Float</option>
                        <option value="boolean">Boolean</option>
                        <option value="email">Email</option>
                        <option value="phone">Phone</option>
                        <option value="date">Date</option>
                        <option value="combobox">Combobox</option>
                        <option value="radio">Radio</option>
                        <option value="checkbox">Checkbox</option>
                        <option value="select">Select</option>
                    </optgroup>
                    <optgroup label="All types">
                        {allDataTypes.map(t => (
                            <option key={t.id} value={t.id}>{t.name}</option>
                        ))}
                    </optgroup>
                </select>
                {openTypeModal && (
                    <button type="button" className="fe-choose" onClick={openTypeModal}>
                        Choose...
                    </button>
                )}
            </div>

            <input
                type="text"
                className="fe-rules"
                placeholder="Rules"
                value={rulesString}
                onChange={(e) => onChange('rules', e.target.value)}
            />

            <input
                type="text"
                className="fe-example"
                placeholder="Example"
                value={field.example || ''}
                onChange={(e) => onChange('example', e.target.value)}
            />

            <div className="fe-preview">
                <code>{preview}</code>
            </div>

            {onRemove && (
                <button type="button" className="fe-remove" onClick={onRemove}>
                    ✕
                </button>
            )}
        </div>
    );
}
