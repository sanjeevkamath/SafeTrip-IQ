from transformers import BertTokenizer, BertModel
import pandas as pd
import torch
from datasets import load_dataset
from transformers import BertTokenizerFast, BertForSequenceClassification, Trainer, TrainingArguments


str = "level 3, re tr"
str.split(" ")[1][0]
dataset = load_dataset('csv', data_files={'train': 'train.csv', 'validation': 'val.csv'})

tokenizer = BertTokenizerFast.from_pretrained('bert-base-uncased')
def tokenize(batch):
    return tokenizer(batch['text'], padding='max_length', truncation=True, max_length=32)
tokenized = dataset.map(tokenize, batched=True)
tokenized = tokenized.remove_columns(['text'])
tokenized.set_format('torch')

model = BertForSequenceClassification.from_pretrained('bert-base-uncased', num_labels=2)

args = TrainingArguments(
    output_dir='./results',
    evaluation_strategy='epoch',
    per_device_train_batch_size=16,
    per_device_eval_batch_size=32,
    learning_rate=2e-5,
    num_train_epochs=3,
    weight_decay=0.01,
    report_to=None  
)

trainer = Trainer(
    model=model,
    args=args,
    train_dataset=tokenized['train'],
    eval_dataset=tokenized['validation']
)

trainer.train()
trainer.evaluate()