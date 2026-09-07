#!/usr/bin/env python3
import json,re,sys
rules=[('email',re.compile(r'[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}',re.I),'[EMAIL]'),('phone',re.compile(r'(?<!\d)(?:\+?\d[\d ().-]{7,}\d)(?!\d)'),'[PHONE]'),('ipv4',re.compile(r'(?<![\w])(?:\d{1,3}\.){3}\d{1,3}(?![\w])'),'[IP ADDRESS]'),('credit_card',re.compile(r'(?<!\d)(?:\d[ -]?){13,19}(?!\d)'),'[CARD]'),('token',re.compile(r'(?<![\w])[A-Za-z0-9_-]{24,}(?![\w])'),'[TOKEN]')]
text=sys.stdin.read(); counts={}; out=text
for name,pattern,replacement in rules:
    out,n=pattern.subn(replacement,out); counts[name]=n
print(json.dumps({'redacted_text':out,'counts':counts,'total':sum(counts.values())},ensure_ascii=False))
