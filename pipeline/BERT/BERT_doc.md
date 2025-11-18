## Training the model:

- To train the model, run sentiment.py
- This will save a model checkpoint to a new folder called result

## Using the trained model:

```python

# Load tokenizer and model using path to chekpoint
checkpoint_path = 'results/checkpoint-315'
tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
model = BertForSequenceClassification.from_pretrained(checkpoint_path)

# Put model in evaluation mode
model.eval()

# Your sentence to test
sentence = "This is my input sentence."

# Tokenize the input
inputs = tokenizer(sentence, return_tensors="pt", padding=True, truncation=True)

# Run through model
with torch.no_grad():  # Disable gradient calculation for inference
    outputs = model(**inputs)

# Get predictions
logits = outputs.logits
predicted_class = torch.argmax(logits, dim=1).item()

print(f"Predicted class: {predicted_class}")
```
