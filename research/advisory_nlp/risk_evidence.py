"""Cheap research topic baseline. Mentions are not severity or travel-safety scores."""
import re

LEXICONS = {
    'crime':r'crime|crimes|criminals?|robber\w*|theft|pickpocket\w*|rape|sexual assault|shooting|carjack\w*',
    'kidnapping':r'kidnap\w*|abduct\w*|hostage\w*|ransom|captors?',
    'terrorism':r'terror\w*|extremis\w*',
    'conflict_unrest':r'armed conflict|civil unrest|\bunrest\b|riots?|violent protests?|protests?|tear gas|water cannons|armed forces|military conflict|warfare',
    'health':r'health\w*|medic\w*|vaccin\w*|disease\w*|illness\w*|poison\w*|malaria|cholera|covid|hospital\w*|surgery',
    'natural_hazards':r'natural disasters?|earthquake\w*|flood\w*|hurricane\w*|tornado\w*|tsunami\w*|monsoon\w*|riptides?|rainfall|rainy season|extreme temperatures?|wildfires?|volcano\w*',
    'transport':r'traffic|road\w*|automobile|driv\w*|vehicles?|taxi\w*|buses|airspace|flights?|aviation|border crossing|land borders|rail\w*',
    'legal_restrictions':r'detention|arrest\w*|prison\w*|laws? on|illegal|prohibited|not allowed to leave|crossing is closed',
}
PATTERNS={category:re.compile(r'(?<!\w)(?:'+pattern+r')(?!\w)',re.I) for category,pattern in LEXICONS.items()}


def extract_topics(text, heading=None):
    body = [category for category,pattern in PATTERNS.items() if pattern.search(text)]
    context = [category for category,pattern in PATTERNS.items() if heading and pattern.search(heading)]
    return {'topics':sorted(set(body+context)), 'body_topics':sorted(body), 'heading_topics':sorted(context),
            'evidence_text':text, 'heading':heading,
            'review_flags':{'explicit_warning':bool(re.search(r'advise\w* against|do not travel|reconsider travel|exercise increased caution',text,re.I)),
                            'generic_reference':bool(re.search(r'visit .*reports|read .*guide|see where to get|take the same precautions',text,re.I)),
                            'negation_or_low_risk':bool(re.search(r'no reports|no recent|low risk|generally .*safe|not a major',text,re.I)),
                            'historical_date':bool(re.search(r'\b(?:19|20)\d{2}\b',text)),
                            'global_context':bool(heading and re.search(r'global travel|Middle East',heading,re.I))}}
