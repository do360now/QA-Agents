
start_gemma3:
	@which ollama > /dev/null 2>&1 || (echo "Error: ollama is not installed or not in PATH"; exit 1)
	ollama launch claude --model gemma3:4b

start_minimax:
	@which ollama > /dev/null 2>&1 || (echo "Error: ollama is not installed or not in Path"; exit 1)
	ollama launch claude --model minimax-m2.5:cloud