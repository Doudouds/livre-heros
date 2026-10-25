"""Consignes de prononciation explicites ; le texte contrôlé par l'ASR reste canonique."""
import re
from pathlib import Path

from .tts_batch import file_hash


def validate_pronunciations(rules, text=None):
    if not isinstance(rules,list):
        raise ValueError('Les prononciations doivent être une liste explicite.')
    seen = set()
    for rule in rules:
        if not isinstance(rule,dict) or set(rule) != {'written','spoken'}:
            raise ValueError('Une prononciation exige written et spoken.')
        written,spoken = rule['written'],rule['spoken']
        if any(not isinstance(value,str) or not value.strip() or value != value.strip()
               or any(char in value for char in '<>\n\r') for value in (written,spoken)):
            raise ValueError('Prononciation vide ou invalide.')
        if written in seen or (text is not None and not re.search(r'(?<!\w)'+re.escape(written)+r'(?!\w)',text)):
            raise ValueError('Prononciation répétée ou absente du texte.')
        seen.add(written)
    return rules


def pronunciation_identity(rules):
    validate_pronunciations(rules)
    return dict(rules=rules,adapter_source_sha256=file_hash(Path(__file__)))


def synthesis_text(text, rules):
    validate_pronunciations(rules)
    replacements = {r['written']:r['spoken'] for r in rules}
    if not replacements:
        return text
    pattern = r'(?<!\w)(?:'+'|'.join(re.escape(word) for word in sorted(replacements,key=len,reverse=True))+r')(?!\w)'
    return re.sub(pattern,lambda match:replacements[match.group()],text)


class PronouncingBackend:
    def __init__(self, delegate, rules):
        self.delegate,self.rules = delegate,rules

    def synthesize(self, text, seed):
        return self.delegate.synthesize(synthesis_text(text,self.rules),seed)
