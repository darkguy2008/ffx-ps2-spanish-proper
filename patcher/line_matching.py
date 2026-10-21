import difflib

from ffx_text import CHOICE, code_tokens, is_character, tokens

LAYOUT = 0x07
MAJORITY = 2


def characters(line):
    return bytes(token[0] for _, token, _ in tokens(line, 0) if is_character(token))


def without_layout(line):
    return b''.join(token for _, token, prefixed in tokens(line, 0) if prefixed or token[0] != LAYOUT)


def exact_pairs(disc, english):
    pairs = []
    for key in (bytes, without_layout):
        matcher = difflib.SequenceMatcher(None, [key(line) for line in disc], [key(line) for line in english], autojunk=False)
        pairs += [(block.a + offset, block.b + offset) for block in matcher.get_matching_blocks() for offset in range(block.size)]
    return pairs


def reworded_pairs(disc, english, space):
    words = lambda line: characters(line).split(space)
    shared = lambda ours, theirs: sum(block.size for block in difflib.SequenceMatcher(None, ours, theirs, autojunk=False).get_matching_blocks())
    pairs = []
    for tag, disc_start, disc_end, english_start, english_end in difflib.SequenceMatcher(None, disc, english, autojunk=False).get_opcodes():
        if tag != 'replace' or disc_end - disc_start != english_end - english_start:
            continue
        for offset in range(disc_end - disc_start):
            ours, theirs = words(disc[disc_start + offset]), words(english[english_start + offset])
            if shared(ours, theirs) * MAJORITY > max(len(ours), len(theirs)):
                pairs.append((disc_start + offset, english_start + offset))
    return pairs


def glossary(sources):
    translations = {}
    for english, spanish in sources:
        for line, translation in zip(english, spanish):
            translations.setdefault(line, set()).add(translation)
    return {line: found.pop() for line, found in translations.items() if len(found) == 1}


def translated_lines(disc, sources, glossaries, space):
    has_text = lambda line: bool(characters(line).strip(space))
    choices = lambda line: len(code_tokens(line, 0, CHOICE))
    local = [(line, spanish[position], adapt) for english, spanish, adapt in sources
             for pairing in (exact_pairs(disc, english), reworded_pairs(disc, english, space)) for line, position in pairing]
    shared = [(line, translations[text], adapt) for translations, adapt in glossaries for line, text in enumerate(disc) if text in translations]
    blank_allowed = lambda candidate: True
    chosen = {}
    for accepted, matches in ((has_text, local), (blank_allowed, local), (has_text, shared)):
        for line, candidate, adapt in matches:
            if line not in chosen and has_text(disc[line]) and accepted(candidate) and choices(candidate) == choices(disc[line]):
                chosen[line] = adapt(candidate, disc[line])
    return chosen, [line for line, text in enumerate(disc) if line not in chosen and has_text(text)]
