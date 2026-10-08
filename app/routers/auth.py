from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..security import (
    DUMMY_HASH, client_ip, hash_password, login_throttle, start_session, verify_password,
)
from ..textutil import clean_text
from ..web import flash, redirect, render

router = APIRouter()

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD = 8


def user_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(User)) or 0


@router.get("/kurulum")
def setup_form(request: Request, db: Session = Depends(get_db)):
    if user_count(db):
        return redirect("/giris")
    return render(request, "setup.html", {"form": {}, "errors": []})


@router.post("/kurulum")
def setup_submit(
    request: Request,
    db: Session = Depends(get_db),
    ad1: str = Form(""), eposta1: str = Form(""), sifre1: str = Form(""),
    ad2: str = Form(""), eposta2: str = Form(""), sifre2: str = Form(""),
):
    if user_count(db):
        return redirect("/giris")
    form = {"ad1": clean_text(ad1, 80), "eposta1": clean_text(eposta1, 200).lower(),
            "ad2": clean_text(ad2, 80), "eposta2": clean_text(eposta2, 200).lower()}
    errors = []
    for n, (ad, eposta, sifre) in enumerate(
        [(form["ad1"], form["eposta1"], sifre1), (form["ad2"], form["eposta2"], sifre2)], 1
    ):
        if not ad:
            errors.append(f"{n}. ortağın adını yazın.")
        if not EMAIL_RE.match(eposta):
            errors.append(f"{n}. ortağın e-posta adresi geçerli değil.")
        if len(sifre) < MIN_PASSWORD:
            errors.append(f"{n}. ortağın şifresi en az {MIN_PASSWORD} karakter olmalı.")
    if form["eposta1"] and form["eposta1"] == form["eposta2"]:
        errors.append("İki ortak aynı e-posta adresini kullanamaz.")
    if errors:
        return render(request, "setup.html", {"form": form, "errors": errors}, status_code=422)

    first = User(name=form["ad1"], email=form["eposta1"], password_hash=hash_password(sifre1))
    second = User(name=form["ad2"], email=form["eposta2"], password_hash=hash_password(sifre2))
    db.add_all([first, second])
    db.commit()
    start_session(request, first)
    flash(request, "Defter hazır. İlk kaydınızı ekleyebilirsiniz.")
    return redirect("/")


@router.get("/giris")
def login_form(request: Request, db: Session = Depends(get_db)):
    if not user_count(db):
        return redirect("/kurulum")
    if request.session.get("uid"):
        return redirect("/")
    return render(request, "login.html", {"email": "", "error": None})


@router.post("/giris")
def login_submit(
    request: Request,
    db: Session = Depends(get_db),
    eposta: str = Form(""),
    sifre: str = Form(""),
):
    ip = client_ip(request)
    email = eposta.strip().lower()
    if login_throttle.blocked(ip):
        return render(
            request, "login.html",
            {"email": email, "error": "Çok fazla hatalı deneme. 15 dakika sonra yeniden deneyin."},
            status_code=429,
        )
    user = db.scalar(select(User).where(User.email == email))
    password_ok = verify_password(sifre, user.password_hash if user else DUMMY_HASH)
    if not user or not password_ok:
        login_throttle.fail(ip)
        return render(
            request, "login.html",
            {"email": email, "error": "E-posta ya da şifre hatalı."},
            status_code=401,
        )
    login_throttle.reset(ip)
    start_session(request, user)
    return redirect("/")


@router.post("/cikis")
def logout(request: Request):
    request.session.clear()
    return redirect("/giris")
