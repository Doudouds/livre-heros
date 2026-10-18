"""Balises éditoriales : texte propre et profils vocaux, sans synthèse."""
from html import escape
import xml.etree.ElementTree as ET


def parse_markup(markup, profiles):
    if not isinstance(markup, str) or '<!' in markup or '<?' in markup:
        raise ValueError('Balisage vocal invalide : déclarations XML interdites.')
    try:
        root = ET.fromstring('<audio>'+markup+'</audio>')
    except ET.ParseError as exc:
        raise ValueError(f'Balise vocale mal fermée : {exc}') from exc
    spans, plain = [], [root.text or '']
    if (root.text or '').strip():
        raise ValueError('Toute parole doit être placée dans une balise <voix>.')
    for element in root:
        if element.tag != 'voix' or list(element) or set(element.attrib)-{'emotion','speaker'}:
            raise ValueError('Seule <voix emotion="…" speaker="…"> est acceptée, sans imbrication.')
        emotion = element.get('emotion')
        if emotion not in profiles:
            raise ValueError(f'Émotion inconnue : {emotion}')
        text, tail = element.text or '', element.tail or ''
        if not text.strip() or tail.strip():
            raise ValueError('Balise vide ou paroles situées hors des balises.')
        speaker = element.get('speaker','narrateur')
        if not speaker.strip():
            raise ValueError('Locuteur vide.')
        plain.extend((text,tail))
        spans.append(dict(text=text.strip(), speaker=speaker, emotion=emotion))
    if not spans:
        raise ValueError('Aucune balise vocale.')
    return ''.join(plain),spans


def render_markup(text, spans):
    """Conserver les espaces et paragraphes du texte d'origine à l'identique."""
    result, offset = [], 0
    for span in spans:
        value = span['text']
        position = text.find(value,offset)
        if position < 0 or text[offset:position].strip():
            raise ValueError('Les portions vocales ne recouvrent pas exactement le texte.')
        result.append(escape(text[offset:position],quote=False))
        result.append('<voix emotion="'+escape(span['emotion'],quote=True)+'" speaker="'
                      +escape(span.get('speaker','narrateur'),quote=True)+'">'
                      +escape(value,quote=False)+'</voix>')
        offset = position+len(value)
    if text[offset:].strip():
        raise ValueError('Fin du texte non balisée.')
    result.append(escape(text[offset:],quote=False))
    return ''.join(result)


def compile_book(book, profiles):
    """Refuser une différence entre les paroles du manuscrit et son balisage."""
    def compile_field(item, text_key, markup_key, spans_key):
        if markup_key not in item:
            raise ValueError(f'Balisage manquant : {markup_key} ({item.get("id",text_key)})')
        plain,spans = parse_markup(item[markup_key],profiles)
        if plain != item[text_key]:
            raise ValueError(f'Le balisage modifie le texte : {item.get("id",text_key)}')
        item[spans_key] = spans
    for scene in book['scenes']:
        if scene.get('values') or scene.get('variants') or scene.get('echoes'):
            raise ValueError('Ce format exige des textes explicites, sans fragments conditionnels non balisés.')
        compile_field(scene,'text','audio_markup','audio_spans')
        choices = scene.get('choices',[])
        if choices:
            question = scene.get('choice_question',book.get('choice_question','Que doit choisir Alex ?'))
            prompt = (question+' Choix 1 : '+choices[0]['text'].rstrip('.?!')
                      +'. Ou choix 2 : '+choices[1]['text'].rstrip('.?!')+'.')
            plain,spans = parse_markup(scene.get('choice_audio_markup',''),profiles)
            if plain != prompt:
                raise ValueError(f'Balisage des deux choix incorrect : {scene["id"]}')
            scene['choice_audio_spans'] = spans
        for choice in choices:
            if choice.get('consequence_variants'):
                raise ValueError('Les conséquences conditionnelles doivent être préparées explicitement.')
            compile_field(choice,'consequence','consequence_audio_markup','consequence_audio_spans')
    book['audio_tagged_version'] = 1
    return book
