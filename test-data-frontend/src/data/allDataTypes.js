const allDataTypes = [
    // Personal / Identity
    { id: 'first_name', name: 'First Name', category: 'Personal', description: 'Common given names.', example: 'Aarav' },
    { id: 'last_name', name: 'Last Name', category: 'Personal', description: 'Common family names.', example: 'Sharma' },
    { id: 'full_name', name: 'Full Name', category: 'Personal', description: 'Concatenated first and last name.', example: 'Aarav Sharma' },
    { id: 'email', name: 'Email Address', category: 'Personal', description: 'Random realistic email addresses.', example: 'aarav.sharma@example.com' },
    { id: 'phone', name: 'Phone Number', category: 'Personal', description: 'Local-format phone numbers with country code variants.', example: '+91-9876543210' },
    { id: 'gender', name: 'Gender', category: 'Personal', description: 'Gender value (Male/Female/Other).', example: 'Male' },
    { id: 'dob', name: 'Date of Birth', category: 'Personal', description: 'Birth date in YYYY-MM-DD format.', example: '1990-05-14' },

    // Address / Location
    { id: 'address_line1', name: 'Address Line 1', category: 'Location', description: 'Street address or PO box.', example: '221B Baker Street' },
    { id: 'address_line2', name: 'Address Line 2', category: 'Location', description: 'Apartment, suite, unit, building, floor, etc.', example: 'Apt 5' },
    { id: 'city', name: 'City', category: 'Location', description: 'City names.', example: 'Mumbai' },
    { id: 'state', name: 'State / Province', category: 'Location', description: 'State, province or region name.', example: 'Karnataka' },
    { id: 'postal_code', name: 'Postal Code / ZIP', category: 'Location', description: 'Postal code / zip code for region.', example: '560001' },
    { id: 'country', name: 'Country', category: 'Location', description: 'Country names or ISO codes.', example: 'IN' },
    { id: 'latitude', name: 'Latitude', category: 'Location', description: 'Latitude coordinate.', example: '12.9716' },
    { id: 'longitude', name: 'Longitude', category: 'Location', description: 'Longitude coordinate.', example: '77.5946' },

    // Finance / Banking (expanded)
    { id: 'bank_name', name: 'Bank Name', category: 'Finance', description: 'Popular bank names.', example: 'HDFC Bank' },
    { id: 'account_number', name: 'Bank Account Number', category: 'Finance', description: 'Numeric bank account number.', example: '012345678901', defaultRule: 'digits, length 9-18' },
    { id: 'ifsc', name: 'IFSC Code (India)', category: 'Finance', description: '11-character Indian IFSC code.', example: 'SBIN0000456', defaultRule: '^[A-Z]{4}0[A-Z0-9]{6}$' },
    { id: 'pan', name: 'PAN Number (India)', category: 'Finance', description: '10-character PAN format.', example: 'ABCDE1234F', defaultRule: '[A-Z]{3}[A-Z][A-Z][0-9]{4}[A-Z]' },
    { id: 'iban', name: 'IBAN', category: 'Finance', description: 'International Bank Account Number.', example: 'GB29NWBK60161331926819' },
    { id: 'swift_bic', name: 'SWIFT/BIC', category: 'Finance', description: 'SWIFT/BIC code (8 or 11 chars).', example: 'HDFCINBBXXX' },
    { id: 'routing_number', name: 'Routing Number (ABA)', category: 'Finance', description: 'US routing number (9 digits).', example: '011000138', defaultRule: '^[0-9]{9}$' },
    { id: 'credit_card_number', name: 'Credit Card Number', category: 'Finance', description: 'Valid-looking credit card numbers (Luhn).', example: '4111 1111 1111 1111' },
    { id: 'credit_card_expiry', name: 'Card Expiry', category: 'Finance', description: 'MM/YY expiry date.', example: '09/28' },
    { id: 'cvv', name: 'CVV', category: 'Finance', description: '3- or 4-digit card security code.', example: '123' },
    { id: 'transaction_id', name: 'Transaction ID', category: 'Finance', description: 'Random transaction identifier.', example: 'TXN-20251105-0001' },
    { id: 'transaction_amount', name: 'Transaction Amount', category: 'Finance', description: 'Monetary amount with currency.', example: '1250.75' },

    // Commerce / Orders / Products
    { id: 'product_name', name: 'Product Name', category: 'Commerce', description: 'Common product names.', example: 'Acme Running Shoes' },
    { id: 'sku', name: 'SKU', category: 'Commerce', description: 'Stock keeping unit identifiers.', example: 'ACME-RT-001' },
    { id: 'price', name: 'Price', category: 'Commerce', description: 'Product price (decimal).', example: '49.99' },
    { id: 'order_id', name: 'Order ID', category: 'Commerce', description: 'Order identifiers.', example: 'ORD-1000123' },
    { id: 'order_status', name: 'Order Status', category: 'Commerce', description: 'Order lifecycle status.', example: 'shipped' },

    // Company / Job
    { id: 'company_name', name: 'Company', category: 'Company', description: 'Company or organization names.', example: 'Acme Corp' },
    { id: 'job_title', name: 'Job Title', category: 'Company', description: 'Employee job titles.', example: 'Senior Software Engineer' },
    { id: 'department', name: 'Department', category: 'Company', description: 'Department name.', example: 'Engineering' },
    { id: 'salary', name: 'Salary', category: 'Company', description: 'Salary amount.', example: '120000' },

    // Identifiers / Codes
    { id: 'uuid', name: 'UUID', category: 'Identifiers', description: 'Random UUID v4.', example: '3fa85f64-5717-4562-b3fc-2c963f66afa6' },
    { id: 'ssn', name: 'SSN (US)', category: 'Identifiers', description: 'US Social Security Number format.', example: '123-45-6789' },
    { id: 'passport', name: 'Passport Number', category: 'Identifiers', description: 'Passport number format (varies by country).', example: 'M0123456' },
    { id: 'isbn', name: 'ISBN', category: 'Identifiers', description: 'Book ISBN (10 or 13 digits).', example: '9780306406157' },

    // IT / Network
    { id: 'ip_v4', name: 'IP Address v4', category: 'IT', description: 'IPv4 address.', example: '192.168.1.100' },
    { id: 'ip_v6', name: 'IP Address v6', category: 'IT', description: 'IPv6 address.', example: '2001:0db8:85a3:0000:0000:8a2e:0370:7334' },
    { id: 'mac_address', name: 'MAC Address', category: 'IT', description: 'MAC addresses.', example: '00:1B:44:11:3A:B7' },
    { id: 'url', name: 'URL', category: 'IT', description: 'Random URLs.', example: 'https://example.com/product/1' },

    // Text / Content
    { id: 'lorem_word', name: 'Lorem Word', category: 'Text', description: 'Random lorem ipsum words.', example: 'lorem' },
    { id: 'lorem_sentence', name: 'Lorem Sentence', category: 'Text', description: 'Random lorem ipsum sentence.', example: 'Lorem ipsum dolor sit amet.' },
    { id: 'paragraph', name: 'Paragraph', category: 'Text', description: 'Multi-sentence paragraph.', example: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit.' },

    // Health / Medical
    { id: 'medical_record', name: 'Medical Record Number', category: 'Health', description: 'Hospital medical record numbers.', example: 'MRN-2025-00123' },
    { id: 'icd_code', name: 'Diagnosis Code (ICD)', category: 'Health', description: 'ICD-10 style codes.', example: 'I10' },

    // Travel / Transport
    { id: 'flight_number', name: 'Flight Number', category: 'Travel', description: 'Airline flight numbers.', example: 'AI-101' },
    { id: 'airline_code', name: 'Airline Code', category: 'Travel', description: 'IATA airline code.', example: 'AI' },
    { id: 'tracking_number', name: 'Tracking Number', category: 'Logistics', description: 'Parcel tracking codes.', example: '1Z9999W99999999999' },

    // Misc / Utility
    { id: 'hex_color', name: 'Hex Color', category: 'Misc', description: 'Hexadecimal color code.', example: '#ff5733' },
    { id: 'boolean', name: 'Boolean', category: 'Misc', description: 'True/False value.', example: 'true' },
    { id: 'integer', name: 'Integer', category: 'Misc', description: 'Integer number.', example: '42' },
    { id: 'float', name: 'Float', category: 'Misc', description: 'Floating point number.', example: '3.1415' },
    { id: 'select', name: 'Dropdown (Select)', category: 'Form', description: 'One option from a list.', example: 'Option A' },
    { id: 'radio', name: 'Radio Button', category: 'Form', description: 'Single selection from a group.', example: 'Yes' },
    { id: 'checkbox', name: 'Checkbox', category: 'Form', description: 'Multiple selection or boolean.', example: 'Checked' }
];

export default allDataTypes;
