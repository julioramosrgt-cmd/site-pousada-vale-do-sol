"""Base de raças caninas e felinas para classificação automática do porte do pet.
size: 'small' (<=10kg), 'medium' (10-25kg), 'large' (>25kg)
Fonte: padrões AKC/CBKC/FCI/American Cat Fanciers Association (referência veterinária resumida).
"""
import re
import unicodedata

DOG_BREEDS = {
    # Pequeno porte
    "yorkshire": "small", "yorkshire terrier": "small", "yorkie": "small",
    "shih tzu": "small", "shih-tzu": "small",
    "maltês": "small", "maltes": "small", "maltese": "small",
    "poodle toy": "small", "poodle micro": "small", "poodle miniatura": "small",
    "chihuahua": "small",
    "pinscher": "small", "pinscher miniatura": "small",
    "lhasa apso": "small", "lhasa": "small",
    "pug": "small",
    "spitz alemão": "small", "spitz alemao": "small", "lulu da pomerania": "small", "pomerania": "small", "pomeranian": "small",
    "cavalier king charles": "small", "king charles spaniel": "small",
    "papillon": "small",
    "bichon frise": "small", "bichon frisé": "small",
    "havanese": "small",
    "west highland white terrier": "small", "westie": "small",
    "cairn terrier": "small",
    "jack russell terrier": "small", "jack russell": "small",
    "beagle harrier": "small",
    "dachshund": "small", "dachshund miniatura": "small", "salsicha": "small", "teckel": "small",
    "shiba inu": "small",
    "boston terrier": "small",
    "french bulldog": "small", "bulldog frances": "small", "bulldog francês": "small",
    "schnauzer miniatura": "small",
    "cocker spaniel": "small",  # borderline; some consider medium
    "brussels griffon": "small",
    "coton de tulear": "small",
    "affenpinscher": "small",

    # Médio porte
    "beagle": "medium",
    "border collie": "medium",
    "bull terrier": "medium",
    "american staffordshire": "medium", "staffordshire bull terrier": "medium", "pitbull": "medium", "pit bull": "medium",
    "cocker": "medium",
    "basset hound": "medium",
    "buldogue inglês": "medium", "bulldog inglês": "medium", "english bulldog": "medium",
    "chow chow": "medium",
    "dalmata": "medium", "dálmata": "medium", "dalmatian": "medium",
    "shar pei": "medium", "shar-pei": "medium",
    "australian shepherd": "medium", "pastor australiano": "medium",
    "welsh corgi": "medium", "corgi": "medium",
    "schnauzer médio": "medium", "schnauzer": "medium",
    "vira lata": "medium", "vira-lata": "medium", "sem raça definida": "medium", "srd": "medium", "mestiço": "medium", "mestico": "medium",
    "whippet": "medium",
    "poodle standard": "medium",
    "brittany": "medium",
    "siberian husky pequeno": "medium",

    # Grande porte
    "labrador": "large", "labrador retriever": "large",
    "golden retriever": "large",
    "pastor alemão": "large", "pastor alemao": "large", "german shepherd": "large",
    "rottweiler": "large",
    "husky siberiano": "large", "siberian husky": "large", "husky": "large",
    "boxer": "large",
    "doberman": "large", "dobermann": "large",
    "akita": "large", "akita inu": "large",
    "malamute": "large", "alaskan malamute": "large",
    "são bernardo": "large", "sao bernardo": "large", "saint bernard": "large",
    "mastim": "large", "mastim inglês": "large", "mastiff": "large", "mastim tibetano": "large",
    "dogue alemão": "large", "dogue alemao": "large", "great dane": "large",
    "cane corso": "large",
    "fila brasileiro": "large",
    "dogo argentino": "large",
    "leonberger": "large",
    "terra nova": "large", "newfoundland": "large",
    "bernese": "large", "bernese mountain": "large", "boiadeiro bernês": "large",
    "weimaraner": "large",
    "rhodesian ridgeback": "large",
    "greyhound": "large", "galgo": "large",
}

CAT_BREEDS = {
    # Small (a maioria dos gatos é small — <=6kg)
    "siames": "small", "siamês": "small", "siamese": "small",
    "persa": "small", "persian": "small",
    "angora": "small", "angorá": "small", "turkish angora": "small",
    "sphynx": "small", "esfinge": "small",
    "bengal": "small", "bengalês": "small",
    "birmanês": "small", "birmanes": "small", "birman": "small",
    "british shorthair": "small",
    "scottish fold": "small",
    "ragdoll": "medium",
    "americano de pelo curto": "small", "american shorthair": "small",
    "russian blue": "small",
    "abissinio": "small", "abissínio": "small", "abyssinian": "small",
    "sagrado da birmania": "small",
    "srd felino": "small", "vira lata felino": "small",

    # Médio (raças felinas maiores)
    "maine coon": "medium",
    "norwegian forest": "medium", "gato da floresta da noruega": "medium",
    "savannah": "medium",
    "chausie": "medium",
    "siberiano": "medium", "siberian cat": "medium",
}

ALL_BREEDS = {**DOG_BREEDS, **CAT_BREEDS}


def _normalize(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = s.replace("-", " ")
    return s


def classify_breed(breed: str, pet_type: str = "") -> tuple[str, bool]:
    """Return (size, matched). size is one of small/medium/large. matched=False means fallback to 'medium'."""
    key = _normalize(breed)
    if not key:
        return ("medium", False)

    # Exact match
    if key in ALL_BREEDS:
        return (ALL_BREEDS[key], True)

    # Substring match: check longest key first
    for k in sorted(ALL_BREEDS.keys(), key=len, reverse=True):
        if k in key or key in k:
            return (ALL_BREEDS[k], True)

    # Type-based fallback: cats default to small, dogs default to medium
    if _normalize(pet_type) in ("gato", "gata", "cat", "felino"):
        return ("small", False)
    return ("medium", False)
