"""Generates backend/eval/fixtures/sample.pdf: a small, original, multi-page
PDF summarizing well-known scenes from Alice's Adventures in Wonderland
(public domain, published 1865). Paraphrased rather than quoted verbatim, so
this is original text describing public-domain scenes -- safe to commit and
redistribute with the repo.

Re-run with: python backend/eval/make_fixture.py
"""

from pathlib import Path

import fitz

PAGES = [
    "Alice sits on the riverbank with her sister on a warm afternoon, growing "
    "drowsy, when a White Rabbit runs past. The rabbit wears a waistcoat, "
    "checks a pocket watch, and mutters that it is late. Alice follows it "
    "across the field and down a large rabbit-hole under a hedge.",

    "Falling slowly down the rabbit-hole, Alice passes shelves lined with "
    "cupboards, bookshelves, and maps hung on pegs. She takes a jar labeled "
    "ORANGE MARMALADE from one shelf as she falls, finds it empty, and puts "
    "it back on another shelf so as not to hurt anyone standing below.",

    "At the bottom, Alice finds a tiny locked door behind a curtain, far too "
    "small to fit through, and a golden key on a three-legged glass table. "
    "On the table she finds a bottle labeled DRINK ME; after checking it "
    "isn't marked poison, she drinks it and shrinks small enough to use the key.",

    "Now too large again after eating a cake labeled EAT ME, Alice cries a "
    "pool of tears so large it floods the hall. She shrinks once more, falls "
    "into her own pool of tears, and meets a Mouse swimming nearby, to whom "
    "she awkwardly tries to make conversation about her cat Dinah.",

    "Soaked from the pool of tears, Alice and a gathering of animals -- "
    "including a Dodo, a Duck, a Lory, and an Eaglet -- hold a Caucus-race, "
    "running in a circle with no clear start or finish, so that everyone can "
    "be declared a winner and dry off in the process.",

    "The White Rabbit mistakes Alice for his housemaid and sends her to fetch "
    "his gloves and fan from his house. Inside, Alice drinks from an unlabeled "
    "bottle and grows enormous, becoming stuck with an arm out the window and "
    "a foot up the chimney, much to the Rabbit's alarm.",

    "Alice meets a blue Caterpillar sitting on a large mushroom, smoking a "
    "hookah. It asks her, slowly and repeatedly, 'Who are you?' The "
    "Caterpillar tells her that eating one side of the mushroom will make her "
    "grow larger, and the other side will make her shrink.",

    "In the woods, Alice encounters the Cheshire Cat grinning from the branch "
    "of a tree. The Cat tells her that everyone in Wonderland is mad, "
    "including itself and Alice, since she must be mad to have come there at "
    "all, and it has a habit of vanishing until only its grin remains.",

    "Alice joins a Mad Tea-Party hosted by the Mad Hatter and the March Hare, "
    "with a Dormouse asleep between them. The Hatter asks Alice the riddle "
    "'Why is a raven like a writing-desk?' without any real answer in mind, "
    "and the table keeps shifting seats whenever a place gets used up.",

    "At the Queen of Hearts' croquet ground, players use live flamingos as "
    "mallets and curled-up hedgehogs as balls, while the arches are soldiers "
    "bent over on hands and feet. The Queen is short-tempered and frequently "
    "shouts 'Off with her head!' at nearly everyone she meets.",
]


def main():
    out_path = Path(__file__).parent / "fixtures" / "sample.pdf"
    doc = fitz.open()
    for text in PAGES:
        page = doc.new_page()
        page.insert_textbox(
            fitz.Rect(72, 72, page.rect.width - 72, page.rect.height - 72),
            text,
            fontsize=13,
            fontname="helv",
        )
    doc.save(out_path)
    doc.close()
    print(f"Wrote {len(PAGES)}-page fixture to {out_path}")


if __name__ == "__main__":
    main()
