# Test Data Generator - Frontend

Simple React app to interact with the Test Data Generator API.

## Running the Application

### 1. Start the Backend API (in one terminal)
```bash
cd /Users/vinayak/Desktop/Watermelon/TestData
source myenv/bin/activate
. .\.venv\Scripts\Activate.ps1
deactivate
python -m uvicorn main:app --reload
```

The API will run on http://localhost:8000

### 2. Start the Frontend (in another terminal)
```bash
cd /Users/vinayak/Desktop/Watermelon/TestData/test-data-frontend
npm start
```
# use webdriver-manager to automatically install & use chromedriver
```bash
python frontend_analyzer.py --url 'https://leetcode.com/accounts/signup/?next=%2Fproblemset%2F' --chromedriver auto --output report.json
```

The frontend will run on http://localhost:3000

## How to Use

1. **Add Fields**: Click "+ Add Field" to add more schema fields
2. **Configure Each Field**:
   - Field Name: Name of the field
   - Type: Select data type (string, integer, email, etc.)
   - Rules: Optional constraints (e.g., "Between 18 and 65")
   - Example: Optional example value
3. **Set Number of Records**: How many test records to generate
4. **Add Additional Rules**: Optional extra context
5. **Click "Generate Data"**: View the generated JSON data below

## Example

- Field Name: `username`, Type: `string`, Rules: `5-15 characters`
- Field Name: `email`, Type: `email`
- Field Name: `age`, Type: `integer`, Rules: `Between 18 and 65`
- Number of Records: `5`

Click "Generate Data" and see the results!
