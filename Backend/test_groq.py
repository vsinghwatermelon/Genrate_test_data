"""
Quick test script to verify Groq integration works
"""

from llm_factory import LLMFactory

def test_ollama():
    print("Testing Ollama...")
    try:
        llm = LLMFactory.create_llm(provider="ollama", model_name="llama3:latest")
        response = llm.invoke("Say hello in one sentence")
        print(f"✓ Ollama response: {response[:100]}")
    except Exception as e:
        print(f"✗ Ollama failed: {e}")

def test_groq():
    print("\nTesting Groq API...")
    try:
        llm = LLMFactory.create_llm(provider="groq")
        response = llm.invoke("Say hello in one sentence")
        print(f"✓ Groq response: {response[:100]}")
    except Exception as e:
        print(f"✗ Groq failed: {e}")

if __name__ == "__main__":
    test_ollama()
    test_groq()
    print("\n✅ Tests completed!")
