# Groq API Integration Guide

## Overview

The Test Data Generator now supports two AI model providers:
1. **Local Ollama** - Run models locally on your machine (llama3:latest)
2. **Groq API** - Use cloud-based models via Groq API (faster, no local GPU required)

## Features

- **Seamless Switching**: Toggle between Ollama and Groq with a simple radio button in the UI
- **Same Functionality**: All generation modes work with both providers:
  - Single table generation
  - Full database generation (manual & intelligent mode)
  - Natural language database generation
  - Selenium script parsing

## Setup Instructions

### 1. Install Required Packages

```bash
pip install groq python-dotenv requests
```

### 2. Configure Environment Variables

Create or update `.env` file in the project root:

```env
groq_api_key=your_groq_api_key_here
model=openai/gpt-oss-20b
```

**Get your Groq API key:**
- Visit [https://console.groq.com/](https://console.groq.com/)
- Sign up for a free account
- Generate an API key
- Copy the key to your `.env` file

### 3. Start the Backend

```bash
python -m uvicorn main:app --reload
```

The backend will be available at `http://localhost:8000`

### 4. Start the Frontend

```bash
cd test-data-frontend
npm start
```

The frontend will be available at `http://localhost:3000`

## Using the Model Selection

1. Open the application in your browser
2. At the top of the page, you'll see "🤖 AI Model:" with two options:
   - **Local Ollama (llama3:latest)** - Uses your local Ollama installation
   - **Groq API (Cloud)** - Uses Groq's cloud API
3. Select your preferred model provider
4. Generate data as usual - the selected model will be used automatically

## Architecture

### Backend Changes

**New Module: `llm_factory.py`**
- `LLMFactory` class provides unified interface for both providers
- `GroqWrapper` class wraps Groq API to match OllamaLLM interface
- Automatic API key loading from `.env`

**Updated Modules:**
- `data_generator.py` - Accepts `provider` parameter
- `db_generator.py` - Passes provider to generators
- `intelligent_db_generator.py` - All agents support provider selection
- `nl_db_generator.py` - Natural language agents support provider selection
- `selenium_llm_parser.py` - Parser supports provider selection
- `main.py` - All endpoints accept `model_provider` parameter

### Frontend Changes

**App.js:**
- Added `modelProvider` state variable
- Radio buttons for provider selection
- All API calls include `model_provider` in request body

**App.css:**
- Styled `.model-provider-selector` component

## Groq API Benefits

- **Faster Generation**: Cloud GPUs provide faster inference
- **No Local Setup**: No need to install Ollama or download large models
- **Consistent Performance**: Cloud infrastructure ensures reliable performance
- **Multiple Models**: Easy to switch between different Groq models

## Local Ollama Benefits

- **Privacy**: All data stays on your machine
- **No API Costs**: Free to use (after initial model download)
- **Offline Capability**: Works without internet connection
- **Customization**: Can use any Ollama-compatible model

## Troubleshooting

### Groq API Key Not Found
- Ensure `.env` file exists in project root
- Check that `groq_api_key` is set correctly (no quotes)
- Restart the backend server after updating `.env`

### Ollama Connection Failed
- Make sure Ollama is installed and running
- Check that `llama3:latest` model is pulled: `ollama pull llama3:latest`
- Verify Ollama is accessible at `http://localhost:11434`

### Module Import Errors
- Ensure all packages are installed: `pip install -r requirements.txt`
- Check that you're in the correct Python environment

## Example Usage

### Single Table with Groq API
1. Select "Groq API (Cloud)" radio button
2. Add fields for your table
3. Click "Generate Data"
4. Data will be generated using Groq's cloud API

### Database with Local Ollama
1. Select "Local Ollama (llama3:latest)" radio button
2. Configure your database schema
3. Click "Generate Database"
4. Data will be generated using your local Ollama model

## Model Comparison

| Feature | Local Ollama | Groq API |
|---------|-------------|----------|
| Speed | Depends on hardware | Very fast |
| Cost | Free | Free tier available |
| Privacy | High (local) | Data sent to cloud |
| Setup | Requires Ollama | Requires API key |
| Offline | Yes | No |
| GPU Required | Recommended | No |

## Configuration

### Changing Groq Model

Update `.env` file:
```env
model=llama-3.1-70b-versatile
```

Available Groq models:
- `openai/gpt-oss-20b` (default)
- `llama-3.1-70b-versatile`
- `mixtral-8x7b-32768`
- And more...

### Changing Ollama Model

Update the code in `llm_factory.py` or pass model name:
```python
generator = TestDataGenerator(provider="ollama", model_name="mistral:latest")
```

## Support

For issues or questions:
1. Check this documentation
2. Review error messages in browser console and terminal
3. Verify `.env` configuration
4. Ensure all dependencies are installed
