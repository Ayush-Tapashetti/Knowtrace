"""Outside-world code: the optional LLM rephraser (D3) and everything that guards it.

Nothing here may decide what a student is missing or what they study next; that is the pure domain
layer. A model may only reword already-selected lesson text, and every failure path falls back to
the authored text.
"""
