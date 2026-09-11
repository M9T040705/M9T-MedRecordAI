"""共享 LLM 客户端（OpenAI 兼容）：项目二复用，无 Key 时返回 None。"""
from __future__ import annotations

from typing import Optional

from .config import settings

_client = None


def get_llm_client():
    """懒加载单例；未配置 Key 返回 None（调用方自动降级规则抽取）。"""
    global _client
    if not settings.llm_api_key:
        return None
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url, timeout=60)
    return _client
