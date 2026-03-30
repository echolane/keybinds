from __future__ import annotations

import pytest


def test_parse_key_expr_normalizes_aliases_and_supports_sequences(kb_env):
    expr = kb_env.parsing.parse_key_expr(' left ctrl + a , shift + enter ')

    assert len(expr) == 2
    first, second = expr
    assert kb_env.winput.VK_LCONTROL in first.groups[0]
    assert ord('A') in first.groups[1]
    assert kb_env.winput.VK_SHIFT in second.groups[0]
    assert kb_env.winput.VK_RETURN in second.groups[1]


def test_register_key_token_extends_parser(kb_env):
    kb_env.constants.register_key_token('macro key', 0xFE)

    parsed = kb_env.parsing.parse_key_expr('macro key')

    assert parsed[0].groups == (frozenset({0xFE}),)
    assert parsed[0].allowed_union == frozenset({0xFE})


@pytest.mark.parametrize('expr', ['', 'ctrl+', 'a,,b', 'ctrl+unknown'])
def test_parse_key_expr_rejects_invalid_input(kb_env, expr):
    with pytest.raises(ValueError):
        kb_env.parsing.parse_key_expr(expr)
