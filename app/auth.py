"""JWT 鉴权 + 科室级权限隔离（对应简历"科室级权限隔离"）。

权限模型：
- 病案科（编码员）：可抽取、可查看本科记录；
- 医务部（管理员）：全量可见；
- 医保办 / 科室：仅查看本科（演示中允许查看全部记录元数据，抽取受控）。

内置用户表演示用；生产环境应替换为院内统一认证（LDAP/SSO）。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings

# 内置用户：用户名 -> {password, department, role}
USERS: Dict[str, dict] = {
    "binganke": {"password": "bingan123", "department": "病案科", "role": "coder"},
    "yiwubu":   {"password": "yiwu123",   "department": "医务部", "role": "admin"},
    "yibaoban": {"password": "yibao123",  "department": "医保办", "role": "viewer"},
    "cardio":   {"password": "cardio123", "department": "心血管内科", "role": "viewer"},
}

DEPARTMENTS = ["病案科", "医务部", "医保办", "心血管内科", "神经内科", "普外科", "儿科"]

_bearer = HTTPBearer(auto_error=False)


def authenticate(username: str, password: str) -> Optional[str]:
    user = USERS.get(username)
    if not user or user["password"] != password:
        return None
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "department": user["department"],
        "role": user["role"],
        "exp": now + timedelta(hours=settings.jwt_expire_hours),
        "iat": now,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"登录态无效：{e}")


def get_current_user(cred: Optional[HTTPAuthorizationCredentials] = Depends(_bearer)) -> dict:
    if cred is None:
        raise HTTPException(status_code=401, detail="缺少 Authorization: Bearer <token>")
    return decode_token(cred.credentials)


def require_departments(*allowed: str):
    """依赖工厂：仅允许指定科室访问。"""
    def dep(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] != "admin" and user["department"] not in allowed:
            raise HTTPException(status_code=403, detail=f"无权限：仅限 {'/'.join(allowed)} 访问")
        return user
    return dep


def can_view(user: dict, record_department: str) -> bool:
    """记录可见性：医务部全量，其他科室仅本科。"""
    return user["role"] == "admin" or user["department"] == record_department
