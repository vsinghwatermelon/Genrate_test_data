import React from 'react';

// Basic SchemaEditor: editable table for schema fields
export default function SchemaEditor({ fields, onChange }) {
    // Handler for editing a field property
    const handleFieldChange = (idx, key, value) => {
        const updated = fields.map((f, i) => i === idx ? { ...f, [key]: value } : f);
        onChange(updated);
    };

    // Handler for removing a field
    const handleRemove = (idx) => {
        const updated = fields.filter((_, i) => i !== idx);
        onChange(updated);
    };

    return (
        <table style={{ width: '100%', background: '#fff', borderCollapse: 'collapse', marginBottom: 16 }}>
            <thead>
                <tr>
                    <th>Name</th>
                    <th>Type</th>
                    <th>Rules</th>
                    <th>Description</th>
                    <th>Example</th>
                    <th>Confidence</th>
                    <th></th>
                </tr>
            </thead>
            <tbody>
                {fields.map((field, idx) => (
                    <tr key={idx}>
                        <td><input value={field.name || ''} onChange={e => handleFieldChange(idx, 'name', e.target.value)} style={{ width: '100%' }} /></td>
                        <td><input value={field.type || ''} onChange={e => handleFieldChange(idx, 'type', e.target.value)} style={{ width: '100%' }} /></td>
                        <td><input value={typeof field.rules === 'string' ? field.rules : JSON.stringify(field.rules || {})} onChange={e => handleFieldChange(idx, 'rules', e.target.value)} style={{ width: '100%' }} /></td>
                        <td><input value={field.description || ''} onChange={e => handleFieldChange(idx, 'description', e.target.value)} style={{ width: '100%' }} /></td>
                        <td><input value={field.example || ''} onChange={e => handleFieldChange(idx, 'example', e.target.value)} style={{ width: '100%' }} /></td>
                        <td><input value={field.confidence || ''} onChange={e => handleFieldChange(idx, 'confidence', e.target.value)} style={{ width: '100%' }} /></td>
                        <td><button style={{ color: 'red' }} onClick={() => handleRemove(idx)}>✕</button></td>
                    </tr>
                ))}
            </tbody>
        </table>
    );
}
