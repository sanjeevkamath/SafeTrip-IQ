from transformers import BertTokenizer, BertModel

tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')

# Load a pre-trained BERT model
model = BertModel.from_pretrained('bert-base-uncased')

text = "Hello, how are you doing today?"
encoded_input = tokenizer(text, return_tensors='pt', padding=True, truncation=True)

outputs = model(**encoded_input)
last_hidden_states = outputs.last_hidden_state
pooled_output = outputs.pooler_output