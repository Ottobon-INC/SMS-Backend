"""Canonical academic stream and coaching-track rules."""

from __future__ import annotations

import re
from typing import Any

STREAM_LABELS: dict[str, str] = {
    "MPC": "Mathematics, Physics, Chemistry",
    "BIPC": "Biology, Physics, Chemistry",
    "MEC": "Mathematics, Economics, Commerce",
    "CEC": "Civics, Economics, Commerce",
    "HEC": "History, Economics, Civics",
}

COACHING_TRACKS: tuple[str, ...] = (
    "IPE",
    "JEE Mains",
    "JEE Advanced",
    "AP EAPCET - Engineering",
    "NEET-UG",
    "AP EAPCET - Agriculture & Pharmacy",
    "CA Foundation",
    "CMA Foundation",
    "CSEET",
    "CUET-UG",
    "IPMAT",
    "CLAT",
    "AILET",
)

ALLOWED_STREAM_TRACKS: dict[str, tuple[str, ...]] = {
    "MPC": ("IPE", "JEE Mains", "JEE Advanced", "AP EAPCET - Engineering"),
    "BIPC": ("IPE", "NEET-UG", "AP EAPCET - Agriculture & Pharmacy"),
    "MEC": ("IPE", "CA Foundation", "CMA Foundation", "CSEET", "CUET-UG", "IPMAT"),
    "CEC": ("IPE", "CA Foundation", "CMA Foundation", "CSEET", "CUET-UG", "IPMAT"),
    "HEC": ("IPE", "CLAT", "AILET", "CUET-UG"),
}

DEFAULT_SUBJECTS_BY_STREAM: dict[str, tuple[str, ...]] = {
    "MPC": ("Mathematics", "Physics", "Chemistry", "English"),
    "BIPC": ("Botany", "Zoology", "Physics", "Chemistry", "English"),
    "MEC": ("Mathematics", "Economics", "Commerce", "English"),
    "CEC": ("Civics", "Economics", "Commerce", "English"),
    "HEC": ("History", "Economics", "Civics", "English"),
}


def normalize_stream_code(value: str | None) -> str:
    return (value or "").strip().upper()


def normalize_track(value: str | None) -> str:
    raw = " ".join((value or "").strip().replace("_", " ").split())
    aliases = {
        "NEET UG": "NEET-UG",
        "NEET-UG": "NEET-UG",
        "CUET UG": "CUET-UG",
        "CUET-UG": "CUET-UG",
        "JEE MAINS": "JEE Mains",
        "JEE MAIN": "JEE Mains",
        "JEE ADVANCED": "JEE Advanced",
        "EAPCET ENGINEERING": "AP EAPCET - Engineering",
        "AP EAPCET ENGINEERING": "AP EAPCET - Engineering",
        "EAPCET AGRICULTURE PHARMACY": "AP EAPCET - Agriculture & Pharmacy",
        "AP EAPCET AGRICULTURE PHARMACY": "AP EAPCET - Agriculture & Pharmacy",
        "CA FOUNDATION": "CA Foundation",
        "CMA FOUNDATION": "CMA Foundation",
    }
    key = re.sub(r"\s*[-&]\s*", " ", raw).upper()
    return aliases.get(key, raw)


def validate_stream_track(stream_code: str, coaching_track: str) -> None:
    if stream_code not in STREAM_LABELS:
        raise ValueError("Unknown stream code.")
    if coaching_track not in COACHING_TRACKS:
        raise ValueError("Unknown coaching track.")
    if coaching_track not in ALLOWED_STREAM_TRACKS[stream_code]:
        raise ValueError(f"{coaching_track} is not valid for {stream_code}.")


def programme_code_for(stream_code: str, coaching_track: str) -> str:
    track_code = re.sub(r"[^A-Za-z0-9]+", "-", coaching_track.upper()).strip("-")
    return f"{stream_code}-{track_code}"


def programme_display_label(
    *,
    programme_code: str | None,
    programme_name: str | None,
    stream_code: str | None,
    coaching_track: str | None,
) -> str:
    stream = normalize_stream_code(stream_code)
    track = normalize_track(coaching_track)
    if stream and track:
        return f"{stream} - {track}"
    if programme_code and programme_name:
        if programme_name.startswith(f"{programme_code} -"):
            return programme_name
        return f"{programme_code} - {programme_name}"
    return programme_name or programme_code or ""


def programme_response_from_row(row: Any) -> dict[str, Any]:
    stream_code = getattr(row, "stream_code", None)
    coaching_track = getattr(row, "coaching_track", None)
    code = getattr(row, "code", None) or getattr(row, "programme_code", None)
    name = getattr(row, "name", None) or getattr(row, "programme_name", None)
    display_label = programme_display_label(
        programme_code=code,
        programme_name=name,
        stream_code=stream_code,
        coaching_track=coaching_track,
    )
    return {
        "id": str(getattr(row, "id")),
        "code": code,
        "name": name,
        "streamCode": stream_code,
        "coachingTrack": coaching_track,
        "displayLabel": display_label,
        "baseStreamLabel": STREAM_LABELS.get(normalize_stream_code(stream_code), name),
        "yearLevel": getattr(row, "year_level", None),
        "subjectIds": getattr(row, "subject_ids", None) or [],
    }


def normalize_programme_match_value(value: Any) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", " ", str(value or "")).strip().lower()
    return " ".join(cleaned.split())
