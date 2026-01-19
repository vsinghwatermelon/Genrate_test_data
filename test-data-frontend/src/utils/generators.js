// Simple sample value generators for common types. These are deterministic-ish
// and intended for preview only. For production you'd use more robust libs.
import allDataTypes from '../data/allDataTypes';

const randomInt = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min;

export function generateSample(typeId) {
    if (!typeId) return '';

    // try to find the declared type in allDataTypes
    const t = allDataTypes.find(x => x.id === typeId || x.name === typeId);
    if (t && t.example) return t.example;

    switch (typeId) {
        case 'first_name': return ['Aarav', 'Neha', 'Rohan', 'Priya'][randomInt(0, 3)];
        case 'last_name': return ['Sharma', 'Patel', 'Kumar', 'Singh'][randomInt(0, 3)];
        case 'full_name': return `${generateSample('first_name')} ${generateSample('last_name')}`;
        case 'email': return `user${randomInt(100, 999)}@example.com`;
        case 'phone': return `+91-${randomInt(7000000000, 9999999999)}`;
        case 'gender': return ['Male', 'Female', 'Other'][randomInt(0, 2)];
        case 'dob': return `19${randomInt(70, 99)}-${String(randomInt(1, 12)).padStart(2, '0')}-${String(randomInt(1, 28)).padStart(2, '0')}`;
        case 'address_line1': return `${randomInt(1, 999)} MG Road`;
        case 'city': return ['Mumbai', 'Bengaluru', 'Delhi', 'Kolkata'][randomInt(0, 3)];
        case 'state': return ['Karnataka', 'Maharashtra', 'Delhi', 'West Bengal'][randomInt(0, 3)];
        case 'postal_code': return String(560000 + randomInt(0, 999));
        case 'country': return 'IN';
        case 'latitude': return (12.9716 + Math.random() * 0.1).toFixed(6);
        case 'longitude': return (77.5946 + Math.random() * 0.1).toFixed(6);
        case 'bank_name': return ['HDFC Bank', 'State Bank of India', 'ICICI Bank'][randomInt(0, 2)];
        case 'account_number': return String(randomInt(100000000, 999999999)) + String(randomInt(1000, 9999));
        case 'ifsc': return 'SBIN000' + String(randomInt(100, 999));
        case 'pan': return 'ABCDE' + String(randomInt(1000, 9999)) + 'F';
        case 'iban': return 'GB29NWBK60161331926819';
        case 'swift_bic': return 'HDFCINBBXXX';
        case 'routing_number': return String(randomInt(100000000, 999999999));
        case 'credit_card_number': return '4111 1111 1111 1111';
        case 'credit_card_expiry': return `${String(randomInt(1, 12)).padStart(2, '0')}/${String(randomInt(24, 30))}`;
        case 'cvv': return String(randomInt(100, 999));
        case 'transaction_id': return `TXN-${new Date().getFullYear()}-${randomInt(1000, 9999)}`;
        case 'price': return (Math.random() * 1000).toFixed(2);
        case 'uuid': return '3fa85f64-5717-4562-b3fc-2c963f66afa6';
        case 'ip_v4': return `192.168.${randomInt(0, 255)}.${randomInt(1, 254)}`;
        case 'ip_v6': return '2001:0db8:85a3:0000:0000:8a2e:0370:7334';
        case 'mac_address': return '00:1B:44:11:3A:B7';
        case 'url': return `https://example.com/${randomInt(1, 999)}`;
        case 'hex_color': return ['#ff5733', '#33aaff', '#bada55'][randomInt(0, 2)];
        case 'boolean': return Math.random() > 0.5 ? 'true' : 'false';
        case 'integer': return String(randomInt(0, 9999));
        case 'float': return (Math.random() * 100).toFixed(4);
        default:
            // fallback: return the declared example if any, else empty
            return (t && t.example) || '';
    }
}

export default generateSample;
