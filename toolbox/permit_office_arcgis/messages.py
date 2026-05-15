from __future__ import annotations

import arcpy

def _log(messages, tag, text):
    line = f"[{tag}] {text}"
    try:
        messages.addMessage(line)
    except Exception:
        arcpy.AddMessage(line)


def _warn(messages, tag, text):
    line = f"[{tag}] WARN: {text}"
    try:
        messages.addWarningMessage(line)
    except Exception:
        arcpy.AddWarning(line)


def _err(messages, tag, text):
    line = f"[{tag}] ERROR: {text}"
    try:
        messages.addErrorMessage(line)
    except Exception:
        arcpy.AddError(line)


