from __future__ import annotations

from functools import wraps
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods


def _ensure_authenticated(view_func):
    @wraps(view_func)
    def wrapper(request: HttpRequest, *args, **kwargs):
        if not request.session.get("authenticated"):
            return redirect("login")
        return view_func(request, *args, **kwargs)

    return wrapper


@require_http_methods(["GET", "POST"])
def login_view(request: HttpRequest) -> HttpResponse:
    # Already logged in
    if request.session.get("authenticated"):
        return redirect("files")

    env_user = settings.USERNAME
    env_pwd = settings.PASSWORD
    env_dir = settings.FILES_ROOT if settings.FILES_ROOT and settings.FILES_ROOT.exists() else None

    if request.method == "POST":
        username = request.POST.get("username", "")
        password = request.POST.get("password", "")
        if username == env_user and password == env_pwd:
            if not env_dir:
                messages.error(request, "Configure DIR no arquivo .env antes de acessar.")
            else:
                request.session["authenticated"] = True
                return redirect("files")
        else:
            messages.error(request, "Usuário ou senha inválidos.")

    return render(
        request,
        "login.html",
        {
            "has_dir": bool(env_dir),
        },
    )


def logout_view(request: HttpRequest) -> HttpResponse:
    if request.method not in ["POST", "GET"]:
        return redirect("login")
    request.session.flush()
    return redirect("login")


@_ensure_authenticated
def files_view(request: HttpRequest, relative_path: str = "") -> HttpResponse:
    if not settings.FILES_ROOT:
        messages.error(request, "Configure DIR no arquivo .env.")
        return redirect("logout")

    base_dir: Path = settings.FILES_ROOT
    if not base_dir.exists():
        messages.error(request, f"Diretório não encontrado: {base_dir}")
        return redirect("logout")

    target_dir = (base_dir / relative_path).resolve()
    # Impede escapar do diretório base
    if base_dir not in target_dir.parents and target_dir != base_dir:
        raise Http404("Diretório inválido.")

    if not target_dir.is_dir():
        raise Http404("Diretório não encontrado.")

    entries = []
    for entry in sorted(target_dir.iterdir()):
        rel = entry.relative_to(base_dir)
        if entry.is_dir():
            entries.append(
                {
                    "kind": "dir",
                    "name": entry.name,
                    "relative_path": rel.as_posix(),
                }
            )
        elif entry.is_file():
            entries.append(
                {
                    "kind": "file",
                    "name": entry.name,
                    "size": entry.stat().st_size,
                    "relative_path": rel.as_posix(),
                }
            )

    parent_rel = None
    if target_dir != base_dir:
        parent_rel = target_dir.parent.relative_to(base_dir).as_posix()

    return render(
        request,
        "files.html",
        {
            "files": entries,
            "base_dir": base_dir,
            "current_dir": target_dir,
            "parent_rel": parent_rel,
        },
    )


@_ensure_authenticated
def download_view(request: HttpRequest, relative_path: str) -> HttpResponse:
    if not settings.FILES_ROOT:
        raise Http404("Diretório não configurado.")

    base_dir: Path = settings.FILES_ROOT
    target = (base_dir / relative_path).resolve()

    # Prevent directory traversal outside the allowed folder.
    if base_dir not in target.parents and target != base_dir:
        raise Http404("Arquivo não encontrado.")

    if not target.is_file():
        raise Http404("Arquivo não encontrado.")

    return FileResponse(
        open(target, "rb"),
        as_attachment=True,
        filename=target.name,
    )
