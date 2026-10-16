"""Frozen public English injection classifier. No remote code or training."""
import time
from pathlib import Path

class Detector:
    def __init__(self,path,threshold=0.5):
        import torch
        from transformers import AutoTokenizer,AutoModelForSequenceClassification
        torch.set_num_threads(2)
        self.torch=torch
        self.tokenizer=AutoTokenizer.from_pretrained(str(path),local_files_only=True)
        self.model=AutoModelForSequenceClassification.from_pretrained(str(path),local_files_only=True,use_safetensors=True).eval()
        self.threshold=threshold
        self.labels=self.model.config.id2label
        self.injection_id=next(int(k) for k,v in self.labels.items() if v.lower() in ('injection','injection-detected','label_1'))
    def score(self,text):
        start=time.monotonic()
        # Scan all text using overlapping windows; do not silently truncate attacks.
        ids=self.tokenizer.encode(text,add_special_tokens=False)
        scores=[]
        for i in range(0,max(1,len(ids)),384):
            batch=self.tokenizer.prepare_for_model(ids[i:i+480],return_tensors='pt',truncation=True,max_length=512)
            batch={k:(v.unsqueeze(0) if v.ndim==1 else v) for k,v in batch.items()}
            with self.torch.inference_mode():
                score=self.model(**batch).logits.softmax(-1)[0,self.injection_id].item()
            scores.append(score)
            if i+480>=len(ids):break
        p=max(scores)
        return {'score':p,'blocked':p>=self.threshold,'seconds':time.monotonic()-start,'windows':len(scores)}
