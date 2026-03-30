from __future__ import annotations

import pytest


def test_parse_logical_expr_is_character_first_and_handles_escapes(kb_env):
    steps = kb_env.logical_parsing.parse_logical_expr(r'ctrl+\+,\,')

    assert len(steps) == 2
    first_step = steps[0]
    assert kb_env.winput.VK_CONTROL in first_step.allowed_vk_union
    assert '+' in first_step.allowed_chars

    second_step = steps[1]
    assert second_step.allowed_chars == frozenset({','})
    assert second_step.allowed_vk_union == frozenset()


def test_named_tokens_still_map_to_virtual_keys(kb_env):
    chord = kb_env.logical_parsing.parse_logical_chord('space')

    assert chord.allowed_chars == frozenset()
    assert chord.allowed_vk_union == frozenset({kb_env.winput.VK_SPACE})


@pytest.mark.parametrize(
    ('text', 'expected'),
    [
        ('ab', 'a,b'),
        ('a,+', r'a,\,,\+'),
        ('\n', r'\n'),
        ('\t,\n', r'\t,\,,\n'),
    ],
)
def test_text_to_logical_expr_escapes_special_characters(kb_env, text, expected):
    assert kb_env.logical_parsing.text_to_logical_expr(text) == expected


@pytest.mark.parametrize('expr', ['', 'ctrl+\\', 'a,,b'])
def test_parse_logical_expr_rejects_invalid_input(kb_env, expr):
    with pytest.raises(ValueError):
        kb_env.logical_parsing.parse_logical_expr(expr)
