# -*- coding: utf-8 -*-
"""API 키 인증. 키를 그대로 비교하지 않고 해시를 비교한다."""
from __future__ import annotations

import hashlib
import hmac

from fastapi import Depends, Header, HTTPException, status

from ..settings import get_settings


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def api_key_id(key: str) -> str:
    """감사 로그에 남길 식별자. 키 자체는 절대 로그에 남기지 않는다."""
    return _hash(key)[:12]


async def require_api_key(x_api_key: str = Header(default="")) -> str:
    s = get_settings()
    if not hmac.compare_digest(_hash(x_api_key), _hash(s.api_key)):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "유효하지 않은 API 키입니다.")
    return api_key_id(x_api_key)


CurrentKey = Depends(require_api_key)
